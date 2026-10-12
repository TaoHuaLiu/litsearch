from __future__ import annotations

import os

from ..http import get_json
from ..models import Record, clean_doi
from ..query import OPENALEX, render_fitted, year_bounds

NAME = "openalex"
API = "https://api.openalex.org/works"
SELECT = "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index"


def available() -> bool:
    return True


def rebuild_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words = {}
    for w, positions in inv.items():
        for p in positions:
            words[p] = w
    return " ".join(words[i] for i in sorted(words))


def base_params() -> dict:
    p = {}
    if os.getenv("OPENALEX_EMAIL"):
        p["mailto"] = os.environ["OPENALEX_EMAIL"]
    if os.getenv("OPENALEX_API_KEY"):
        p["api_key"] = os.environ["OPENALEX_API_KEY"]
    return p


def to_record(w: dict, source: str) -> Record:
    loc = w.get("primary_location") or {}
    src = (loc.get("source") or {}).get("display_name") or ""
    doi = clean_doi(w.get("doi"))
    return Record(
        title=w.get("title") or "",
        authors=[(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []],
        year=w.get("publication_year"),
        publication=src,
        abstract=rebuild_abstract(w.get("abstract_inverted_index")),
        doi=doi,
        url=loc.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else w.get("id", "")),
        sources={source},
    )


def search(ast, max_results: int, extra_filters: list[str] | None = None, source: str = NAME,
           log=print) -> list[Record]:
    q, truncated = render_fitted(ast, OPENALEX)
    if not q:
        raise ValueError("query has nothing searchable in OpenAlex")
    q = q.replace(",", " ")  # commas separate filters in the OpenAlex API
    # wildcards are only allowed on the unstemmed field
    field = "title_and_abstract.search.exact" if any(c in q for c in "*?") else "title_and_abstract.search"
    filters = [f"{field}:{q}"] + (extra_filters or [])
    lo, hi = year_bounds(ast)
    if lo: filters.append(f"from_publication_date:{lo}-01-01")
    if hi: filters.append(f"to_publication_date:{hi}-12-31")
    params = {**base_params(), "filter": ",".join(filters), "select": SELECT,
              "per-page": min(200, max_results), "cursor": "*"}
    out: list[Record] = []
    while len(out) < max_results:
        data = get_json(API, params)
        res = data.get("results") or []
        out += [to_record(w, source) for w in res]
        cur = (data.get("meta") or {}).get("next_cursor")
        if not res or not cur:
            break
        params["cursor"] = cur
    total = (data.get("meta") or {}).get("count")
    if total is not None:
        log(f"    {source}: {total} matching works, keeping {min(total, max_results)}")
    return out[:max_results]
