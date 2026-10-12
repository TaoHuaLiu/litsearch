# Obtenir les clés API

litsearch interroge chaque base avec **vos propres clés**. Elles restent sur votre ordinateur : collez-les dans l'onglet
**Paramètres** de l'interface web (ou dans le fichier `.env`, voir en bas de page). Une base sans clé est simplement
ignorée ; **OpenAlex et ACM fonctionnent sans aucune clé**, vous pouvez donc commencer tout de suite.

| Base | Clé nécessaire ? | Coût | Délai | Variable |
|---|---|---|---|---|
| OpenAlex, ACM | non (facultative) | gratuit | immédiat | `OPENALEX_EMAIL`, `OPENALEX_API_KEY` |
| Google Scholar | oui (SerpAPI) | gratuit jusqu'à 250 recherches/mois | immédiat | `SERPAPI_KEY` |
| IEEE Xplore | oui | gratuit | validation manuelle, heures ouvrées (US) | `IEEE_API_KEY` |
| ScienceDirect | oui (+ accès institutionnel) | gratuit pour un usage académique | immédiat, mais accès au contenu à vérifier | `ELSEVIER_API_KEY`, `ELSEVIER_INSTTOKEN` |
| Taylor & Francis, Wiley | pas d'API | — | — | export RIS depuis le site, puis import |

---

## OpenAlex (et ACM)

ACM passe par OpenAlex : ce qui suit vaut pour les deux.

**Sans rien faire, ça marche.** Deux réglages facultatifs améliorent le service :

- **E-mail** (`OPENALEX_EMAIL`) : votre adresse, simplement. Elle est envoyée à OpenAlex pour identifier vos requêtes.
- **Clé** (`OPENALEX_API_KEY`) : multiplie par 10 le quota quotidien gratuit. Utile si vous lancez beaucoup de
  recherches ou de grosses requêtes.
  1. Créez un compte sur <https://openalex.org> (bouton *Sign in*, ~30 secondes).
  2. Ouvrez <https://openalex.org/settings/api> et copiez la clé.

## Google Scholar (via SerpAPI)

Google Scholar n'a pas d'API officielle ; litsearch passe par le service SerpAPI.

1. Créez un compte sur <https://serpapi.com/users/sign_up> et confirmez votre e-mail (et votre numéro de téléphone
   si demandé).
2. La clé est affichée sur <https://serpapi.com/manage-api-key>. Copiez-la dans **Google Scholar (SerpAPI)**.

**Quota** : le plan gratuit donne **250 recherches par mois** (50 par heure). litsearch consomme **1 recherche par
tranche de 20 résultats** : avec « Résultats max. par base » à 100, une requête coûte jusqu'à 5 recherches.
Consultez votre consommation sur <https://serpapi.com/dashboard>. Pour économiser : baissez le nombre maximal de
résultats, et utilisez **Aperçu des requêtes → Ouvrir sur le site** pour tester une requête gratuitement dans Scholar
avant de la lancer.

## IEEE Xplore

1. Créez un compte sur <https://developer.ieee.org> (lien *Register* en haut de la page) et confirmez votre e-mail.
2. Demandez une clé depuis votre compte : décrivez brièvement l'usage, par exemple « Revue systématique de
   littérature, projet étudiant ENSIBS, recherche de métadonnées », et indiquez l'adresse du site web de
   l'établissement (une seule clé par application).
3. La clé est délivrée **manuellement, en heures ouvrées américaines (8 h – 17 h, heure de New York, du lundi au
   vendredi)**, donc souvent le lendemain. Vous recevez un e-mail ; la clé est aussi visible dans votre compte.

Les limites d'appels (par seconde et par jour) sont affichées dans votre compte développeur ; une recherche
litsearch n'en consomme que quelques-uns. Les conditions d'utilisation interdisent de republier le contenu en masse :
gardez les résultats pour votre revue.

## ScienceDirect (Elsevier)

1. Créez un compte Elsevier (de préférence avec votre **adresse e-mail universitaire**) sur <https://dev.elsevier.com>.
2. Ouvrez <https://dev.elsevier.com/apikey/manage> → *Create API Key*, donnez un nom (ex. « litsearch »), acceptez
   les conditions. La clé apparaît immédiatement.

**Attention, avoir la clé ne suffit pas** : Elsevier ne donne accès aux résultats que si la requête vient d'une
institution abonnée. Deux possibilités :

- **lancer la recherche depuis le réseau de l'école** (sur place, ou via le VPN de l'université) ; c'est le cas le
  plus simple ;
- **ou** demander un **insttoken** à la bibliothèque / au SCD, qui le demande à Elsevier. Collez-le dans
  **ScienceDirect : insttoken**. Il permet de travailler hors du réseau ; gardez-le strictement personnel.

Si ScienceDirect renvoie une erreur 401/403 dans les messages de la recherche, c'est presque toujours ce point.
Quotas : 20 000 requêtes par semaine, 2 par seconde ; litsearch fait aussi une requête par article pour récupérer
le résumé.

## Taylor & Francis et Wiley

Pas de clé : ces sites n'ont pas d'API de recherche. Dans l'onglet **Recherche**, cliquez **Aperçu des requêtes →
Ouvrir sur le site**, exportez les résultats en **RIS**, puis déposez le fichier dans **Importer des exports**.

---

## Où sont enregistrées les clés ?

L'onglet **Paramètres** les écrit dans un fichier de votre profil utilisateur :

- Windows : `%APPDATA%\litsearch\.env`
- macOS / Linux : `~/.config/litsearch/.env`

Vous pouvez aussi éditer ce fichier à la main (modèle : `.env.example` du dépôt), une ligne par clé :
`SERPAPI_KEY=votre_clé`. Ne partagez jamais ce fichier ni vos clés (ni par e-mail, ni dans le dépôt Git) :
chaque collègue utilise les siennes, ce qui répartit aussi les quotas.

**Une clé ne marche pas ?** Vérifiez qu'il n'y a ni espace ni guillemet autour, enregistrez, puis relancez la page.
Dans l'onglet Recherche, une base dont la clé manque apparaît grisée avec « clé manquante ».
