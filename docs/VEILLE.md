# Bulletins de veille

L’onglet **Veille** prépare une édition hebdomadaire ou mensuelle avec les découvertes de la période. Chaque présentation reprend les fiches existantes avec description, utilité, fonctionnement, liens et preuves. Les images disponibles sont copiées avec l’édition. La préparation utilise les résumés déjà conservés et ne déclenche aucun appel supplémentaire à un modèle.

## Préparer et relire

1. Ouvre **Veille**, choisis semaine ou mois, puis une date de référence. Le bulletin couvre l’intervalle complet qui précède cette date. Une date dans la semaine du 2 novembre produit le bulletin du 26 octobre au 1er novembre. Une date en novembre produit le bulletin d’octobre.
2. Clique sur **Préparer le bulletin**. Les sources ajoutées pendant cette période sont retenues par défaut. Les favoris parlant du même outil sont regroupés lorsque leur nom et leur périmètre de liens concordent. Les articles et notes sans outil restent des découvertes à part entière.
3. Ouvre **Relire et composer le bulletin** pour modifier le titre, l’introduction, les rubriques et les présentations, ou retirer un contenu et son image. Enregistre, puis utilise **Valider pour diffusion** après relecture. Les références et les versions précédentes sont conservées.
4. Le lien **HTML / imprimer en PDF** ouvre un article autonome avec ses images. Utilise l’impression du navigateur pour l’enregistrer en PDF. L’export Markdown privilégie les textes, liens et références. Le **RSS privé** contient les éditions validées et nécessite l’authentification de l’application dans le lecteur RSS.

Un brouillon peut être repréparé depuis les sources. Son état précédent reste archivé. Une édition déjà validée ou diffusée garde son contenu lors des passages programmés. Une période vide est enregistrée comme telle et ne peut pas être validée pour envoi.

## Programmer la préparation sur le NAS

Active le worker et les périodes souhaitées dans `.env`.

```dotenv
COMPOSE_PROFILES=automation
DIGEST_ENABLED=true
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

Le lundi vaut 0. Le jour du mois accepte 1 à 28. La préparation a lieu au premier passage du worker après l’heure prévue, avec contrôle environ toutes les trente secondes entre les imports. Après une interruption, le worker prépare le dernier intervalle échu pour chaque rythme activé. Il réutilise une édition existante pour cette période.

`DIGEST_SCOPE=analyzed` sélectionne les sources traitées pendant la période. Ce suivi est disponible sur les nouveaux traitements, ou via la date des résumés existants. Pour une veille fondée sur la consultation, choisis `DIGEST_SCOPE=viewed` et `DIGEST_TRACK_VIEWS=true`. Le web conserve alors une trace quotidienne des sources effectivement ouvertes dans l’interface. Le suivi commence à son activation.

La limite retient les découvertes les plus récemment ajoutées, traitées ou consultées. Le bulletin mensuel regroupe les rubriques et indique les compléments déjà présentés dans une précédente édition mensuelle. Les rythmes hebdomadaire et mensuel gardent des historiques distincts.

## Diffuser par mail

Configure un relais SMTP autorisé à envoyer depuis ton adresse. Les secrets sont transmis au worker uniquement.

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
DIGEST_AUTO_SEND=false
```

Plusieurs destinataires peuvent être séparés par des virgules, avec un maximum de vingt. Chaque destinataire reçoit son propre message. Le mail contient une version texte et une version HTML avec images intégrées. Pour un relais en TLS implicite, choisis `DIGEST_SMTP_TLS=ssl` et son port, généralement 465.

Après validation du bulletin, **Demander l’envoi** enregistre la demande pour le worker. Avec `DIGEST_AUTO_SEND=true`, la validation demande aussi l’envoi. Une génération programmée produit un brouillon à relire. Les envois restent soumis à `DIGEST_SEND_ENABLED=true` et au choix des canaux.

Pour une diffusion entièrement automatique, active aussi `DIGEST_AUTO_APPROVE=true`, avec `DIGEST_ENABLED=true`, `DIGEST_AUTO_SEND=true` et `DIGEST_SEND_ENABLED=true`. Les nouvelles éditions programmées sont alors sélectionnées pour diffusion selon ce choix. Elles portent la mention de rédaction automatique à relire. Un brouillon déjà modifié manuellement conserve sa relecture avant diffusion.

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

Le premier prépare le brouillon ciblé. Le second vérifie les échéances et traite les demandes de diffusion déjà validées. Les tests automatisés utilisent un corpus synthétique et des transports simulés. Le relais SMTP, le webhook et le lecteur RSS de l’installation restent à qualifier avec leurs paramètres réels.
