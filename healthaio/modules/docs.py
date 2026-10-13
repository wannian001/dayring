"""The two reading pages under the menu: Guide (#guide, how to use the app) and History (#history, how the
personal system this project comes from changed over a year). Their words live in the web app
(js/pages/guide.js, js/history-content.js), so the server only names the page; `build-static` still writes
api/guide.json and api/history.json, so the static demo opens them like any other page."""
from typing import Any, Dict

from ..context import Context

DOC_PAGES = ("guide", "history")


def build(ctx: Context, page: str) -> Dict[str, Any]:
    if page not in DOC_PAGES:
        raise ValueError(f"not a reading page: {page}")
    return {"page": page}
