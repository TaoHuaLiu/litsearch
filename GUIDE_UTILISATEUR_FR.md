# Guide utilisateur : litsearch (recherche bibliographique booléenne)

`litsearch` prend une requête booléenne et renvoie un tableau **Auteur | Titre | Année | Publication | Résumé complet**
(XLSX, et CSV en option) à partir de plusieurs bases : OpenAlex, Google Scholar, IEEE Xplore, ScienceDirect et ACM.

## 0. Sans ligne de commande (interface web)

**Installer (une seule fois)**
1. Téléchargez `Installer-litsearch.bat` (Windows) ou `Installer-litsearch.command` (Mac) depuis le dossier `installer/` du dépôt.
2. Double-cliquez dessus. Sous Windows, si un écran bleu « Windows a protégé votre ordinateur » apparaît :
   *Informations complémentaires* → *Exécuter quand même*. Sur Mac, la première fois : clic droit → *Ouvrir*.
3. Attendez « Terminé ». Un raccourci **Recherche biblio** apparaît sur le Bureau.

Pour **mettre à jour**, relancez simplement le même installeur.

**Utiliser**
1. Double-cliquez sur **Recherche biblio** : la page s'ouvre dans votre navigateur (Edge, Chrome, Firefox, Safari…).
   Une fenêtre noire reste ouverte en arrière-plan ; fermez-la quand vous avez fini.
2. Onglet **Paramètres** : collez vos clés API puis *Enregistrer* (« Comment obtenir les clés ? » explique où les demander). Elles restent sur votre
   ordinateur et ne sont jamais partagées. OpenAlex et ACM marchent sans clé.
3. Onglet **Recherche** : tapez la requête, choisissez les années et les bases, cliquez **Lancer la recherche**,
   puis **Télécharger l'Excel**.
4. **Aperçu des requêtes** montre la requête traduite pour chaque base, avec un bouton **Ouvrir sur le site**.
   Pour Taylor & Francis et Wiley (sans API) : ouvrez le site, exportez les résultats en RIS, puis déposez le
   fichier dans **Importer des exports** avant de lancer la recherche.

## 1. Installation

En ligne de commande, avec [uv](https://docs.astral.sh/uv/) (installe aussi la commande `litsearch` accessible depuis n'importe quel dossier) :

```bash
uv tool install --python 3.12 "litsearch[gui] @ https://github.com/TaoHuaLiu/litsearch/archive/refs/heads/main.zip"
```

Les clés API se règlent dans l'onglet **Paramètres** de l'interface web, ou à la main dans le fichier
`~/.config/litsearch/.env` (Mac/Linux) ou `%APPDATA%\litsearch\.env` (Windows), sur le modèle de `.env.example`.
Un fichier `.env` dans le dossier courant est aussi lu, et passe avant.

Clés dont vous pouvez disposer (démarches détaillées, quotas et pièges : [litsearch/cles_api.md](litsearch/cles_api.md), aussi affiché dans l'onglet Paramètres) :

| Source | Variable | Où l'obtenir |
|---|---|---|
| OpenAlex | `OPENALEX_EMAIL` (facultatif, recommandé) | aucune clé nécessaire |
| Google Scholar | `SERPAPI_KEY` | https://serpapi.com/ (Scholar n'a pas d'API officielle) |
| IEEE Xplore | `IEEE_API_KEY` | https://developer.ieee.org/ |
| ScienceDirect | `ELSEVIER_API_KEY` (+ `ELSEVIER_INSTTOKEN` si fourni) | https://dev.elsevier.com/ |
| ACM | aucune | passe par OpenAlex (préfixe DOI `10.1145`), car ACM n'a pas d'API de recherche publique |

Une source sans clé est simplement ignorée (un avertissement s'affiche). OpenAlex et ACM fonctionnent sans clé.

## 2. Lancer une recherche

Avec un fichier de requêtes (une requête par bloc, blocs séparés par une ligne vide, lignes `#` = commentaires) :

```bash
litsearch queries.txt -o resultats.xlsx --csv
```

Avec une requête directe :

```bash
litsearch '("adaptive transparency") AND (trust OR "mental workload")' --sources openalex,ieee --max 200
```

| Option | Rôle |
|---|---|
| `-o fichier.xlsx` | fichier de sortie (défaut `results.xlsx`) |
| `--csv` | écrit aussi un CSV (UTF-8) à côté |
| `--sources` | liste parmi `openalex,scholar,ieee,sciencedirect,acm` (défaut : toutes) |
| `--max N` | nombre maximal de résultats par source et par requête (défaut 100) |
| `--strict` | supprime les résultats qui ne satisfont pas exactement la requête complète |
| `--no-backfill` | ne cherche pas les résumés manquants |

Les requêtes d'un fichier sont nommées Q1, Q2, … dans l'ordre.

## 3. Syntaxe des requêtes

| Fonction | Syntaxe |
|---|---|
| Expression exacte | `"decision making"` (guillemets typographiques et tirets longs sont normalisés) |
| Opérateurs | `AND`, `OR`, `NOT` (majuscules ou minuscules). Priorité : NOT > AND > OR. Un espace vaut AND |
| Négation | `NOT x`, `AND NOT x`, `-x`, `-"une expression"` |
| Parenthèses | `( ... )`, imbriquées possibles |
| Proximité | `a NEAR/5 b` (dans n'importe quel ordre), `a NEXT/5 b` ou `a PRE/5 b` (a avant b), `a W/5 b` : au plus 5 mots entre les deux |
| Jokers | `explain*` (suite de lettres), `transparen?y` (une lettre) |
| Champs | `title:`, `abstract:`, `author:`, `publication:` : `title:"adaptive transparency"`, `title:(a OR b)` |
| Tout dans le titre | `title:(maintenance "digital twin" -review)` : si toute la requête porte sur le titre, Google Scholar reçoit `allintitle:` |
| Années | `year:2020`, `year:2020-2024`, `year:>=2020`, `year:<2024` |

Pièges fréquents (déjà rencontrés dans vos requêtes) :
- Parenthèse manquante ou en trop : l'outil s'arrête et indique la position de l'erreur.
- `A AND B OR C` se lit `(A AND B) OR C` : ajoutez des parenthèses pour l'autre sens.
- Évitez des parenthèses à l'intérieur d'une expression exacte, par exemple `"human-autonomy teaming (HAT)"` :
  préférez `"human-autonomy teaming" OR HAT`.

## 4. Lire les résultats

Feuille **Results** (une ligne par article, dédoublonné entre sources et entre requêtes) :

| Colonne | Contenu |
|---|---|
| Author | auteurs séparés par `;` |
| Title, Year, Publication | titre, année, revue ou conférence |
| Full Abstract | résumé complet |
| DOI, URL | identifiants et lien |
| Sources | bases ayant trouvé l'article |
| Query | requêtes concernées (Q1, Q2…) |
| Match | `yes` : la requête complète est vérifiée localement sur titre+résumé+auteurs+année ; `no` : non (souvent une quasi-correspondance due à la racinisation, ex. « transparent » vs « transparency ») ; `unknown` : pas de résumé pour vérifier |

Feuille **Queries** : nombre de résultats bruts par requête et par source, et les éventuelles erreurs.

Résumés : s'ils manquent, l'outil les cherche par DOI ou titre dans OpenAlex puis Crossref. Google Scholar ne fournit
qu'un extrait ; s'il n'y a rien de mieux, l'extrait est conservé avec la mention `[Scholar snippet only]`.

## 5. Limites à connaître

- **Google Scholar** : requête limitée à environ 256 caractères. Les requêtes longues sont réduites aux groupes AND
  qui tiennent (un message l'indique), puis le filtre local vérifie le reste. Le quota dépend de votre abonnement SerpAPI.
- **ScienceDirect** : nombre d'opérateurs booléens limité (8), même réduction ; les résumés peuvent exiger un accès institutionnel.
- Dans OpenAlex/ACM, la recherche porte sur titre+résumé avec racinisation : utilisez `--strict` pour ne garder que les correspondances exactes.
- Les connecteurs Scholar, IEEE et ScienceDirect nécessitent vos clés et n'ont pas pu être testés en réel ; OpenAlex et ACM l'ont été.
- Les résultats d'un échec temporaire d'une source ne bloquent pas les autres : consultez la feuille **Queries**.

## 6. Dépannage

| Message | Cause / solution |
|---|---|
| `Skipping scholar: API key missing` | ajoutez la clé (onglet Paramètres ou fichier `.env`) ou retirez la source de `--sources` |
| `Query Q2 is invalid: Missing ')'…` | corrigez les parenthèses à la position indiquée |
| `0 results` pour ACM | normal si peu d'articles ACM correspondent ; élargissez la requête |
| Beaucoup de `unknown` | peu de résumés disponibles ; relancez sans `--no-backfill` |

## 7. Tests (développement)

```bash
.venv/bin/python -m pytest -q tests
```
