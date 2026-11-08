# Formats et couverture des contenus

État de l’implémentation 0.5.0, 8 novembre 2026. L’import conserve tous les favoris. Importer des métadonnées, obtenir du texte, rédiger un résumé et analyser une vidéo sont quatre opérations distinctes.

## Contrat Karakeep

Le schéma officiel distingue les favoris `link`, `text`, `asset` et `unknown`. Un favori fichier annonce `image` ou `pdf`. Les pièces jointes ont leur propre type : HTML extrait, capture, PDF, capture de fichier, bannière, archive complète, vidéo, fichier du favori, archive préextraite, dépôt utilisateur, avatar ou inconnu. Un lien peut référencer un fichier HTML, une image, une capture, un PDF et une vidéo. [Schéma officiel lu, révision du 8 novembre](https://github.com/karakeep-app/karakeep/blob/a891444dae92a673df800185ae3ad1d7b0fef61d/packages/open-api/karakeep-openapi-spec.json), [documentation 0.30](https://docs.karakeep.com/v0.30.0/api/get-a-single-bookmark).

Ce contrat décrit les réponses possibles de l’API. Il ne prouve ni la version du NAS, ni les formats que son écran d’envoi accepte, ni la présence du contenu pour chaque hébergeur. Le diagnostic local compte les types effectivement observés. Audio seul, DOCX et autres fichiers non décrits restent inventoriés et signalés comme non pris en charge ; leur suffixe n’entraîne pas l’exécution d’un programme.

## Matrice fonctionnelle

| Contenu reçu | Traitement | Limites affichées |
|---|---|---|
| Site ou article avec texte/HTML | Nettoyage HTML, preuve de page, recherche et résumé français si le LLM est activé | Le résumé reste attribué à la source ; couverture des longs textes indiquée |
| Site avec HTML dans une pièce jointe | Lecture bornée du fichier Karakeep, archivage et empreinte de provenance | Échec visible, reprise explicite ; aucune visite automatique de l’URL originale |
| Site collecté mais texte absent de la liste | Lecture de l’API de contenu Karakeep | Pagination bornée et versions cohérentes ; aucune synthèse du document à partir du seul titre |
| Collecte en attente, en échec ou accès privé | Métadonnées conservées, nouvelles réponses importées au passage suivant | Le contenu inaccessible reste indiqué comme absent |
| Note texte, avec ou sans URL | Preuve de note, recherche, export, résumé configuré | Note personnelle distincte des propos d’un éditeur |
| PDF autonome ou joint à un lien | Original, texte par page via Poppler ; OCR des pages sans texte sur activation | 20 Mio maximum, limites de pages/temps/mémoire ; pagination et troncature visibles |
| PDF numérisé | Aperçu de page puis OCR configuré, avec reprise et budget | Sans OCR activé, aucun texte n’est inventé |
| PDF protégé ou endommagé | Échec explicite de l’extracteur ; conservation des anciennes preuves | Le déchiffrement sans mot de passe n’est pas proposé ; essai réel protégé à qualifier |
| Image JPEG, PNG, WebP ou GIF | Original ; OCR sur activation et JPEG normalisé pour le modèle | 20 mégapixels, 20 Mio ; format illisible signalé |
| Animation GIF ou WebP | OCR de la première image uniquement | Couverture partielle, nombre d’images et absence d’analyse du mouvement affichés |
| TIFF, BMP et autres formats d’image | Import et original ; échec explicite si OCR demandé | Aucun OCR prétendument terminé ; conversion éventuelle à étudier selon les formats réels |
| Vidéo jointe, Instagram/YouTube/autre | Vidéo locale, sous-titres textuels embarqués si configurés, ASR et OCR configurés | Durée/taille bornées, étapes indépendantes, écran échantillonné ; silence/sans audio traité séparément |
| Lien Instagram/YouTube sans vidéo jointe | Textes fournis par Karakeep uniquement | Pas de transcription ni d’analyse vidéo complète ; pas de téléchargement direct chez l’hébergeur |
| Bannière, capture et image du favori | Aperçu local normalisé, sans IA | Une miniature n’est pas une analyse du contenu |
| Archive complète, archive préextraite, dépôt utilisateur ou pièce jointe inconnue | Référence inventoriée ; couverture limitée explicitement | Aucun dépaquetage ni exécution automatique ; fichiers supplémentaires non extraits signalés |

Toutes les cartes ont un aperçu : image conservée, image d’une vidéo, preuve existante ou couverture générique explicite. Les téléchargements exigent le réglage habituel `DOWNLOAD_MEDIA`; l’affichage du secours ne l’exige pas.

## Dans l’application

**Administration → Couverture des contenus** donne les compteurs par type et par couverture. Chaque compteur ouvre les sources concernées. **Sources → Couverture** filtre avant pagination. La fiche explique ses limites dans **Couverture du contenu** : métadonnées seules, contenu disponible, analyse partielle, analyse configurée terminée ou format non pris en charge. « Terminée » concerne les étapes et limites configurées ; l’écran d’une vidéo reste échantillonné et la fidélité du résumé n’est pas certifiée.

Les erreurs et pauses restent visibles séparément. Une ancienne synthèse conservée ne transforme pas un nouvel échec d’extraction en succès. Les originaux, preuves, traductions et synthèses conservent leurs rôles et références respectifs.

## Qualification reproductible

Les tests `test_content_matrix.py`, `test_all_bookmarks.py`, `test_documents.py`, `test_media_worker.py` et `test_source_enrichment.py` couvrent l’import sans doublon, les notes, l’HTML inline/séparé, les types inconnus, les aperçus, l’authentification, la recherche/export, le PDF natif/joint/numérisé/corrompu, les quatre formats image, une animation limitée à sa première image, la vidéo avec/sans audio, les sous-titres, les reprises et les quotas. Les dépendances média et Poppler sont testées dans le worker Docker en CI. Ces tests utilisent des contenus fictifs, pas les comptes du propriétaire.

Restent à qualifier sur l’installation : version et formats d’envoi acceptés par Karakeep, PDF réellement protégés, hébergeurs et contenus privés, fidélité des moteurs réels, RAM et délais sur le NAS. Le [pilote](PILOTE.md) produit désormais l’inventaire sans contenu privé.
