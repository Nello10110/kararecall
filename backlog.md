# Backlog — Mémoire

Mise à jour du 5 novembre 2026 à partir de l’[étude d’exploitation](docs/ETUDE-EXPLOITATION.md). Ordre de réalisation proposé : **P0 avant usage autonome sur le NAS, P1 pour l’usage quotidien enrichi, P2 selon les résultats du pilote**. Les travaux ne sont pas encore réalisés sauf cases cochées. Les fournisseurs et dépenses ne sont pas sélectionnés automatiquement.

## Déjà livré

- [x] POC sur trois vidéos avec transcription locale, OCR et fiches sourcées.
- [x] Interface dédiée : consultation, recherche globale, vidéo et transcription côte à côte, passages cliquables, exports Markdown et contexte pour assistant.
- [x] Dépôt GitHub privé, Compose web/worker, configuration d’exemple et CI sur données synthétiques.
- [x] [Document d’architecture](docs/ARCHITECTURE.md) : composants, flux, rôles IA et options locales.
- [x] Étude des limites, coûts, alternatives et critères de passage à l’exploitation ; quatre limites de retraitement/cache/couverture reproduites sur un corpus fictif.

## P0 — Socle avant exploitation autonome

### Préserver les preuves lors des retraitements

- [ ] Versionner les extractions de façon immuable : média, moteur/fournisseur, modèle/version et paramètres ; une fiche doit citer exactement les preuves utilisées lors de sa rédaction.
- [ ] Remplacer les références reposant uniquement sur la position d’un segment par des références attachées à une version de preuve ; prévoir une migration des fiches existantes.
- [ ] Préparer les nouvelles sorties dans une génération isolée, valider l’ensemble, puis publier atomiquement ; conserver une ancienne génération cohérente si une étape échoue.
- [ ] Vérifier qu’une nouvelle transcription, un changement de modèle et une référence devenue absente ne modifient pas les preuves d’une ancienne fiche et ne cassent pas la consultation.

Acceptation : tests de retraitement et d’échec sans dérive des références ni mélange entre ancien catalogue et nouvelles preuves.

### Rendre les reprises et le cache explicites

- [ ] Inclure fournisseur, modèle/version, paramètres et version du traitement dans les clés de cache, sans inclure les secrets.
- [ ] Ajouter un retraitement volontaire par source/étape ; changer une clé d’authentification ne doit pas invalider des résultats valides.
- [ ] Séparer les états téléchargement, audio, OCR, synthèse et publication ; une panne audio ne doit pas bloquer indéfiniment un OCR indépendant.
- [ ] Traiter une vidéo sans piste audio ou sans paroles comme un cas normal ; afficher « non applicable » ou l’état réellement observé.
- [ ] Ajouter un mode de rattrapage borné pour l’import initial, sans augmenter la concurrence par défaut ; rendre visible le nombre réel de sources en attente.

Acceptation : panne du Mac, erreur API et redémarrage reprennent sans perte ni appel identique inutile, et l’interface distingue partiel, terminé, en attente et échec.

### Raccorder les moteurs et qualifier un pilote réel

- [ ] Choisir un premier profil de traitement : API ou service Mac. Proposition : transcription et OCR spécialisé sur le Mac, synthèse locale ou API interchangeable.
- [ ] Exposer les briques faster-whisper/Apple Vision locales derrière un service authentifié sur le réseau privé, si le profil Mac est retenu ; prévoir démarrage et redémarrage du service.
- [ ] Comparer la vitesse/qualité avec whisper.cpp si nécessaire ; FFmpeg/Whisper reste une variante locale à adapter, pas une suppression du besoin de reconnaissance vocale.
- [ ] Valider les contrats réels d’audio, vision et texte, y compris les paramètres non pris en charge, les horodatages et les réponses JSON ; `check` seul ne suffit pas.
- [ ] Lire des favoris et télécharger au moins un média avec l’API REST Karakeep réelle, sans modifier les favoris et sans retourner sur Instagram.
- [ ] Définir le périmètre de collecte et la taille du premier import ; ajouter la sélection par listes/tags si nécessaire, car le filtre actuel est une sous-chaîne d’URL et ne sélectionne pas les listes Karakeep.
- [ ] Qualifier vingt sources variées : silence, nom propre, texte bref à l’écran, ambiguïté, plusieurs outils, absence de média ; mesurer précision, durée et mémoire.

Acceptation : chaîne réelle reproductible, paramètres documentés, limites affichées et aucun moteur/call distant activé sans configuration explicite.

### Borner et mesurer les dépenses

- [ ] Ajouter une limite de sortie compatible avec chaque fournisseur et permettre de régler le raisonnement lorsque le modèle le propose.
- [ ] Enregistrer par étape les usages disponibles, durée audio, nombre de captures, tokens facturés et coût estimé selon des tarifs configurés ; ne pas journaliser les clés ou les contenus privés.
- [ ] Fixer un plafond de sources/appels par période, limiter les reprises consécutives et suspendre le traitement facturable quand le budget configuré est atteint ou ne peut pas être évalué de manière sûre.
- [ ] Garder des fournisseurs explicites, sans bascule payante automatique ; afficher un budget comme estimation et non comme facture garantie.
- [ ] Mesurer le coût d’un lot avant d’autoriser un import massif ; distinguer import initial et coût mensuel récurrent.

Acceptation : on peut expliquer le coût d’une fiche, limiter les sorties et arrêter les nouveaux appels à la limite choisie.

### Déployer et restaurer sur le homelab

- [ ] Déployer le Compose sur le NAS, renseigner son `.env` et vérifier les UID/GID, accès réseau, espace disque et ressources réels.
- [ ] Importer le corpus privé du POC dans le volume, sans le faire passer par GitHub ; vérifier une reconstruction et des références d’origine.
- [ ] Configurer l’accès LAN/VPN ou le reverse proxy HTTPS choisi ; préserver authentification, accès aux médias et requêtes vidéo partielles.
- [ ] Sauvegarder volume et configuration puis restaurer réellement dans un volume neuf ; tester une mise à jour et le retour à une sauvegarde.
- [ ] Mesurer le worker en charge avec les autres services du NAS ; prévoir un signal d’erreur utile et la détection d’un worker arrêté ou d’un manque d’espace disque.

Acceptation : restauration et mise à jour vérifiées ; le web reste consultable pendant une panne des moteurs ; absence de données ou clés dans le dépôt et les images.

## P1 — Usage quotidien et enrichissement demandé

### Recherche internet systématique par outil

- [ ] Après identification d’un outil, rechercher son site, documentation et dépôt officiels lorsqu’ils existent ; décrire son utilité et son fonctionnement à partir des sources consultées.
- [ ] Commencer par un budget borné : une recherche et jusqu’à deux pages par nouvel outil, avec cache partagé entre favoris du même outil et date de révision.
- [ ] Comparer Brave + lecture simple des pages et Firecrawl pour les extractions difficiles ; suivre coût et quota partagés, sans souscrire automatiquement.
- [ ] Conserver les URL, dates, traces de lecture et citations ; distinguer description de l’éditeur, propos de la vidéo et capacités effectivement testées.
- [ ] Gérer noms ambigus, URL tronquées, pages absentes et contradictions sans inventer de correspondance ; un lien inaccessible reste signalé.
- [ ] Limiter les données envoyées à la recherche aux informations utiles, et borner volumes, délais et redirections de la récupération ; bloquer l’accès à des adresses privées depuis les liens non fiables.

Acceptation : chaque enrichissement est retraçable, un doublon ne relance pas toute la recherche, un échec ne bloque pas les fiches existantes et le coût est visible.

### Revue et navigation

- [ ] Permettre de corriger et valider une synthèse « À relire », les noms et les liens, sans perdre l’historique ni les preuves.
- [ ] Donner les écritures éditoriales à un seul propriétaire/une transaction ; éviter des modifications concurrentes des JSON par le web et le worker.
- [ ] Regrouper les fiches d’un même outil issues de plusieurs favoris, en conservant toutes leurs provenances.
- [ ] Recueillir les retours d’usage puis ajuster navigation et filtres ; améliorer les actions de reprise et les explications des erreurs.
- [ ] Ajouter recherche et surlignage directement dans le panneau de transcription, puis navigation au passage correspondant.
- [ ] Améliorer l’extrait et l’ouverture à l’instant précis depuis les résultats globaux.

Déjà disponible : la recherche globale inclut transcriptions et OCR ; la transcription apparaît à côté de la vidéo avec passages cliquables.

### Couverture et traitements économes

- [ ] Répartir le budget texte entre légende, audio, OCR et portions de vidéo ; signaler les preuves non envoyées au modèle.
- [ ] Détecter et importer les pistes de sous-titres textuels disponibles, avec origine et horodatages, pour éviter une nouvelle reconnaissance.
- [ ] Améliorer l’échantillonnage des captures pour les textes brefs, sans envoyer toutes les images à un LLM par défaut ; documenter la couverture.
- [ ] Étudier découpage/reprise des vidéos longues ou volumineuses et la sélection d’un OCR/vision plus riche seulement lorsque nécessaire.

## P2 — Conversation, recherche avancée et long terme

### MCP en lecture seule

- [ ] Réutiliser les fonctions de recherche/lecture pour un serveur MCP : fiche, source, transcription, preuve horodatée et contexte.
- [ ] Choisir transport et authentification selon les assistants réellement utilisés ; comparer adaptateur local sur Mac et service HTTP du homelab.
- [ ] Borner les résultats et conserver les citations ; aucune écriture Karakeep ni exécution d’outil découvert dans les sources.
- [ ] Qualifier des demandes naturelles, y compris orales, et l’abstention lorsque l’information est absente.

### Mesurer avant de passer au sémantique

- [ ] Constituer vingt questions de souvenirs indépendantes des fiches et mesurer le moteur lexical ; proposition initiale : bonne source dans les trois premiers résultats sur au moins seize questions.
- [ ] Si ce niveau est insuffisant, comparer lexical et recherche hybride multilingue ; conserver les preuves et mesurer les faux positifs.
- [ ] Garder les embeddings comme index dérivé reconstruisible ; n’ajouter une base vectorielle séparée que si l’échelle mesurée le justifie.

### Stockage, performances et maintenance

- [ ] Hacher les médias en flux, réutiliser les empreintes connues et éviter de relire tout le corpus pour chaque nouvelle fiche.
- [ ] Ajouter pagination côté interface et reconstruction ciblée ; mesurer recherche et mémoire avec un corpus représentatif avant une nouvelle base serveur.
- [ ] Définir quotas, espace libre, rétention des médias/versions et conservation des traces ; ne pas supprimer automatiquement les preuves citées.
- [ ] Définir le traitement des favoris supprimés et des pièces jointes remplacées. Actuellement les suppressions restent locales et les remplacements sont bloqués.
- [ ] Prévoir migrations de schéma, vérification des dépendances et modèles dépréciés, tests périodiques de restauration et mise à jour.
- [ ] Étudier les exports utiles vers AFFiNE/Wiki.js et une image Docker dans un registre privé si ces besoins se confirment.

## Critère de passage à l’exploitation

Les critères et charges indicatives sont dans l’[étude](docs/ETUDE-EXPLOITATION.md#critères-proposés-pour-donner-le-feu-vert-au-nas). Le chantier peut commencer sur l’architecture actuelle ; le feu vert à l’usage autonome demande la validation du lot P0, et non la seule existence du Compose.
