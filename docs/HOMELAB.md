# Déploiement sur le homelab

Pour configurer le NAS et lancer le premier import, suis le [manuel pas à pas](INSTALLATION.md).

Ce guide décrit les commandes disponibles. Le [guide P0](P0.md) détaille le profil API, les limites et les commandes de reprise/vérification. Les preuves sont désormais versionnées et publiées par génération ; la qualification des moteurs réels et du NAS reste à réaliser selon le [backlog](../backlog.md).

## Configuration

Le dépôt privé contient uniquement le code et des tests fictifs. Sur le NAS, cloner le dépôt puis exécuter `python3 scripts/setup_env.py --profile deepseek` ou créer `.env` depuis `.env.example`. Garder ce fichier sur le serveur : Compose transmet explicitement les variables requises à chaque service. Le service web ne reçoit aucune clé Karakeep ou IA.

| Paramètres `.env` | Rôle |
|---|---|
| `KARARECALL_USERNAME`, `KARARECALL_PASSWORD` | Accès web ; mot de passe d’exemple refusé |
| `KARARECALL_BIND_ADDRESS`, `KARARECALL_PORT` | Adresse d’écoute de l’hôte et port ; défaut 127.0.0.1:8765 |
| `KARARECALL_VOLUME_NAME` | Nom du volume persistant, défaut `kararecall-storage` |
| `PUID`, `PGID` | UID/GID de l’utilisateur non privilégié créé dans l’image ; défaut 10001 |
| `COMPOSE_PROFILES=automation` | Active le service worker avec un simple `docker compose up` |
| `SYNC_ENABLED` | Autorise la collecte périodique ; défaut false |
| `KARAKEEP_BASE_URL`, `KARAKEEP_API_KEY` | Adresse Karakeep et clé Bearer ; pas besoin d’ajouter `/api/v1` |
| `KARAKEEP_URL_FILTER` | Sous-chaîne d’URL facultative ; ex. `instagram.com` ; vide = tous les favoris |
| `SYNC_INTERVAL_SECONDS`, `WORKER_BATCH_SIZE` | Période et maximum de traitements par passage ; défaut 900 s et 3 |
| `DOWNLOAD_MEDIA` | Téléchargement des pièces jointes vidéo ; défaut true |
| `MEDIA_MAX_MB`, `MEDIA_MAX_SECONDS` | Limites de taille et durée ; défaut 100 Mio, 300 s |
| `HTTP_TIMEOUT_SECONDS` | Délai réseau par requête ; défaut 120 s |
| `LLM_ENABLED` | Résumés des sources et rédaction des fiches à partir des preuves ; défaut false |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | API compatible OpenAI ; URL incluant `/v1` si requis par le serveur |
| `LLM_THINKING`, `VISION_THINKING` | Paramètre `thinking.type` facultatif ; profil DeepSeek : `disabled` |
| `AI_TOKEN_LIMIT_PARAM` | `max_tokens` pour DeepSeek ; `max_completion_tokens` pour les serveurs le demandant |
| `LLM_MAX_INPUT_CHARS` | Budget de texte source transmis à une synthèse ; défaut 24000 caractères |
| `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_MODEL` | API `audio/transcriptions` compatible avec WAV/multipart/`verbose_json` |
| `VISION_BASE_URL`, `VISION_API_KEY`, `VISION_MODEL` | API multimodale pour lire le texte visible ; URL/clé héritent du LLM si vides |
| `VISION_INTERVAL_SECONDS`, `VISION_MAX_FRAMES` | Échantillonnage réparti sur la vidéo ; défaut minimum 5 s et maximum 12 images |

Les noms des modèles doivent être ceux du serveur concerné. Aucun modèle, fournisseur ni abonnement n’est fourni par le projet. L’API Ollama texte ne remplace pas une API de transcription. Un modèle vision doit accepter les images encodées dans `image_url`. Pour ASR, choisir un modèle/service acceptant `response_format=verbose_json` ; tous les modèles audio OpenAI ou compatibles ne l’acceptent pas. Si l’ASR renvoie seulement du texte, l’extraction est explicitement marquée avec une précision à l’échelle du média entier.

Sur le Mac, utiliser une adresse réseau joignable depuis le NAS et configurer le serveur de modèles pour écouter sur ce réseau. Ne pas exposer un Ollama sans protection sur internet. Une panne ou extinction du Mac provoque un échec réessayé plus tard ; le web et les anciennes fiches restent utilisables. Les services distants reçoivent les données correspondant aux étapes activées : texte pour la synthèse, audio pour ASR, captures pour vision. La mémoire des modèles est consommée sur leur serveur, pas sur le NAS.

Pour une clé contenant `$` ou `#`, utiliser des guillemets simples dans `.env`. Ne pas ajouter de commentaire sur la même ligne qu’une valeur si la configuration est aussi utilisée directement par les scripts Python. Ne pas mettre d’identifiant dans une URL : utiliser les champs `*_API_KEY`.

## Import initial de tous les favoris

Voir le [guide import et DeepSeek](IMPORT-ET-DEEPSEEK.md). Renseigner les accès Karakeep et `COMPOSE_PROFILES=automation`, puis démarrer les services. Dans **Traitements**, cliquer sur **Importer tout l’historique** ; `SYNC_ENABLED=false` peut être conservé. Ce passage importe le catalogue et les textes, sans IA ni téléchargement. Ensuite, qualifier un premier traitement avant d’activer la boucle. Garder les deux filtres URL/tags vides pour analyser aussi les sites et articles ; corriger `instagram.com` dans un ancien `.env`.

## Lancement et diagnostic

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail=50 web worker
docker compose --profile automation run --rm worker python worker.py check
```

La commande `check` fait uniquement des lectures Karakeep et des listes de modèles, sans inférence. Un test complet dépendra du modèle réellement installé et de ses droits. Pour un passage manuel, arrêter la boucle s’il y en a une puis lancer :

```sh
docker compose --profile automation stop worker
docker compose --profile automation run --rm worker python worker.py once
# Reprendre la boucle si elle est activée dans .env.
docker compose up -d
```

Un verrou empêche deux workers de modifier le même volume. La synchronisation parcourt toutes les pages de favoris à chaque passage pour détecter les modifications ; elle conserve les suppressions et ne modifie jamais Karakeep. Les identifiants servent à dédupliquer, les réponses brutes sont conservées par version et les tâches réussies ne sont pas rejouées sans changement de source ou de configuration du pipeline. Changer uniquement une clé n’invalide pas les résultats réussis ; les échecs reprendront après leur délai.

Les erreurs de traitement sont conservées sans contenu de réponse distant ni clé dans `data/worker.sqlite`. Le résumé est dans `data/service-status.json` et la vue Traitements. Le statut `done` d’une tâche signifie que les étapes **configurées** ont fini ; sans ASR/vision, il ne signifie pas qu’une vidéo a été analysée. Une erreur ASR laisse la vision progresser et publier ses résultats ; la synthèse attend les étapes en échec. Trois tentatives automatiques sont permises par défaut, puis `worker.py retry --source ID --stage asr|vision|llm|all` permet une reprise explicite. Une nouvelle pièce jointe remplaçant une vidéo locale est bloquée, avec conservation de l’ancienne version et de ses références ; la migration de versions n’est pas automatisée.

Le web a une limite de 384 Mio et le worker de 768 Mio ; un seul média est traité à la fois. Les images utilisent `python:3.12-slim` et sont construites pour l’architecture du NAS. Le parcours web a été testé sous OrbStack Linux ARM64, autour de 21 Mio au repos avec le petit corpus de test. Ce n’est pas une mesure de charge du worker ni une garantie mémoire pour un gros corpus. Une limite trop basse peut provoquer un arrêt OOM, à diagnostiquer via `docker compose ps` et les journaux.

## Réseau

Pour un accès LAN direct, utiliser `KARARECALL_BIND_ADDRESS=0.0.0.0`. Pour un reverse proxy installé sur l’hôte, garder `127.0.0.1` et viser `http://127.0.0.1:8765`. Pour un proxy lui-même conteneurisé, connecter `web` au réseau Docker du proxy via un override Compose et viser `http://web:8765`. Conserver HTTPS, `Authorization` et les requêtes Range. Aucun certificat ni nom DNS n’est provisionné par ce dépôt.

## Sauvegarde et restauration

Sauvegarder **le volume et `.env`**, séparément du dépôt. Le volume contient `data/` et `vault/`, dont `data/current.json`, toutes les générations, les caches et le journal d’usage ; il contient des données privées. Les anciens JSON à la racine ne représentent plus nécessairement la publication courante. Pour un instantané cohérent, arrêter les services avant de l’archiver :

```sh
docker compose stop
docker compose run --rm --no-deps -T web tar -C /workspace -czf - data vault > kararecall-backup.tar.gz
docker compose up -d
```

Restaurer dans un volume neuf, services arrêtés, puis vérifier l’intégrité avant de relancer :

```sh
docker compose stop
docker compose run --rm --no-deps -T web tar -C /workspace -xzf - < kararecall-backup.tar.gz
docker compose run --rm --no-deps -T web python verify_storage.py
docker compose up -d
```

Pour importer le POC déjà présent sur une autre machine, créer une archive des dossiers `data/` et `vault/` depuis ce dossier, puis utiliser la même restauration. Exclure `data/models/` et les caches pour éviter de copier les modèles locaux ; conserver les JSON, réponses brutes, vérifications, médias et extractions. Ne jamais passer cette archive par Git. Le worker garde les fiches éditoriales existantes et remplace uniquement ses propres synthèses de la source traitée.

Ne pas utiliser `docker compose down -v` sur l’installation réelle : cela supprime son volume de données. Un simple `down` conserve le volume. Changer `KARARECALL_VOLUME_NAME` pointe vers une autre bibliothèque. Changer `PUID`/`PGID` après création du volume ne réattribue pas automatiquement ses fichiers ; conserver les mêmes valeurs ou migrer les droits lors d’un arrêt.

## Mise à jour

Pour une installation sous l’ancien nom, commence par la [migration vers KaraRecall](#passer-à-kararecall).

```sh
git pull --ff-only
# Comparer .env.example avec .env pour les nouveaux paramètres.
docker compose up -d --build
```

Le dépôt n’inclut pas d’image publiée dans un registre : le NAS doit pouvoir cloner le dépôt privé et construire les images. Pour Portainer ou un gestionnaire de stacks Git, fournir l’accès privé au dépôt, le chemin `compose.yaml` et les valeurs du `.env` via son mécanisme de variables. Les conteneurs en fonctionnement n’ont pas besoin d’accès GitHub. La procédure a été testée localement ; le déploiement sur le NAS reste à effectuer.

## Passer à KaraRecall

Cette procédure s’applique aux installations dont le `.env` contient des variables `MEMOIRE_*`. Elle transfère le catalogue, les médias, les preuves et le suivi des traitements vers un nouveau volume.

1. Dans l’ancien dossier d’installation, avant de mettre le code à jour, arrête les services et sauvegarde le volume et la configuration.

   ```sh
   umask 077
   docker compose stop &&
     docker compose run --rm --no-deps -T web tar -C /workspace -czf - data vault > kararecall-migration.tar.gz &&
     cp -p .env .env.avant-kararecall
   ```

2. Pointe Git vers le nouveau nom du dépôt et récupère le code.

   ```sh
   git remote set-url origin https://github.com/Nello10110/kararecall.git
   git pull --ff-only
   ```

   Si tu utilises SSH, l’adresse est `git@github.com:Nello10110/kararecall.git`.

3. Dans `.env`, remplace le préfixe `MEMOIRE_` par `KARARECALL_` en conservant les valeurs. Mets `COMPOSE_PROJECT_NAME=kararecall` et `KARARECALL_VOLUME_NAME=kararecall-storage`. Vérifie avec `docker volume ls` que ce volume est neuf. Si ce nom est pris, choisis un autre nom de volume libre dans `KARARECALL_VOLUME_NAME`. Garde les mêmes `PUID` et `PGID`.

4. Restaure la sauvegarde, vérifie le contenu, puis démarre KaraRecall.

   ```sh
   docker compose run --rm --no-deps --build -T web tar -C /workspace -xzf - < kararecall-migration.tar.gz &&
     docker compose run --rm --no-deps -T web python verify_storage.py &&
     docker compose up -d --build
   ```

   Vérifie que tes sources, fiches et preuves sont visibles dans l’interface. Garde la sauvegarde et l’ancien volume jusqu’à cette vérification.
