# Usage quotidien et administration de KaraRecall

Audit et évolution du 8 novembre 2026. La version 0.3.0 conserve le modèle local et portable, les preuves et la lecture seule de Karakeep. Cet audit se fonde sur le code, les parcours existants et les retours du pilote NAS ; ce n’est pas une étude d’usage auprès de plusieurs utilisateurs.

## Ce que l’utilisateur cherche à faire

Au quotidien, ouvrir l’application pour retrouver une découverte, comprendre rapidement ce qu’elle apporte, consulter le texte ou la vidéo et récupérer un contexte sourcé pour poursuivre dans un assistant. Il doit pouvoir distinguer un favori simplement importé d’un contenu résumé et d’une vidéo dont les paroles et l’écran ont été analysés.

Lors d’un ajout ou d’une reprise d’historique, vérifier que les favoris sont arrivés, lancer une analyse si nécessaire et comprendre une attente. Une erreur, un quota, une désactivation et un worker absent ne demandent pas la même action. La consultation doit rester agréable même si un service IA est indisponible.

Chaque semaine ou mois, lire les bulletins déjà préparés et vérifier leur état réel de rédaction et de diffusion. La préparation manuelle doit rester une option ponctuelle, sans donner l’impression que l’automatisation exige un travail manuel à chaque édition.

Pour administrer, identifier les versions du web et du worker, les services renseignés, le dernier contrôle de connexion, le dernier signe de vie, les limites consommées et l’état de la publication. Suspendre l’automatisation, annuler la suite d’une commande et exporter un diagnostic sans contenus doivent être possibles sans manipuler le journal d’usage ou les preuves.

## Problèmes observés dans l’interface précédente

- La recherche servait aussi d’accueil, avec des recommandations, statistiques et exemples issus du POC. Les actions prioritaires et les alertes de fonctionnement étaient dispersées.
- Sources et Traitements répétaient les commandes globales. Le bouton de vidage était trop proche des usages de consultation.
- Les états vidéo dominaient les filtres, alors que l’application couvre aussi articles, notes et fichiers. Le nombre de vidéos analysées pouvait être pris pour le nombre de sources ayant reçu un résumé.
- Les connexions et la configuration des modèles étaient difficiles à inspecter depuis le web. Un worker configuré, présent ou connecté à ses fournisseurs sont pourtant trois faits différents.
- Les pauses de quota n’expliquaient pas toujours quelle limite était atteinte. Les commandes en attente n’étaient pas suffisamment séparées du travail réellement en cours.
- La conservation en volume Docker pouvait être confondue avec une sauvegarde. Un export descriptif ne remplace pas une copie des médias, preuves et fichiers de configuration.

## Architecture des écrans livrée

| Écran | Décision et contenu |
| --- | --- |
| Tableau de bord | Nouvel accueil : recherche rapide, vrais compteurs, dernières sources, répartition par format, ajouts des sept derniers jours, alertes avec liens d’action et aperçu du budget. |
| Recherche | Recentrée sur la recherche lexicale. Les suggestions proviennent des outils réellement présents ; les exemples figés du POC ont été retirés. Les citations et liens vers les passages restent disponibles. |
| Mes outils | Recherche locale par nom ou usage, filtre de relecture et tri. La description, les limites, les liens et les preuves restent dans la fiche détaillée. |
| Sources | Consultation par cartes, recherche, format, état et ordre. Les filtres sont conservables dans l’URL. Les commandes coûteuses restent dans la fiche de la source ou dans Activité. |
| Activité | Remplace le libellé Traitements, tout en conservant la route `#/processing`. File, progression, annulation de la suite, import historique et lancement global. Tableau des états filtrable par pause, échec, résumé ou absence de résumé. |
| Veille | Rythme configuré et état de diffusion visibles, éditions consultables, génération ponctuelle repliée. Les modifications et l’impression PDF restent disponibles. |
| Administration | Nouvel espace à quatre onglets : Connexions et santé ; Consommation IA ; Données et sauvegarde ; Automatisation. Le vidage confirmé est isolé dans ce dernier onglet. |

Aucun écran de preuve, de revue ou de contexte n’a été supprimé. Les anciennes routes de sources, d’outils, de veille et de traitements sont préservées. La recherche affiche les extraits traduits lorsqu’ils existent et signale les traductions manquantes sans transformer un texte original en résumé français. Le changement porte sur la hiérarchie et la présentation, sans conversion de la recherche en moteur sémantique.

## Informations d’administration disponibles

Le worker transmet un état public de sa configuration : rôle activé ou désactivé, renseignement des champs nécessaires, fournisseur connu et modèle. Les clés, les URL complètes et les identifiants intégrés ne sont pas transmis par ce mécanisme. Le contrôle de connexion explicite utilise les lectures déjà disponibles ; il n’effectue aucune inférence IA et ne prouve pas la qualité des résultats du modèle.

La santé distingue un worker jamais observé, trop ancien, présent et en cours de traitement. Les versions du web et du worker sont affichées lorsqu’elles sont transmises ; une différence déclenche une alerte. Une configuration historique qui ne contient pas encore ces métadonnées est présentée comme non transmise, sans valeur inventée.

Les coûts sont ceux du journal de KaraRecall, avec les réserves des appels non confirmés. Ils excluent les appels indépendants de Karakeep et ne constituent pas une facture du fournisseur. Les quotas journaliers et mensuels utilisent UTC ; la chronologie des favoris affichée sur l’accueil utilise l’heure de Paris.

L’espace libre concerne le système de fichiers du volume, et non la seule taille de la bibliothèque. La génération active et sa publication sont visibles. L’application ne prétend pas connaître l’existence d’une sauvegarde externe : elle affiche « Non vérifiable depuis l’application ». L’export du catalogue JSON contient des données privées et des références ; les médias n’y sont pas inclus.

Le diagnostic téléchargeable est une projection séparée : version, compteurs, états, stockage et consommation. Il exclut favoris, médias, listes de commandes, modèles, URL de services et erreurs libres. L’authentification reste nécessaire pour le télécharger.

## Commandes et limites

La suspension dans l’application empêche les prochains passages automatiques de synchronisation, recherche et préparation des bulletins. Un passage déjà engagé peut se terminer. Les commandes explicites restent utilisables ; importer manuellement ne lève pas une suspension volontaire. La suspension créée par le vidage local, distincte, est levée au prochain import. La reprise n’active pas une option désactivée dans le `.env`, notamment `SYNC_ENABLED`.

Annuler la suite d’une commande ne prétend pas interrompre une requête déjà partie chez un fournisseur. Ses résultats peuvent encore être publiés ; les éléments suivants de cette commande ne sont pas lancés. Le journal de coûts n’est pas remis à zéro. Un vidage confirmé n’est pas annulable par ce bouton.

Les clés et les paramètres de fournisseur restent dans le `.env` ou Dockhand. L’interface les explique et affiche les états publics ; elle ne propose pas de modifier des secrets ni de redémarrer les conteneurs du NAS.

## Direction visuelle et accessibilité

Surfaces translucides, fond bleu nuit, accents menthe et pervenche, bordures fines et typographie système. Un thème clair est disponible et la préférence est conservée uniquement dans le navigateur. Aucune police, bibliothèque graphique ou image décorative distante n’est chargée. Les illustrations décoratives sont dessinées en CSS et SVG.

Le même système de couleurs est appliqué aux fiches, preuves, vidéos, formulaires de revue et bulletins. Les informations opérationnelles d’une source saine sont repliables ; les erreurs et pauses restent ouvertes. Les actions de destruction sont séparées des actions de lecture.

Sur téléphone, le menu devient un panneau latéral avec gestion du focus et fermeture au clavier. Un menu fermé est exclu de la navigation. Les états ne reposent pas uniquement sur la couleur ; les textes et marqueurs restent lisibles. Les progressions utilisent des éléments natifs et les graphes des attributs SVG, compatibles avec la politique CSP sans autoriser les styles inline. Des replis opaques sont prévus lorsque la transparence est réduite ou non prise en charge ; les mouvements suivent la préférence de réduction d’animation.

## Validation et travail restant

La validation utilise des fixtures pour les états de fonctionnement, les quotas, les commandes et leurs protections. La prévisualisation visuelle locale utilise une copie du corpus privé du POC ; elle ne simule pas une connexion réelle au NAS ni aux fournisseurs. Les données privées et captures de prévisualisation sont exclues de Git.

À qualifier après déploiement : métadonnées et version du worker effectivement remontées, contrôle des endpoints réels, fidélité des contenus, usage sur les appareils habituels et restauration d’une sauvegarde du NAS. La planification de sauvegardes NAS, un navigateur de versions restaurables, les permissions multi-utilisateur et l’édition des secrets ne sont pas implémentés par cette évolution. Ces besoins ne doivent pas être présentés comme déjà couverts par un écran.

## Revue des fiches — version 0.4

Le retour d’usage montre que la refonte glass ne suffisait pas : le détail d’un outil donnait encore trop de place à la provenance et aux tâches d’entretien. La lecture quotidienne est désormais organisée en trois niveaux.

| Niveau | Contenu |
| --- | --- |
| Accéder et comprendre | Nom, usage, domaine disponible, lien principal et copie du contexte pour un assistant. |
| Approfondir | Utilité, fonctionnement, limites, liens utiles et compléments documentaires. Les textes restent attribués et leurs références se déplient. |
| Entretenir | Présentation complète, sources et identification consultables ; édition, regroupement et commande web en bas de fiche, dans un volet replié. |

Les cartes d’outils et les résultats de recherche reprennent cette priorité. Les indications d’auteur ou de vidéo ne servent plus de sous-titre d’outil. Le choix du lien principal ne réalise aucune vérification supplémentaire et n’invente pas un site lorsque l’adresse manque.

La même passe couvre les sources vidéo, les articles, leurs preuves et les bulletins : commandes de traitement ou de diffusion après le contenu ; alertes de panne visibles mais compactes ; édition secondaire ; exports regroupés. Les paramètres administratifs restent dans Administration et Activité. Les citations, révisions et anciennes routes sont conservées.

Validation locale sur une copie du corpus du POC : fiches et listes d’outils, ouverture des références vers le passage vidéo, éditeur replié, sources vidéo et article, bulletin et son éditeur. Contrôles à 390 px et en taille bureau, dans les thèmes clair et sombre. Les tests JavaScript utilisent un corpus fictif pour le choix de lien, les entrées manquantes ou non vérifiées, les références et la séparation lecture/édition. La validation des parcours sur les appareils habituels du NAS reste à confirmer.
