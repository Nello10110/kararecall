# Images Docker et mises à jour

[🇫🇷 Français](IMAGES-DOCKER.md) · [🇬🇧 English](en/docker-images.md)

Les images publiques sont publiées sur GitHub Container Registry pour Linux AMD64 et ARM64 :

- `ghcr.io/nello10110/kararecall-web:latest`
- `ghcr.io/nello10110/kararecall-worker:latest`

Le téléchargement ne demande pas de compte GitHub. Les images contiennent le code ; les favoris, médias, preuves et clés restent dans le volume et le `.env` privés de l’installation.

## Utiliser latest dans une stack existante

Dans les deux services KaraRecall, supprimer entièrement `build:` (y compris `context`, `target` et `args`), remplacer `image:` et remplacer `pull_policy: build` par `pull_policy: always` :

```yaml
services:
  recall:
    image: ghcr.io/nello10110/kararecall-web:latest
    pull_policy: always
    # Conserver ici les autres paramètres du service existant.
  recall_worker:
    image: ghcr.io/nello10110/kararecall-worker:latest
    pull_policy: always
    # Conserver ici les autres paramètres du service existant.
```

Cet extrait n’est pas une stack complète. Conserver les variables d’environnement, volumes, réseaux, reverse proxy, limites et noms de services de son installation. En particulier, garder le volume `kararecall-storage` et le `.env` existants. Aucune modification des autres services Karakeep n’est nécessaire.

Dans Dockhand, redéployer les deux services en demandant le téléchargement des images. En terminal, depuis le dossier de la stack :

```sh
docker compose config -q
docker compose pull recall recall_worker
docker compose up -d --no-deps recall recall_worker
```

Le Compose du dépôt utilise les noms `web` et `worker` : avec ce fichier, remplacer les deux noms ci-dessus et activer le worker avec `--profile automation` si nécessaire.

`latest` est un tag mobile, pas un service de surveillance. Le téléchargement et la recréation se font au déploiement ; un conteneur déjà lancé ne change pas tout seul. Un simple `restart` ne télécharge pas les images. Aucun agent de mise à jour automatique du NAS n’est installé par KaraRecall.

## Ce que publie la CI

Après chaque push sur `main`, les tests Python, Docker, médias et MCP doivent réussir. La CI construit ensuite les images web et worker pour les deux architectures et les publie sous le même tag `sha-SHA_GIT_COMPLET`. Elle promeut `latest` seulement quand les deux constructions ont réussi. Les pull requests ne publient aucune image. Une exécution plus ancienne ne remplace pas `latest` si un autre commit est désormais sur `main`.

Les deux changements de tag dans le registre ne constituent pas une transaction atomique. Pour un déploiement strictement reproductible, ou un retour à une version précédente, utiliser le même tag `sha-…` pour les deux images et vérifier leur révision. Dans le Compose du dépôt :

```dotenv
KARARECALL_IMAGE_TAG=sha-REMPLACER_PAR_LE_SHA_GIT_COMPLET_PUBLIE
```

Les tags de commit ne sont pas déplacés vers un autre commit par le workflow. Seuls les commits publiés par ce workflow possèdent ces images ; un ancien commit du dépôt peut ne pas en avoir.

Après mise à jour, vérifier les versions web/worker dans Administration et une fiche avec ses preuves. Un retour à une ancienne image ne restaure pas le volume : conserver une [sauvegarde vérifiée](HOMELAB.md#sauvegarde-et-restauration) avant une mise à jour qui modifie les données.

## Construction locale et UID/GID personnalisés

Les images publiées utilisent l’utilisateur non privilégié `10001:10001`, comme les anciennes constructions par défaut. Un volume créé avec d’autres UID/GID exige de conserver ces identifiants via une construction locale ou de migrer ses droits lors d’un arrêt. Les variables `PUID`/`PGID` ne changent pas les utilisateurs d’une image déjà publiée.

Pour développer ou construire avec ces variables :

```sh
docker compose -f compose.yaml -f deploy/compose.build.yaml up -d --build
```

Conserver les deux options `-f` pour les commandes suivantes de cette installation locale. L’override utilise des images `kararecall-web:local` et `kararecall-worker:local`, sans télécharger `latest`. Le test `scripts/check_container.py` utilise automatiquement ce mode et un volume jetable.

Références : [Container Registry GitHub](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [politique de téléchargement Compose](https://docs.docker.com/reference/compose-file/services/#pull_policy).
