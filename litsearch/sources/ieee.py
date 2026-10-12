from __future__ import annotations

import os

from ..http import get_json
from ..models import Record, clean_doi
from ..query import IEEE, render_fitted, year_bounds

NAME = "ieee"
API = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
KEY = "IEEE_API_KEY"


def available() -> bool:
    return bool(os.getenv(KEY))


def search(ast, max_results: int, log=print) -> list[Record]:
    q, _ = render_fitted(ast, IEEE)
    if not q:
        raise ValueError("query has nothing searchable in IEEE Xplore")
    params = {"apikey": os.environ[KEY], "querytext": q, "max_records": min(200, max_results),
              "sort_field": "article_title", "sort_order": "asc"}
    lo, hi = year_bounds(ast)
    if lo: params["start_year"] = lo
    if hi: params["end_year"] = hi
    out: list[Record] = []
    start = 1
    while len(out) < max_results:
        data = get_json(API, {**params, "start_record": start})
        arts = data.get("articles") or []
        for a in arts:
            doi = clean_doi(a.get("doi"))
            out.append(Record(
                title=a.get("title") or "",
                authors=[x.get("full_name", "") for x in (a.get("authors") or {}).get("authors", [])],
                year=int(a["publication_year"]) if a.get("publication_year") else None,
                publication=a.get("publication_title") or "",
                abstract=a.get("abstract") or "", doi=doi,
                url=a.get("html_url") or (f"https://doi.org/{doi}" if doi else ""), sources={NAME}))
        total = data.get("total_records", 0)
        start += len(arts)
        if not arts or start > total:
            break
    return out[:max_results]
