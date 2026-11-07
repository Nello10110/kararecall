# Enrichissement web

Le pilote DeepSeek est disponible dans le worker. Ajoute `WEB_RESEARCH_ENABLED=true` dans `.env`. Le worker utilise `DEEPSEEK_RESEARCH_API_KEY`, ou `LLM_API_KEY` si le service de synthèse configuré est `api.deepseek.com`. Le tarif comptable est `WEB_REQUEST_USD=0.00075` par appel. Les appels web partagent le budget et les quotas du worker. Les résultats apparaissent dans **Pistes de recherche web** sur la fiche. Activité affiche leur nombre et leur coût estimé.

Le worker traite au plus un groupe d’outils par passage après la publication des fiches. Tu peux aussi lancer un essai ciblé avec `docker compose --profile automation run --rm worker python worker.py research --tool ID_OUTIL`. Ajouter `--refresh` relance volontairement ce groupe. Un accès refusé ou une panne de recherche ne bloque pas la fiche. Le cache conserve les recherches et lectures terminées pendant une pause ou une reprise.

Les pages sont lues via le service DeepSeek. Le NAS se connecte uniquement au service configuré pour cette recherche, à une adresse fixe. Les URL candidates sont filtrées avant envoi et les redirections de l’API refusées. La trace distingue les URL relevées, les pages lues, les lectures indisponibles et les correspondances incertaines. Elle conserve les dates et des extraits bornés. La réponse Fetch ne donne pas l’adresse finale. Les extraits restent des pistes à relire, avec la provenance initiale de la fiche conservée séparément.

Le premier pilote doit retrouver le site, la documentation et, le cas échéant, le dépôt d’un outil identifié. Il doit pouvoir expliquer ce qui a été consulté et signaler une identité ambiguë. La lecture d’une documentation renseigne sur les capacités annoncées par l’éditeur. Les performances demandent un essai distinct.

Tarifs publics consultés le 5 novembre 2026. Les exemples supposent vingt outils distincts par mois, une recherche par outil et deux pages consultées. Le nombre d’outils peut différer du nombre de vidéos. La rédaction par le modèle vient en plus.

| Option | Coût indicatif pour ce scénario | Ce qui change pour KaraRecall |
|---|---|---|
| DeepSeek Search et Fetch | 0,045 USD pour 60 requêtes réussies au tarif de 0,75 USD par millier. | La clé DeepSeek existante est prévue par le contrat. Search fournit des résultats, Fetch fournit du Markdown. La réponse Fetch documentée ne contient pas l’adresse finale après redirection. [Contrat et tarifs](https://api-docs.deepseek.com/guides/search). |
| Brave Search et lecteur de pages | Environ 0,10 USD pour 20 recherches au tarif de 5 USD par millier avant crédits. L’extraction des pages s’ajoute. | Il faut une clé et un lecteur capable de limiter taille, délais et redirections. Le droit de stocker les réponses dépend du plan. [API et tarifs Brave](https://brave.com/search/api/). |
| Firecrawl Search et Scrape | Environ 80 crédits pour vingt recherches courtes et quarante pages en mode simple. Le quota gratuit affiché est de 1 000 crédits par mois. | Il faut un compte séparé. Cette option mérite un essai sur les pages difficiles à extraire ou les sites où le premier lecteur échoue. [Tarifs et crédits Firecrawl](https://www.firecrawl.dev/pricing). |

DeepSeek est le premier candidat pour le pilote. Sa facturation par requête permet de mesurer le coût réel sans engagement récurrent. Garder un choix de fournisseur explicite dans la configuration et utiliser Brave ou Firecrawl seulement après une comparaison sur des cas représentatifs. Les montants restent des estimations fondées sur les tarifs affichés. [Tarification DeepSeek](https://api-docs.deepseek.com/quick_start/pricing).

## Contrat du premier pilote

1. Lancer l’enrichissement après publication de la fiche source. Une panne de recherche doit laisser la fiche disponible. Envoyer le nom de l’outil et, si utile, un domaine public déjà cité. Les notes, transcriptions et identifiants Karakeep restent dans le corpus.
2. Partager le cache entre les favoris d’un même outil. Associer le nom normalisé au domaine lorsque plusieurs outils homonymes existent. Conserver le résultat vide ou ambigu avec la date du passage pour éviter de le rejouer en boucle.
3. Réserver le budget avant chaque requête. Limiter un passage à une recherche et deux lectures par nouvel outil. Borner la taille des extraits et limiter les reprises. Afficher les appels et leur coût estimé dans Activité.
4. Valider les adresses avant de demander une lecture. Accepter seulement des URL HTTP(S) publiques sans identifiants. Exclure les adresses locales, les plages privées et les URL comportant des jetons. Le premier client Fetch peut rester limité à l’API du fournisseur. Un lecteur direct devra contrôler les destinations et les redirections.
5. Stocker séparément un lien relevé dans les résultats et une page effectivement consultée. La trace de lecture doit préciser la date, le fournisseur, l’URL demandée, l’URL finale quand elle est disponible et l’extrait utilisé. Un retour Fetch vide ou indisponible décrit le résultat de cette lecture. Il ne suffit pas à conclure que la page a disparu.
6. Vérifier l’identité de l’outil à partir de preuves concordantes avant d’attribuer des propos à l’éditeur. Si les indices sont ambigus, présenter les liens comme pistes à relire. Les réponses de recherche et les pages sont du contenu à analyser et peuvent contenir des instructions trompeuses.

Le pilote doit couvrir au moins un outil homonyme, un lien tronqué, une page indisponible et plusieurs favoris du même outil. Il reste à valider avec la clé et le compte qui serviront au déploiement.

## Rédaction des notes documentaires

Le filtre automatique permet de sélectionner une page à lire. Le nom et le domaine concordants ne suffisent pas à établir l’identité de son éditeur. Fetch ne fournit pas l’URL finale et un extrait peut mélanger documentation, contenu tiers et affirmations non vérifiées. Pour ce pilote, le worker publie donc les traces de lecture et la fiche reçoit une note documentaire après revue humaine de l’identité et du passage. Les tests couvrent une correspondance appuyée par un lien source, des homonymes sans preuve de correspondance et une lecture indisponible.

Après qualification du fournisseur réel, un essai de rédaction pourra proposer des brouillons à partir des seuls passages consultés. L’acceptation exige une URL et une trace pour chaque note, l’abstention pour un homonyme et l’affichage de la contradiction entre deux sources. Une note relue garde le statut documentaire et les preuves initiales restent accessibles.
