# Tous les favoris et profil DeepSeek

État du 5 novembre 2026. Ce guide complète l’architecture et remplace le périmètre Instagram et le choix de fournisseur proposés dans l’étude initiale. Le volume annoncé est d’environ vingt vidéos par mois ; le nombre de sites, articles et notes s’y ajoute et reste à mesurer.

## Ce qui est pris en compte

La collecte normale n’applique plus de filtre par défaut. Elle lit toutes les pages Karakeep avec `includeContent=true`, sans filtre d’archive ni de favori étoilé. Les identifiants empêchent les doublons. Le JSON original reste conservé, avec les tags et les indicateurs archivé/étoilé.

| Favori | Contenu exploité actuellement | Limite explicite |
|---|---|---|
| Site ou article | Titre, description, texte intégral/HTML fourni par Karakeep, notes personnelles et liens présents dans le HTML | Aucun retour sur le site pour compléter un texte absent. Les scripts et styles sont exclus du texte ; le JSON brut garde le contenu reçu. |
| Note texte | Texte et éventuelle URL d’origine, plus la note personnelle associée | Une note sans URL reste consultable et exportable, sans lien original inventé. |
| Fichier image ou PDF | Métadonnées et texte fourni par Karakeep. Si absent, le worker peut conserver l’original et extraire les pages PDF ou le texte de l’image. | L’OCR d’image autonome est activable dans `.env`. Les PDF numérisés sans texte incorporé sont signalés. [Paramètres et limites](HOMELAB.md#pdf-et-images). |
| Vidéo jointe à un lien | Textes Karakeep, téléchargement du média, transcription/OCR selon la configuration | Aucun téléchargement direct Instagram. Sans ASR, les paroles ne sont pas reconnues. L’OCR porte sur des captures échantillonnées. |
| Type inconnu | Métadonnées et réponse brute | Aucune analyse du fichier n’est annoncée. |

Légende/titre, page, note personnelle, paroles et OCR sont des preuves distinctes. Le résumé IA fourni par Karakeep reste exclu des preuves. Les liens conservés ne sont pas vérifiés par leur seule présence.

Le modèle texte produit maintenant un **résumé de lecture sourcé pour chaque favori**, même sans outil identifiable. Il ajoute des fiches d’outils seulement lorsque des noms explicites sont présents. Résumé, mots de recherche, tags et texte source alimentent la recherche lexicale ; le résumé figure sur la page source et dans son Markdown, avec les citations. Il reste marqué « À relire ». La couverture partielle d’un texte trop long est signalée. Un titre seul ne permet pas de prétendre résumer tout un article.

## Première passe sur tout l’historique

1. Créer le `.env`, renseigner les accès Karakeep et démarrer web et worker avec le profil Compose `automation`. `SYNC_ENABLED=false` permet de commencer sans analyses périodiques.
2. Dans **Traitements**, cliquer sur **Importer tout l’historique**. La demande persiste sur le volume. Le worker la prend en charge pendant son attente habituelle, sans attendre quinze minutes. Si aucun worker n’est démarré, l’interface indique l’attente.
3. Le worker lit toutes les pages puis publie le catalogue complet. Ce passage ignore volontairement les filtres URL et tags et inclut les favoris archivés. Il ne télécharge pas les médias et ne lance aucune inférence. Une erreur de pagination laisse la publication précédente intacte.
4. Contrôler le nombre de favoris, les textes disponibles et les cas sans texte. Choisir ensuite les étapes IA, faire un premier traitement avec `WORKER_BATCH_SIZE=1`, puis activer la collecte périodique.

Commande équivalente, lorsque la boucle est arrêtée :

```sh
docker compose --profile automation run --rm --build worker python worker.py import-history
```

Relancer l’import met à jour les sources sans refaire une analyse inchangée. Les demandes concurrentes en attente sont regroupées ; une demande interrompue reprend après redémarrage. Un média remplacé côté Karakeep reste bloqué pour protéger l’ancienne version et est signalé. Les favoris supprimés de Karakeep restent dans la bibliothèque locale.

La collecte périodique applique toujours les éventuels filtres explicitement configurés : garder **`KARAKEEP_URL_FILTER=` et `KARAKEEP_TAG_FILTER=`** pour traiter tous les favoris. Un ancien `.env` contenant `instagram.com` doit être corrigé manuellement ; la mise à jour du code ne remplace jamais la configuration privée.

La file d’import est distincte de la file d’analyses. Une mention « import terminé » signifie catalogue récupéré, pas vidéos intégralement analysées. Les analyses restent séquentielles, bornées par `WORKER_BATCH_SIZE`, les quotas et le budget. Avec trois sources par passage de quinze minutes, le maximum théorique est 288 sources/jour, mais les appels IA et leurs quotas limitent souvent davantage ce débit.

## Préparer DeepSeek

Sur une installation neuve :

```sh
python3 scripts/setup_env.py --profile deepseek
```

Ce profil est aussi le défaut du script. Il crée un mot de passe web aléatoire et refuse de remplacer un `.env` existant. Aucun secret n’est affiché et aucune connexion n’est lancée.

| Paramètre | Valeur proposée |
|---|---|
| `LLM_BASE_URL`, `VISION_BASE_URL` | `https://api.deepseek.com` |
| `LLM_MODEL`, `VISION_MODEL` | `deepseek-flash` |
| `LLM_API_KEY` | Votre clé DeepSeek ; vision en hérite si sa clé est vide |
| `AI_TOKEN_LIMIT_PARAM` | `max_tokens` |
| `LLM_THINKING`, `VISION_THINKING` | `disabled` ; réglage explicite de ce fournisseur |
| `LLM_REASONING_EFFORT`, `VISION_REASONING_EFFORT` | Vides ; pas de paramètre de raisonnement ajouté |
| `ASR_MODEL`, `ASR_BASE_URL`, `ASR_API_KEY` | Vides ; transcription non configurée |
| Tarifs entrée/sortie texte et vision | 0,30 / 1,20 USD par million de tokens, valeurs de pointe conservatrices |

Les clés Karakeep et DeepSeek sont renseignées directement dans le `.env` du NAS. Elles ne passent ni dans le chat, ni dans Git, ni dans le service web. `SYNC_ENABLED` et `LLM_ENABLED` restent false après génération ; `COMPOSE_PROFILES=automation` démarre le worker pour les commandes web et les bulletins. Un modèle vision renseigné active son étape lorsque la collecte et les traitements sont activés, indépendamment de `LLM_ENABLED`. Vider `VISION_MODEL` pour commencer par les seuls textes.

La documentation officielle actuelle annonce texte et vision pour Flash, via Chat Completions et images `image_url` encodées en base64. Ce contrat correspond au client livré ; sa disponibilité pour votre compte, la fidélité des résultats et les réponses JSON restent à qualifier avec votre clé. Le projet n’a pas validé d’inférence DeepSeek réelle.

La transcription utilise une autre route, `audio/transcriptions`, avec `verbose_json`. Aucun service DeepSeek compatible avec ce contrat audio n’a été identifié dans les pages consultées. Garder cette étape désactivée jusqu’au choix d’un service ASR : serveur Whisper local sur le Mac, ou autre API compatible, avec clé distincte si nécessaire. Le modèle vision ne remplace pas la reconnaissance des paroles.

Le profil historique `--profile api` reste disponible comme alternative Groq/OpenAI ; il n’est plus le choix par défaut.

## Budget et qualification

Hypothèse de calcul, **pas une mesure** : une synthèse texte avec 5 000 tokens d’entrée et 1 000 de sortie coûte environ 0,0027 USD au tarif de pointe sans cache, soit **0,054 USD pour vingt synthèses**. Mille favoris semblables représenteraient environ 2,70 USD pour cette seule étape. Les images, l’audio, les reprises et les textes longs s’ajoutent ; leur coût ne se déduit pas du seul nombre de vidéos. Le profil conserve 2 USD/mois, 50 appels/jour et 400/mois ; douze captures peuvent déjà représenter douze appels pour une vidéo. L’historique pourra donc s’étaler sur plusieurs périodes si ces quotas restent inchangés.

La récupération du catalogue ne fait aucun appel IA payant. Les analyses ultérieures peuvent en faire. Le journal utilise les tokens rapportés et les tarifs configurés, avec une réservation avant réseau. Un tarif nul ou un usage inconnu conserve la réserve de 0,05 USD. Ces estimations ne garantissent pas la facture fournisseur.

Avant le NAS : qualifier quelques articles, une note, un PDF avec/sans texte et une vidéo ; contrôler citations, absence de texte, paramètres DeepSeek, temps, mémoire et coût réellement rapporté. La recherche complémentaire DeepSeek Search/Fetch est disponible par commande web explicite ; `WEB_RESEARCH_ENABLED=true` active aussi son passage périodique. Les pages lues peuvent fournir un complément français sourcé, avec les mêmes quotas IA.

## Sécurité et contrôles

Le navigateur dispose d’une seule nouvelle commande : `POST /api/import-history`. Authentification, jeton de session anti-CSRF, refus des origines différentes et corps JSON borné sont contrôlés. La commande n’accepte aucun chemin, endpoint, modèle ou instruction. Elle écrit uniquement une demande locale sous `data/control/`. Le worker reste l’unique propriétaire de la publication ; Karakeep reste lu exclusivement par GET.

Les tests utilisent des sites, notes et fichiers fictifs ainsi que des API simulées. Ils vérifient import manuel sans synchronisation active ni inférence, déduplication, reprise après interruption, échec sans publication partielle, résumé d’article sans outil, citations, recherche, profils et protections HTTP. Le contrôle Compose vérifie aussi la consommation d’une demande depuis le web avec la collecte périodique désactivée, puis signale la configuration manquante sans joindre un fournisseur.

Références officielles consultées le 5 novembre 2026 : [schéma REST Karakeep](https://github.com/karakeep-app/karakeep/blob/main/packages/open-api/karakeep-openapi-spec.json), [base et modèles DeepSeek](https://api-docs.deepseek.com/), [vision](https://api-docs.deepseek.com/guides/vision), [paramètre thinking](https://api-docs.deepseek.com/guides/thinking_mode), [tarifs](https://api-docs.deepseek.com/quick_start/pricing).
