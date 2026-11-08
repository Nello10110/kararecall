# Utiliser KaraRecall depuis un assistant

[🇫🇷 Français](MCP.md) · [🇬🇧 English](en/mcp.md)

L’adaptateur MCP s’exécute sur le poste de l’assistant. Il lit l’API web de KaraRecall et reprend ses identifiants. Il ouvre cinq outils, pour rechercher des favoris, lire une fiche, parcourir une source, consulter une preuve précise et récupérer le contexte Markdown. Les résultats donnent les références `ID_FAVORI#ID_PREUVE`, les URL originales et, selon la source, la page ou l’horodatage.

## Démarrage

Sur le poste où tourne l’assistant, avec Python 3.10 ou plus récent et un clone du dépôt :

```sh
python3 -m venv .venv-mcp
.venv-mcp/bin/python -m pip install -r requirements/mcp.txt
```

Crée `.env.mcp` dans le dossier du projet et protège ce fichier avec `chmod 600 .env.mcp`. Les exemples ci-dessous utilisent des valeurs à remplacer.

```dotenv
KARARECALL_URL=https://kararecall.example.net
KARARECALL_USERNAME=admin
KARARECALL_PASSWORD=REMPLACER_PAR_LE_MOT_DE_PASSE_WEB
```

Utilise l’adresse de KaraRecall accessible depuis ce poste, via HTTPS ou ton réseau privé. Un essai sur le même ordinateur peut utiliser `http://127.0.0.1:8765`. L’authentification reprend les identifiants de l’interface.

Dans un client compatible avec les serveurs MCP locaux, choisis le transport **stdio**. Configure la commande avec le chemin absolu de `.venv-mcp/bin/python` et un argument contenant le chemin absolu de `scripts/assistant_mcp.py`. Le client démarre lui-même le processus et communique avec lui par son entrée et sa sortie standard. [Transport stdio du SDK MCP](https://py.sdk.modelcontextprotocol.io/run/).

Autre possibilité, construire l’image dédiée sur le poste et utiliser `docker` comme commande du client MCP.

```sh
docker build --target mcp -t kararecall-mcp:local .
```

Fournir les arguments `run --rm -i --env-file /chemin/absolu/.env.mcp kararecall-mcp:local`. Utiliser une adresse KaraRecall joignable depuis le conteneur. `127.0.0.1` désigne alors le conteneur de l’adaptateur.

## Choix du transport

Stdio convient à un assistant local et réutilise l’accès HTTP existant au NAS. L’adaptateur transmet uniquement des requêtes GET et refuse les redirections. Les commandes d’import, d’édition et d’exécution de programmes sont hors de ses outils. Les sorties sont bornées et la pagination est disponible pour les preuves et le contexte.

Un client qui accepte uniquement un serveur MCP distant demanderait un service Streamable HTTP avec authentification adaptée. Cette option devient utile si l’assistant ne sait pas démarrer un processus local. [Comparaison des transports](https://py.sdk.modelcontextprotocol.io/run/).

## Essai

Demande à l’assistant de retrouver un outil en décrivant un usage. Vérifie qu’il cite l’URL d’origine et une preuve. Demande ensuite le passage exact puis une information absente. Le test d’intégration couvre le dialogue stdio, l’accès authentifié, la preuve horodatée, les limites de sortie et l’abstention sur le corpus fictif. Le client vocal réellement utilisé reste à qualifier.
