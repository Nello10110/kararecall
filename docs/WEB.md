# Interface et API

L’interface est servie par `web_server.py`, sans compilation ni dépendance tierce. En développement local : `python3 web_server.py --open-browser`, ou le lanceur `Ouvrir KaraRecall.command`. Le serveur écoute sur `127.0.0.1:8765` par défaut. Une configuration `.env` existante est chargée ; sans identifiants, seul le démarrage sur la boucle locale est autorisé. Le [guide homelab](HOMELAB.md) décrit le mode Docker avec authentification obligatoire.

## Parcours

- **Recherche** : mots ou description d’un souvenir, classement lexical, filtres outils/sources.
- **Mes outils** : description, utilité, fonctionnement, limites, liens et preuves. Les synthèses automatiques sont marquées « À relire ».
- **Revue des fiches** : corriger le nom, le résumé, les rubriques et les liens, marquer la fiche comme relue ou regrouper deux fiches du même outil. Les citations existantes et les versions précédentes restent conservées. Une page externe consultée peut recevoir une note attribuée après revue par l’utilisateur.
- **Sources** : favoris conservés localement, texte disponible, état réel des extractions. Les listes Sources et Activité chargent 24 entrées à la fois, avec filtrage avant pagination.
- **Preuves** : recherche et surlignage dans la transcription, captures horodatées et ouverture du passage depuis les résultats globaux. Les preuves de document affichent le numéro de page du PDF ou l’aperçu de l’image.
- **Activité** : présence des médias, transcription/OCR et état du dernier passage du worker. Actualiser le catalogue pour charger les nouveaux résultats. Un bouton permet de demander l’import de tout l’historique ; il ne lance pas d’analyse IA et ne modifie pas Karakeep. La demande est persistée et exécutée par le worker. Les analyses suivent la configuration et les quotas habituels. Elle affiche le budget comptabilisé, les appels, les sources en attente et les étapes en erreur/non applicables, et signale un état de collecte trop ancien.
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

Les requêtes `HEAD` et `Range` permettent la navigation vidéo. Le reverse proxy doit conserver ces en-têtes, le statut 206 et l’en-tête `Authorization`. Le serveur est prévu pour un usage personnel derrière un reverse proxy, avec un compte partagé configuré dans `.env` ; il n’a pas de gestion multi-utilisateur ; l’éditeur de fiches est limité à la revue sourcée.

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

## Résumés français et commandes de traitement

Les sources affichent un titre éditorial français (80 caractères maximum) et un résumé d’une phrase (180 caractères maximum). Une ancienne légende n’est plus utilisée comme grand titre. Tant qu’une source n’a pas été retraitée, un intitulé neutre et l’attente du résumé français sont affichés. Les noms propres des outils sont conservés.

**Résumer / traduire**, disponible sur chaque source et en commande globale dans Activité, travaille sur les preuves déjà conservées. Cette commande ne télécharge pas de média et ne contacte pas Karakeep. Le worker et `LLM_ENABLED=true` restent nécessaires. Les sources en langue étrangère ou mêlant plusieurs langues reçoivent des traductions françaises par extrait, avec les identifiants et les temps des preuves originales. La traduction de documents longs peut demander plusieurs appels ; les morceaux sont mis en cache et la commande reprend après quota. Les textes originaux restent accessibles avec **Afficher les preuves originales**.

Hashtags, appels promotionnels et répétitions publicitaires sont écartés du contexte éditorial, des textes de présentation et des traductions ; les réponses REST et les preuves brutes restent conservées pour permettre de vérifier les citations. La reformulation peut se tromper : elle ne devient pas une preuve brute. Les titres, résumés, rubriques, mots-clés et bulletins sont demandés en français.

**Relancer l’analyse complète** relit Karakeep pour cette source et relance les étapes configurées, dont l’audio et la vision si activés. Cette action peut refaire des appels facturables. Le bouton **Importer tout l’historique** reste un import du catalogue sans IA ni téléchargement de média. Le compteur « sources avec résumé IA » est distinct du compteur de vidéos ayant effectivement une transcription et une analyse d’écran.

**Enrichir la description sur le web**, sur chaque outil, ou la commande globale, demande une recherche DeepSeek Search/Fetch. Le client doit disposer d’une clé de recherche, héritée de `LLM_API_KEY` lorsque le LLM pointe vers DeepSeek, ou fournie par `DEEPSEEK_RESEARCH_API_KEY`. La commande explicite peut fonctionner même avec `WEB_RESEARCH_ENABLED=false` ; ce paramètre contrôle la recherche périodique autonome. Le complément français n’utilise que les pages lues et cite leurs URL. Il ne remplace pas les descriptions sourcées d’origine ni les corrections manuelles, et ne prouve pas les performances annoncées. Une identité ambiguë ne déclenche pas de lecture documentaire attribuée à l’outil.

**Vider la bibliothèque locale** demande de saisir `VIDER`. Le worker publie une génération vide, annule les commandes encore en file et suspend la synchronisation automatique jusqu’au prochain import. Karakeep n’est jamais modifié. Les anciennes générations, les preuves, les bulletins et le journal de facturation restent conservés : ce bouton ne libère pas leur espace disque et ne remet pas le budget à zéro.

`POST /api/actions` reçoit `{ "kind": "llm" | "refresh" | "research" | "clear" }`, avec `source_id` pour une source, `tool_id` pour une recherche d’outil et `confirmation: "VIDER"` pour le vidage. `refresh` exige une source ; `llm` sans source traite un instantané de toutes les sources présentes au moment de la demande. Le même contrôle d’authentification, d’origine et anti-CSRF s’applique. La file durable dans `data/control/actions.json` expose sa progression dans `/api/control` et `/api/catalog`, reprend après redémarrage et respecte les quotas. Un doublon de commande encore active n’est pas ajouté.

### Source partielle et quota IA

Les paroles françaises sont affichées dès qu’elles existent, même si la vision est en pause et qu’aucun résumé IA n’a encore été rédigé. La langue audio est conservée dans les métadonnées de traitement. Pour les anciens catalogues, l’API peut relire la langue de `transcript.json` ou `subtitles.json` sans modifier la génération publiée : elle contrôle le statut et l’empreinte du média. Une détection conservatrice du texte français sert de secours aux anciens enregistrements sans langue. Les traductions restent prioritaires et les originaux restent accessibles ; la langue d’un résumé français n’écrase pas une langue audio étrangère connue. Une traduction réellement manquante produit un seul avis, sans répéter un faux passage à chaque horodatage.

La fiche affiche les états distincts des paroles, de la lecture d’écran et du résumé, le détail du dernier échec et les compteurs d’appels disponibles. Le diagnostic de quota distingue le plafond journalier (renouvellement à minuit UTC), le plafond mensuel d’appels et le budget mensuel insuffisant pour réserver un nouvel appel. Aucune limite n’est augmentée par ce correctif. Un titre français abrégé de la publication peut être utilisé en attendant le titre éditorial : cela ne constitue pas une synthèse de la vidéo.

Le bouton **Réessayer l’analyse de l’écran** transmet `{ "kind": "refresh", "source_id": "ID", "stage": "vision" }` à `/api/actions`. Il cible l’invalidation du cache vision ; les autres extractions valides restent réutilisables. La reprise après quota conserve les images déjà reconnues. L’étape `stage` est validée parmi `all`, `asr`, `vision`, `document`, `llm`, et ne s’applique qu’à `refresh`.

## Espace de travail 0.3

L’accueil devient **Tableau de bord** (`#/dashboard`). La recherche garde `#/search`. **Activité** garde la route historique `#/processing` ; **Administration** est accessible à `#/administration`, avec `tab=connections|usage|storage|automation`. L’[audit d’usage et d’administration](UX-ET-ADMINISTRATION.md) décrit les choix d’écrans, les informations disponibles et leurs limites.

`GET /api/overview` et `GET /api/administration` agrègent le catalogue et les états locaux, sans appeler Karakeep ni un modèle. `GET /api/administration/diagnostic` exporte une projection excluant les contenus et les secrets. `GET /download/catalog.json` exporte le catalogue privé et ses références, sans les médias : il ne s’agit pas d’une sauvegarde complète.

`/api/sources` accepte aussi `type=all|article|video|note|file`, `sort=recent|oldest` et les états `failed|paused|pending|summarized`, filtrés avant pagination. Les états `complete` et `partial` gardent leur sens historique lié aux vidéos.

Les commandes authentifiées et protégées par anti-CSRF ajoutent :

- `POST /api/actions` avec `{ "kind": "check" }` : contrôle de lecture des connexions exécuté par le worker, sans inférence IA ; résultat horodaté dans `data/connection-check.json`.
- `POST /api/actions/ID/cancel` avec `{}` : annule les éléments suivants de la commande. Une opération déjà engagée peut se terminer et publier ses résultats.
- `POST /api/automation` avec `{ "paused": true|false }` : suspend ou reprend les prochains passages automatiques, sans changer les clés, les plafonds ou les options du `.env`. Un passage déjà engagé peut se terminer ; les commandes manuelles restent disponibles.

Les styles sont répartis entre les composants de base (`styles.css`) et le système glass (`glass.css`). `workspace.js` contient les écrans de consultation et d’administration, `app.js` conserve la navigation et les fiches/preuves, et `digests.js` conserve la veille. Le web et le worker embarquent `version.py`. Les deux images doivent être mises à jour ensemble.

Une suspension explicite depuis Administration reste active pendant un import manuel de l’historique. Seule la suspension créée par le vidage local est levée automatiquement au prochain import, conformément à son message de confirmation.

## Lecture des fiches 0.4

Les outils mettent en tête leur nom, une présentation utile et le meilleur lien explicite disponible. Le lien est choisi parmi ceux conservés dans la fiche, sans fabriquer de domaine ni qualifier automatiquement un site d’officiel. Les liens de publication d’origine, réseaux sociaux, adresses avec identifiants et liens signalés en échec ne sont pas utilisés comme destination principale. Une page d’accueil déjà enregistrée comme lien d’outil consulté reste admissible, même si elle est aussi un favori. Un lien relevé mais non vérifié reste présenté comme tel. Le lien est aussi accessible depuis les cartes de la bibliothèque et les résultats de recherche, sans imbriquer les ancres.

L’utilité, le fonctionnement et les limites précèdent les informations de provenance. Une présentation qui se borne à mentionner une vidéo laisse place, lorsqu’il existe, à un texte utile déjà sourcé dans la fiche. Le contenu conservé n’est pas réécrit : la description complète, les repères, les références et les sources restent disponibles dans les volets correspondants. Les références identiques d’une affirmation sont regroupées et les passages restent cliquables. L’attribution reste affichée sous chaque texte ; les hypothèses restent signalées.

**Gérer cette fiche**, replié en bas de page, contient l’éditeur, le regroupement et la recherche web explicite. Les contrôles de révision, l’authentification, l’anti-CSRF et les routes ne changent pas. L’export est regroupé dans un menu natif.

Les sources donnent priorité à la consultation du document ou de la vidéo et à ses preuves. **Gérer cette source** contient les traitements et leur état détaillé ; un échec ou une pause produit un avis compact avec un bouton qui ouvre les détails. Les sources sans vidéo n’affichent plus des étapes audio/écran non pertinentes. Les bulletins présentent l’article avant **Diffusion et édition**, qui conserve les commandes et le suivi d’envoi. Leur préparation automatique ne nécessite pas une composition manuelle.

Les composants de lecture et les liens sont dans `details.js`, leur présentation dans `details.css`. Ils restent servis par la liste statique authentifiée et la politique CSP existante. Les volets et menus utilisent les éléments HTML natifs, avec focus visible et mise en page mobile. Aucun appel IA ou externe n’est ajouté par l’ouverture d’une fiche.
