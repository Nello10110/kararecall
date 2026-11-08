# Repository layout and development

[🇫🇷 Français](../STRUCTURE.md) · [🇬🇧 English](repository.md)

The root keeps the project entry points: `README.md`, `AGENTS.md`, `compose.yaml`, `Dockerfile` and `.env.example`. Implementation, dependencies and documentation have dedicated directories.

```text
kararecall/
├── README.md                 French presentation and language selector
├── compose.yaml              Deployment using published images
├── Dockerfile                Image builds
├── kararecall/               Python package: core, HTTP, worker, evidence and integrations
├── web/                      Static HTML / CSS / JavaScript interface
├── requirements/             Worker, MCP and historical macOS dependency lists
├── deploy/                   Development Compose override
├── scripts/                  Setup, diagnostics and verification
│   └── macos/                Finder launchers
├── docs/                     French guides and backlog
│   ├── en/                   English presentation and guides
│   └── assets/               French/English functional diagrams
├── tests/                    Python tests and fictional fixtures
├── tests_js/                 UI component tests
└── benchmarks/               Fictional search reference
```

Private `data/`, `vault/`, model downloads, POC screenshots, backups and `.env` files remain excluded. Reorganization does not move existing data or change `/workspace/data` and `/workspace/vault` in Docker.

## Commands from the repository root

```sh
python3 -m kararecall search "a remembered topic" --json
python3 -m kararecall.web_server --open-browser
python3 -m kararecall.worker check
python3 -m kararecall.recovery
python3 scripts/setup_env.py --profile deepseek
PYTHONPYCACHEPREFIX=.build/pycache python3 -m unittest discover -s tests -v
```

Internal imports use the `kararecall` package. Portable core functions live in `kararecall/core.py`. No custom `PYTHONPATH` is needed from the project root or inside the images. Default data/configuration paths still refer to the project root; `KARARECALL_ROOT` selects another library volume.

## Dependencies and local builds

| Purpose | File |
|---|---|
| Docker worker | `requirements/worker.txt` |
| MCP adapter | `requirements/mcp.txt` |
| Historical macOS processing | `requirements/macos.txt` |
| POC macOS recorded versions | `requirements/macos.lock.txt` |

Core/web consultation uses the standard library. Historical macOS requirements are not the Docker worker requirements.

```sh
docker compose -f compose.yaml -f deploy/compose.build.yaml up -d --build
```

Keep the root `compose.yaml` first so project paths resolve from the root. The disposable container check uses the same override.

## Migrating custom commands

Standard deployment retains services, credentials, ports, volume and API. Updating both images is sufficient. If a personal script/custom Compose overrides container commands, replace `python worker.py` with `python -m kararecall.worker` and `python web_server.py` with `python -m kararecall.web_server`.

Diagnostics use `python scripts/pilot.py` and `python scripts/verify_storage.py`. Finder launchers are under `scripts/macos/` and resolve the root automatically. MCP desktop clients should pass the absolute `scripts/assistant_mcp.py` entry point, which works from any working directory.

## Documentation maintenance

Each public French guide has an English counterpart listed in `docs/languages.json`, with a two-way flag selector. The [English presentation](README.md) links to every English guide. `python3 scripts/check_docs.py` checks counterparts, local targets/anchors and the number of remaining tasks in the two roadmaps. Keep commands, status, limits and language links aligned when changing either edition. The application UI and generated editorial text remain French; this language selector affects documentation only.
