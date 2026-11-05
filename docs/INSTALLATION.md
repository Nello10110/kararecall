# Installer KaraRecall sur son NAS

Ce guide mène jusqu’à la consultation de tous les favoris Karakeep. La première installation importe les textes et métadonnées avec l’IA désactivée. Les résumés DeepSeek s’activent ensuite, à l’étape 6.

## Avant de commencer

- Docker avec Compose v2 fonctionne sur le NAS.
- Tu disposes d’un accès au dépôt GitHub privé, de l’adresse de Karakeep et de sa clé API.
- Prépare ta clé DeepSeek si tu veux activer les résumés à l’étape 6.

Les commandes se lancent dans le terminal du NAS, par exemple en SSH. Pour essayer sur le Mac avec OrbStack, les mêmes commandes conviennent.

## 1. Récupérer l’application

Lance ces commandes depuis le dossier du NAS où tu ranges tes applications.

```sh
git clone https://github.com/Nello10110/kararecall.git
cd kararecall
```

L’accès Git au dépôt privé doit être configuré sur cette machine. Si tu utilises une clé SSH GitHub, remplace l’adresse HTTPS par `git@github.com:Nello10110/kararecall.git`.

**Si ton NAS n’a pas Git**, télécharge le ZIP du dépôt depuis ton compte GitHub, décompresse-le sur le NAS, puis ouvre un terminal dans ce dossier. Conserve les fichiers cachés, notamment `.env.example` et `.dockerignore`.

Si KaraRecall est déjà installé, conserve son `.env` et suis la procédure de [mise à jour](#mise-à-jour).

Si ta configuration utilise encore les anciens noms, suis d’abord la [migration vers KaraRecall](HOMELAB.md#passer-à-kararecall).

## 2. Créer la configuration

Avec Python 3, lance cette commande.

```sh
python3 scripts/setup_env.py --profile deepseek
```

**Sans Python sur le NAS**, lance la commande Docker suivante.

```sh
docker run --rm --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD,dst=/app" --workdir /app \
  python:3.12-slim python scripts/setup_env.py --profile deepseek
```

Le script crée **`.env`** avec un mot de passe web aléatoire et les réglages DeepSeek. Il conserve un fichier existant. Docker télécharge l’image Python si nécessaire.

## 3. Renseigner les accès

Ouvre `.env` dans ton éditeur habituel ou avec `nano .env`. **Modifie les quatre lignes existantes** ci-dessous.

```dotenv
COMPOSE_PROFILES=automation
KARARECALL_BIND_ADDRESS=0.0.0.0
KARAKEEP_BASE_URL='https://karakeep.example.net'
KARAKEEP_API_KEY='REMPLACER_PAR_TA_CLE_KARAKEEP'
```

Remplace l’adresse d’exemple par celle de **ton** Karakeep, accessible depuis le NAS. Utilise son adresse réseau ou son nom DNS. `localhost` désigne le conteneur de KaraRecall. Renseigne l’adresse de base du serveur.

Conserve les valeurs suivantes pour le premier import.

```dotenv
SYNC_ENABLED=false
LLM_ENABLED=false
KARAKEEP_URL_FILTER=
KARAKEEP_TAG_FILTER=
```

Les deux filtres vides incluent les sites, articles, notes, fichiers et vidéos. `automation` démarre le service de collecte. Avec `SYNC_ENABLED=false`, le service attend la demande d’import.

Tes identifiants pour l’interface figurent dans **`KARARECALL_USERNAME`** et **`KARARECALL_PASSWORD`**. Le mot de passe généré peut être conservé. Les clés restent dans `.env` sur le NAS, hors du dépôt Git.

L’adresse d’écoute `0.0.0.0` permet l’accès depuis ton réseau domestique. Pour un essai limité au Mac lui-même, garde `127.0.0.1`. Pour un accès distant, utilise ton VPN ou le [reverse proxy HTTPS du homelab](HOMELAB.md#réseau).

## 4. Démarrer

```sh
docker compose up -d --build
docker compose ps
```

Le premier démarrage construit les images et peut prendre quelques minutes. Vérifie que les services **web** et **worker** sont démarrés et que le web passe à `healthy`.

Depuis ton navigateur, ouvre **`http://IP_DU_NAS:8765`**, en remplaçant `IP_DU_NAS` par son adresse locale. Pour un essai sur le Mac, ouvre [http://127.0.0.1:8765](http://127.0.0.1:8765).

Connecte-toi avec les identifiants de `.env`. La bibliothèque démarre vide.

## 5. Importer tous tes favoris

Dans **Traitements**, clique sur **Importer tout l’historique**.

Attends le message indiquant le nombre de favoris pris en compte, puis ouvre **Sources** ou **Recherche**. Les textes fournis par Karakeep sont consultables et recherchables immédiatement. Relancer l’import met à jour chaque entrée portant le même identifiant Karakeep.

Le bouton importe le catalogue et les textes disponibles. À ce stade, les PDF et images sans texte fourni par Karakeep apparaissent avec l’état **Métadonnées seulement**. Le traitement des fichiers se configure ensuite. [PDF et images](HOMELAB.md#pdf-et-images).

## 6. Activer DeepSeek et les mises à jour automatiques

Arrête d’abord le service de collecte pour faire un essai sur un seul favori.

```sh
docker compose stop worker
```

Modifie les lignes suivantes dans `.env`.

```dotenv
LLM_API_KEY='REMPLACER_PAR_TA_CLE_DEEPSEEK'
LLM_ENABLED=true
SYNC_ENABLED=true
WORKER_BATCH_SIZE=1
```

Conserve les adresses, modèles et tarifs préparés par le profil. Il prévoit la synthèse de texte et la lecture de captures avec DeepSeek. La vision utilise la même clé si `VISION_API_KEY` est vide. **Les analyses utilisent des appels facturables**. Le budget comptable est de 2 USD/mois par défaut.

Pour commencer par les seuls textes, vide `VISION_MODEL` et mets `DOWNLOAD_MEDIA=false` avant cet essai. Tu pourras réactiver les captures ensuite avec `VISION_MODEL=deepseek-flash` et `DOWNLOAD_MEDIA=true`. La transcription des paroles passe par un service audio à configurer séparément. [Options audio et limites](IMPORT-ET-DEEPSEEK.md#préparer-deepseek).

Vérifie les accès, puis lance un passage sur au plus un favori.

```sh
docker compose run --rm --no-deps worker python worker.py check &&
  docker compose run --rm --no-deps worker python worker.py once
```

`check` vérifie les accès en lecture. `once` exécute les étapes activées. Si une commande indique une erreur, consulte le dépannage ci-dessous avant de poursuivre. Dans le navigateur, clique sur **Actualiser** dans Traitements et contrôle le résumé, ses preuves et les éventuels états d’erreur.

Quand ce premier résultat te convient, démarre la boucle.

```sh
docker compose up -d worker
```

Le service passe immédiatement, puis toutes les quinze minutes. Il traite au plus un favori par passage avec ce réglage. Pour passer à trois, change `WORKER_BATCH_SIZE` dans `.env`, puis relance la même commande. Les traitements réussis inchangés sont réutilisés. Tu peux suivre la progression de l’historique et les quotas dans Traitements.

## Dépannage rapide

| Symptôme | À vérifier |
|---|---|
| Impossible de cloner le dépôt | Configure l’accès Git au dépôt privé sur le NAS ou utilise la méthode ZIP de l’étape 1. |
| `.env existe déjà` | Ouvre le fichier existant et complète-le à partir de l’étape 3. |
| Page inaccessible | Remplacer `IP_DU_NAS`, vérifier `KARARECALL_BIND_ADDRESS=0.0.0.0`, le pare-feu local et `docker compose ps`. |
| Port 8765 déjà utilisé | Mettre `KARARECALL_PORT=8766` dans `.env`, relancer `docker compose up -d`, puis ouvrir ce nouveau port. |
| Import bloqué « En attente » | Vérifier `COMPOSE_PROFILES=automation` et la présence du service worker dans `docker compose ps`. |
| Erreur Karakeep ou HTTP 401/403 | Vérifier l’adresse accessible depuis le conteneur et la clé dans `.env`. |
| Erreur IA | Vérifier la clé DeepSeek, le modèle et le crédit du compte. Consulter l’état dans Traitements. |
| Budget/quota atteint | Consulter Traitements. Les analyses reprennent quand le quota se renouvelle. |
| Modification de `.env` sans effet | Relancer `docker compose up -d` pour appliquer les paramètres aux services. |

Affiche les derniers messages des services avec cette commande.

```sh
docker compose logs --tail=50 web worker
```

## Mise à jour

Lance ces commandes depuis le dossier cloné avec Git.

```sh
git pull --ff-only
docker compose up -d --build
```

Compare `.env.example` et `.env` pour repérer les nouveaux paramètres. Conserve tes valeurs. Pour une installation par ZIP, remplace le code en conservant ton `.env`, puis reconstruis avec la seconde commande.

Les données restent dans le volume Docker `kararecall-storage`. Sauvegarde le volume et ton `.env` en suivant la [procédure de sauvegarde](HOMELAB.md#sauvegarde-et-restauration). Pour arrêter les services en conservant les données, utilise `docker compose stop`.
