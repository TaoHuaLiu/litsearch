"""ACM has no public search API. ACM DOIs all start with 10.1145, so we search
OpenAlex restricted to that DOI prefix (boolean query supported, abstracts
included when OpenAlex has them; the rest is backfilled from Crossref)."""
from __future__ import annotations

from . import openalex

NAME = "acm"


def available() -> bool:
    return True


def search(ast, max_results: int, log=print):
    return openalex.search(ast, max_results, extra_filters=["doi_starts_with:10.1145"],
                           source=NAME, log=log)
