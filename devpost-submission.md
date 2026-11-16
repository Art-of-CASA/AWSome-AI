# AWSome

## One-line Summary

Comprendre l'investisseur avant de composer le portefeuille : AWSome croise dialogue vocal, choix en simulation et données sur 111 actifs pour expliquer chaque proposition et ses limites.

## Problem

Une tolérance déclarée ne suffit pas à caractériser ce qu'une personne peut supporter. Une demande de titre médiatisé doit être confrontée au profil et à son effet sur tout le portefeuille.

## Solution

Entretien vocal, questionnaire, trois mises en situation, 42 critères traçables, appariement à 111 actifs et mini-portefeuille fictif. La description complète prête à copier est dans [devpost-description.md](devpost-description.md).

## Why This Matters

L'utilisateur voit la raison d'une proposition, la contrainte qui la limite et l'effet d'une modification. Le refus devient une explication vérifiable et une possibilité de discussion.

## How We Used AI

Classificateur, Critique, Découvreur et Chercheur pour le profil ; Conseiller et Explicateur avec outils pour les propositions. Modèles configurés sur Bedrock. Calculs financiers et contrôles déterministes ; contrat fermé pour la restitution financière.

## How We Used Codex

Pour cette préparation, Codex a lu le dépôt GitHub et le code local, consulté le projet Devpost, les exigences et la grille officielles, recalculé les résultats des trois personas et rédigé les textes. Aucun autre récit de développement avec Codex n'est avancé sans preuve. L'événement ne demande pas de champ dédié à Codex ni d'identifiant de session.

## Key Features

- Profil avec provenance et critères inconnus visibles.
- Replay de marché, fourchettes de résultats et titres masqués.
- Exclusions et plafonds prioritaires sur les préférences.
- Propositions, comparaison, conversation et « Et si… ? ».
- Preuves datées et traces des outils consultables.

## Architecture

Streamlit sur EC2 et CloudFront ; Bedrock pour les agents ; Transcribe et Polly pour la voix ; DynamoDB pour les traces ; S3, Systems Manager et GitHub Actions pour la livraison ; IAM et OIDC pour les accès temporaires. Guardrails provisionné, désactivé par défaut. Voir [README.md](README.md) et [documentation technique](docs/documentation_technique.md).

## Testing Instructions

Suivre le guide Windows ou macOS/Linux du README. Charger les trois personas et comparer NVIDIA. Lancer `scripts/lancer_tests.py --timeout 300` pour les suites locales. `mvp_profil/evaluer_classement.py --verifier` valide le corpus, sans appel au modèle. `scripts/tableau_personas.py` régénère le tableau des résultats.

Vérification de cette révision documentaire : recalcul local des 42 critères, 111 actifs, budgets 45/22/15 %, 57 exclusions pour Mateo et scénario NVIDIA de Robert 5,3 → 18,4 %. Corpus valide : 51 phrases, 88 couples. Pas de nouvelle mesure de précision des modèles ni de vérification fonctionnelle complète du serveur hébergé.

## Public Demo Link

https://d29e3l5vv5fmjy.cloudfront.net

## Public Repository Link

https://github.com/Art-of-CASA/AWSome-AI

## Demo Video

Lien Google Drive de la démonstration : **à renseigner**. Le champ vidéo du projet Devpost consulté est vide. Le clip promotionnel local de 20 secondes ne remplace pas une démonstration fonctionnelle avec architecture et constats.

Plan en cinq minutes : problème et Robert ; entretien et replay ; Amira ; preuves ; demande NVIDIA de Robert et confirmation ; « Et si… ? » ; architecture et traces ; limites. Script détaillé : [docs/script_video.md](docs/script_video.md).

## Screenshot Shot List

1. Accueil avec les trois personas et le replay.
2. Profil : budget de perte et provenance d'un critère.
3. Robert : demande de 20 % de NVIDIA, conflit et proposition de 5 %.
4. Mateo : exclusion de NVIDIA avec sa preuve.
5. « Et si… ? » ou détail des outils et données consultées.

Captures fonctionnelles récentes : **à rassembler** ; les visuels marketing ne sont pas présentés comme des preuves de fonctionnement.

## Submission Readiness Notes

Lecture Devpost du 15 novembre 2026, heure de Montréal : AWSome est déjà publié et rattaché au hackathon avec une date de soumission le 15 novembre à 20 h 38. **Les nouveaux textes sont des brouillons locaux ; cette préparation ne met pas à jour la page publiée.** La présence d'une soumission n'atteste pas l'envoi des livrables par courriel.

Le formulaire officiel contient trois champs spécifiques : URL de l'outil déployé, URL du dépôt Git et numéro d'équipe. Les rubriques narratives de `devpost-description.md` suivent la description actuelle ; elles ne sont pas présentées comme des questions supplémentaires imposées par l'événement.

Devpost précise que l'énoncé complet a été distribué séparément aux équipes. Ce document complet n'a pas été trouvé dans les fichiers examinés. La correspondance ci-dessous s'appuie sur les exigences officielles accessibles et sur les personas et le cas documentés dans le dépôt.

| Critère officiel | Poids | Éléments mis en avant |
|---|---|---|
| Intelligence financière et explicabilité | 40 % | Capacité/déclaré/observé, stress, exclusions, plafonds, preuves et sensibilité |
| Architecture technique et usage d'AWS | 25 % | Rôles des agents, outils, contrôles, voix, hébergement, traces et livraison |
| Expérience utilisateur et fonctionnalités | 10 % | Parcours vocal, personas, replay, comparaison, confirmation et « Et si… ? » |
| Storytelling et présentation | 25 % | Robert en ouverture, même titre pour trois profils, résultat chiffré et démonstration guidée |

Sources consultées via Devpost : [événement et critères](https://datathon-polyfinances-bnc-aws.devpost.com/), [règles](https://datathon-polyfinances-bnc-aws.devpost.com/rules), [projet existant](https://devpost.com/software/awsome).

Échéances des exigences : liens et fin des modifications le **15 novembre 2026 à 23 h 59 HE** ; vidéo de cinq minutes maximum, documentation technique PDF et one-pager PDF par courriel le **16 novembre à 14 h HE**. Destinataire : `logiciel@polyfinances.ca`, objet `Datathon - Équipe XX`. Aucun courriel n'est envoyé par cette préparation.

Noms des livrables : `EQUIPE-XX_video_datathon_2026`, `EQUIPE-XX_doc_tech.pdf`, `EQUIPE-XX_onepager.pdf`. Les documents Markdown existants ne constituent pas leurs exports PDF.

## Known Limitations

Heuristique, seuils non calibrés sur des décisions réelles, historique limité, couverture ESG et positions de fonds partielles. Précision réelle de la voix et des agents à mesurer. Parité de la version hébergée à vérifier. Guardrails désactivé par défaut. Pas de promesse de rendement, de conformité réglementaire ou de sécurité absolue.

## TODO Official Form Fields

| ID | Libellé officiel | Réponse préparée |
|---|---|---|
| 30224 | URL de l'outil déployé | https://d29e3l5vv5fmjy.cloudfront.net |
| 30225 | URL du dépôt Git | https://github.com/Art-of-CASA/AWSome-AI |
| 30226 | Numéro d'équipe | À relever dans l'inscription de l'équipe ; ne pas inventer |

## À finaliser

- [ ] Relire et publier les textes avant la fin autorisée des modifications.
- [ ] Vérifier le parcours sur la version hébergée et réaliser les captures fonctionnelles.
- [ ] Renseigner le numéro d'équipe et le lien Google Drive de démonstration.
- [ ] Exporter le one-pager et la documentation en PDF, puis remettre les livrables par le canal officiel.
