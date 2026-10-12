"""Resolve missing DOIs from title + year + first author (OpenAlex, then Crossref).

A candidate is accepted only if: titles match (difflib ratio >= THRESHOLD on normalised titles, or the record's
title is a truncated "..." prefix of the candidate's), years differ by at most 1 (when both known) and, when both
sides list authors, the first author's surname appears among the candidate's. Confidence is "élevée" only when
title, year and author all positively matched; otherwise "à vérifier"."""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

from .http import get_json
from .models import Record, clean_doi, norm_title
from .sources import openalex

THRESHOLD = 0.92
CROSSREF = "https://api.crossref.org/works"
HIGH, CHECK = "élevée", "à vérifier"
MIN_PREFIX = 25  # characters of a truncated title needed to trust a prefix match


def surname(name: str) -> str:
    name = (name or "").strip()
    last = name.split(",")[0] if "," in name else (name.split() or [""])[-1]
    return norm_title(last).replace(" ", "")


def _title_match(rec_title: str, cand_title: str) -> tuple[bool, bool]:
    """(matches, exact): exact is False for prefix matches of truncated titles."""
    a, b = norm_title(rec_title), norm_title(cand_title)
    if not a or not b:
        return False, False
    if SequenceMatcher(None, a, b).ratio() >= THRESHOLD:
        return True, True
    if re.search(r"(…|\.\.\.)\s*$", rec_title.strip()):
        stem = norm_title(re.sub(r"(…|\.\.\.)\s*$", "", rec_title.strip()))
        if len(stem) >= MIN_PREFIX and b.startswith(stem):
            return True, False
    return False, False


def judge(r: Record, title: str, year: int | None, authors: list[str]) -> str | None:
    """None = reject, else the confidence label."""
    ok, exact = _title_match(r.title, title)
    if not ok:
        return None
    year_known = bool(r.year and year)
    if year_known and abs(r.year - year) > 1:
        return None
    author_known = bool(r.authors and authors and surname(r.authors[0]))
    if author_known and surname(r.authors[0]) not in {surname(a) for a in authors}:
        return None
    return HIGH if exact and year_known and author_known else CHECK


def _openalex_candidates(r: Record) -> list[tuple[str, int | None, list[str], str]]:
    params = {**openalex.base_params(), "select": "doi,title,publication_year,authorships", "per-page": 5,
              "filter": "title.search:" + re.sub(r"[,:|…]", " ", re.sub(r"(…|\.\.\.)\s*$", "", r.title))}
    out = []
    for w in get_json(openalex.API, params).get("results") or []:
        if w.get("doi"):
            out.append((w.get("title") or "", w.get("publication_year"),
                        [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []],
                        clean_doi(w["doi"])))
    return out


def _crossref_candidates(r: Record) -> list[tuple[str, int | None, list[str], str]]:
    q = re.sub(r"(…|\.\.\.)\s*$", "", r.title).strip()
    if r.authors:
        q += " " + surname(r.authors[0])
    params = {"query.bibliographic": q, "rows": 5, "select": "DOI,title,issued,author"}
    if os.getenv("OPENALEX_EMAIL"):
        params["mailto"] = os.environ["OPENALEX_EMAIL"]
    out = []
    for it in get_json(CROSSREF, params).get("message", {}).get("items") or []:
        parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
        out.append(((it.get("title") or [""])[0], parts[0] if parts else None,
                    [a.get("family", "") for a in it.get("author") or []], clean_doi(it.get("DOI"))))
    return out


def _key(r: Record) -> str:
    return f"{norm_title(r.title)}|{r.year or ''}|{surname(r.authors[0]) if r.authors else ''}"


def resolve_one(r: Record) -> dict | None:
    """{'doi','source','confidence'} or None. Network errors propagate to the caller (not cached)."""
    for source, fetch in (("openalex", _openalex_candidates), ("crossref", _crossref_candidates)):
        best = None
        for title, year, authors, doi in fetch(r):
            conf = judge(r, title, year, authors)
            if conf and (best is None or (conf == HIGH and best["confidence"] != HIGH)):
                best = {"doi": doi, "source": source, "confidence": conf}
        if best:
            return best
    return None


def resolve(records: list[Record], log=print, workers: int = 6, cache_path: str | Path | None = None) -> None:
    for r in records:  # label what the sources gave us
        r.doi = clean_doi(r.doi)
        if r.doi and not r.doi_source:
            r.doi_source = "fournie"
    todo = [r for r in records if not r.doi and r.title]
    if not todo:
        return
    cache: dict = {}
    if cache_path and Path(cache_path).is_file():
        cache = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    log(f"  Resolving DOIs for {len(todo)} records without one (OpenAlex, then Crossref)...")
    errors = 0

    def work(r: Record):
        nonlocal errors
        k = _key(r)
        if k in cache:
            return k, cache[k], False
        try:
            return k, resolve_one(r), True
        except Exception:
            errors += 1
            return k, "error", False

    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(work, todo))
    found = 0
    for r, (k, res, fresh) in zip(todo, results):
        if res == "error":
            continue
        if fresh:
            cache[k] = res
        if res:
            r.doi, r.doi_source, r.doi_confidence = res["doi"], res["source"], res["confidence"]
            found += 1
    if cache_path:
        Path(cache_path).write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    high = sum(1 for r in todo if r.doi_confidence == HIGH)
    log(f"  {found}/{len(todo)} DOIs found ({high} high confidence, {found - high} to check)"
        + (f"; {errors} lookups failed (not cached, rerun to retry)" if errors else ""))
