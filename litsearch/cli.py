from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import load_keys
from .doi import resolve as resolve_dois
from .enrich import backfill, dedupe
from .export import write_csv, write_xlsx
from .importers import load as load_import
from .models import Record
from .query import Doc, QueryError, matches, parse, render_fitted
from .sources import ALL, DIALECTS


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_queries(arg: str) -> list[tuple[str, str]]:
    """A file (queries separated by blank lines, '#' comment lines ignored) or a literal query."""
    text = Path(arg).read_text(encoding="utf-8") if os.path.isfile(arg) else arg
    blocks, cur = [], []
    for line in text.splitlines() + [""]:
        if line.strip().startswith("#"):
            continue
        if line.strip():
            cur.append(line.strip())
        elif cur:
            blocks.append(" ".join(cur)); cur = []
    return [(f"Q{i}", b) for i, b in enumerate(blocks, 1)]


def _doc(r: Record) -> Doc:
    return Doc(title=r.title, abstract=r.abstract, authors=" ".join(r.authors),
               publication=r.publication, year=r.year)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="litsearch", description="Boolean literature search across scholarly sources.")
    ap.add_argument("queries", nargs="?", help="query string, or a text file with queries separated by blank lines")
    ap.add_argument("--import", dest="imports", action="append", default=[], metavar="FILE[=LABEL]",
                    help="add records exported by another tool (.bib/.bibtex, .xlsx, .csv, .ris, .md); repeatable")
    ap.add_argument("-o", "--output", default="results.xlsx", help="output .xlsx (default results.xlsx)")
    ap.add_argument("--csv", action="store_true", help="also write a CSV next to the XLSX")
    ap.add_argument("--sources", default=",".join(ALL), help=f"comma list among: {', '.join(ALL)}")
    ap.add_argument("--max", type=int, default=100, help="max results per source per query (default 100)")
    ap.add_argument("--strict", action="store_true", help="drop records that do not satisfy the full query")
    ap.add_argument("--resolve-doi", action="store_true",
                    help="find missing DOIs from title+year+first author (OpenAlex, then Crossref) before deduplication")
    ap.add_argument("--doi-cache", default=".doi_cache.json", help="cache file for --resolve-doi (default .doi_cache.json)")
    ap.add_argument("--print-queries", action="store_true",
                    help="print each query translated to every selected source's syntax, then exit "
                         "(use it for engines without an API: tandf, wiley)")
    ap.add_argument("--no-backfill", action="store_true", help="do not look up missing abstracts")
    a = ap.parse_args(argv)

    load_keys()

    names = [s.strip().lower() for s in a.sources.split(",") if s.strip()]
    bad = [n for n in names if n not in ALL]
    if bad:
        ap.error(f"unknown source(s): {', '.join(bad)}")

    queries = load_queries(a.queries) if a.queries else []
    if not queries and not a.imports:
        ap.error("no query and no --import given")
    try:
        asts = parse_all(queries)
    except QueryError as e:
        log(str(e))
        return 2

    if a.print_queries:
        for label, text in queries:
            print(f"[{label}] {text}")
            for n in names:
                q, cut = render_fitted(asts[label], DIALECTS[n])
                print(f"  {n}{' (reduced to fit limits)' if cut else ''}: {q or '(nothing searchable)'}")
        return 0

    imports = []
    for spec in a.imports:
        path, _, src = spec.partition("=")
        imports.append((path, src or None))
    try:
        records, stats, raw = run(queries, names, imports, max_results=a.max, strict=a.strict,
                                  resolve_doi=a.resolve_doi, doi_cache=a.doi_cache, backfill_abstracts=not a.no_backfill)
    except NoSource:
        return 2

    out = Path(a.output)
    write_xlsx(out, records, stats)
    if a.csv:
        write_csv(out.with_suffix(".csv"), records)
    no_abs = sum(1 for r in records if not r.has_abstract())
    log(f"\n{raw} raw results -> {len(records)} unique records ({no_abs} without full abstract)")
    log(f"Written: {out}" + (f" and {out.with_suffix('.csv')}" if a.csv else ""))
    return 0


class NoSource(RuntimeError):
    pass


def parse_all(queries: list[tuple[str, str]]) -> dict:
    asts = {}
    for label, text in queries:
        try:
            asts[label] = parse(text)
        except QueryError as e:
            raise QueryError(f"Query {label} is invalid: {e}\n  {text}") from e
    return asts


def run(queries: list[tuple[str, str]], names: list[str], imports: list[tuple[str, str | None]] = (), *,
        max_results: int = 100, strict: bool = False, resolve_doi: bool = False,
        doi_cache: str = ".doi_cache.json", backfill_abstracts: bool = True,
        log=log) -> tuple[list[Record], list[dict], int]:
    """Search, import, dedupe, backfill and match. Returns (records, per-query stats, raw count).
    Shared by the CLI and the GUI."""
    asts = parse_all(queries)
    active = []
    for n in names if queries else []:
        if getattr(ALL[n], "MANUAL", False):
            log(f"! {n}: no API. Get the query with --print-queries, run it on the site, then --import the export")
        elif ALL[n].available():
            active.append(n)
        else:
            log(f"! Skipping {n}: API key missing (see README / .env.example)")
    if queries and not active and not imports:
        log("No usable source.")
        raise NoSource()

    records: list[Record] = []
    stats: list[dict] = []
    for label, text in queries:
        log(f"[{label}] {text[:100]}{'...' if len(text) > 100 else ''}")
        for n in active:
            try:
                found = ALL[n].search(asts[label], max_results, log=log)
                note = ""
            except Exception as e:  # one failing source must not abort the run
                found, note = [], f"FAILED: {e}"
                log(f"  ! {n}: {e}")
            for r in found:
                r.queries = [label]
            records += found
            stats.append({"label": label, "query": text, "source": n, "count": len(found), "note": note})
            log(f"  {n}: {len(found)} results")

    for path, src in imports:
        label = src or Path(path).stem
        try:
            found = load_import(path, src)
        except Exception as e:
            log(f"! import {path}: {e}")
            stats.append({"label": "import", "query": path, "source": label, "count": 0, "note": f"FAILED: {e}"})
            continue
        for r in found:
            r.queries = ["import"]
        records += found
        stats.append({"label": "import", "query": path, "source": label, "count": len(found), "note": "imported file"})
        log(f"[import] {path}: {len(found)} records")

    if resolve_doi:
        resolve_dois(records, log=log, cache_path=doi_cache)
    else:
        for r in records:
            if r.doi and not r.doi_source:
                r.doi_source = "fournie"
    raw = len(records)
    records = dedupe(records)
    if backfill_abstracts:
        backfill(records, log=log)
        records = dedupe(records)  # backfill may reveal DOIs
    for r in records:
        d = _doc(r)
        qs = [q for q in r.queries if q in asts]
        if not qs:  # imported only: no query to evaluate
            r.match = "n/a"
            continue
        ok = any(matches(asts[q], d) for q in qs)
        r.match = "yes" if ok else ("unknown" if not r.abstract else "no")
    if strict:
        records = [r for r in records if r.match != "no"]
    records.sort(key=lambda r: (-(r.year or 0), r.title.lower()))
    return records, stats, raw


if __name__ == "__main__":
    raise SystemExit(main())
