# Organisation du dépôt

[🇫🇷 Français](STRUCTURE.md) · [🇬🇧 English](en/repository.md)

La racine contient les points d’entrée du projet : `README.md`, `AGENTS.md`, `compose.yaml`, `Dockerfile` et le modèle privé de configuration `.env.example`. Le code, les dépendances et les guides ont leurs dossiers.

```text
kararecall/
├── README.md                 Présentation et sélecteur de langue
├── compose.yaml              Déploiement avec les images publiées
├── Dockerfile                Construction des images
├── kararecall/               Paquet Python : cœur, web, worker, modèles, preuves
├── web/                      Interface HTML / CSS / JavaScript
├── requirements/             Dépendances worker, MCP et traitement macOS
├── deploy/                   Surcharge Compose de développement
├── scripts/                  Installation, diagnostics et vérifications
│   └── macos/                Lanceurs Finder
├── docs/                     Guides français et backlog
│   ├── en/                   Guides anglais et présentation anglaise
│   └── assets/               Schémas fonctionnels dans les deux langues
├── tests/                    Tests Python et données fictives
├── tests_js/                 Tests des composants de l’interface
└── benchmarks/               Référence de recherche fictive
```

Les dossiers privés `data/`, `vault/`, les sauvegardes, les modèles, les captures du POC et les fichiers `.env` restent exclus du dépôt. Ils ne sont pas déplacés par cette réorganisation. Le volume Docker et ses chemins `/workspace/data` et `/workspace/vault` restent identiques.

## Commandes à utiliser depuis la racine

```sh
python3 -m kararecall search "mon souvenir" --json
python3 -m kararecall.web_server --open-browser
python3 -m kararecall.worker check
python3 -m kararecall.recovery
python3 scripts/setup_env.py --profile deepseek
PYTHONPYCACHEPREFIX=.build/pycache python3 -m unittest discover -s tests -v
```

Les imports internes utilisent le paquet `kararecall`. Le cœur portable se trouve dans `kararecall/core.py`. Aucun `PYTHONPATH` personnalisé n’est nécessaire depuis la racine, ni dans les images Docker. Les valeurs par défaut de la bibliothèque et du `.env` visent toujours la racine du projet ; `KARARECALL_ROOT` permet de choisir un autre volume.

## Dépendances et construction locale

| Besoin | Fichier |
|---|---|
| Worker Docker | `requirements/worker.txt` |
| Adaptateur MCP | `requirements/mcp.txt` |
| Scripts historiques macOS | `requirements/macos.txt` |
| Versions relevées sur le POC macOS | `requirements/macos.lock.txt` |

Le serveur web et le cœur de consultation restent utilisables avec la bibliothèque standard. Les fichiers macOS ne sont pas les dépendances du worker Docker.

```sh
docker compose -f compose.yaml -f deploy/compose.build.yaml up -d --build
```

Garder `compose.yaml` en premier : les chemins du projet sont résolus depuis sa racine. Le test `scripts/check_container.py` utilise aussi cette surcharge.

## Migration des anciennes commandes

Le déploiement standard garde les mêmes services, `.env`, ports, volume et API. À partir de la version 0.6.1, les images acceptent aussi les anciens chemins `/app/worker.py` et `/app/web_server.py`. Pour un Compose personnalisé, laisser les images choisir leur commande de démarrage. Si une commande personnalisée est nécessaire, utiliser `python -m kararecall.worker` ou `python -m kararecall.web_server` avec les arguments voulus.

Les commandes de diagnostic deviennent `python scripts/pilot.py` et `python scripts/verify_storage.py`. Les lanceurs Finder sont dans `scripts/macos/` et reviennent automatiquement à la racine. Le client MCP utilise le chemin absolu de `scripts/assistant_mcp.py`, afin de fonctionner depuis n’importe quel répertoire de travail.

## Documentation bilingue

Chaque guide public possède un équivalent dans `docs/en/`, avec un lien 🇫🇷 / 🇬🇧 en tête. La [présentation anglaise](en/README.md) oriente vers tous les guides anglais. `scripts/check_docs.py` vérifie les correspondances, les liens locaux, les ancres et les compteurs de tâches restantes des deux backlogs. L’interface et les synthèses restent en français ; ce sélecteur change uniquement la documentation.
