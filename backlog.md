# Backlog de KaraRecall

Mise à jour du 8 novembre 2026 à partir de l’[étude d’exploitation](docs/ETUDE-EXPLOITATION.md). Les cases cochées distinguent les fonctions livrées et les décisions documentées. Les essais ouverts demandent le NAS, les services configurés ou un retour d’usage. La livraison 0.5.0 termine les travaux locaux de couverture et d’outillage ; elle ne coche pas les validations réelles à leur place. **Le propriétaire a signalé le démarrage sur son NAS et un premier favori analysé.** La qualification détaillée reste à effectuer avec le [pilote](docs/PILOTE.md) depuis son réseau.

Volume prévu précisé par l’utilisateur : **environ 20 vidéos/mois**. Dimensionner la première version pour ce volume, sans service Mac obligatoire ni abonnement de recherche payant par défaut. Les optimisations de débit passent après la fiabilité et l’usage quotidien.

## Déjà livré

- [x] POC sur trois vidéos avec transcription locale, OCR et fiches sourcées.
- [x] Interface dédiée : consultation, recherche globale, vidéo et transcription côte à côte, passages cliquables, exports Markdown et contexte pour assistant.
- [x] Dépôt GitHub (désormais public), Compose web/worker, configuration d’exemple et CI sur données synthétiques.
- [x] [Document d’architecture](docs/ARCHITECTURE.md) : composants, flux, rôles IA et options locales.
- [x] Étude des limites, coûts, alternatives et critères de passage à l’exploitation ; quatre limites de retraitement/cache/couverture reproduites sur un corpus fictif.

## P0 — Socle avant exploitation autonome

Implémentation et commandes : [P0.md](docs/P0.md). Les clés personnelles ne sont pas renseignées et aucun appel IA facturé n’a été effectué pendant les tests.

Le [guide du pilote](docs/PILOTE.md) donne les commandes de qualification REST, des modèles et du NAS, ainsi que la mesure de recherche. Les validations réelles restent ouvertes jusqu’au retour de ces essais.

### Préserver les preuves lors des retraitements

- [x] Versionner les extractions de façon immuable : média, moteur/fournisseur, modèle/version et paramètres ; une fiche doit citer exactement les preuves utilisées lors de sa rédaction.
- [x] Remplacer les références reposant uniquement sur la position d’un segment par des références attachées à une version de preuve ; prévoir une migration des fiches existantes.
- [x] Préparer les nouvelles sorties dans une génération isolée, valider l’ensemble, puis publier atomiquement ; conserver une ancienne génération cohérente si une étape échoue.
- [x] Vérifier qu’une nouvelle transcription, un changement de modèle et une référence devenue absente ne modifient pas les preuves d’une ancienne fiche et ne cassent pas la consultation.

Acceptation : tests de retraitement et d’échec sans dérive des références ni mélange entre ancien catalogue et nouvelles preuves.

### Rendre les reprises et le cache explicites

- [x] Inclure fournisseur, modèle/version, paramètres et version du traitement dans les clés de cache, sans inclure les secrets.
- [x] Ajouter un retraitement volontaire par source/étape ; changer une clé d’authentification ne doit pas invalider des résultats valides.
- [x] Séparer les états téléchargement, audio, OCR, synthèse et publication ; une panne audio ne doit pas bloquer indéfiniment un OCR indépendant.
- [x] Traiter une vidéo sans piste audio ou sans paroles comme un cas normal ; afficher « non applicable » ou l’état réellement observé.
- [x] Rendre visible le nombre réel de sources en attente, sans augmenter la concurrence par défaut.

Acceptation : panne du Mac, erreur API et redémarrage reprennent sans perte ni appel identique inutile, et l’interface distingue partiel, terminé, en attente et échec.

### Raccorder les moteurs et qualifier un pilote réel

- [x] Choisir un premier profil de traitement : proposition d’un profil API économique pour rendre le NAS indépendant du Mac, si la transmission convient. Garder le profil Mac audio/OCR comme alternative ; son économie seule ne le rend pas prioritaire aux volumes estimés.
- [ ] Valider les contrats réels d’audio, vision et texte, y compris les paramètres non pris en charge, les horodatages et les réponses JSON ; `check` seul ne suffit pas.
- [ ] Lire des favoris et télécharger au moins un média avec l’API REST Karakeep réelle, sans modifier les favoris et sans retourner sur Instagram.
- [x] Inclure tous les favoris par défaut : sites, articles, notes, fichiers et vidéos, sans filtre Instagram ; conserver les filtres URL/tags facultatifs.
- [x] Ajouter dans Traitements un import durable de tout l’historique, indépendant du batch d’analyses, sans appel IA ni téléchargement et sans doublon.
- [x] Produire un résumé de lecture sourcé même sans outil identifié, consultable, recherchable et exportable ; notes personnelles distinctes des textes éditeur.
- [x] Proposer le profil DeepSeek texte/vision avec paramètres documentés, clés dans `.env` et transcription audio séparée. Voir [le guide](docs/IMPORT-ET-DEEPSEEK.md).
- [ ] Mesurer le nombre total de favoris et de pages sans texte lors du premier import réel ; qualifier articles, notes et fichiers en plus des vidéos.
- [x] Extraire le texte incorporé aux PDF et lire les images autonomes via le service vision sur activation explicite. Les originaux, preuves de page/image, limites et échecs sont consultables. [Paramètres](docs/HOMELAB.md#pdf-et-images).
- [x] Extraire le texte des PDF numérisés sur option, avec aperçu par page, provenance, reprise et plafond d’appels vision.
- [ ] Qualifier vingt sources variées : silence, nom propre, texte bref à l’écran, ambiguïté, plusieurs outils, absence de média ; mesurer précision, durée et mémoire.

Acceptation : chaîne réelle reproductible, paramètres documentés, limites affichées et aucun moteur/call distant activé sans configuration explicite.

### Borner et mesurer les dépenses

- [x] Ajouter une limite de sortie compatible avec chaque fournisseur et permettre de régler le raisonnement lorsque le modèle le propose.
- [x] Enregistrer par étape les usages disponibles, durée audio, nombre de captures, tokens facturés et coût estimé selon des tarifs configurés ; ne pas journaliser les clés ou les contenus privés.
- [x] Réserver un budget configurable avant les appels, appliquer des quotas par période et limiter les reprises ; garder la réserve des appels incertains et suspendre les nouveaux appels aux limites. Ce contrôle comptable ne remplace pas les limites de dépenses du fournisseur.
- [x] Garder des fournisseurs explicites, sans bascule payante automatique ; afficher un budget comme estimation et non comme facture garantie.
- [ ] Mesurer le coût d’un lot avant d’autoriser un import massif ; distinguer import initial et coût mensuel récurrent.

Acceptation : on peut expliquer le coût d’une fiche, limiter les sorties et arrêter les nouveaux appels à la limite choisie.

### Déployer et restaurer sur le homelab

- [x] Automatiser la sauvegarde/restauration d’un corpus versionné dans un volume Docker neuf et la vérification de son intégrité sous OrbStack ; validation NAS encore à faire.

- [ ] Déployer le Compose sur le NAS, renseigner son `.env` et vérifier les UID/GID, accès réseau, espace disque et ressources réels.
- [ ] Importer le corpus privé du POC dans le volume, sans le faire passer par GitHub ; vérifier une reconstruction et des références d’origine.
- [ ] Configurer l’accès LAN/VPN ou le reverse proxy HTTPS choisi ; préserver authentification, accès aux médias et requêtes vidéo partielles.
- [ ] Sauvegarder volume et configuration puis restaurer réellement dans un volume neuf ; tester une mise à jour et le retour à une sauvegarde.
- [x] Signaler une absence récente de statut du worker et un espace disque disponible inférieur à 256 Mio dans Traitements.
- [ ] Mesurer le worker en charge avec les autres services du NAS.

Acceptation : restauration et mise à jour vérifiées ; le web reste consultable pendant une panne des moteurs ; absence de données ou clés dans le dépôt et les images.

## P1 — Usage quotidien et enrichissement demandé

### Couvrir tous les types de favoris et pièces jointes Karakeep

- [x] Découpler les miniatures de l’OCR : importer les images/bannières/captures Karakeep, extraire une image des vidéos locales sans IA et fournir un aperçu générique explicite si aucune image n’est accessible. Maintenir l’authentification et l’absence de téléchargement à l’ouverture d’une page.
- [x] Récupérer le texte des sites fourni comme fichier HTML séparé ou via l’API de contenu Karakeep ; conserver la provenance, les erreurs et les preuves versionnées. Un simple titre ne doit pas être présenté comme une analyse de l’article complet.
- [x] Inventorier les types du contrat API officiel et distinguer type de favori, format, pièces jointes et fournisseur dans la [matrice](docs/FORMATS-ET-COUVERTURE.md).
- [ ] Confirmer les formats réellement enregistrables dans la version Karakeep déployée sur le NAS. Base officielle : favoris **lien, note texte, fichier image/PDF, inconnu** ; pièces jointes HTML extrait, bannière, capture, capture de fichier, PDF, archive complète/préextraite, vidéo, fichier de favori, dépôt utilisateur, avatar et inconnu. Vérifier les différences entre versions au lieu de supposer qu’un MP3 ou un fichier bureautique est pris en charge.
- [x] Construire une [matrice de qualification et de limites](docs/FORMATS-ET-COUVERTURE.md) : sites/articles, notes, images (JPEG/PNG/WebP/GIF et formats effectivement acceptés), PDF texte/numérisés/protégés, Instagram, YouTube, autres hébergeurs, vidéos jointes avec/sans audio et sous-titres. Ajouter audio seul et documents bureautiques **si Karakeep permet réellement de les enregistrer** ; afficher sinon une limite explicite.
- [x] Étendre les tests synthétiques : import/dédoublonnage et exports de treize familles de favoris, HTML inline/séparé, quatre formats image, animation limitée à sa première image, PDF joint/natif/numérisé/corrompu, couverture et filtres avant pagination. Les tests existants couvrent authentification, redirections, cache, quotas, silence, sous-titres et anciennes preuves.
- [ ] Compléter la matrice réelle avec les PDF protégés, hébergeurs et contenus privés du NAS ; vérifier langue/fidélité, durées, mémoire et reprises sur les services configurés.
- [x] Traiter les PDF joints aux liens, lire JPEG/PNG/WebP/GIF avec couverture partielle des animations, et distinguer métadonnées, contenu disponible, analyse partielle/terminée et format inconnu. Ajouter Administration → Couverture et les filtres de source ; signaler les archives/pièces jointes sans extracteur. Aucun téléchargement direct chez un hébergeur ni nouvel appel IA implicite.
- [ ] Ajouter d’autres extracteurs seulement si l’inventaire NAS montre des formats utiles actuellement signalés non pris en charge.
- [ ] Qualifier cette matrice sur le NAS avec un échantillon varié, notamment les sites et vidéos Instagram/YouTube signalés, puis documenter les formats et limites dans le guide.

Acceptation : aucun favori ignoré silencieusement ; chaque carte a un aperçu, chaque extraction indique sa couverture réelle, les preuves restent consultables et les formats non pris en charge sont explicitement signalés. Les correctifs 0.4.1 et la matrice 0.5.0 sont testés sur données synthétiques ; la qualification NAS de cette matrice reste ouverte. Contrat de référence : [contenu d’un favori Karakeep 0.30](https://docs.karakeep.com/v0.30.0/api/get-a-single-bookmark) et [schéma OpenAPI officiel](https://github.com/karakeep-app/karakeep/blob/main/packages/open-api/karakeep-openapi-spec.json).

### Recherche internet systématique par outil

- [x] Rechercher après publication et afficher les sites, documents et dépôts candidats, avec lecture ciblée via DeepSeek.
- [x] Permettre la revue de l’identité de l’éditeur et l’ajout de notes de description, d’usage et de fonctionnement attribuées à une page effectivement consultée.
- [x] Évaluer l’attribution des notes documentaires et retenir la revue avant publication pour le pilote. [Critères](docs/RECHERCHE-WEB.md#rédaction-des-notes-documentaires).
- [x] Appliquer une recherche et jusqu’à deux pages par nouvel outil, avec cache partagé, date de passage et budget persistant.
- [x] Comparer Brave et Firecrawl pour la recherche et la lecture, avec un scénario de vingt outils par mois. [Comparatif](docs/RECHERCHE-WEB.md).
- [x] Conserver les URL, dates et traces immuables, séparées des affirmations et preuves initiales.
- [x] Présenter les résultats ambigus et lectures indisponibles sans attribuer automatiquement les affirmations à l’éditeur. Rejeter les adresses tronquées ou sensibles.
- [x] Limiter les données envoyées au nom de l’outil et aux adresses candidates retenues. Borner volume et délais. Refuser la connexion directe à une destination découverte et les redirections de l’API.
- [ ] Qualifier le pilote avec le compte DeepSeek réel, dont les homonymes et les contradictions.

Acceptation : chaque enrichissement est retraçable, un doublon ne relance pas toute la recherche, un échec ne bloque pas les fiches existantes et le coût est visible.

### Revue et navigation

- [x] Corriger et valider les fiches depuis l’interface avec conservation des révisions et des preuves.
- [x] Sérialiser les écritures éditoriales et les traitements via un verrou partagé. Refuser une modification fondée sur une révision ancienne.
- [x] Regrouper explicitement des fiches du même outil, avec conservation des références, sources et anciens liens.
- [ ] Recueillir les retours d’usage puis ajuster navigation et filtres ; améliorer les actions de reprise et les explications des erreurs.
- [x] Rechercher et surligner les mots dans le panneau de transcription, puis ouvrir le passage correspondant.
- [x] Centrer l’extrait sur un mot retrouvé et ouvrir directement le passage ou la page depuis les résultats globaux.

Déjà disponible : la recherche globale inclut transcriptions et OCR ; la transcription apparaît à côté de la vidéo avec passages cliquables.

### Bulletin de veille hebdomadaire et mensuel

Produire un petit article illustré, structuré et agréable à lire, pour retrouver les découvertes de la période et préparer leur diffusion.

- [x] Sélectionner les favoris ajoutés, traités ou consultés, avec suivi des ouvertures sur activation explicite. Inclure outils, sites, articles, notes et autres contenus.
- [x] Proposer un rendez-vous hebdomadaire et un récapitulatif mensuel, activables séparément, avec jour, heure et fuseau configurables, ainsi qu’une génération manuelle depuis l’interface.
- [x] Construire un article avec titre, courte introduction, rubriques thématiques et quelques lignes par découverte. Pour un outil, présenter ce qu’il fait, son utilité et un cas d’usage lorsque les sources le permettent. Ajouter un lien vers la fiche et la source originale.
- [x] Accompagner les présentations de petites images issues des preuves ou d’illustrations sourcées, avec légende et texte alternatif. Prévoir un rendu lisible sur mobile, y compris lorsque les images sont absentes ou bloquées.
- [x] Regrouper les favoris parlant du même outil et distinguer les nouveautés des compléments. Donner au bulletin mensuel une synthèse des thèmes et découvertes marquantes, avec une longueur réglable.
- [x] Générer les textes à partir des fiches et preuves conservées, avec attribution des affirmations et liens vers les références. Réutiliser les résumés existants et appliquer les budgets IA aux éventuels appels supplémentaires.
- [x] Fournir la page Veille, le mail SMTP, un RSS privé, les exports HTML/Markdown et l’impression PDF dans le navigateur. Proposer un webhook JSON pour les automatisations et messageries.
- [x] Permettre de prévisualiser, corriger et sélectionner les contenus et images partageables avant diffusion. Configurer les destinataires et accès de diffusion via les paramètres privés de l’installation, avec activation explicite des envois automatiques.
- [x] Conserver les éditions et leur état de génération ou d’envoi. Dédupliquer les envois par période et destination, gérer les reprises et préciser le comportement en l’absence de nouveautés.

Le bulletin doit se lire en quelques minutes, présenter les découvertes avec leurs illustrations et références, puis pouvoir être relu et exporté pour diffusion. Une reprise doit préserver l’édition et son suivi d’envoi.

La rédaction automatique produit des articles à partir des preuves réelles avec cache, quotas et citations par paragraphe. Une première édition reprend l’historique. Les échéances suivantes ne demandent aucune action éditoriale. Le mail et le webhook exigent une configuration et une édition validée. Le [guide Veille](docs/VEILLE.md) détaille les réglages et limites.

- [ ] Qualifier le relais SMTP ou webhook réel et la lecture RSS sur le NAS, puis ajuster la présentation après les premiers bulletins.

### Couverture et traitements économes

- [x] Proposer un traitement optionnel des longs articles et documents avec résumés de passages, reprise, couverture en caractères et citations du texte original.
- [x] Comparer DeepSeek Search/Fetch aux options de recherche existantes et définir le contrat du premier pilote. [Choix proposé et critères](docs/RECHERCHE-WEB.md).

- [x] Répartir le budget texte entre légende, audio, OCR et portions de vidéo ; signaler les preuves non envoyées au modèle.
- [x] Détecter et conserver les pistes textuelles embarquées, avec origine et horodatages. Réutiliser une piste exploitable avant l’ASR quand l’option est activée.
- [x] Proposer un échantillonnage par changements visuels, avec le même plafond d’envois. Vérifier sa pertinence pour les textes brefs lors du pilote.
- [x] Étudier le découpage et la reprise des médias longs, ainsi que le recours ciblé à la vision selon la couverture. [Décision](docs/EXPLOITATION-LONG-TERME.md#médias-longs).

## P2 — Conversation, recherche avancée et long terme

### MCP en lecture seule

- [x] Adapter l’API de lecture à MCP pour les fiches, sources, transcriptions, preuves et contextes. [Guide MCP](docs/MCP.md).
- [x] Choisir stdio pour un assistant local, avec accès au NAS authentifié via l’API web. Documenter l’option distante pour les clients qui la nécessitent.
- [x] Borner les résultats MCP et conserver les citations. Les outils proposés sont en lecture seule.
- [ ] Qualifier des demandes naturelles, y compris orales, et l’abstention lorsque l’information est absente.

### Mesurer avant de passer au sémantique

- [x] Constituer vingt questions de souvenir sur un corpus de référence fictif, sans fiches générées, et mesurer le moteur lexical : 15/20 dans les trois premiers résultats ; [script et limites](docs/PILOTE.md#référence-de-recherche-050).
- [ ] Mesurer vingt questions indépendantes sur les souvenirs réels du propriétaire ; seuil proposé de 16/20 dans les trois premiers. Le corpus de référence ne valide pas le NAS ni la pertinence sur ses favoris.
- [x] Définir les conditions d’un index sémantique dérivé et reconstruisible. [Critères](docs/EXPLOITATION-LONG-TERME.md#recherche-et-exports).

### Stockage, performances et maintenance

- [x] Séparer import du catalogue historique et analyses par lots bornées avec les quotas existants.
- [x] Mesurer copie, publication et pagination sur un catalogue de 2 002 sources synthétiques. [Mesures locales](docs/PILOTE.md#mesures-locales-de-référence).
- [ ] Mesurer les copies/reconstructions et la pagination HTTP sur l’historique réel du NAS.
- [x] Hacher en flux et réutiliser les empreintes des fichiers inchangés lors des publications, avec invalidation si les métadonnées du fichier changent.
- [x] Paginer les sources côté HTTP et interface, réutiliser les exports Markdown des sources stables et mesurer copie et publication.
- [ ] Relever latence de recherche et mémoire sur le corpus représentatif du NAS avant de choisir un nouveau moteur ou une base serveur.
- [x] Définir quotas, réserve d’espace libre pour les téléchargements, conservation des versions et des traces.
- [x] Définir le traitement des favoris absents et des pièces jointes remplacées, avec conservation des preuves locales.
- [x] Documenter migrations, vérification des dépendances et modèles, mise à jour et restauration périodique. [Maintenance](docs/EXPLOITATION-LONG-TERME.md#maintenance).
- [x] Étudier les exports ciblés vers AFFiNE et Wiki.js et les conditions d’un registre Docker privé. [Options](docs/EXPLOITATION-LONG-TERME.md#recherche-et-exports).

## Critère de passage à l’exploitation

Les critères et charges indicatives sont dans l’[étude](docs/ETUDE-EXPLOITATION.md#critères-proposés-pour-donner-le-feu-vert-au-nas). Le chantier peut commencer sur l’architecture actuelle ; le feu vert à l’usage autonome demande la validation du lot P0, et non la seule existence du Compose.

## Évolutions conditionnelles après le pilote

- Si le profil Mac est retenu, exposer la transcription locale derrière un service authentifié et comparer faster-whisper et whisper.cpp sur les mêmes extraits. L’OCR Apple Vision peut faire l’objet du même raccordement.
- Si le test de souvenirs passe sous le seuil proposé, comparer la recherche lexicale et une recherche hybride sur les mêmes questions, preuves et faux positifs.


## Retour d’usage du 7 novembre : français et pilotage

- [x] Titres éditoriaux français courts, résumés de source limités à une phrase et 180 caractères.
- [x] Traductions françaises des preuves conservées en langue étrangère, séparées des originaux, avec temps, références et cache reprenable.
- [x] Nettoyage des hashtags, appels promotionnels et répétitions dans les vues éditoriales ; preuves originales conservées pour vérification.
- [x] Boutons de synthèse/traduction par source ou en masse ; relance complète par source ; import historique depuis Sources et Traitements.
- [x] File persistante avec progression, quota, reprise après redémarrage et protection contre les doubles commandes.
- [x] Vidage local confirmé et suspension de la collecte ; aucune modification de Karakeep ni remise à zéro de la facturation.
- [x] Recherche complémentaire par outil ou en masse ; description française tirée uniquement de pages lues et citées.
- [x] Compteurs séparés : résumés IA de sources et vidéos avec transcription + OCR réellement terminés.
- [ ] Qualifier ces nouvelles commandes et la fidélité des traductions avec les modèles et les contenus réels du NAS.

### Correctif : paroles disponibles pendant une pause de vision

- [x] Afficher les paroles françaises indépendamment du résumé IA, avec lecture compatible des métadonnées de langue des anciennes générations.
- [x] Expliquer sur la source les étapes terminées, en pause et en attente, sans présenter une collecte partielle comme une analyse vidéo complète.
- [x] Distinguer les limites journalière, mensuelle et budgétaire sans les contourner ni remettre le journal d’usage à zéro.
- [x] Ajouter une reprise ciblée de la lecture de l’écran, avec réutilisation des autres extractions valides.
- [x] Reproduire le cas de huit segments français, sans résumé et avec vision en pause, sur données fictives.

## Espace de travail et administration — 8 novembre 2026

Audit : [usage quotidien et administration](docs/UX-ET-ADMINISTRATION.md).

- [x] Tableau de bord avec compteurs réels, nouveautés, formats, alertes et aperçu des quotas.
- [x] Recherche recentrée et suppression des exemples figés du POC.
- [x] Filtres de sources par format, état et tri, appliqués avant pagination et conservables dans l’URL.
- [x] Filtre de relecture et recherche dans la bibliothèque d’outils.
- [x] Écran Activité avec commandes, progression et annulation de la suite d’une commande.
- [x] Administration : connexions, contrôle de lecture explicite, versions, santé, consommation, stockage et suspension de l’automatisation.
- [x] Export de diagnostic sans contenus ni secrets ; export privé du catalogue JSON distinct d’une sauvegarde.
- [x] Vidage local déplacé dans une zone dédiée avec confirmation explicite.
- [x] Thèmes glass sombre/clair, navigation mobile et maintien des anciennes routes de preuves et fiches.
- [ ] Qualifier les nouveaux états de configuration, le contrôle des fournisseurs et les parcours sur le NAS après mise à jour des deux images.
- [x] Étudier le [parcours de restauration et la preuve de sauvegarde externe](docs/RESTAURATION-ET-GENERATIONS.md). Livrer un inventaire et un contrôle d’intégrité de génération en lecture seule ; conserver le retour par volume neuf et le statut « sauvegarde non observée ».
- [ ] Qualifier une restauration externe réelle sur le NAS avant de proposer un retour à une ancienne génération depuis l’interface.

## Distribution Docker — 8 novembre 2026

- [x] Publication GHCR des images web/worker AMD64 et ARM64 après réussite des tests sur `main`.
- [x] Tags de commit pour figer une paire et promotion de `latest` après les deux constructions.
- [x] Compose prêt à télécharger les images, guide de migration depuis `build.context` et construction locale conservée séparément.
- [ ] Valider le premier téléchargement et la mise à jour des deux services sur le NAS via Dockhand.

## Réponses vision structurées — correctif 0.3.1

- [x] Activer le mode JSON natif des appels Chat Completions DeepSeek officiels, avec consigne et exemple JSON.
- [x] Distinguer une réponse vide, un JSON invalide, une troncature et un refus, sans journaliser le contenu reçu.
- [x] Unifier l’OCR vidéo/image/PDF et borner à une seconde requête par image en cas de sortie inexploitable, comptabilisée et soumise aux quotas.
- [x] Versionner le contrat OCR dans les caches, conserver le cache audio et reproduire les échecs sur une vidéo synthétique sans publier de faux succès.
- [ ] Confirmer la reprise de la source en échec après mise à jour du NAS vers 0.3.1 ; vérifier les textes reconnus et les références.

## Ergonomie des fiches — version 0.4

- [x] Mettre les liens explicites et l’usage en tête des outils, sans inventer de site officiel.
- [x] Déplacer l’édition, le regroupement et l’enrichissement web dans un volet secondaire en bas de fiche.
- [x] Regrouper les références sans perdre les passages ni leur attribution et retirer les mentions de vidéo des sous-titres de navigation des outils.
- [x] Revoir les cartes, résultats, sources, preuves et bulletins avec la même priorité donnée à la lecture.
- [x] Vérifier les parcours bureau/mobile et les thèmes sur une copie privée, ainsi que les cas de liens invalides ou absents sur fixtures.
- [ ] Confirmer le confort de lecture et les liens principaux sur le corpus réel du NAS après mise à jour vers 0.4.

## Outillage du pilote — version 0.5.0

- [x] Rapport de couverture sans titres, identifiants de favoris ni URL, inclus dans Administration, le diagnostic partageable et `pilot.py`.
- [x] Mesure HTTP authentifiée de trois routes, trois lectures chacune, avec tailles et latences uniquement.
- [x] Mesure comptable d’un lot depuis une date avec fuseau : appels, réserves incertaines, coûts par étape, sans modifier le journal ni appeler un modèle.
- [x] Inventaire des générations et vérification d’une ancienne publication sans restauration ni modification du pointeur.
- [ ] Exécuter ces mesures sur le NAS avec ses services réels ; relever aussi mémoire, coût du lot et sauvegarde externe.
