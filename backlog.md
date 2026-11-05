# Backlog — Mémoire

Demandes et travaux restants, sans ordre de priorité. La priorisation sera décidée avec l’utilisateur. Ce document ne déclenche ni recherche web, ni appel IA, ni changement de configuration.

## Enrichissement systématique par recherche internet

- [ ] Ajouter une étape de recherche web pour compléter chaque outil identifié : description, utilité, fonctionnement, documentation, site officiel et dépôt lorsqu’ils existent.
- [ ] Conserver les pages consultées, leur date, leur URL et une trace de lecture ; rattacher chaque enrichissement à sa source.
- [ ] Distinguer les propos de la vidéo, les descriptions de l’éditeur et les vérifications réalisées ; un site consulté ne prouve pas les performances annoncées.
- [ ] Gérer les noms ambigus, les URL tronquées, les pages absentes et les contradictions sans inventer de correspondance.
- [ ] Définir fournisseur de recherche, fréquence de rafraîchissement, cache, limites de coût et mécanisme de reprise.

## Accès naturel depuis un assistant : MCP à étudier

- [ ] Évaluer un serveur MCP pour chercher dans la bibliothèque et lire fiches, transcriptions, preuves horodatées et liens depuis un assistant conversationnel.
- [ ] Comparer MCP et API HTTP existante ; décider du périmètre sans imposer MCP à l’interface web.
- [ ] Prévoir authentification, accès en lecture seule, résultats bornés et citations jusqu’aux preuves originales.
- [ ] Valider des demandes formulées naturellement, notamment à l’oral, avec abstention lorsque l’information manque.

## Transcription, vidéo et recherche

Déjà disponible : transcription à côté de la vidéo, passages cliquables, recherche globale dans les textes transcrits et OCR. Les paroles du POC ont été transcrites localement avec Whisper ; le worker Docker appelle un service ASR configuré séparément du service vision.

- [ ] Ajouter une recherche directement dans le panneau de transcription avec surlignage et navigation au passage correspondant.
- [ ] Améliorer la présentation des extraits de recherche et l’ouverture directe du passage retrouvé.
- [ ] Évaluer une recherche sémantique ou hybride pour retrouver un besoin exprimé avec d’autres mots ; conserver les citations et mesurer les résultats sur des requêtes variées.
- [ ] Choisir et valider les services réels de transcription, vision et synthèse : Mac ou API distante, compatibilité, qualité du français, noms propres, horodatages, coûts et confidentialité.
- [ ] Améliorer l’échantillonnage des captures pour les textes brefs et documenter sa couverture ; le worker est limité à 12 images par défaut.
- [ ] Étudier le traitement des vidéos longues et volumineuses, des vidéos sans parole et la reprise indépendante des étapes après un échec.

## Navigation et revue des fiches

- [ ] Recueillir les besoins d’usage quotidien puis ajuster navigation, filtres et éléments affichés.
- [ ] Permettre la correction et la validation des synthèses marquées « À relire », des noms d’outils et des liens, en conservant leurs preuves.
- [ ] Gérer les doublons d’outils issus de plusieurs favoris et les regrouper sans perdre leurs provenances.
- [ ] Rendre les erreurs, les tâches en attente et les reprises plus faciles à comprendre et à piloter.
- [ ] Étudier les exports ou liens utiles vers AFFiNE et Wiki.js selon les usages ; aucun connecteur n’est encore implémenté.

## Déploiement et exploitation du homelab

- [ ] Déployer le Compose sur le NAS, remplir son `.env` et vérifier les connexions réelles ; le dépôt privé et les tests locaux/CI sont déjà en place.
- [ ] Importer le corpus privé du POC dans le volume du NAS sans l’envoyer sur GitHub.
- [ ] Configurer l’accès LAN et, si nécessaire, le reverse proxy HTTPS ou le VPN du homelab.
- [ ] Effectuer une sauvegarde puis un essai de restauration du volume et de la configuration.
- [ ] Mesurer mémoire, temps de traitement et espace disque sur le NAS avec un corpus représentatif ; vérifier le comportement lorsque le Mac ou une API est indisponible.
- [ ] Définir la gestion des favoris supprimés et des pièces jointes remplacées. Actuellement, les suppressions restent locales et le remplacement d’une vidéo conservée est bloqué pour préserver ses preuves.
- [ ] Évaluer une image Docker publiée dans un registre privé si la construction depuis le dépôt devient gênante pour le gestionnaire de stacks.

## État des raccordements IA

Les adresses, clés et modèles sont prévus dans `.env.example` pour trois rôles indépendants : `ASR_*` pour les paroles, `VISION_*` pour le texte des captures, `LLM_*` pour la synthèse des fiches. La synchronisation et les appels IA restent désactivés tant que leur configuration n’est pas renseignée et activée. Aucun service réel n’est sélectionné par défaut.
