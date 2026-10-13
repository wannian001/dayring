"""The reading pages under the menu: Overview (#project, what the project is and who it is for) and Guide (#guide,
how to use the app). Their words live in the web app (js/pages/project.js, guide.js), so the server only names the
page; `build-static` still writes api/project.json and api/guide.json, so the static demo opens them like any other
page. History (how the personal system this project comes from changed over a year) quotes that personal system, so
it lives on the author's own site and the menu links out to it."""
from typing import Any, Dict

from ..context import Context

DOC_PAGES = ("project", "guide")


def build(ctx: Context, page: str) -> Dict[str, Any]:
    if page not in DOC_PAGES:
        raise ValueError(f"not a reading page: {page}")
    return {"page": page}
