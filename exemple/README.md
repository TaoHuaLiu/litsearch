# Exemple pas à pas : de l'identification au comptage PRISMA

Données **fictives** (7 articles inventés, DOI `10.1000/demo.*`), pour comprendre l'outil sans réseau ni clé d'API.

```bash
cd 05-outils/recherche
bash exemple/run_exemple.sh        # ~1 s, hors ligne ; résultats dans exemple/sortie/
```

## Ce que contient le dossier
| Fichier | Rôle |
|---|---|
| `donnees/pop_export.bibtex` | export Publish or Perish : pas de DOI, résumés tronqués (extraits Scholar) |
| `donnees/scholar.xlsx` | xlsx Scholar : pas de DOI, un titre **tronqué** par « … » |
| `donnees/openalex_results.md` | export OpenAlex : DOI et résumés complets |
| `donnees/ebsco.ris` | export EBSCO : un DOI écrit en `https://doi.org/…` et en majuscules |
| `doi_cache.json` | réponses OpenAlex/Crossref déjà « en cache » pour que l'exemple tourne hors ligne |
| `make_data.py` | régénère `donnees/` et `doi_cache.json` |
| `fill_decisions.py` | **simule le relecteur** (étape 2) |
| `sortie/` | résultats produits par `run_exemple.sh` |

## Étape 1 — Identification (`python -m litsearch --import … --resolve-doi`)
12 enregistrements bruts en entrée (2 + 3 + 4 + 3), 7 articles uniques en sortie. Ce qui se passe :
1. **Import** : chaque fichier est converti dans un format commun. `=pop`, `=scholar`… donnent le nom de la source.
2. **Résolution des DOI** (`--resolve-doi`) : les 6 enregistrements sans DOI sont cherchés par titre + année + premier auteur
   (OpenAlex, puis Crossref). Ici, 4 trouvés sur 6 : 3 en confiance **élevée**, 1 **à vérifier** (le titre tronqué par « … »),
   et 2 introuvables. Les 2 introuvables sont l'article de Garcia (présent chez Scholar et EBSCO, sans DOI) : il reste fusionné par titre + année.
3. **Dédoublonnage** : les enregistrements qui ont le même DOI, ou à défaut le même titre et la même année, sont fusionnés.
   L'article « Adaptive transparency… » apparaît dans 4 sources et n'a plus qu'une ligne (`Sources` = ebsco, openalex, pop, scholar).
   **Sans** `--resolve-doi`, la version tronquée de Scholar resterait un doublon.
4. Les colonnes `DOI_source` (fournie / openalex / crossref) et `DOI_confiance` (élevée / à vérifier) permettent de relire les DOI devinés.
   Un DOI fourni par une source l'emporte toujours sur un DOI deviné.

Résultat : `sortie/1_registre.xlsx` (et `.csv`), avec l'onglet `Queries` qui garde le nombre brut par source (c'est lui qui alimente la case « identifiés » du diagramme PRISMA).

> En vrai : ajoutez `--doi-cache .doi_cache.json` (valeur par défaut) et retirez `--no-backfill` pour aussi récupérer les résumés manquants
> (OpenAlex puis Crossref). Les deux demandent le réseau. Sans clé ni e-mail, OpenAlex limite vite le débit :
> définissez `OPENALEX_EMAIL` dans `.env`.

## Étape 2 — Screening puis éligibilité (à la main dans Excel)
Ouvrez `1_registre.xlsx` et remplissez, **sans supprimer de ligne** :

| Colonne | Valeurs | Quand |
|---|---|---|
| `Screening` | inclure / exclure / douteux | après lecture du titre et du résumé |
| `Motif_screening` | texte libre | obligatoire si `exclure` |
| `Texte_integral` | inclure / exclure | pour les lignes `inclure` ou `douteux` après lecture du PDF |
| `Motif_FT` | texte libre | obligatoire si `Texte_integral` = exclure |

`fill_decisions.py` fait ce travail à votre place dans l'exemple : 3 exclus au screening (transparence optique, transparence
gouvernementale, publié avant 2015), 1 « douteux » finalement exclu au texte intégral.
Résultat : `sortie/2_registre_decide.xlsx`.

## Étape 3 — Comptes (`python prisma_counts.py`)
```
identifiés 12 → doublons 5 → screenés 7 → exclus 3 → texte intégral 4 → exclus 1 → inclus 3
```
Le script vérifie la cohérence (motif manquant, décision de texte intégral sur une ligne déjà exclue…) et se termine en erreur si
quelque chose cloche. `sortie/3_prisma_counts.csv` peut être saisi dans l'application PRISMA2020 (estech.shinyapps.io/prisma_flowdiagram)
pour obtenir le diagramme de flux.

## Pour refaire avec vos données
Remplacez les 4 `--import` par vos fichiers (`02-recherche/…`), ajoutez vos requêtes si vous voulez aussi interroger les API
(`python -m litsearch queries.txt --import …`), et **copiez le xlsx avant de relancer** `litsearch` : un nouvel export
efface les colonnes de décision.
