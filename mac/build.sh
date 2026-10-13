#!/bin/bash
# Builds "mac/build/Health AIO.app" with the Command Line Tools alone (swiftc, no Xcode project).
#
#   mac/build.sh            build when the sources changed since the last build
#   mac/build.sh --force    build anyway
#
# Every build gets a new ad-hoc signature, and macOS ties Full Disk Access to the signature: after a real rebuild
# you switch Full Disk Access on again for "Health AIO". That is why an app built from the same sources is left alone.
set -euo pipefail
export LC_COLLATE=C

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
BUILD="$HERE/build"
APP="$BUILD/Health AIO.app"
SHOWN="mac/build/Health AIO.app"
WORK="$BUILD/work"

FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

# What the app is built from. The version and the recorded paths are not in it: they change without the app changing.
sources_hash() {
  cd "$HERE"
  for f in build.sh Info.plist tools/make_icon.swift Sources/*.swift; do
    printf '== %s\n' "$f"
    cat "$f"
  done | shasum -a 256 | cut -d' ' -f1
}

HASH="$(sources_hash)"
STAMP="$APP/Contents/Resources/build-hash"
if [[ $FORCE == 0 && -f "$STAMP" && "$(cat "$STAMP")" == "$HASH" ]] && codesign --verify "$APP" 2>/dev/null; then
  echo "$SHOWN is up to date: its sources have not changed since it was built."
  echo "Left untouched, so macOS keeps its Full Disk Access. Run with --force to rebuild anyway"
  echo "(then switch Full Disk Access on again for Health AIO)."
  exit 0
fi

command -v swiftc >/dev/null || { echo "swiftc not found: install the Command Line Tools (xcode-select --install)." >&2; exit 1; }

VERSION="$(sed -n -E "s/^__version__[[:space:]]*=[[:space:]]*['\"]([^'\"]+)['\"].*/\1/p" "$REPO/healthaio/__init__.py" 2>/dev/null | head -n 1 || true)"
VERSION="${VERSION:-0.3.0}"
PYTHON="$(command -v python3 || true)"

rm -rf "$WORK"
mkdir -p "$WORK"
SOURCES=("$HERE"/Sources/*.swift)
FLAGS=(-O -swift-version 5 -parse-as-library -module-name HealthAIO)

echo "Compiling for Apple silicon (arm64)…"
swiftc "${FLAGS[@]}" -target arm64-apple-macos13.0 "${SOURCES[@]}" -o "$WORK/HealthAIO-arm64"
BINARY="$WORK/HealthAIO-arm64"
ARCHS="arm64"

echo "Compiling for Intel (x86_64)…"
if swiftc "${FLAGS[@]}" -target x86_64-apple-macos13.0 "${SOURCES[@]}" -o "$WORK/HealthAIO-x86_64" 2> "$WORK/x86_64.log"; then
  lipo -create "$WORK/HealthAIO-arm64" "$WORK/HealthAIO-x86_64" -output "$WORK/HealthAIO"
  BINARY="$WORK/HealthAIO"
  ARCHS="arm64 + x86_64"
else
  echo "  the x86_64 slice did not compile here; building for Apple silicon only."
fi
# The Command Line Tools ship libswiftCompatibilityPacks without an x86_64 slice; the linker says so, and this app
# does not use what is in it. Any other message is shown as it is.
if grep -q "libswiftCompatibilityPacks" "$WORK/x86_64.log"; then
  echo "  (linker note: no x86_64 copy of libswiftCompatibilityPacks in the Command Line Tools; not used by this app)"
fi
grep -v "libswiftCompatibilityPacks" "$WORK/x86_64.log" >&2 || true

echo "Drawing the icon…"
swiftc -O -parse-as-library -target "$(uname -m)-apple-macos13.0" \
  "$HERE/tools/make_icon.swift" "$HERE/Sources/RingLogo.swift" -o "$WORK/make_icon"
"$WORK/make_icon" "$WORK/icon_1024.png"
ICONSET="$WORK/AppIcon.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$WORK/icon_1024.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  sips -z "$((size * 2))" "$((size * 2))" "$WORK/icon_1024.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$WORK/AppIcon.icns"

echo "Assembling the app…"
STAGE="$WORK/Health AIO.app"
mkdir -p "$STAGE/Contents/MacOS" "$STAGE/Contents/Resources"
cp "$BINARY" "$STAGE/Contents/MacOS/HealthAIO"
PLIST="$STAGE/Contents/Info.plist"
cp "$HERE/Info.plist" "$PLIST"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PLIST"
plutil -replace CFBundleVersion -string "$VERSION" "$PLIST"
# Local build outputs (never committed): where this repository is, and the Python found when building.
plutil -replace HealthAIORepo -string "$REPO" "$PLIST"
if [[ -n "$PYTHON" ]]; then plutil -replace HealthAIOPython -string "$PYTHON" "$PLIST"; fi
plutil -lint "$PLIST" >/dev/null
printf 'APPL????' > "$STAGE/Contents/PkgInfo"
cp "$WORK/AppIcon.icns" "$STAGE/Contents/Resources/AppIcon.icns"
echo "$HASH" > "$STAGE/Contents/Resources/build-hash"

echo "Signing (ad hoc)…"
# swiftc already gave the binary a linker signature; replacing it is expected, so that line is not shown
codesign --force --deep -s - "$STAGE" 2> "$WORK/codesign.log" || { cat "$WORK/codesign.log" >&2; exit 1; }
grep -v "replacing existing signature" "$WORK/codesign.log" >&2 || true
codesign --verify "$STAGE"

rm -rf "$APP"
mv "$STAGE" "$APP"
rm -rf "$WORK"

echo
echo "Built $SHOWN (version $VERSION, $ARCHS, ad-hoc signed)."
echo "This build has a new signature, so macOS has forgotten any Full Disk Access an earlier build had:"
echo "  System Settings > Privacy & Security > Full Disk Access: remove an old \"Health AIO\" if it is listed,"
echo "  add this one with + and switch it on."
if pgrep -f "Health AIO.app/Contents/MacOS/HealthAIO" >/dev/null 2>&1; then
  echo "Health AIO is running: quit it from its menu bar icon, then open the new build."
fi
echo "Open it from the repository folder:  open \"$SHOWN\""
