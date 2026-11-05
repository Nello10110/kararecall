# Interface et API

L’interface est servie par `web_server.py`, sans compilation ni dépendance tierce. En développement local : `python3 web_server.py --open-browser`, ou le lanceur `Ouvrir Mémoire.command`. Le serveur écoute sur `127.0.0.1:8765` par défaut. Une configuration `.env` existante est chargée ; sans identifiants, seul le démarrage sur la boucle locale est autorisé. Le [guide homelab](HOMELAB.md) décrit le mode Docker avec authentification obligatoire.

## Parcours

- **Recherche** : mots ou description d’un souvenir, classement lexical, filtres outils/sources.
- **Mes outils** : description, utilité, fonctionnement, limites, liens et preuves. Les synthèses automatiques sont marquées « À relire ».
- **Sources** : favoris conservés localement, texte disponible, état réel des extractions.
- **Preuves** : transcription et captures horodatées, vidéo locale avec navigation à l’instant cité. Les formats lisibles dépendent du navigateur.
- **Traitements** : présence des médias, transcription/OCR et état du dernier passage du worker. Actualiser le catalogue pour charger les nouveaux résultats. La vue ne pilote pas les tâches. Elle affiche le budget comptabilisé, les appels, les sources en attente et les étapes en erreur/non applicables, et signale un état de collecte trop ancien.
- **Approfondir** : export Markdown ou copie du contexte destiné à un autre assistant ; aucune requête IA n’est lancée par ce bouton. Un champ sélectionnable remplace le presse-papiers si nécessaire.

Le Markdown conserve les liens relatifs du coffre : les fichiers associés sont nécessaires pour consulter les preuves hors de l’application. Le contexte à copier fournit les URL originales et les extraits utiles même sans accès au volume.

## Routes de lecture

| Route | Résultat |
|---|---|
| `/api/health` | Santé du serveur HTTP |
| `/api/catalog` | Outils, sources, compteurs et état public du worker |
| `/api/search?q=…&scope=all` | Recherche ; scope accepte aussi `tools` ou `sources` |
| `/api/tools/ID` | Fiche d’outil |
| `/api/sources/ID` | Source et preuves |
| `/api/context/ID` | Contexte Markdown d’un outil |
| `/download/tool/ID.md` | Export d’un outil |
| `/download/source/ID.md` | Export d’une source |
| `/assets/…` | Médias/images figurant dans la liste autorisée du catalogue |

Pages, API et médias sont protégés ensemble par HTTP Basic si configuré. Les fichiers `.env`, réponses API brutes, modèles et scripts ne sont pas servis. Le catalogue JSON est rechargé quand sa génération, sa date ou sa taille change. Une requête utilise une seule génération pour ses données et fichiers ; les preuves des anciennes versions restent accessibles depuis les fiches qui les citent. Les écritures de JSON utilisent un remplacement atomique. La consultation n’effectue aucune modification de favoris ou de fiches ; seul le worker écrit les résultats dans le volume partagé.

Les requêtes `HEAD` et `Range` permettent la navigation vidéo. Le reverse proxy doit conserver ces en-têtes, le statut 206 et l’en-tête `Authorization`. Le serveur est prévu pour un usage personnel derrière un reverse proxy, avec un compte partagé configuré dans `.env` ; il n’a pas de gestion multi-utilisateur ni d’éditeur intégré.
