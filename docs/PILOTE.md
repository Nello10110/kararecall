# Qualifier KaraRecall sur le NAS

Ce parcours sépare la validation de l’installation, l’accès à Karakeep et les essais des modèles. Les rapports sont des compteurs et des durées. Les favoris et les clés restent sur le NAS.

## Installer et contrôler le stockage

Suis l’installation Compose et ouvre l’interface depuis ton réseau. Lance le premier import depuis Traitements. [Manuel d’installation](INSTALLATION.md).

```sh
docker compose ps
docker compose exec -T web python verify_storage.py
```

Vérifie que le nombre de sources te paraît cohérent, qu’un article est recherchable et qu’une note sans URL s’ouvre. Si tu importes le corpus du POC, restaure-le sur un volume neuf, puis ouvre une ancienne fiche et son passage cité. Pour un accès par VPN ou proxy HTTPS, vérifie la connexion et le déplacement dans une vidéo depuis cet accès. Teste ensuite la sauvegarde et la restauration sur un volume distinct. [Exploitation et sauvegarde](HOMELAB.md#sauvegarde-et-restauration).

## Vérifier Karakeep avec le worker

Depuis le dossier Compose, avec `KARAKEEP_BASE_URL` et `KARAKEEP_API_KEY` renseignées dans `.env` :

```sh
docker compose --profile automation run --rm worker python pilot.py --probe-karakeep --probe-media
```

La lecture parcourt les favoris réels avec l’API REST, déduplique les identifiants et compte les types et les pages sans texte. Le test média essaie au plus trois pièces jointes et garde la première téléchargée avec succès, dans un dossier temporaire. Il utilise une limite de 20 Mio ou celle du worker si elle est inférieure. Le rapport contient le type, la taille et le délai. `absent` signale qu’aucune pièce jointe exploitable n’a été trouvée. `failed` indique un échec de téléchargement. Ces lectures sont séparées du catalogue publié et des appels aux modèles.

## Tester les modèles sur des cas représentatifs

Commence par un seul favori avec `WORKER_BATCH_SIZE=1`. Vérifie les paramètres de tes services, relève les compteurs d’usage, puis lance le premier passage décrit dans le manuel. [Essai DeepSeek](INSTALLATION.md#6-activer-deepseek-et-les-mises-à-jour-automatiques).

```sh
docker compose --profile automation run --rm worker python worker.py usage
docker compose stats --no-stream
```

Pour élargir le lot, sélectionne une vingtaine de cas dans tes favoris. Inclure des articles, notes, images et PDF, des vidéos sans audio, des noms propres et du texte bref à l’écran. Pour chaque cas, contrôler les preuves brutes, le résumé et les étapes effectivement terminées. Vérifier au moins une vidéo avec la transcription et les horodatages, ainsi que les sorties JSON de chaque moteur activé. Relever les durées, l’usage avant et après le lot et la RAM du worker en charge. Les appels dépendant de tes comptes sont mesurés à cette étape.

Pour tester le web, active le pilote sur une fiche et contrôle le résultat avec les cas d’homonymie, de lien incomplet et de page indisponible. Pour le MCP, tester depuis ton assistant une demande de souvenir, le passage exact puis une demande sans réponse. [Recherche web](RECHERCHE-WEB.md) · [MCP](MCP.md).

## Mesurer la recherche

Écris vingt questions de mémoire dans `.pilot-questions.json`, avant de consulter les résultats. Associe chaque question à l’identifiant Karakeep de la source attendue. Garde ce fichier sur ton installation. Exemple de structure :

```json
[
  {"query":"L’article sur le stockage de chaleur en hiver", "source_id":"ID_FAVORI"}
]
```

```sh
docker compose --profile automation run --rm \
  --volume "$PWD/.pilot-questions.json:/questions.json:ro" \
  worker python pilot.py --questions /questions.json
```

Le rapport donne les rangs par ordre des questions, avec les scores agrégés au premier rang et dans les trois premiers résultats. Il exclut les questions et identifiants. Le seuil proposé est seize bonnes sources sur vingt dans les trois premiers résultats. Utiliser les échecs pour décider si le coût d’une recherche hybride se justifie.
