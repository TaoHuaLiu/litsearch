from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from ..http import get_json, put_json
from ..models import Record, clean_doi
from ..query import ELSEVIER, render_fitted, year_bounds

NAME = "sciencedirect"
SEARCH = "https://api.elsevier.com/content/search/sciencedirect"
ARTICLE = "https://api.elsevier.com/content/article/doi/{}"
KEY = "ELSEVIER_API_KEY"


def available() -> bool:
    return bool(os.getenv(KEY))


def _headers():
    h = {"X-ELS-APIKey": os.environ[KEY], "Accept": "application/json"}
    if os.getenv("ELSEVIER_INSTTOKEN"):
        h["X-ELS-Insttoken"] = os.environ["ELSEVIER_INSTTOKEN"]
    return h


def _abstract(doi: str) -> str:
    try:
        d = get_json(ARTICLE.format(doi), headers=_headers())
        core = d["full-text-retrieval-response"]["coredata"]
        return (core.get("dc:description") or "").strip()
    except Exception:
        return ""


def search(ast, max_results: int, log=print) -> list[Record]:
    q, truncated = render_fitted(ast, ELSEVIER)
    if not q:
        raise ValueError("query has nothing searchable in ScienceDirect")
    if truncated:
        log(f"    sciencedirect: boolean-operator limit hit, sent a reduced query: {q}")
    lo, hi = year_bounds(ast)
    out: list[Record] = []
    offset = 0
    while len(out) < max_results:
        body = {"qs": q, "display": {"offset": offset, "show": min(100, max_results - len(out)),
                                      "sortBy": "relevance"}}
        if lo or hi:
            body["date"] = f"{lo or 1900}-{hi or 2100}"
        data = put_json(SEARCH, body, headers=_headers())
        res = data.get("results") or []
        for r in res:
            doi = clean_doi(r.get("doi"))
            date = str(r.get("publicationDate") or "")
            out.append(Record(
                title=r.get("title") or "",
                authors=[a.get("name", "") for a in r.get("authors") or []],
                year=int(date[:4]) if date[:4].isdigit() else None,
                publication=r.get("sourceTitle") or "", doi=doi,
                url=r.get("uri") or (f"https://doi.org/{doi}" if doi else ""), sources={NAME}))
        offset += len(res)
        if not res or offset >= data.get("resultsFound", 0):
            break
    out = out[:max_results]
    with ThreadPoolExecutor(4) as ex:  # search results carry no abstract
        for rec, ab in zip(out, ex.map(lambda r: _abstract(r.doi) if r.doi else "", out)):
            rec.abstract = ab
    return out
