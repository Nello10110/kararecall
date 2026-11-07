# KaraRecall

KaraRecall est une application à héberger chez toi pour retrouver, résumer et explorer tes favoris Karakeep. Elle conserve les textes et preuves disponibles, ainsi que des fiches avec la description des outils, leurs usages, leur fonctionnement et des liens pour approfondir.

Le manuel couvre la configuration du NAS, le premier import et l’activation de DeepSeek. Il inclut une méthode sans Python installé sur le NAS. **[Manuel d’installation](docs/INSTALLATION.md)**.

Pour transférer une installation sous l’ancien nom et conserver son historique, suis la [migration vers KaraRecall](docs/HOMELAB.md#passer-à-kararecall).

Les évolutions à discuter et les travaux restants sont dans le [backlog](backlog.md), avec un ordre de réalisation proposé et des critères vérifiables.

Le [document d’architecture](docs/ARCHITECTURE.md) décrit le fonctionnement global, le rôle de chaque modèle, les options locales et les raccordements encore à réaliser.

Le [guide du pilote](docs/PILOTE.md) permet de vérifier l’installation sur le NAS. Les décisions de stockage, de mise à jour et d’export sont dans le [guide d’exploitation à long terme](docs/EXPLOITATION-LONG-TERME.md).

L’[étude pour l’usage quotidien](docs/ETUDE-EXPLOITATION.md) compare les options et les coûts. Le [socle P0](docs/P0.md) implémente maintenant les générations cohérentes, preuves versionnées, reprises et budgets. La qualification des API réelles et du NAS reste à effectuer.

Le NAS conserve les données et sert l’interface. Un travailleur optionnel synchronise Karakeep en lecture seule, extrait les médias et appelle les services IA configurés. Les modèles tournent sur une autre machine ou chez un fournisseur API : aucun gros modèle n’est chargé sur le NAS.

## Démarrage rapide

Avec Docker Compose v2 et un accès au dépôt GitHub privé, lance ces commandes depuis le dossier de tes applications sur le NAS.

```sh
git clone https://github.com/Nello10110/kararecall.git
cd kararecall
python3 scripts/setup_env.py --profile deepseek
```

Ouvre `.env` et complète les lignes `KARAKEEP_BASE_URL` et `KARAKEEP_API_KEY`. Mets `COMPOSE_PROFILES=automation` pour démarrer le worker et `KARARECALL_BIND_ADDRESS=0.0.0.0` pour accéder à l’interface depuis le réseau du NAS. Conserve `SYNC_ENABLED=false` et `LLM_ENABLED=false` pour le premier import. Les filtres URL/tags restent vides afin de prendre tous les favoris.

```sh
docker compose up -d --build
```

Ouvre **`http://IP_DU_NAS:8765`** avec `KARARECALL_USERNAME` et `KARARECALL_PASSWORD` indiqués dans `.env`, puis clique sur **Traitements → Importer tout l’historique**. Sur le Mac, garder l’écoute `127.0.0.1` et ouvrir [http://127.0.0.1:8765](http://127.0.0.1:8765).

Les commandes pour un NAS sans Python et le premier essai DeepSeek figurent dans le manuel. Pour un accès distant, utilise un VPN ou le [reverse proxy HTTPS du homelab](docs/HOMELAB.md#réseau).

**Une nouvelle installation démarre vide.** Les favoris, vidéos, notes et clés du POC ne sont pas inclus dans Git ni dans les images. Les données persistent dans le volume Docker `kararecall-storage`, indépendamment des conteneurs. Le [guide homelab](docs/HOMELAB.md) explique aussi comment importer un corpus local existant.

## Activer la collecte et les fiches IA

Le profil recommandé prépare DeepSeek `deepseek-flash` pour les captures et la synthèse. La transcription audio reste à configurer séparément. Aucun compte ni clé n’est fourni ; aucun appel n’est activé par la création du fichier. Le [guide import et DeepSeek](docs/IMPORT-ET-DEEPSEEK.md) précise les capacités, limites et coûts. Le profil alternatif `--profile api` reste disponible.

Dans `.env`, renseigner `KARAKEEP_BASE_URL`, `KARAKEEP_API_KEY` et la clé DeepSeek dans `LLM_API_KEY`. La vision hérite de la clé LLM si `VISION_API_KEY` est vide. **Tous les favoris sont collectés par défaut**, y compris sites, articles, notes, fichiers et favoris archivés. Garder `KARAKEEP_URL_FILTER=` et `KARAKEEP_TAG_FILTER=` pour conserver ce périmètre ; corriger un ancien `.env` limité à Instagram.

Dans **Traitements**, le bouton **Importer tout l’historique** demande au worker de récupérer le catalogue complet, sans appel IA ni téléchargement média. Le worker doit être démarré avec ses accès Karakeep ; la synchronisation périodique peut rester désactivée pour cet import. Les analyses suivront ensuite par lots avec les étapes et le budget configurés.

Le [guide P0](docs/P0.md) donne le premier passage manuel puis l’activation de `SYNC_ENABLED=true`, `LLM_ENABLED=true` et du profil Compose `automation`. Commencer avec `WORKER_BATCH_SIZE=1`, contrôler les preuves, puis démarrer la boucle. `ASR_MODEL` et `VISION_MODEL` vides désactivent leurs étapes.

Ces services sont indépendants et facultatifs. Un modèle ASR ou vision vide désactive l’étape et aucun audio/image n’est envoyé à ce service. Sans ces étapes, une fiche peut être produite depuis la légende et le texte de page ; elle ne constitue pas une analyse vidéo. L’ASR doit prendre en charge le contrat `verbose_json` : la seule compatibilité texte avec OpenAI ne suffit pas.

```sh
# Vérifier les adresses, l’authentification et les modèles annoncés.
docker compose --profile automation run --rm worker python worker.py check
# Construire puis lancer la consultation et la boucle automatique.
docker compose up -d --build
docker compose logs --tail=50 worker
```

Le contrôle de connexion ne lance pas d’inférence. Les premières analyses permettront de vérifier la compatibilité réelle du modèle et de son JSON. Le worker démarre immédiatement, puis repasse toutes les 15 minutes, trois sources par passage par défaut. Les erreurs sont réessayées avec délai croissant, trois tentatives au maximum par configuration ; les résultats déjà traités sont réutilisés. Aucune tâche Codex n’est nécessaire.

## Consulter et poursuivre

Recherche par souvenir, bibliothèque d’outils, sources originales, transcription et captures horodatées, lecture vidéo à l’instant cité, suivi des traitements et exports Markdown. Le bouton de contexte prépare un texte à copier dans un assistant, avec les explications, liens et preuves. Il n’appelle pas lui-même de service IA.

Chaque favori peut recevoir un résumé de lecture sourcé ; les articles sans outil identifiable restent des sources avec leur résumé et ne sont pas transformés en faux outils. Lors d’un traitement, KaraRecall conserve les PDF et images sans texte fourni par Karakeep. Le texte des PDF est extrait localement, page par page. Pour les images, `IMAGE_OCR_ENABLED=true` active la lecture par le service vision configuré. [Paramètres et limites](docs/HOMELAB.md#pdf-et-images).

Les fiches générées automatiquement portent **À relire**. Leurs propos sont attribués aux sources. Les liens relevés restent non vérifiés ; une vérification documentaire exige une trace externe explicite. La recherche est lexicale, avec normalisation des accents et rapprochement orthographique, sans embeddings.

## Veille hebdomadaire et mensuelle

L’onglet **Veille** présente de véritables articles rédigés à partir des favoris et de leurs preuves, avec les captures disponibles. Le worker produit une première sélection de l’historique, puis les éditions hebdomadaires et mensuelles. La rédaction et la diffusion fonctionnent automatiquement après raccordement du modèle et du canal d’envoi dans `.env`. Les exports HTML/Markdown, le PDF via impression et le RSS privé restent disponibles. [Guide des bulletins](docs/VEILLE.md).

## Architecture et stockage

```text
Navigateur → web (Python + HTML/CSS/JS) → catalogue, médias, Markdown
                                         ↑
Karakeep (GET uniquement) → worker → volume persistant
                              ↕
                 LLM / transcription / vision configurés
```

Les réponses brutes, médias, extractions et JSON de sources/fiches constituent le corpus portable. Après publication, `data/current.json` sélectionne une génération complète sous `data/generations/…` ; les chemins du catalogue sont relatifs à cette génération et les anciennes preuves restent conservées. `vault/` contient les fiches Markdown générées et `data/catalog.json` le catalogue. SQLite conserve les tâches et le journal d’usage, ainsi qu’un index régénérable. La consultation fonctionne sans IA ni accès internet une fois les données présentes. AFFiNE et Wiki.js restent utilisables pour les notes personnelles ou des copies Markdown ; aucun connecteur vers eux n’est implémenté.

Le web est limité à 384 Mio et le worker à 768 Mio avec traitement séquentiel. Ces limites ne couvrent pas le serveur de modèles extérieur. [Exploitation, sauvegarde, mise à jour et paramètres](docs/HOMELAB.md) · [Interface et API de lecture](docs/WEB.md).

## Développement et validation

Python 3.12 est utilisé dans les images. Le cœur et les tests HTTP n’ont aucune dépendance tierce :

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_container.py
docker build --target worker -t kararecall-worker:local .
docker run --rm --mount "type=bind,src=$PWD/tests,dst=/tests,readonly" -e PYTHONPATH=/app kararecall-worker:local python -m unittest discover -s /tests -p test_media_worker.py -v
```

Les tests distribués utilisent un corpus fictif, des API locales simulées et une petite vidéo synthétique. Ils couvrent la pagination, la déduplication, les références inventées, les reprises sur erreur, l’authentification, les chemins autorisés, les exports, les requêtes vidéo partielles et les étapes ASR/vision. La CI reproduit ces contrôles sur Linux, y compris sauvegarde/restauration sur un volume neuf. Le test Compose crée puis supprime son propre volume temporaire.

Les scripts historiques `scripts/process.py`, `transcribe.py`, `frames.py` et `ocr.swift` permettent toujours un traitement local sur macOS avec `requirements.txt` ; ils ne sont pas utilisés par le worker Docker. Les lanceurs `.command` démarrent la consultation locale depuis ce dossier.

Les fiches sont modifiables et regroupables depuis le navigateur. Un assistant compatible peut lire la bibliothèque via l’adaptateur local. [Guide MCP](docs/MCP.md).

La recherche web par outil s’active dans le worker. Les résultats et les pages consultées sont présentés séparément des preuves de la fiche. [Configuration et coût](docs/RECHERCHE-WEB.md).

**Limites connues :** aucune connexion réelle à vos futurs endpoints ni aucun déploiement sur le NAS n’a encore été validé. Les vidéos sont limitées à 100 Mio et 300 secondes par défaut ; la vision échantillonne au plus 12 images et peut manquer un texte bref. Les modèles peuvent se tromper et les références valides ne garantissent pas l’exactitude d’une reformulation. Le budget comptable par défaut est de 2 USD/mois ; les tarifs et usages estimés ne remplacent pas la facture fournisseur. Les suppressions Karakeep ne sont pas répercutées localement. Un remplacement de pièce jointe vidéo déjà conservée est bloqué pour préserver ses preuves et demande une intervention.

Documentation des contrats utilisés : [API Karakeep](https://github.com/karakeep-app/karakeep/blob/main/packages/open-api/karakeep-openapi-spec.json), [compatibilité OpenAI d’Ollama](https://docs.ollama.com/api/openai-compatibility), [transcription audio](https://platform.openai.com/docs/guides/speech-to-text), [variables Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
