"""Google Scholar through SerpAPI (Scholar has no official API)."""
from __future__ import annotations

import os
import re

from ..http import get_json
from ..models import Record
from ..query import SCHOLAR, render_fitted, year_bounds

NAME = "scholar"
API = "https://serpapi.com/search.json"
KEY = "SERPAPI_KEY"


def available() -> bool:
    return bool(os.getenv(KEY))


def _parse(r: dict) -> Record:
    info = r.get("publication_info") or {}
    summary = info.get("summary") or ""
    parts = [p.strip() for p in summary.split(" - ")]
    ym = re.findall(r"\b(?:19|20)\d{2}\b", summary)
    authors = [a["name"] for a in info.get("authors") or []] or (
        [a.strip() for a in parts[0].split(",") if a.strip()] if parts and parts[0] else [])
    pub = re.sub(r",?\s*(?:19|20)\d{2}\s*$", "", parts[1]).strip() if len(parts) > 1 else ""
    snippet = r.get("snippet") or ""
    return Record(
        title=re.sub(r"^\[[A-Z]+\]\s*", "", r.get("title") or ""),
        authors=authors, year=int(ym[-1]) if ym else None, publication=pub,
        abstract=snippet, abstract_is_snippet=bool(snippet),
        url=r.get("link") or "", sources={NAME},
    )


def search(ast, max_results: int, log=print) -> list[Record]:
    q, truncated = render_fitted(ast, SCHOLAR)
    if not q:
        raise ValueError("query has nothing searchable in Google Scholar")
    if truncated:
        log(f"    scholar: query exceeds Scholar's ~256-char limit, sent a reduced version: {q}")
    params = {"engine": "google_scholar", "q": q, "num": 20, "api_key": os.environ[KEY], "hl": "en"}
    lo, hi = year_bounds(ast)
    if lo: params["as_ylo"] = lo
    if hi: params["as_yhi"] = hi
    out: list[Record] = []
    start = 0
    while len(out) < max_results:
        data = get_json(API, {**params, "start": start})
        if data.get("error"):
            if out:
                break
            raise RuntimeError(f"SerpAPI: {data['error']}")
        res = data.get("organic_results") or []
        out += [_parse(r) for r in res]
        if not res or "next" not in (data.get("serpapi_pagination") or {}):
            break
        start += 20
    return out[:max_results]
