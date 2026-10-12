"""Local web interface (Streamlit) for colleagues who do not use the command line.

    litsearch-gui            # opens http://localhost:8501 in the default browser

Runs on the user's own machine with the user's own keys (config.user_env_path())."""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path

NAMES = {"openalex": "OpenAlex", "scholar": "Google Scholar", "ieee": "IEEE Xplore", "sciencedirect": "ScienceDirect",
         "acm": "ACM (via OpenAlex)", "tandf": "Taylor & Francis", "wiley": "Wiley"}
NEED_KEY = {"scholar": "SERPAPI_KEY", "ieee": "IEEE_API_KEY", "sciencedirect": "ELSEVIER_API_KEY"}

SYNTAX = """
| Besoin | Écrire |
|---|---|
| Expression exacte | `"digital twin"` |
| Les deux mots | `a AND b` (ou simplement `a b`) |
| L'un ou l'autre | `a OR b` |
| Exclure | `NOT a` ou `-a`, `-"supply chain"` |
| Grouper | `("digital twin" OR "virtual twin") AND maintenance` |
| Troncature | `prognos*` (prognosis, prognostics…) |
| Proximité | `fault NEAR/3 detection` (au plus 3 mots entre) |
| Dans le titre | `title:"digital twin"`, `title:(a OR b)` |
| Tout dans le titre | `title:(maintenance "digital twin" -review)` → Scholar reçoit `allintitle:` |
"""


def launch() -> None:
    """Console-script entry point: start Streamlit on this file."""
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", __file__,
                              "--server.address=localhost",  # not reachable from the network: keys stay private
                              "--client.toolbarMode=minimal", "--browser.gatherUsageStats=false",
                              "--server.headless=false"]))


def app() -> None:
    import streamlit as st

    from litsearch.cli import NoSource, run
    from litsearch.config import KEYS, load_keys, read_user_keys, save_user_keys, user_env_path
    from litsearch.export import COLUMNS, _row, write_xlsx
    from litsearch.links import search_url
    from litsearch.query import QueryError, parse, render_fitted
    from litsearch.sources import ALL, DIALECTS

    st.set_page_config(page_title="Recherche bibliographique", layout="wide")
    load_keys()
    import os

    st.title("Recherche bibliographique multi-bases")
    tab_search, tab_keys, tab_help = st.tabs(["Recherche", "Paramètres (clés API)", "Aide"])

    with tab_keys:
        st.write(f"Les clés sont enregistrées sur cet ordinateur uniquement : `{user_env_path()}`")
        with st.expander("Comment obtenir les clés ?"):
            st.markdown((Path(__file__).with_name("cles_api.md")).read_text(encoding="utf-8"))
        saved = read_user_keys()
        with st.form("keys"):
            vals = {}
            for var, label, url in KEYS:
                vals[var] = st.text_input(f"{label} — [obtenir]({url})", value=saved.get(var, os.getenv(var, "")),
                                          type="password" if "KEY" in var or "TOKEN" in var else "default", key=var)
            if st.form_submit_button("Enregistrer"):
                p = save_user_keys(vals)
                st.success(f"Clés enregistrées dans {p}")

    with tab_help:
        st.markdown("### Syntaxe des requêtes\n" + SYNTAX)
        st.markdown("""
### Taylor & Francis et Wiley
Ces deux sites n'ont pas d'API : l'outil ne peut pas les interroger lui-même.
1. Dans **Recherche**, cliquez **Aperçu des requêtes**, puis **Ouvrir sur le site** pour T&F ou Wiley.
2. Sur le site, sélectionnez les résultats et exportez-les au format **RIS**.
3. Revenez ici, déposez le fichier dans **Importer des exports** et lancez la recherche.

### Le fichier Excel
Colonne `Match` : `yes` = l'article satisfait toute la requête, `no` = non, `unknown` = pas de résumé pour vérifier.
Remplissez ensuite `Screening` (inclure/exclure/douteux) et `Motif_screening`. Ne supprimez pas de lignes.
""")

    with tab_search:
        query = st.text_area("Requête", height=150, placeholder='("digital twin" OR "virtual twin") AND "predictive maintenance"')
        with st.expander("Aide-mémoire de la syntaxe"):
            st.markdown(SYNTAX)
        c1, c2, c3 = st.columns(3)
        y_from = c1.number_input("Année de début", 1900, 2100, 2024)
        y_to = c2.number_input("Année de fin", 1900, 2100, 2026)
        max_res = c3.number_input("Résultats max. par base", 10, 1000, 100, step=10)

        st.write("**Bases interrogées automatiquement**")
        cols = st.columns(5)
        chosen = []
        for col, n in zip(cols, ["openalex", "scholar", "ieee", "sciencedirect", "acm"]):
            ok = ALL[n].available()
            label = NAMES[n] + ("" if ok else " (clé manquante)")
            if col.checkbox(label, value=ok, disabled=not ok, key=f"src_{n}"):
                chosen.append(n)
        st.caption("Taylor & Francis et Wiley : utilisez « Ouvrir sur le site » dans l'aperçu, exportez en RIS "
                   "puis importez le fichier ci-dessous.")

        uploads = st.file_uploader("Importer des exports (RIS, BibTeX, CSV, XLSX)", accept_multiple_files=True,
                                   type=["ris", "bib", "bibtex", "csv", "xlsx"])
        labels = {}
        for f in uploads or []:
            stem = Path(f.name).stem.lower()
            guess = "tandf" if "tand" in stem or "taylor" in stem else "wiley" if "wiley" in stem else stem
            labels[f.name] = st.text_input(f"Base d'origine de « {f.name} »", value=guess, key=f"lab_{f.name}")

        with st.expander("Options avancées"):
            strict = st.checkbox("Garder seulement les articles qui satisfont exactement la requête (strict)")
            resolve = st.checkbox("Retrouver les DOI manquants (plus lent)")
            no_backfill = st.checkbox("Ne pas chercher les résumés manquants (plus rapide)")

        full = query.strip()
        if full and "year:" not in full:
            full = f"({full}) AND year:{int(y_from)}-{int(y_to)}"
        ast = None
        if full:
            try:
                ast = parse(full)
            except QueryError as e:
                st.error(f"Requête invalide : {e}")

        b1, b2 = st.columns(2)
        if b1.button("Aperçu des requêtes", disabled=ast is None, width="stretch"):
            for n in NAMES:
                q, cut = render_fitted(ast, DIALECTS[n])
                st.markdown(f"**{NAMES[n]}**" + (" — *réduite pour respecter la limite du site*" if cut else ""))
                st.code(q or "(rien d'interrogeable)", language=None)
                if url := search_url(n, ast):
                    st.link_button("Ouvrir sur le site", url)

        if b2.button("Lancer la recherche", type="primary", disabled=ast is None and not uploads,
                     width="stretch"):
            with tempfile.TemporaryDirectory() as tmp, st.status("Recherche en cours…", expanded=True) as status:
                imports = []
                for f in uploads or []:
                    p = Path(tmp) / f.name
                    p.write_bytes(f.getvalue())
                    imports.append((str(p), labels.get(f.name) or None))
                queries = [("Q1", full)] if ast is not None else []
                try:
                    records, stats, raw = run(queries, chosen, imports, max_results=int(max_res), strict=strict,
                                              resolve_doi=resolve, backfill_abstracts=not no_backfill,
                                              doi_cache=str(user_env_path().parent / "doi_cache.json"),
                                              log=lambda m: st.text(m.strip()))
                except NoSource:
                    status.update(label="Aucune base utilisable : cochez une base ou importez un fichier.", state="error")
                    st.stop()
                for s in stats:  # imports were read from a temp folder: keep only the file name
                    if s["label"] == "import":
                        s["query"] = Path(s["query"]).name
                buf = io.BytesIO()
                write_xlsx(buf, records, stats)
                st.session_state["result"] = (records, buf.getvalue(), raw)
                status.update(label=f"Terminé : {raw} résultats bruts → {len(records)} articles uniques", state="complete")

        if "result" in st.session_state:
            records, data, raw = st.session_state["result"]
            st.download_button("Télécharger l'Excel", data, file_name="resultats.xlsx", type="primary",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            show = ["Title", "Year", "Author", "Publication", "Sources", "Match"]
            idx = [COLUMNS.index(c) for c in show]
            st.dataframe([{c: _row(r)[i] for c, i in zip(show, idx)} for r in records], width="stretch")


if __name__ == "__main__":
    app()
