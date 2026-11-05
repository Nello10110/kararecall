# Mémoire — second cerveau personnel

Une interface web pour retrouver les découvertes enregistrées dans Karakeep, consulter leurs preuves et repartir avec une fiche utile : **description de l’outil, usages, fonctionnement, limites et liens pour approfondir**.

Le NAS conserve les données et sert l’interface. Un travailleur optionnel synchronise Karakeep en lecture seule, extrait les médias et appelle les services IA configurés. Les modèles tournent sur une autre machine ou chez un fournisseur API : aucun gros modèle n’est chargé sur le NAS.

## Démarrer avec Docker Compose

Prérequis : Docker avec Compose v2, accès GitHub au dépôt privé. Depuis le homelab :

```sh
git clone https://github.com/Nello10110/second-cerveau.git
cd second-cerveau
python3 scripts/setup_env.py
# Consulter .env pour les identifiants et ajuster la configuration.
docker compose up -d --build
```

Sans Python sur l’hôte : copier `.env.example` vers `.env` et remplacer impérativement le mot de passe d’exemple. Le script génère un mot de passe aléatoire, protège le fichier en lecture/écriture propriétaire et refuse de remplacer une configuration existante.

Ouvrir [http://127.0.0.1:8765](http://127.0.0.1:8765) avec les identifiants de `.env`. Sur le réseau local du NAS, définir `MEMOIRE_BIND_ADDRESS=0.0.0.0`, recréer le service et ouvrir `http://IP_DU_NAS:8765`. Pour un accès internet, utiliser le reverse proxy HTTPS du homelab ou un VPN. L’authentification est HTTP Basic ; elle doit être transportée en HTTPS hors d’un environnement de confiance.

**Une nouvelle installation démarre vide.** Les favoris, vidéos, notes et clés du POC ne sont pas inclus dans Git ni dans les images. Les données persistent dans le volume Docker `memoire-storage`, indépendamment des conteneurs. Le [guide homelab](docs/HOMELAB.md) explique aussi comment importer un corpus local existant.

## Activer la collecte et les fiches IA

Tout se règle dans `.env`. Exemple de configuration, à compléter avec vos propres valeurs :

```dotenv
COMPOSE_PROFILES=automation
SYNC_ENABLED=true
KARAKEEP_BASE_URL=https://karakeep.exemple.fr
KARAKEEP_API_KEY=VOTRE_CLE

LLM_ENABLED=true
LLM_BASE_URL=http://IP_DU_MAC:11434/v1
LLM_MODEL=NOM_DU_MODELE_INSTALLE
LLM_API_KEY=
```

Créer la clé Karakeep dans ses paramètres API. Le serveur LLM doit exposer `chat/completions` compatible OpenAI et produire du JSON. L’exemple utilise un Ollama déjà installé et joignable sur le Mac ; une API distante compatible peut être configurée avec sa propre URL, clé et modèle. `localhost` dans le conteneur désigne le conteneur, pas le Mac.

Pour analyser les vidéos, configurer aussi :

- `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_MODEL` : transcription via `audio/transcriptions`, multipart et `verbose_json`.
- `VISION_BASE_URL`, `VISION_API_KEY`, `VISION_MODEL` : lecture du texte des captures via `chat/completions` multimodal. URL et clé vides héritent de celles du LLM ; le modèle reste explicite.

Ces services sont indépendants et facultatifs. Un modèle ASR ou vision vide désactive l’étape et aucun audio/image n’est envoyé à ce service. Sans ces étapes, une fiche peut être produite depuis la légende et le texte de page ; elle ne constitue pas une analyse vidéo. L’ASR doit prendre en charge le contrat `verbose_json` : la seule compatibilité texte avec OpenAI ne suffit pas.

```sh
# Vérifier les adresses, l’authentification et les modèles annoncés.
docker compose --profile automation run --rm worker python worker.py check
# Construire puis lancer la consultation et la boucle automatique.
docker compose up -d --build
docker compose logs --tail=50 worker
```

Le contrôle de connexion ne lance pas d’inférence. Les premières analyses permettront de vérifier la compatibilité réelle du modèle et de son JSON. Le worker démarre immédiatement, puis repasse toutes les 15 minutes, trois sources par passage par défaut. Les erreurs sont réessayées avec délai croissant ; les résultats déjà traités sont réutilisés. Aucune tâche Codex n’est nécessaire.

## Consulter et poursuivre

Recherche par souvenir, bibliothèque d’outils, sources originales, transcription et captures horodatées, lecture vidéo à l’instant cité, suivi des traitements et exports Markdown. Le bouton de contexte prépare un texte à copier dans un assistant, avec les explications, liens et preuves. Il n’appelle pas lui-même de service IA.

Les fiches générées automatiquement portent **À relire**. Leurs propos sont attribués aux sources. Les liens relevés restent non vérifiés ; une vérification documentaire exige une trace externe explicite. La recherche est lexicale, avec normalisation des accents et rapprochement orthographique, sans embeddings.

## Architecture et stockage

```text
Navigateur → web (Python + HTML/CSS/JS) → catalogue, médias, Markdown
                                         ↑
Karakeep (GET uniquement) → worker → volume persistant
                              ↕
                 LLM / transcription / vision configurés
```

`data/sources.json`, `data/entities.json`, réponses brutes, médias et extractions constituent le corpus portable. `vault/` contient les fiches Markdown générées et `data/catalog.json` le catalogue. SQLite sert aux tâches et à un index régénérable. La consultation fonctionne sans IA ni accès internet une fois les données présentes. AFFiNE et Wiki.js restent utilisables pour les notes personnelles ou des copies Markdown ; aucun connecteur vers eux n’est implémenté.

Le web est limité à 384 Mio et le worker à 768 Mio avec traitement séquentiel. Ces limites ne couvrent pas le serveur de modèles extérieur. [Exploitation, sauvegarde, mise à jour et paramètres](docs/HOMELAB.md) · [Interface et API de lecture](docs/WEB.md).

## Développement et validation

Python 3.12 est utilisé dans les images. Le cœur et les tests HTTP n’ont aucune dépendance tierce :

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_container.py
docker build --target worker -t memoire-worker:local .
docker run --rm --mount "type=bind,src=$PWD/tests,dst=/tests,readonly" -e PYTHONPATH=/app memoire-worker:local python -m unittest discover -s /tests -p test_media_worker.py -v
```

Les tests distribués utilisent un corpus fictif, des API locales simulées et une petite vidéo synthétique. Ils couvrent la pagination, la déduplication, les références inventées, les reprises sur erreur, l’authentification, les chemins autorisés, les exports, les requêtes vidéo partielles et les étapes ASR/vision. La CI reproduit ces contrôles sur Linux. Le test Compose crée puis supprime son propre volume temporaire.

Les scripts historiques `scripts/process.py`, `transcribe.py`, `frames.py` et `ocr.swift` permettent toujours un traitement local sur macOS avec `requirements.txt` ; ils ne sont pas utilisés par le worker Docker. Les lanceurs `.command` démarrent la consultation locale depuis ce dossier.

**Limites connues :** aucune connexion réelle à vos futurs endpoints ni aucun déploiement sur le NAS n’a encore été validé. Les vidéos sont limitées à 100 Mio et 300 secondes par défaut ; la vision échantillonne au plus 12 images et peut manquer un texte bref. Les modèles peuvent se tromper et les références valides ne garantissent pas l’exactitude d’une reformulation. Les suppressions Karakeep ne sont pas répercutées localement. Un remplacement de pièce jointe déjà conservée est bloqué pour préserver ses preuves et demande une intervention. Il n’y a pas encore d’éditeur de fiches dans le navigateur.

Documentation des contrats utilisés : [API Karakeep](https://github.com/karakeep-app/karakeep/blob/main/packages/open-api/karakeep-openapi-spec.json), [compatibilité OpenAI d’Ollama](https://docs.ollama.com/api/openai-compatibility), [transcription audio](https://platform.openai.com/docs/guides/speech-to-text), [variables Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
