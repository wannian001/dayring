"""The reading pages under the menu: Overview (#project), Guide (#guide) and History (#history)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from healthaio.modules import PAGES, docs

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "healthaio" / "web"
APP = (WEB / "js" / "app.js").read_text(encoding="utf-8")
I18N = (WEB / "js" / "i18n.js").read_text(encoding="utf-8")
ICONS = (WEB / "js" / "icons.js").read_text(encoding="utf-8")


class Registry(unittest.TestCase):
    def test_the_pages_are_registered_and_only_name_themselves(self):
        for name in docs.DOC_PAGES:
            self.assertIn(name, PAGES)
            self.assertEqual(PAGES[name](None), {"page": name})
        with self.assertRaises(ValueError):
            docs.build(None, "today")


class Menu(unittest.TestCase):
    def test_they_sit_under_the_menu_not_in_it(self):
        listed = re.findall(r'"(\w+)"', re.search(r"const DOCS\s*=\s*\[([^\]]*)\]", APP).group(1))
        self.assertEqual(listed, ["project", "guide", "history"])
        nav = re.search(r"const NAV\s*=\s*\[([^\]]*)\]", APP).group(1)
        for name in listed:
            self.assertNotIn(f'"{name}"', nav)  # the tab bar keeps the six items of the health loop
        glyphs = dict(re.findall(r'(\w+): "(\w+)"', re.search(r"const DOC_ICON\s*=\s*\{([^}]*)\}", APP).group(1)))
        self.assertEqual(sorted(glyphs), sorted(listed))
        for glyph in glyphs.values():
            self.assertRegex(ICONS, rf"\b{glyph}: '<", glyph)  # an icon the kit draws
        self.assertIn('class="side-docs"', APP)
        self.assertIn("history: historyPage", APP)  # never a top-level `history`: it would hide window.history
        self.assertNotRegex(APP, r"import history from")

    def test_every_word_in_both_languages(self):
        for key in ("nav.about", "nav.project", "nav.guide", "nav.history", "doc.other_lang"):
            self.assertEqual(I18N.count(f'"{key}"'), 2, key)


RENDER = """
globalThis.document = { documentElement: { dataset: {} } };
const [web, lang, page] = process.argv.slice(1);
const i18n = await import(`${web}/js/i18n.js`);
i18n.setLang(lang);
const mod = (await import(`${web}/js/pages/${page}.js`)).default;
const { HISTORY, AXIS } = await import(`${web}/js/history-content.js`);
process.stdout.write(JSON.stringify({ html: mod.render({ page }), history: HISTORY, axis: AXIS }));
"""


@unittest.skipUnless(shutil.which("node"), "needs node to render the pages")
class Words(unittest.TestCase):
    @staticmethod
    def render(lang, page):
        out = subprocess.run(["node", "--input-type=module", "-e", RENDER, "--", str(WEB), lang, page],
                             capture_output=True, text=True, check=True, timeout=60)
        return json.loads(out.stdout)

    def test_pages_render_in_both_languages(self):
        for lang, guide_title, history_title in (("en", "Guide", "History"), ("zh", "使用说明", "迭代记录")):
            self.assertIn(f"<h1>{guide_title}</h1>", self.render(lang, "guide")["html"])
            html = self.render(lang, "history")["html"]
            self.assertIn(f"<h1>{history_title}</h1>", html)
            self.assertEqual(len(re.findall(r'class="card doc-gen"', html)), 4)  # four generations
            self.assertEqual(len(re.findall(r'<button type="button" class="r\d" data-to="g\d"', html)), 4)
            self.assertNotRegex(html, r'href="#g\d"')  # the app routes on the hash: in-page jumps are buttons

    def test_the_overview_says_the_same_things_in_both_languages(self):
        shapes = []
        for lang, title in (("en", "Overview"), ("zh", "项目说明")):
            html = self.render(lang, "project")["html"]
            self.assertIn(f"<h1>{title}</h1>", html)
            shapes.append([len(re.findall(pattern, html)) for pattern in
                           (r'class="card doc-card"', r"<li><b>[^<]*</b><span>", r"<li><details", r"<tr>", r'class="chip"')])
        self.assertEqual(shapes[0], shapes[1])
        self.assertEqual(shapes[0][:3], [3, 5, 4])  # three cards, the five steps of the loop, four folds

    def test_the_two_languages_say_the_same_things(self):
        h = self.render("en", "history")["history"]

        def shape(c):
            gens = []
            for g in c["gens"]:
                parts = g.get("stages") or [g]
                gens.append([(len(p["examples"]), len(p["pairs"])) for p in parts])
            return gens, len(c["cards"]), [len(x["items"]) for x in c["cards"]], len(c["lessons"]), len(c["notyet"]), len(c["axisLabels"]), len(c["sample"]["lines"])

        self.assertEqual(shape(h["zh"]), shape(h["en"]))
        self.assertEqual(len(self.render("en", "history")["axis"]["marks"]), len(h["en"]["axisLabels"]))

    def test_the_year_axis_is_drawn_to_real_days(self):
        html = self.render("en", "history")["html"]
        lefts = [float(x) for x in re.findall(r'class="seg \w+" style="left:([\d.]+)%', html)]
        widths = [float(x) for x in re.findall(r'class="seg \w+" style="left:[\d.]+%;width:([\d.]+)%', html)]
        self.assertEqual(lefts[0], 0.0)
        self.assertAlmostEqual(lefts[-1] + widths[-1], 100.0, places=1)  # the last span ends on the last day
        self.assertEqual(lefts, sorted(lefts))

    def test_no_personal_data_on_the_pages(self):
        text = "".join((WEB / "js" / f).read_text(encoding="utf-8") for f in ("history-content.js", "pages/guide.js", "pages/project.js"))
        for leak in ("/Users/", "Data/raw", "Vault/", "kg", "bpm", " ms", "MAE"):
            self.assertNotIn(leak, text, leak)


if __name__ == "__main__":
    unittest.main()
