"""Taylor & Francis Online has no public search API (its SRU endpoint sits behind a Cloudflare challenge),
so this source only produces the query to paste into https://www.tandfonline.com/search/advanced.
Run it there, export the results (RIS/CSV) and bring them back with --import."""
from __future__ import annotations

NAME = "tandf"
MANUAL = True


def available() -> bool:
    return False


def search(ast, max_results: int, log=print):
    raise NotImplementedError("manual source: use --print-queries, then --import the export")
