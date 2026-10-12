"""Deduplication and abstract backfill (OpenAlex, then Crossref)."""
from __future__ import annotations

import html
import os
import re
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

from .http import get_json
from .models import Record, clean_doi, norm_title
from .sources import openalex

CROSSREF = "https://api.crossref.org/works"


def _key(r: Record) -> str:
    return ("doi:" + r.doi) if r.doi else f"t:{norm_title(r.title)}:{r.year or ''}"


def merge(a: Record, b: Record) -> Record:
    a.sources |= b.sources
    for q in b.queries:
        if q not in a.queries:
            a.queries.append(q)
    if len(b.authors) > len(a.authors): a.authors = b.authors
    if b.doi and (not a.doi or (b.doi_source == "fournie" and a.doi_source != "fournie" and a.doi == b.doi)):
        a.doi, a.doi_source, a.doi_confidence = b.doi, b.doi_source, b.doi_confidence
    for f in ("year", "publication", "url"):
        if not getattr(a, f) and getattr(b, f): setattr(a, f, getattr(b, f))
    # prefer a real abstract over a snippet, and the longer of two real abstracts
    if b.has_abstract() and (not a.has_abstract() or len(b.abstract) > len(a.abstract)):
        a.abstract, a.abstract_is_snippet = b.abstract, False
    elif not a.abstract and b.abstract:
        a.abstract, a.abstract_is_snippet = b.abstract, b.abstract_is_snippet
    return a


def dedupe(records: list[Record]) -> list[Record]:
    by_key: dict[str, Record] = {}
    by_title: dict[str, Record] = {}
    for r in records:
        r.doi = clean_doi(r.doi)
        k = _key(r)
        tk = norm_title(r.title)
        hit = by_key.get(k) or (by_title.get(tk) if tk and (not r.doi or True) else None)
        if hit and (not (hit.year and r.year) or abs(hit.year - r.year) <= 1):
            merge(hit, r)
            by_key[_key(hit)] = hit
        else:
            by_key[k] = r
            if tk: by_title.setdefault(tk, r)
    seen, out = set(), []
    for r in by_key.values():
        if id(r) not in seen:
            seen.add(id(r)); out.append(r)
    return out


def _strip_jats(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", html.unescape(s)).strip()
    return re.sub(r"^abstract[:.\s]+", "", s, flags=re.I)


def _from_openalex(r: Record) -> dict | None:
    params = openalex.base_params()
    params["select"] = openalex.SELECT
    if r.doi:
        res = get_json(openalex.API, {**params, "filter": f"doi:https://doi.org/{r.doi}"}).get("results")
        return res[0] if res else None
    t = re.sub(r"[,:|]", " ", r.title)
    res = get_json(openalex.API, {**params, "filter": f"title.search:{t}", "per-page": 5}).get("results") or []
    for w in res:
        if SequenceMatcher(None, norm_title(w.get("title") or ""), norm_title(r.title)).ratio() >= 0.92:
            return w
    return None


def _from_crossref(doi: str) -> str:
    params = {"mailto": os.environ["OPENALEX_EMAIL"]} if os.getenv("OPENALEX_EMAIL") else None
    try:
        return _strip_jats(get_json(f"{CROSSREF}/{doi}", params)["message"].get("abstract", ""))
    except Exception:
        return ""


def _fill(r: Record) -> None:
    try:
        w = _from_openalex(r)
    except Exception:
        w = None
    if w:
        found = openalex.to_record(w, "")
        if found.abstract:
            r.abstract, r.abstract_is_snippet = found.abstract, False
        if not r.doi and found.doi: r.doi, r.doi_source, r.doi_confidence = found.doi, "openalex", "à vérifier"
        if not r.year and found.year: r.year = found.year
        if not r.publication and found.publication: r.publication = found.publication
        if r.abstract_is_snippet or not r.authors or len(r.authors) < len(found.authors):
            if found.authors and (not r.authors or r.abstract_is_snippet is False):
                r.authors = found.authors
    if not r.has_abstract() and r.doi:
        ab = _from_crossref(r.doi)
        if ab:
            r.abstract, r.abstract_is_snippet = ab, False


def backfill(records: list[Record], log=print, workers: int = 6) -> None:
    todo = [r for r in records if not r.has_abstract()]
    if not todo:
        return
    log(f"  Backfilling abstracts for {len(todo)} records (OpenAlex, then Crossref)...")
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(_fill, todo))
    log(f"  {sum(r.has_abstract() for r in todo)}/{len(todo)} recovered")
