# Interface et API

L’interface est servie par `web_server.py`, sans compilation ni dépendance tierce. En développement local : `python3 web_server.py --open-browser`, ou le lanceur `Ouvrir KaraRecall.command`. Le serveur écoute sur `127.0.0.1:8765` par défaut. Une configuration `.env` existante est chargée ; sans identifiants, seul le démarrage sur la boucle locale est autorisé. Le [guide homelab](HOMELAB.md) décrit le mode Docker avec authentification obligatoire.

## Parcours

- **Recherche** : mots ou description d’un souvenir, classement lexical, filtres outils/sources.
- **Mes outils** : description, utilité, fonctionnement, limites, liens et preuves. Les synthèses automatiques sont marquées « À relire ».
- **Revue des fiches** : corriger le nom, le résumé, les rubriques et les liens, marquer la fiche comme relue ou regrouper deux fiches du même outil. Les citations existantes et les versions précédentes restent conservées. Une page externe consultée peut recevoir une note attribuée après revue par l’utilisateur.
- **Sources** : favoris conservés localement, texte disponible, état réel des extractions. Les listes Sources et Traitements chargent 24 entrées à la fois, avec filtrage avant pagination.
- **Preuves** : recherche et surlignage dans la transcription, captures horodatées et ouverture du passage depuis les résultats globaux. Les preuves de document affichent le numéro de page du PDF ou l’aperçu de l’image.
- **Traitements** : présence des médias, transcription/OCR et état du dernier passage du worker. Actualiser le catalogue pour charger les nouveaux résultats. Un bouton permet de demander l’import de tout l’historique ; il ne lance pas d’analyse IA et ne modifie pas Karakeep. La demande est persistée et exécutée par le worker. Les analyses suivent la configuration et les quotas habituels. Elle affiche le budget comptabilisé, les appels, les sources en attente et les étapes en erreur/non applicables, et signale un état de collecte trop ancien.
- **Approfondir** : export Markdown ou copie du contexte destiné à un autre assistant ; aucune requête IA n’est lancée par ce bouton. Un champ sélectionnable remplace le presse-papiers si nécessaire.

Le Markdown conserve les liens relatifs du coffre : les fichiers associés sont nécessaires pour consulter les preuves hors de l’application. Le contexte à copier fournit les URL originales et les extraits utiles même sans accès au volume.

Le parcours **Veille** prépare et relit les bulletins avec leurs images et preuves. La première édition historique, la rédaction automatique, la planification, le RSS privé et les canaux de diffusion sont décrits dans le [guide des bulletins](VEILLE.md).

## Routes de lecture

| Route | Résultat |
|---|---|
| `/api/health` | Santé du serveur HTTP |
| `/api/control` | Jeton anti-CSRF de la session web et état de l’import global |
| `/api/catalog` | Outils, sources, compteurs et état public du worker |
| `/api/catalog?compact=1` | Vue utilisée au démarrage, avec les sources récentes et la première source de chaque fiche |
| `/api/sources?limit=24&offset=0&stage=all&q=` | Résumés paginés, ordre antéchronologique, filtre d’état et de titre, auteur ou tag. Maximum 100 par page |
| `/api/search?q=…&scope=all` | Recherche ; scope accepte aussi `tools` ou `sources` |
| `/api/tools/ID` | Fiche d’outil |
| `/api/research/ID` | Trace de recherche web de la fiche, si elle existe |
| `/api/editorial/ID` | Dernière révision de la fiche avec sa version précédente |
| `/api/sources/ID` | Source et preuves |
| `/api/context/ID` | Contexte Markdown d’un outil |
| `/download/tool/ID.md` | Export d’un outil |
| `/download/source/ID.md` | Export d’une source |
| `/download/document/ID/ASSET_ID` | Téléchargement authentifié d’un original associé à une source ou à sa preuve archivée |
| `/assets/…` | Médias/images figurant dans la liste autorisée du catalogue |

Pages, API et médias sont protégés ensemble par HTTP Basic si configuré. Les fichiers `.env`, réponses API brutes, modèles et scripts ne sont pas servis. Le catalogue JSON est rechargé quand sa génération, sa date ou sa taille change. Une requête utilise une seule génération pour ses données et fichiers ; les preuves des anciennes versions restent accessibles depuis les fiches qui les citent. Les écritures de JSON utilisent un remplacement atomique. La revue est enregistrée dans une génération avec le même verrou d’écriture que le worker.

Les commandes administratives exigent la même authentification, une origine autorisée, du JSON et l’en-tête `X-KaraRecall-CSRF` obtenu via `/api/control`.

- `POST /api/import-history` reçoit `{}` dans un corps de 1 Kio maximum. Il enregistre une demande dans `data/control/`.
- `POST /api/tools/ID/edit` vérifie la révision de la fiche, et celle de l’autre fiche en cas de regroupement. La commande conserve les anciennes versions et publie la nouvelle après validation. Les anciens liens des fiches regroupées restent utilisables. Une fiche revue ou corrigée est préservée lors des traitements suivants.

Les requêtes `HEAD` et `Range` permettent la navigation vidéo. Le reverse proxy doit conserver ces en-têtes, le statut 206 et l’en-tête `Authorization`. Le serveur est prévu pour un usage personnel derrière un reverse proxy, avec un compte partagé configuré dans `.env` ; il n’a pas de gestion multi-utilisateur ni d’éditeur intégré.

## Routes des bulletins

Les routes suivantes exigent l’authentification de l’application. Les commandes POST utilisent le même jeton anti-CSRF que la revue des fiches.

| Route | Résultat |
|---|---|
| `GET /api/digests` | Éditions, paramètres publics et état du worker de diffusion |
| `GET /api/digests/ID` | Contenu et révision de l’édition |
| `GET /api/digests/ID/article.html` | Article autonome illustré, imprimable en PDF |
| `GET /api/digests/ID/article.md` | Export texte Markdown |
| `GET /api/digests/feed.xml` | RSS des éditions validées |
| `GET /api/digests/assets/EMPREINTE.png` | Image copiée et contrôlée par empreinte, JPEG également pris en charge |
| `POST /api/digests/generate` | Préparation avec `kind`, date `anchor` facultative et `refresh` explicite pour un brouillon |
| `POST /api/digests/ID/edit` | Relecture avec `revision`, titre, introduction et sélection des entrées |
| `POST /api/digests/ID/approve` | Validation de la révision pour diffusion |
| `POST /api/digests/ID/send` | Demande persistée, exécutée par le worker configuré |
| `POST /api/digests/view` | Ouverture d’une source, conservée si le suivi des consultations est activé |

Les éditions et leur historique sont distincts des générations du catalogue. Une édition contient les extraits de preuves utilisés et ses images copiées. Les opérations sont sérialisées par un verrou dédié. Une édition possède une clé déterministe par rythme et intervalle. Une diffusion possède une clé par canal et destination. Un envoi dont le résultat est incertain demande une vérification auprès du service de diffusion.
