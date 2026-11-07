# Bulletins de veille automatiques

KaraRecall rédige des articles à partir des vrais favoris et de leurs preuves. Chaque découverte donne un titre et deux ou trois paragraphes qui expliquent le sujet, son intérêt et son fonctionnement, avec les limites présentes dans les sources. Les références sont conservées avec chaque paragraphe. Les captures vidéo disponibles et les captures de page de Karakeep illustrent les articles.

La première édition reprend une sélection de l’historique pour fournir un bulletin dès le démarrage, même si les favoris ont été enregistrés plusieurs mois auparavant. Les éditions suivantes couvrent la semaine ou le mois échu. La rédaction, la sélection pour diffusion et la demande d’envoi sont automatiques par défaut. La modification depuis le web reste une option.

## Raccordement initial sur le NAS

Le worker doit être démarré et disposer de ses accès Karakeep et du modèle texte. Le profil DeepSeek du manuel prépare ces paramètres. La rédaction utilise le même modèle que les fiches et partage son budget et ses quotas. Compter un appel supplémentaire par article réellement rédigé. Les articles terminés sont mis en cache et réutilisés après une interruption.

```dotenv
COMPOSE_PROFILES=automation
SYNC_ENABLED=true
LLM_ENABLED=true
DIGEST_ENABLED=true
DIGEST_WRITE_ARTICLES=true
DIGEST_INITIAL_HISTORY=true
DIGEST_INITIAL_MAX_ITEMS=6
DIGEST_AUTO_APPROVE=true
DIGEST_AUTO_SEND=true
DIGEST_WEEKLY=true
DIGEST_MONTHLY=true
DIGEST_TIMEZONE=Europe/Paris
DIGEST_TIME=08:00
DIGEST_WEEKDAY=0
DIGEST_MONTHDAY=1
DIGEST_SCOPE=added
DIGEST_WEEKLY_MAX_ITEMS=12
DIGEST_MONTHLY_MAX_ITEMS=24
KARARECALL_PUBLIC_URL=http://IP_DU_NAS:8765
```

Les clés Karakeep et LLM restent dans les champs privés de `.env` décrits dans le [manuel](INSTALLATION.md). Une installation sans modèle configuré affiche une attente de configuration. Un article avec des références inventées est refusé. Une panne ou un budget atteint conserve les articles terminés et diffère la suite. Une erreur de rédaction laisse la collecte et les anciennes éditions disponibles.

Le lundi vaut 0. Le jour du mois accepte 1 à 28. Le worker vérifie les échéances environ toutes les trente secondes entre ses imports. Il prépare le dernier intervalle échu de chaque rythme et déduplique les éditions par période. La première édition historique se prépare une seule fois dès que le catalogue contient des sources.

`DIGEST_SCOPE=analyzed` sélectionne les sources traitées pendant la période. `DIGEST_SCOPE=viewed` avec `DIGEST_TRACK_VIEWS=true` utilise les sources ouvertes dans l’interface après activation du suivi. L’édition historique utilise les dates d’ajout des favoris. Les limites retiennent les découvertes les plus récentes. Chaque rythme conserve son historique et les compléments déjà présentés sont signalés.

## Diffusion automatique par mail

Le relais et les destinataires doivent être définis une fois dans `.env`. Les secrets sont transmis au worker uniquement.

```dotenv
DIGEST_SEND_ENABLED=true
DIGEST_CHANNELS=email
DIGEST_SMTP_HOST=smtp.exemple.fr
DIGEST_SMTP_PORT=587
DIGEST_SMTP_TLS=starttls
DIGEST_SMTP_USERNAME=ton-identifiant
DIGEST_SMTP_PASSWORD=ton-secret
DIGEST_EMAIL_FROM=veille@exemple.fr
DIGEST_EMAIL_TO=destinataire@exemple.fr
```

Le worker envoie l’édition lorsque les articles ont été rédigés et que les références renvoyées existent. Le message contient une version texte et une version HTML avec les images intégrées. L’édition conserve son statut de rédaction automatique. Les références présentes ne garantissent pas à elles seules l’exactitude de chaque reformulation du modèle.

Plusieurs destinataires peuvent être séparés par des virgules, avec un maximum de vingt. Chaque destinataire reçoit son message. Pour un relais TLS implicite, choisir `DIGEST_SMTP_TLS=ssl` et son port, généralement 465. Le bouton **Valider pour diffusion** sert au parcours facultatif avec `DIGEST_AUTO_APPROVE=false`.

L’onglet Veille permet de consulter les articles, les sources et le suivi. Le lien HTML ouvre un article autonome avec ses images et le navigateur permet de l’enregistrer en PDF. Le Markdown conserve les textes et références. Le RSS privé contient les éditions sélectionnées pour diffusion et nécessite l’authentification de l’application.

## Autres canaux

La page Veille, le RSS privé et les exports permettent de lire ou diffuser une édition selon le destinataire. Le webhook envoie un objet JSON générique avec `id`, `title`, `start`, `end`, `markdown` et `html`. Il peut alimenter une automatisation de ton homelab. Une messagerie demandant son propre format nécessite une transformation dans cette automatisation.

```dotenv
DIGEST_CHANNELS=webhook
DIGEST_WEBHOOK_URL=https://ton-service.exemple/webhook/veille
DIGEST_WEBHOOK_TOKEN=
```

Utilise `DIGEST_CHANNELS=email,webhook` pour les deux. La requête contient une clé d’idempotence fondée sur l’édition et, si configuré, un jeton Bearer. L’adresse doit être HTTPS. Une adresse HTTP sur la boucle locale est acceptée pour les tests. Les redirections sont refusées.

Le suivi distingue une acceptation par le relais ou le webhook d’un résultat incertain. Une panne après le début d’un envoi conserve cet état afin d’éviter un second envoi automatique. Dans ce cas, vérifier le relais ou la destination. Les reçus restent dans l’édition, avec un identifiant de destination haché. Les adresses et secrets restent dans `.env`.

## Stockage et mise à jour

Le Compose utilise déjà le volume persistant nommé `kararecall-storage` par défaut, monté sur `/workspace` dans le web et le worker. Les éditions, images copiées, révisions, consultations et reçus sont sous `data/digests/` dans ce volume. Ils sont inclus dans la sauvegarde de `data/`. Une recréation des conteneurs conserve ces données.

Après modification du `.env`, applique les paramètres avec la commande suivante.

```sh
docker compose up -d --build
```

Une installation existante conserve son volume si `KARARECALL_VOLUME_NAME` garde la même valeur. Le [guide homelab](HOMELAB.md#sauvegarde-et-restauration) décrit la sauvegarde et la restauration dans un volume neuf.

Pour préparer un bulletin depuis le terminal, le worker accepte ces commandes.

```sh
docker compose --profile automation run --rm worker python worker.py digest-generate --kind weekly --anchor 2026-11-02
docker compose --profile automation run --rm worker python worker.py digest-run
```

Le premier prépare une édition ciblée. Le type `--kind initial` couvre l’historique disponible. Le second vérifie les échéances et traite les rédactions en attente et les diffusions automatiques. Les tests automatisés utilisent un corpus synthétique et des transports simulés. Le relais SMTP, le webhook et le lecteur RSS de l’installation restent à qualifier avec leurs paramètres réels.
