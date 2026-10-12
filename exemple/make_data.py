"""Génère les données FICTIVES de l'exemple (donnees/) et le cache DOI pré-rempli (doi_cache.json).
À lancer depuis recherche/ :  .venv/bin/python exemple/make_data.py"""
import json
import sys
from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from litsearch.doi import _key  # noqa: E402
from litsearch.importers import load  # noqa: E402

D = HERE / "donnees"
D.mkdir(exist_ok=True)

(D / "pop_export.bibtex").write_text("""@article{pop00001,
\tauthor = {A Smith and B Jones},
\ttitle = {Adaptive transparency for autonomous agents under time pressure},
\tjournal = {Demo Journal of Human Factors},
\tyear = {2025},
\tabstract = {… an adaptive transparency scheme for autonomous agents when the operator is under time …},
\tnote = {Query date: 2026-10-02 11:39:07}
}
@article{pop00002,
\tauthor = {D Lee},
\ttitle = {Explainable AI for operators of supervisory control systems},
\tjournal = {Demo Control Review},
\tyear = {2023},
\tabstract = {… explanations that help operators of supervisory control systems calibrate …},
\tnote = {Query date: 2026-10-02 11:39:07}
}
""", encoding="utf-8")

(D / "openalex_results.md").write_text("""# OpenAlex — données fictives de démonstration

## Q1 transparence adaptative

### 1. Adaptive transparency for autonomous agents under time pressure

- Auteurs : Alice Smith, Bob Jones
- Annee : 2025 — Type : article — Cite par : 12
- OpenAlex : https://openalex.org/W0000001
- DOI : [https://doi.org/10.1000/demo.001](https://doi.org/10.1000/demo.001)
- Resume :

> We study an adaptive transparency scheme in which an autonomous agent increases or reduces the detail of its explanations according to the operator's time pressure and workload.


### 2. Trust calibration in human-robot teaming: a longitudinal study

- Auteurs : Claire Martin
- Annee : 2024 — Type : article — Cite par : 4
- OpenAlex : https://openalex.org/W0000002
- DOI : [https://doi.org/10.1000/demo.002](https://doi.org/10.1000/demo.002)
- Resume :

> A longitudinal experiment on operators' trust calibration when cooperating with a robot whose transparency varies over sessions.


### 3. Smart windows with dynamic transparency changes

- Auteurs : Hao Chen
- Annee : 2024 — Type : article — Cite par : 26
- OpenAlex : https://openalex.org/W0000003
- DOI : [https://doi.org/10.1000/demo.004](https://doi.org/10.1000/demo.004)
- Resume :

> We present an electrochromic smart window whose optical transparency changes under compression.


### 4. A review of human-autonomy teaming

- Auteurs : Kim Roe
- Annee : 2014 — Type : article — Cite par : 300
- OpenAlex : https://openalex.org/W0000004
- DOI : [https://doi.org/10.1000/demo.007](https://doi.org/10.1000/demo.007)
- Resume :

> A review of early work on human-autonomy teaming.
""", encoding="utf-8")

(D / "ebsco.ris").write_text("""TY  - JOUR
TI  - Adaptive transparency for autonomous agents under time pressure
AU  - Smith, Alice
AU  - Jones, Bob
PY  - 2025///
DO  - https://doi.org/10.1000/DEMO.001
JO  - Demo Journal of Human Factors
AB  - We study an adaptive transparency scheme in which an autonomous agent increases or reduces the detail of its explanations according to the operator's time pressure and workload.
ER  - 
TY  - JOUR
TI  - Workload-adaptive explanations in decision support
AU  - Garcia, Maria
PY  - 2022///
JO  - Demo Decision Support Letters
AB  - Explanations whose length adapts to the decision maker's workload in a decision support tool.
ER  - 
TY  - JOUR
TI  - Government transparency and open data portals
AU  - Novak, Petr
PY  - 2019///
DO  - 10.1000/demo.006
JO  - Demo Public Policy
AB  - How open government portals disclose information to citizens.
ER  - 
""", encoding="utf-8")

wb = Workbook()
ws = wb.active
ws.title = "Références uniques"
ws.append(["Références uniques — données fictives"])
ws.append([]); ws.append([])
ws.append(["ID référence", "Thématique(s)", "Titre", "Auteurs", "Année", "Revue / conférence / source",
           "Extrait Google Scholar (pas le résumé intégral)", "URL publication"])
ws.append(["REF-0001", "a", "Adaptive transparency for autonomous agents under …", "A Smith; B Jones", 2025,
           "Demo Journal of Human Factors", "… adaptive transparency for autonomous agents …", "https://example.org/1"])
ws.append(["REF-0002", "b", "Trust calibration in human-robot teaming: a longitudinal study", "C Martin", 2024,
           "Demo HRI Proceedings", "… trust calibration … robot whose transparency varies …", "https://example.org/2"])
ws.append(["REF-0003", "c", "Workload-adaptive explanations in decision support", "M Garcia", 2022,
           "Demo Decision Support Letters", "… explanations whose length adapts to workload …", "https://example.org/5"])
wb.save(D / "scholar.xlsx")

# Cache DOI pré-rempli : l'exemple tourne hors ligne. Valeurs fictives, au format écrit par litsearch/doi.py.
cache = {}
for f, tag in (("pop_export.bibtex", "pop"), ("scholar.xlsx", "scholar")):
    for r in load(D / f, tag):
        t = r.title
        if t.startswith("Adaptive transparency for autonomous agents under …"):
            cache[_key(r)] = {"doi": "10.1000/demo.001", "source": "openalex", "confidence": "à vérifier"}
        elif t.startswith("Adaptive transparency for autonomous agents under time"):
            cache[_key(r)] = {"doi": "10.1000/demo.001", "source": "openalex", "confidence": "élevée"}
        elif t.startswith("Explainable AI"):
            cache[_key(r)] = {"doi": "10.1000/demo.003", "source": "crossref", "confidence": "élevée"}
        elif t.startswith("Trust calibration"):
            cache[_key(r)] = {"doi": "10.1000/demo.002", "source": "openalex", "confidence": "élevée"}
        else:  # recherché mais introuvable
            cache[_key(r)] = None
for r in load(D / "ebsco.ris", "ebsco"):
    if not r.doi:
        cache[_key(r)] = None
(HERE / "doi_cache.json").write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(cache)} entrées de cache écrites")
