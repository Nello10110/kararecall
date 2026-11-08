# Déploiement sur le homelab

[🇫🇷 Français](HOMELAB.md) · [🇬🇧 English](en/homelab.md)

Pour configurer le NAS et lancer le premier import, suis le [manuel pas à pas](INSTALLATION.md).

Ce guide décrit les commandes disponibles. Le [guide P0](P0.md) détaille le profil API, les limites et les commandes de reprise/vérification. Les preuves sont désormais versionnées et publiées par génération ; la qualification des moteurs réels et du NAS reste à réaliser selon le [backlog](BACKLOG.md).

## Configuration

Le dépôt public contient uniquement le code et des tests fictifs. Sur le NAS, cloner le dépôt puis exécuter `python3 scripts/setup_env.py --profile deepseek` ou créer `.env` depuis `.env.example`. Garder ce fichier sur le serveur : Compose transmet explicitement les variables requises à chaque service. Le service web ne reçoit aucune clé Karakeep ou IA.

| Paramètres `.env` | Rôle |
|---|---|
| `KARARECALL_USERNAME`, `KARARECALL_PASSWORD` | Accès web ; mot de passe d’exemple refusé |
| `KARARECALL_BIND_ADDRESS`, `KARARECALL_PORT` | Adresse d’écoute de l’hôte et port ; défaut 127.0.0.1:8765 |
| `KARARECALL_VOLUME_NAME` | Nom du volume persistant, défaut `kararecall-storage` |
| `KARARECALL_IMAGE_TAG` | Tag commun aux deux images publiées ; défaut `latest` |
| `PUID`, `PGID` | UID/GID utilisés seulement par `deploy/compose.build.yaml` ; images publiées en 10001:10001 |
| `COMPOSE_PROFILES=automation` | Active le service worker avec un simple `docker compose up` |
| `SYNC_ENABLED` | Autorise la collecte périodique ; défaut false |
| `KARAKEEP_BASE_URL`, `KARAKEEP_API_KEY` | Adresse Karakeep et clé Bearer ; pas besoin d’ajouter `/api/v1` |
| `KARAKEEP_URL_FILTER` | Sous-chaîne d’URL facultative ; ex. `instagram.com` ; vide = tous les favoris |
| `SYNC_INTERVAL_SECONDS`, `WORKER_BATCH_SIZE` | Période et maximum de traitements par passage ; défaut 900 s et 3 |
| `DOWNLOAD_MEDIA` | Téléchargement des vidéos et des PDF/images sans texte fourni par Karakeep ; défaut true |
| `STORAGE_MIN_FREE_MB` | Espace libre réservé pendant les nouveaux téléchargements. Défaut 256 Mio |
| `REUSE_SUBTITLES` | Détecte les pistes de sous-titres textuelles embarquées et les réutilise avant l’ASR ; défaut false |
| `PDF_MAX_PAGES` | Nombre de pages analysées localement par PDF ; défaut 25, maximum 100 |
| `PDF_OCR_ENABLED`, `PDF_OCR_MAX_PAGES` | OCR des pages sans texte via le service vision. Désactivé par défaut, plafond de 3 pages par PDF si activé, maximum 10 |
| `IMAGE_OCR_ENABLED` | Envoie les images autonomes au service vision configuré pour lire le texte ; défaut false |
| `MEDIA_MAX_MB`, `MEDIA_MAX_SECONDS` | Limites de taille et durée ; défaut 100 Mio, 300 s |
| `HTTP_TIMEOUT_SECONDS` | Délai réseau par requête ; défaut 120 s |
| `LLM_ENABLED` | Résumés des sources et rédaction des fiches à partir des preuves ; défaut false |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | API compatible OpenAI ; URL incluant `/v1` si requis par le serveur |
| `LLM_THINKING`, `VISION_THINKING` | Paramètre `thinking.type` facultatif ; profil DeepSeek : `disabled` |
| `AI_TOKEN_LIMIT_PARAM` | `max_tokens` pour DeepSeek ; `max_completion_tokens` pour les serveurs le demandant |
| `LLM_MAX_INPUT_CHARS` | Budget de texte source transmis à une synthèse ; défaut 24000 caractères |
| `LLM_DOCUMENT_SECTIONS` | Nombre maximal de résumés de passages avant la synthèse d’un article ou d’un document long. Défaut 0, maximum 10 |
| `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_MODEL` | API `audio/transcriptions` compatible avec WAV/multipart/`verbose_json` |
| `VISION_BASE_URL`, `VISION_API_KEY`, `VISION_MODEL` | API multimodale pour lire le texte visible ; URL/clé héritent du LLM si vides |
| `VISION_INTERVAL_SECONDS`, `VISION_MAX_FRAMES` | Échantillonnage réparti sur la vidéo ; défaut minimum 5 s et maximum 12 images |
| `VISION_SAMPLE_MODE` | `regular` par défaut. `changes` choisit les changements visuels les plus marqués dans des fenêtres espacées, dans le même budget d’images |

Les noms des modèles doivent être ceux du serveur concerné. Aucun modèle, fournisseur ni abonnement n’est fourni par le projet. L’API Ollama texte ne remplace pas une API de transcription. Un modèle vision doit accepter les images encodées dans `image_url`. Pour ASR, choisir un modèle/service acceptant `response_format=verbose_json` ; tous les modèles audio OpenAI ou compatibles ne l’acceptent pas. Si l’ASR renvoie seulement du texte, l’extraction est explicitement marquée avec une précision à l’échelle du média entier.

Sur le Mac, utiliser une adresse réseau joignable depuis le NAS et configurer le serveur de modèles pour écouter sur ce réseau. Ne pas exposer un Ollama sans protection sur internet. Une panne ou extinction du Mac provoque un échec réessayé plus tard ; le web et les anciennes fiches restent utilisables. Les services distants reçoivent les données correspondant aux étapes activées : texte pour la synthèse, audio pour ASR, captures pour vision. La mémoire des modèles est consommée sur leur serveur, pas sur le NAS.

Pour une clé contenant `$` ou `#`, utiliser des guillemets simples dans `.env`. Ne pas ajouter de commentaire sur la même ligne qu’une valeur si la configuration est aussi utilisée directement par les scripts Python. Ne pas mettre d’identifiant dans une URL : utiliser les champs `*_API_KEY`.

## Import initial de tous les favoris

Voir le [guide import et DeepSeek](IMPORT-ET-DEEPSEEK.md). Renseigner les accès Karakeep et `COMPOSE_PROFILES=automation`, puis démarrer les services. Dans **Activité**, cliquer sur **Importer tout l’historique** ; `SYNC_ENABLED=false` peut être conservé. Ce passage importe le catalogue et les textes, sans IA ni téléchargement. Ensuite, qualifier un premier traitement avant d’activer la boucle. Garder les deux filtres URL/tags vides pour analyser aussi les sites et articles ; corriger `instagram.com` dans un ancien `.env`.

## Sous-titres embarqués

`REUSE_SUBTITLES=true` cherche une piste de texte locale dans la vidéo téléchargée. Le worker préfère une piste française quand elle est présente, ignore les pistes forcées et conserve les extraits avec leurs temps, leur langue, leur numéro de piste et l’empreinte de la vidéo. Une piste textuelle lue jusqu’au bout remplace l’appel ASR du passage. Une piste absente, partielle ou illisible laisse fonctionner l’ASR configuré. Les sous-titres sont identifiés séparément des paroles reconnues. Un retraitement explicite `--stage asr` peut demander une vraie transcription.

Avec `VISION_SAMPLE_MODE=changes`, le worker compare des images réduites environ toutes les demi-secondes en local. Il privilégie un changement par fenêtre tout en respectant l’espacement et le plafond d’images envoyées au modèle. Un texte très bref entre deux sondes ou une scène déjà chargée peut passer inaperçu. Le mode et l’intervalle sont conservés avec le résultat.

## PDF et images

Avec `LLM_DOCUMENT_SECTIONS` activé, un texte long est découpé à proximité des paragraphes ou des espaces. Les passages sont répartis sur le document disponible. Chaque résumé intermédiaire est mis en cache et la synthèse finale cite les extraits originaux, avec page pour un PDF. La couverture indique la proportion de caractères représentés dans la synthèse. Le réglage ajoute jusqu’à un appel texte par passage aux appels habituels, soumis au même budget.

Le worker télécharge l’original des PDF et images sans texte fourni par Karakeep lorsque `DOWNLOAD_MEDIA=true`. La limite est de 20 Mio par fichier, ou moins si `MEDIA_MAX_MB` est inférieur. L’original est accessible en téléchargement dans la fiche source. Les preuves restent liées à l’empreinte du fichier, y compris lorsqu’une pièce jointe est remplacée dans Karakeep.

- Le worker Docker extrait le texte incorporé aux PDF avec Poppler, avec des limites de temps, mémoire, pages et sortie. Chaque page conserve son numéro. Une limite atteinte est signalée. [Documentation de pdftotext](https://manpages.debian.org/trixie/poppler-utils/pdftotext.1.en.html).
- Avec `PDF_OCR_ENABLED=true`, les premières pages sans texte dans cette fenêtre sont converties localement en JPEG de 1280 pixels de côté au maximum. Seuls ces aperçus sont envoyés au service vision configuré. Les preuves OCR portent le numéro de page et le modèle utilisé. Les pages terminées sont réutilisées après un arrêt. Compter jusqu’à `PDF_OCR_MAX_PAGES` appels vision par PDF, dans les quotas IA partagés. Les pages avec une couche texte incomplète ne sont pas éligibles à ce traitement. [Documentation de pdftoppm](https://manpages.debian.org/trixie/poppler-utils/pdftoppm.1.en.html).
- Une image est conservée comme original par défaut. Pour lire son texte, définir `IMAGE_OCR_ENABLED=true` avec un modèle vision déjà configuré. Le service reçoit un aperçu JPEG sans métadonnées, limité à 1280 pixels de côté. JPEG, PNG, WebP et GIF sont acceptés jusqu’à 20 mégapixels. Pour une animation GIF ou WebP, seule la première image est lue ; le nombre d’images et la couverture partielle sont affichés. L’appel est comptabilisé comme un appel vision.

L’import manuel du catalogue reste indépendant du téléchargement et de l’extraction. Utiliser `python -m kararecall.worker retry --source ID --stage document` pour retraiter volontairement un fichier déjà conservé. Le suivi se trouve dans Activité et dans la fiche source.

## Lancement et diagnostic

```sh
docker compose up -d
docker compose ps
docker compose logs --tail=50 web worker
docker compose --profile automation run --rm worker python -m kararecall.worker check
```

La commande `check` fait uniquement des lectures Karakeep et des listes de modèles, sans inférence. Un test complet dépendra du modèle réellement installé et de ses droits. Pour un passage manuel, arrêter la boucle s’il y en a une puis lancer :

```sh
docker compose --profile automation stop worker
docker compose --profile automation run --rm worker python -m kararecall.worker once
# Reprendre la boucle si elle est activée dans .env.
docker compose up -d
```

Un verrou empêche deux workers de modifier le même volume. La synchronisation parcourt toutes les pages de favoris à chaque passage pour détecter les modifications ; elle conserve les suppressions et ne modifie jamais Karakeep. Les identifiants servent à dédupliquer, les réponses brutes sont conservées par version et les tâches réussies ne sont pas rejouées sans changement de source ou de configuration du pipeline. Changer uniquement une clé n’invalide pas les résultats réussis ; les échecs reprendront après leur délai.

Les erreurs de traitement sont conservées sans contenu de réponse distant ni clé dans `data/worker.sqlite`. Le résumé est dans `data/service-status.json` et la vue Activité. Le worker actualise son signal de présence pendant l’attente entre deux passages. La vue signale un état ancien et un espace libre inférieur à `STORAGE_MIN_FREE_MB`. Un téléchargement qui atteindrait ce seuil est interrompu. Le statut `done` signifie que les étapes configurées ont fini. L’interface affiche séparément la transcription et l’OCR réellement disponibles. Une erreur ASR laisse la vision progresser et publier ses résultats. La synthèse attend les étapes en échec. Trois tentatives automatiques sont permises par défaut, puis `python -m kararecall.worker retry --source ID --stage asr|vision|document|llm|all` permet une reprise explicite. [Politique de conservation et de versionnement](EXPLOITATION-LONG-TERME.md#conservation).

Le web a une limite de 384 Mio et le worker de 768 Mio ; un seul média est traité à la fois. Les images utilisent `python:3.12-slim` ; le registre fournit Linux AMD64 et ARM64, sélectionné automatiquement par Docker. Le parcours web a été testé sous OrbStack Linux ARM64, autour de 21 Mio au repos avec le petit corpus de test. Ce n’est pas une mesure de charge du worker ni une garantie mémoire pour un gros corpus. Une limite trop basse peut provoquer un arrêt OOM, à diagnostiquer via `docker compose ps` et les journaux.

## Réseau

Pour un accès LAN direct, utiliser `KARARECALL_BIND_ADDRESS=0.0.0.0`. Pour un reverse proxy installé sur l’hôte, garder `127.0.0.1` et viser `http://127.0.0.1:8765`. Pour un proxy lui-même conteneurisé, connecter `web` au réseau Docker du proxy via un override Compose et viser `http://web:8765`. Conserver HTTPS, `Authorization` et les requêtes Range. Aucun certificat ni nom DNS n’est provisionné par ce dépôt.

## Sauvegarde et restauration

Sauvegarder **le volume et `.env`**, séparément du dépôt. Le volume contient `data/` et `vault/`, dont `data/current.json`, toutes les générations, les caches et le journal d’usage ; il contient des données privées. Les anciens JSON à la racine ne représentent plus nécessairement la publication courante. Pour un instantané cohérent, arrêter les services avant de l’archiver :

```sh
umask 077
docker compose --profile automation stop
docker compose run --rm --no-deps -T web tar -C /workspace -czf - data vault > kararecall-backup.tar.gz
cp -p .env .env.sauvegarde
```

Relance les services utilisés avant la sauvegarde avec `docker compose up -d` ou `docker compose --profile automation up -d` selon ton installation.

Restaure et vérifie dans un volume neuf, avec un projet Compose séparé. Choisis un nom de volume libre différent du volume utilisé en production.

```sh
KARARECALL_VOLUME_NAME=kararecall-restore-test docker compose -p kararecall-restore run --rm --no-deps -T web tar -C /workspace -xzf - < kararecall-backup.tar.gz
KARARECALL_VOLUME_NAME=kararecall-restore-test docker compose -p kararecall-restore run --rm --no-deps -T web python scripts/verify_storage.py
```

Pour importer le POC déjà présent sur une autre machine, crée une archive des dossiers `data/` et `vault/` depuis ce dossier, puis utilise la même restauration. Exclure `data/models/` et les caches pour éviter de copier les modèles locaux. Conserve les JSON, réponses brutes, vérifications, médias et extractions. Transfère l’archive par ton réseau privé. Le worker conserve les fiches relues et remplace ses propres synthèses. Pour activer un volume restauré, arrête d’abord les services de production, indique son nom dans `KARARECALL_VOLUME_NAME` et redémarre avec le profil utilisé. Garde le volume précédent jusqu’à validation.

Ne pas utiliser `docker compose down -v` sur l’installation réelle : cela supprime son volume de données. Un simple `down` conserve le volume. Changer `KARARECALL_VOLUME_NAME` pointe vers une autre bibliothèque. Changer `PUID`/`PGID` après création du volume ne réattribue pas automatiquement ses fichiers ; conserver les mêmes valeurs ou migrer les droits lors d’un arrêt.

## Mise à jour

Pour une installation sous l’ancien nom, commence par la [migration vers KaraRecall](#passer-à-kararecall).

```sh
git pull --ff-only
# Comparer .env.example avec .env pour les nouveaux paramètres.
docker compose --profile automation pull web worker
docker compose --profile automation up -d --no-deps web worker
```

Le Compose utilise les images publiques GHCR avec `latest` et `pull_policy: always`. Aucun accès Git privé ni build sur le NAS n’est nécessaire. Dans Dockhand/Portainer, télécharger puis redéployer les deux services ensemble, en conservant les variables et le volume. `latest` ne met pas à jour un conteneur déjà lancé : un déploiement reste nécessaire. Pour un Compose personnalisé avec anciens `build.context`, supprimer les deux blocs `build` et remplacer les images selon le [guide des images](IMAGES-DOCKER.md). Ce guide explique aussi les versions figées, le retour arrière et la construction locale avec UID/GID personnalisés.

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
   docker compose run --rm --no-deps -T web tar -C /workspace -xzf - < kararecall-migration.tar.gz &&
     docker compose run --rm --no-deps -T web python scripts/verify_storage.py &&
     docker compose up -d
   ```

   Vérifie que tes sources, fiches et preuves sont visibles dans l’interface. Garde la sauvegarde et l’ancien volume jusqu’à cette vérification.

Le [guide des formats](FORMATS-ET-COUVERTURE.md) détaille les PDF joints aux liens et les formats sans extracteur. Le [parcours des générations et de restauration](RESTAURATION-ET-GENERATIONS.md) permet d’inventorier et vérifier un ancien état sans le restaurer. Les mesures de coût de lot et de latence HTTP sont dans le [pilote](PILOTE.md#mesures-de-couverture-de-lot-et-http-050).
