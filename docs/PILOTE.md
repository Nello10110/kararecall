# Qualifier KaraRecall sur le NAS

Ce parcours sépare la validation de l’installation, l’accès à Karakeep et les essais des modèles. Les rapports sont des compteurs et des durées. Les favoris et les clés restent sur le NAS.

## Installer et contrôler le stockage

Suis l’installation Compose et ouvre l’interface depuis ton réseau. Lance le premier import depuis Activité. [Manuel d’installation](INSTALLATION.md).

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
docker stats --no-stream "$(docker compose ps -q web)" "$(docker compose --profile automation ps -q worker)"
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

Le rapport donne les rangs par ordre des questions, les latences médiane et maximale et la mémoire maximale du processus de mesure. Il exclut les questions et identifiants. Le seuil proposé est seize bonnes sources sur vingt dans les trois premiers résultats. Utilise les échecs pour décider si le coût d’une recherche hybride se justifie.

Après un lot représentatif, lance `docker compose exec -T web python pilot.py` pour relever les durées de copie et de publication de la dernière génération du worker. Dans l’onglet Réseau du navigateur, compare la taille et le temps de chargement de `/api/catalog?compact=1` et `/api/sources?limit=24`. Note le nombre total de favoris, le temps de recherche et la mémoire des deux conteneurs avec les autres services du NAS en charge.

## Mesures locales de référence

Sur le Mac, un catalogue de 2 002 sources synthétiques et deux fiches a donné les résultats suivants sur trois requêtes HTTP locales par route, avec un serveur déjà chargé.

| Requête | Taille JSON | Latence médiane |
|---|---:|---:|
| Catalogue complet | 1,19 Mo | 5,3 ms |
| Catalogue compact | 11,3 ko | 0,8 ms |
| Page de 24 sources | 14,3 ko | 0,5 ms |
| Recherche lexicale de test | 149 ko | 181 ms |

Les deux publications du catalogue ont duré 0,29 et 0,48 s, après 3 et 4 ms de copie initiale. Le pic du processus de mesure, qui a aussi généré le corpus et exécuté la recherche, était de 162 Mio. Ces valeurs décrivent un corpus surtout textuel et de petits médias synthétiques. La charge sur le NAS et ses temps de publication sont à relever séparément.

## Mesures de couverture, de lot et HTTP (0.5.0)

Le rapport standard inclut les compteurs de couverture par type, sans titres ni URL. Pour relever les tailles et délais des routes locales depuis le conteneur web :

```sh
docker compose exec -T web python pilot.py --http-url http://127.0.0.1:8765
```

Les identifiants HTTP viennent de l’environnement du service. Trois lectures sont effectuées pour chacune des routes catalogue compact, sources paginées et vue d’ensemble. Aucune réponse privée n’est conservée dans le rapport. Les redirections sont refusées.

Avant un lot, noter sa date de début en UTC, puis utiliser cette date exacte après traitement :

```sh
docker compose exec -T web python pilot.py --usage-since 2026-11-08T12:00:00Z
```

Remplacer l’exemple par le début réel du lot. Le rapport compte les appels et les montants enregistrés depuis cet instant. Les réserves incertaines restent visibles ; une absence d’usage mesuré ne signifie pas que le fournisseur n’a rien facturé. Les montants utilisent les tarifs configurés. La commande n’envoie aucun appel IA et ouvre le journal SQLite en lecture seule. Comparer ensuite un lot initial et un mois courant au lieu d’extrapoler seulement le premier import.

Pour les générations et la sauvegarde, suivre le [parcours de restauration](RESTAURATION-ET-GENERATIONS.md).

## Référence de recherche 0.5.0

```sh
PYTHONPYCACHEPREFIX=.build/pycache python3 scripts/benchmark_search.py
```

Le jeu `benchmarks/search_memories.json` comporte vingt documents et questions fictifs. Il ne contient aucune fiche produite par un LLM ; les questions ne sont pas générées à partir des fiches. Le moteur actuel retrouve la bonne source en première position pour **15 questions sur 20**, donc également 15/20 dans les trois premières. Sur le Mac, la médiane observée était de 2,4 ms pour ce petit corpus ; la taille et la machine du NAS demandent une mesure séparée.

Les cinq absences montrent notamment les limites des reformulations sans mots communs suffisants. Les seuils et le corpus n’ont pas été modifiés pour masquer ces échecs. Le résultat est inférieur au seuil proposé de 16/20 ; il justifie de préparer une comparaison hybride, mais ne suffit pas à choisir un modèle d’embedding ni à conclure sur les souvenirs réels. Le test privé de vingt questions reste ouvert, puis les mêmes questions pourront servir à comparer lexical/hybride et faux positifs. Aucun moteur sémantique n’est activé par cette livraison.
