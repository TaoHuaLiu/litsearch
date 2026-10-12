#!/usr/bin/env bash
# Exemple complet, hors ligne. Lancer depuis le dossier recherche/ :  bash exemple/run_exemple.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
D=exemple/donnees
OUT=exemple/sortie
mkdir -p "$OUT"

echo "=== Étape 1 — Identification : importer 4 exports, résoudre les DOI, dédoublonner ==="
$PY -m litsearch \
  --import $D/pop_export.bibtex=pop \
  --import $D/scholar.xlsx=scholar \
  --import $D/openalex_results.md=openalex \
  --import $D/ebsco.ris=ebsco \
  --resolve-doi --doi-cache exemple/doi_cache.json \
  --no-backfill \
  -o $OUT/1_registre.xlsx --csv

echo
echo "=== Étape 2 — Screening + éligibilité (ici simulé ; en vrai : vous remplissez les colonnes dans Excel) ==="
$PY exemple/fill_decisions.py $OUT/1_registre.xlsx $OUT/2_registre_decide.xlsx

echo
echo "=== Étape 3 — Comptes PRISMA ==="
$PY prisma_counts.py $OUT/2_registre_decide.xlsx --csv $OUT/3_prisma_counts.csv
