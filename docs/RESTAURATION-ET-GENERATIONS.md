# Retrouver une publication et restaurer le service

[🇫🇷 Français](RESTAURATION-ET-GENERATIONS.md) · [🇬🇧 English](en/recovery-and-generations.md)

## Ce qui existe

Les générations publiées sont immuables. `data/current.json` sélectionne une publication cohérente, avec ses sources, preuves, médias et fiches. Les journaux d’usage, les commandes en file, les caches, les bulletins et la configuration ont une vie séparée. Une ancienne génération constitue un historique local ; elle ne constitue pas une sauvegarde externe.

La commande suivante inventorie cet historique sans changer de publication :

```sh
docker compose exec -T web python -m kararecall.recovery
```

Pour vérifier l’intégrité d’une génération dont l’identifiant figure dans le rapport :

```sh
docker compose exec -T web python -m kararecall.recovery --generation IDENTIFIANT_HEXADECIMAL
```

Cette lecture vérifie catalogue, références, originaux, images, HTML complémentaire et empreintes d’aperçus. Elle ne déplace aucun pointeur et ne change pas les budgets. Une génération absente, un chemin invalide ou un fichier incohérent produit un échec. La présence d’une génération valide ne prouve pas qu’une sauvegarde a été copiée hors du NAS.

## Retour à une sauvegarde : parcours retenu

Le parcours d’exploitation reste la restauration dans un **volume neuf**, après arrêt des écritures sur le volume à sauvegarder. Conserver la configuration privée et le tag commun des deux images, restaurer l’archive dans le volume neuf, puis exécuter `verify_storage.py`. Vérifier une fiche ancienne, une citation, un article et une lecture vidéo avant de changer le volume utilisé par les services. Le volume précédent reste disponible pour revenir en arrière. [Commandes de sauvegarde et restauration](HOMELAB.md#sauvegarde-et-restauration).

Après une restauration ancienne, rapprocher le journal d’usage des dépenses réellement engagées depuis la sauvegarde. Revenir à une ancienne archive ne remet pas à zéro la facture du fournisseur. Garder les envois de bulletins suspendus tant que leur suivi n’a pas été rapproché : une archive plus ancienne peut ignorer un envoi déjà effectué.

## Étude d’un bouton de retour à une génération

Un simple changement de `current.json` ne suffit pas. Le worker pourrait réappliquer immédiatement son état courant ; des commandes manuelles et diffusions pourraient reprendre ; l’ancienne génération pourrait ne pas conserver tous les médias cités. Un futur retour depuis l’interface devra donc :

1. Acquérir le verrou du worker, suspendre l’automatisation et présenter le nombre de sources/fiches avant et après.
2. Vérifier intégrité et compatibilité du schéma, puis préparer une **nouvelle** génération à partir de la sélection, sans modifier l’ancienne.
3. Préserver le journal d’usage actuel et les suivis d’envoi ; mettre à l’écart les commandes non terminées et réconcilier les empreintes des travaux.
4. Publier atomiquement, journaliser la sélection et conserver la génération courante précédente pour annuler le retour.
5. Demander une reprise explicite, après vérification des médias et citations.

Ce bouton n’est pas livré comme fonction opérationnelle. L’inventaire et le contrôle en lecture seule sont disponibles ; le retour par volume neuf reste le parcours documenté. Aucun écran ne déclare une sauvegarde « saine » sur la seule présence de fichiers locaux.

## Preuve d’une sauvegarde externe

Une future attestation devra provenir du système qui copie réellement les archives : date, destination autorisée, empreinte de l’archive, version des images et résultat d’une restauration dans un volume distinct. Sans cette observation, l’administration garde **Sauvegarde non observée**. La qualification de la restauration et du stockage externe reste une opération sur le NAS.
