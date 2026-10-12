"""Search-page URLs with the query pre-filled, so a user can run or check it on the publisher site.
Parameter names come from each site's own search URLs; sites change them, so check a first result."""
from __future__ import annotations

from urllib.parse import urlencode

from .query import render_fitted, year_bounds
from .sources import DIALECTS


def _years(lo, hi):
    return range(lo, hi + 1) if lo and hi else ()


def search_url(source: str, ast) -> str | None:
    q, _ = render_fitted(ast, DIALECTS[source])
    if not q:
        return None
    lo, hi = year_bounds(ast)
    if source == "scholar":
        p = {"q": q, "hl": "en"}
        if lo: p["as_ylo"] = lo
        if hi: p["as_yhi"] = hi
        return "https://scholar.google.com/scholar?" + urlencode(p)
    if source == "ieee":
        p = {"queryText": q}
        if lo or hi: p["ranges"] = f"{lo or 1800}_{hi or 2100}_Year"
        return "https://ieeexplore.ieee.org/search/searchresult.jsp?" + urlencode(p)
    if source == "sciencedirect":
        p = {"qs": q}
        if years := _years(lo, hi): p["years"] = ",".join(map(str, years))
        return "https://www.sciencedirect.com/search?" + urlencode(p)
    if source in ("tandf", "wiley"):
        host = "www.tandfonline.com" if source == "tandf" else "onlinelibrary.wiley.com"
        p = {"AllField": q}
        if lo: p["AfterYear"] = lo
        if hi: p["BeforeYear"] = hi
        return f"https://{host}/action/doSearch?" + urlencode(p)
    return None
