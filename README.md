# litsearch: boolean literature search

Takes a boolean query and returns **Author | Title | Year | Publication | Full Abstract** (XLSX, optional CSV) from:

| Source | How | Key needed |
|---|---|---|
| OpenAlex | REST API, title+abstract boolean search | no (email recommended) |
| Google Scholar | SerpAPI (Scholar has no official API) | `SERPAPI_KEY` |
| IEEE Xplore | official API | `IEEE_API_KEY` |
| ScienceDirect | Elsevier API | `ELSEVIER_API_KEY` |
| ACM | OpenAlex restricted to DOI prefix `10.1145` (ACM has no public search API) | no |
| Taylor & Francis | **manual**: no API, the tool only generates the query (`--print-queries`) | no |
| Wiley | **manual**: no API, the tool only generates the query (`--print-queries`) | no |

French guide: [GUIDE_UTILISATEUR_FR.md](GUIDE_UTILISATEUR_FR.md)

## Install

From any folder, with [uv](https://docs.astral.sh/uv/) (puts `litsearch`, `litsearch-gui` and `litsearch-prisma` on the PATH):

```bash
uv tool install --python 3.12 "litsearch[gui] @ <repo archive URL or path>"
uv tool install --python 3.12 --editable ".[gui]"     # maintainer: code changes apply immediately
```

Keys are read, first value winning, from: the environment, `./.env` in the current folder, the user config file
(`~/.config/litsearch/.env` on macOS/Linux, `%APPDATA%\litsearch\.env` on Windows, also written by the GUI's
*Paramètres* tab), then a `.env` next to the source. Template: `.env.example`.

Colleagues without CLI experience: double-click `installer/Installer-litsearch.bat` (Windows) or
`installer/Installer-litsearch.command` (macOS). They install uv + litsearch and put a *Recherche biblio* shortcut on
the Desktop that opens the web interface (`litsearch-gui`, Streamlit on localhost only). Re-running updates.
Set `REPO_ZIP` at the top of both installers to the repo's archive URL (e.g.
`https://github.com/<user>/<repo>/archive/refs/heads/main.zip`; the repo must be public, or the download needs a token).

Development: `python3 -m venv .venv && .venv/bin/pip install -e ".[gui,test]"`.

## Use

```bash
litsearch queries.txt -o results.xlsx --csv
litsearch '("adaptive transparency") AND (trust OR "mental workload")' --sources openalex,ieee --max 200
```

Engines without an API (`tandf`, `wiley`): print the query in their syntax, run it on the site, export the
results (RIS/CSV) and merge them with `--import`:

```bash
litsearch queries.txt --print-queries --sources tandf,wiley
litsearch queries.txt --sources openalex --import tandf.ris=tandf --import wiley.ris=wiley
```

Dialects: T&F supports `AND/OR/NOT`, phrases, `* ?` and `"a b"~n` proximity (only between two single words,
otherwise NEAR becomes AND); Wiley supports `AND/OR/NOT`, phrases and `*` only (NEAR becomes AND, `?` is dropped).
Both syntaxes come from library guides, not publisher documentation, so check a first query on the site.

Options: `--sources` (default all), `--max` per source per query (default 100), `--strict` (drop records that do
not satisfy the full query), `--no-backfill`, `--csv`.

A query file holds one query per block, blocks separated by a blank line (`#` lines are comments). Queries are
labelled Q1, Q2, ...

Sources whose key is missing are skipped with a warning; a failing source never aborts the run.

## Query syntax

| Feature | Syntax |
|---|---|
| Phrase | `"decision making"` (curly quotes and en/em dashes are normalised) |
| Boolean | `AND`, `OR`, `NOT` (case-insensitive); precedence NOT > AND > OR; a space is an implicit AND |
| Negation | `NOT x`, `AND NOT x`, `-x`, `-"a phrase"` |
| Grouping | `( ... )`, nested |
| Proximity | `a NEAR/5 b` (either order), `a NEXT/5 b` or `a PRE/5 b` (a before b), `a W/5 b` (unordered); up to n words between |
| Wildcards | `explain*`, `transparen?y` |
| Fields | `title:`, `abstract:`, `author:`, `publication:` e.g. `title:"adaptive transparency"`, `title:(a OR b)` |
| All in title | when every clause is a `title:` field, Scholar gets `allintitle:` (e.g. `title:(maintenance "digital twin" -review)`); mixed queries are sent without the title restriction |
| Years | `year:2020`, `year:2020-2024`, `year:>=2020`, `year:<2024` |

Syntax errors are reported with their position (unbalanced parentheses, dangling operator, unclosed quote...).

## How results are produced

1. Each source gets the query rewritten in its own syntax. Where a source lacks a feature, it is downgraded
   (NEAR becomes AND; author/field restrictors are dropped) and enforced locally instead.
2. Records are deduplicated (DOI, else title+year) and merged; the `Sources` column lists every source that found them.
3. Missing abstracts are looked up by DOI/title in OpenAlex, then Crossref. Scholar only returns a snippet;
   if no full abstract is found the snippet is kept and prefixed `[Scholar snippet only]`.
4. The full query is re-evaluated locally on title+abstract+authors+year and reported in `Match`:
   `yes`, `no`, or `unknown` (no abstract to check).

Extra columns after the five required ones: DOI, URL, Sources, Query, Match. A second sheet, `Queries`, records
raw counts per query and source (and any failure).

## Limits worth knowing

- **Scholar** queries are limited to about 256 characters; longer ones are reduced to the AND-groups that fit and
  the local matcher checks the rest (a message is printed). Quota depends on your SerpAPI plan.
- **ScienceDirect** limits boolean operators per query (8); same reduction. Abstracts may need institutional access.
- **OpenAlex/ACM** search stems words and covers title+abstract, so `Match = no` rows are often near-misses
  (e.g. "transparent" vs "transparency"). Use `--strict` for exact matching only.
- The Scholar, IEEE and ScienceDirect connectors need your own keys and have not been run live here; OpenAlex and
  ACM have.

## Tests

```bash
.venv/bin/python -m pytest -q tests
```

## Import other tools' exports, track screening, count for PRISMA

```bash
litsearch --import pop.bibtex=pop --import scholar.xlsx=scholar-xlsx --import openalex_results.md=openalex-md \
    --import ebsco.ris=ebsco -o registre.xlsx          # can be combined with a query file
litsearch-prisma registre.xlsx --csv prisma_counts.csv
```

Formats: `.bib/.bibtex` (Publish or Perish), `.xlsx` / `.csv` (header with Title/Titre), `.ris` (EBSCO), `.md` (`openalex_results.md`).
`--resolve-doi` finds missing DOIs from title + year + first author (OpenAlex, then Crossref; cached in `.doi_cache.json`;
`DOI_source` / `DOI_confiance` columns flag guessed DOIs). A worked, offline example is in [exemple/](exemple/README.md).
Imported records go through the same dedupe, abstract backfill and `Match` as live searches (`Match` = `n/a` if no query applies).
Fill `Screening` (inclure/exclure/douteux), `Motif_screening`, `Texte_integral` (inclure/exclure), `Motif_FT` in the xlsx;
never delete rows. `prisma_counts.py` prints the PRISMA counts and exits non-zero on a missing reason or inconsistent decision.
Warning: re-running litsearch rewrites the xlsx and blanks these columns; copy the file before re-exporting.
