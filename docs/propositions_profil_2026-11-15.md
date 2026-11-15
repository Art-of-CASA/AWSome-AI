# Propositions pour le profil investisseur : synthèse de 5 analyses

Date : 15 novembre 2026. Cinq agents ont travaillé en parallèle sur une copie du dépôt, avec le conflit de fusion d'`app.py` résolu. Aucun fichier de `/workshop` n'a été modifié pendant ce travail, et aucun service AWS ni modèle réel n'a été appelé : les réponses du modèle sont simulées.

| Agent | Sujet | Dossier de travail |
|---|---|---|
| 1 | Questionnaire adaptatif fondé sur la valeur de l'information | `/tmp/agent1/adaptatif/` (interrompu avant son rapport ; chiffres lus dans ses fichiers de résultats) |
| 2 | Extraction conversationnelle et questions contextuelles | `/tmp/agent2/RAPPORT_AGENT2.md` |
| 3 | Validité, réglementation canadienne, parcours personnalisés | `/tmp/agent3/RAPPORT_AGENT3.md` |
| 4 | Architecture multi-agents, contrat Profil v2, agent d'explication | `/tmp/agent4/agent4/RAPPORT_agent4.md` |
| 5 | Prototype du moteur d'appariement et utilité de chaque critère | `/tmp/agent5/appariement/RAPPORT_agent5.md` |

Les dossiers `/tmp` disparaissent au redémarrage de la machine : copier ce qui doit être gardé.

Limites communes : les profils synthétiques sont tirés au hasard et ne représentent pas de vrais utilisateurs ; le modèle simulé est optimiste (le critique est souvent toujours d'accord) ; les corpus de phrases ont été écrits par les agents eux-mêmes. Aucun chiffre ci-dessous ne mesure le vrai Claude ni de vrais utilisateurs.

---

## 1. Ce qu'il faut retenir

1. **Retirer des questions qui comptent pour le budget ne fait gagner que 3 à 4 questions.** Le pilote adaptatif de l'agent 1 ne pose une question que si sa réponse peut encore changer le budget ou la composante limitante, prouvé par énumération des réponses restantes. Sur 1 000 profils synthétiques : **34 → 30,6 questions en moyenne (minimum 28)**, avec 0 budget moins prudent que le questionnaire complet.
2. **Le vrai gain vient de déplacer les questions d'appariement et de préférence vers une étape de détail ultérieure.** L'agent 5 a mesuré l'effet de chaque critère sur l'ensemble des actifs compatibles. Environ **11 des 34 questions** (q_a1 excepté, voir 3) ne changent aucun verdict ou ne servent qu'au tri : il en resterait environ 23 au départ.
3. **Des parcours personnalisés gardent exactement le même résultat.** L'agent 3 aiguille tôt (court terme, retraite, jeune à long horizon, novice, ESG ou non) et a vérifié sur 4 000 profils aléatoires : 0 écart de budget, 0 écart d'exclusion. Personas : Amira 37 → 31, Robert 37 → 31, Mateo 37 → 36 ; court terme 37 → 29 (26 en version allégée), novice 37 → 27.
4. **Le parcours conversation coûte aujourd'hui plus de questions que le questionnaire.** Agent 1 : 36 en tout (10 tours + 26 questions restantes) contre 34. Cause structurelle relevée par l'agent 2 : 16 critères, 10 tours, au plus 2 critères par question, donc au moins 4 critères partent aux compléments. Avec les questions contextuelles et le groupe G02, il faut 12, 13 et 11 tours pour tout couvrir (Amira, Mateo, Robert), contre 14, 14 et 13.
5. **Une exclusion dynamique rend presque tout l'univers « inconnu ».** Prototype de l'agent 5 : avec « rien de lié à Elon Musk » et une recherche réaliste (seul TSLA vérifié), **0 actif compatible sur 111**, 80 inconnus. Le chercheur doit produire des « non concerné » explicites, au moins sur la liste courte.
6. **Le réglage G3 = canada_usa des personas est le critère qui exclut le plus** : 26 actifs exclus et 19 inconnus sur 111. Ce n'est pourtant qu'une « hypothèse de test, défaut prudent ».

---

## 2. Défauts trouvés en chemin

| Défaut | Où | Trouvé par | Correction proposée |
|---|---|---|---|
| B1 « jamais » plante la synthèse (`KeyError`) et `recouper_rupture` (`ValueError`) | `synthese.py:77`, `profil.py:162` et suiv. | les 5 | Correctif complet : `/tmp/agent3/correctif_jamais.patch`. « Jamais » compte comme la classe 50 % ou plus, jamais au-delà ; alerte ; décote B3 ; H1 reste `non_teste` si rien n'est vendu ; R1 l'inclut. Puis `scripts/sync_grille.py`. |
| Fourchette « croissance » (80 % d'actions) rangée au niveau 5 au lieu de 4 : perte de stress de 45 % au lieu de 32 % | `simulations.VERS_B6` | 3 | Ranger « croissance » au niveau 4 ; afficher un scénario de crise dans les fourchettes (les « mauvaises années » affichées ne vont que de −6,5 % à −12,5 %). |
| La question A5 réellement posée est lue comme visant aussi l'horizon : « six mois » n'est pas lu | `reponses_directes._cibles_question` | 2 (déjà M4 de la revue) | Retirer A2 quand le libellé parle d'argent disponible hors placement ; intersecter avec `criteres_question`. Le test existant utilise un autre libellé et ne le voit pas. |
| Clarifications jamais posées quand le modèle est lent (critère toujours « en analyse ») | `moteur_conversation.suivante` | 2 | Ne plus bloquer un critère dont la dernière réponse a déjà été analysée une fois. |
| E1 non monotone : passer de « limiter » à « exclure_directe » rend 8 actifs compatibles | `config/correspondances.json` | 5 | Aligner les deux règles sur `energie_fossile_via_fonds` et `partielle`. |
| A2 et B7 utilisent `recovery_days` (creux → retour, 403 j en moyenne) au lieu de `underwater_days` (sommet → retour, 711 j) | `criteres_appariement.csv`, `sync_grille.py` | 5 | Remplacer la colonne. |
| « En fait » rouvre tous les critères connus | `entretien.demande_correction` | 2 (M12) | Version ciblée testée : 140 → 29 critères rouverts sur 14 phrases, sans oubli. |
| Aucune règle ne compare les connaissances (C1) au risque demandé, exemple pourtant cité par l'Instruction générale 31-103CP | `profil.incoherences` | 3 | Règle R10 : C1 débutant avec B1 ≥ 40 %, « jamais », B5 très élevé ou D12 « accepte » → précision expliquée. |
| Textes encore à « 66 actifs » alors que l'univers en compte 111 | `docs/criteres_profil_actifs.md`, `hypotheses_profil.json` | 5 | Mettre à jour. |
| `entretien.replique()` jamais appelé (code mort) | `entretien.py` | 4 (déjà m2) | Supprimer. |

---

## 3. Utilité de chaque critère

Croisement de la mesure de l'agent 5 (effet réel sur la synthèse et sur les verdicts du prototype d'appariement) et du classement réglementaire de l'agent 3 (Règlement 31-103, art. 13.2 et 13.3 ; Instruction générale 31-103CP).

| Rôle mesuré | Critères | Avis réglementaire et action |
|---|---|---|
| Synthèse seulement | A2, A4 à A9, B1, B1R, B2, B3, B5, B6, B7, D9 | Garder. B1R est un recoupement utile (cas de Robert). |
| Appariement seulement | A3, A12, C1, D1, D4, D6, E1, E2, E5, F2 | Garder ; E1, E2, E5, F2 peuvent passer derrière une question-filtre « voulez-vous exclure quelque chose ? » (agent 3). |
| Les deux | A10, D2, D12, G3 | Garder. D2 et D12 peuvent devenir oui/non au départ, le pourcentage plus tard. |
| Tri seulement | D3, D5, D7, D11 | Déplacer vers l'étape de détail. D3 et D7 sont jugés superflus par l'agent 3. |
| Aucun effet calculé | A1, B4, C2, D8, D8O, E4, G1, G2, H1 | A1 est **obligatoire** (situation personnelle) : le garder et ajouter l'âge. B4 superflu. G1, G2 utiles à la construction du portefeuille, plus tard. |

Questions à fusionner : D6 et E5 (listes d'exclusions en double) ; D1, D2, D12 (poser D12 d'abord).

### Informations manquantes pour l'étape suivante

- **Besoin de risque** : montant cible, date, apports. À comparer au rendement permis par le budget, jamais pour relever le budget (agents 3 et 5).
- **Âge ou année de naissance**, demandés par l'Instruction générale.
- **Retraits chiffrés** : montant, date, fréquence (A9 détaillé), date du projet (A3 = projet_date).
- **Montant exact**, positions déjà détenues (actions de l'employeur), devise de dépense, nombre de positions souhaité.
- **Comptes** : CELIAPP, FERR, CRI dans G2 ; revenus garantis hors portefeuille (A11, prévu dans la grille mais jamais posé).
- **Pourcentages non configurés** : secteur d'emploi (A12), part hors CAD (D4), « limiter » les fossiles (E1), exposition indirecte tolérée par FNB.

---

## 4. Questionnaire en deux temps (proposition convergente)

**Temps 1, profil de base (environ 23 questions, moins selon le parcours).**
- Aiguillage : A3, A2, A1 avec l'âge, C2, question-filtre sur les exclusions.
- Sécurité (bandes 0 et 1 de `pilotage.py`) : A9, A10, A5, A7, toujours posées en premier.
- Capacité et tolérance, avec arrêt dès que le budget ne peut plus changer (pilote de l'agent 1), en gardant B1, B1R, le replay et D8 avec l'effet de mode si des titres individuels sont possibles.
- Contraintes d'exclusion qui changent les verdicts.

**Temps 2, détail du portefeuille (seulement si la réponse change la proposition en cours).** Proposé par l'agent 5 :
1. accès aux cotations américaines, seulement si un candidat est inconnu à cause de G3 ;
2. pourcentages manquants, seulement si la pondération proposée dépasse un défaut prudent ;
3. départage par D3, D5, D7 ou D11 quand deux candidats sont à égalité, ou FNB contre titres directs ;
4. nouvelle recherche du chercheur sur la seule liste courte ;
5. quiz C1 seulement si un actif complexe (9 sur 111) est candidat ;
6. montant exact, compte, retraits datés.

À vérifier avant de déplacer une question : les règles R4 et R7 utilisent D5 et E1.

### Parcours de l'agent 3 (extrait)

| Parcours | Déclencheur | Sauté (justification) | Ajouté |
|---|---|---|---|
| Court terme | A2 = moins de 3 ans | B1R, fourchettes : la capacité (8 %) borne déjà le budget | montant et date de l'achat ; somme garantie ailleurs ? |
| Retraite | A1 = pré-retraite ou retraite | D3, D7 ; A6 n'est **pas** déduit | A11 revenus garantis, retraits chiffrés, FERR et CRI |
| Jeune long terme | études ou début de carrière, A2 ≥ 10 ans | D3, D7 ; A9 et A10 fusionnées si « ni retrait ni revenu » | CELIAPP, montant cible |
| Novice | C2 = aucun | B3 (déduit : jamais vécu de baisse) | explication de chaque terme |
| Sans exclusion | question-filtre « non » | E1, E2, E4, E5, F2 (valeurs énoncées par l'option) | — |

Prérequis d'intégration : un statut `non_requis`, sinon la synthèse compte les critères sautés comme inconnus et applique les réglages prudents.

---

## 5. Conversation plus courte (agent 2)

- **14 questions contextuelles (V01 à V14) et 2 groupes (G01 activité, G02 expérience)**, dans `/tmp/agent2/mvp_profil/questions_conversation.py`. Exemple : un retraité reçoit « Les revenus de ce placement seront-ils indispensables pour compléter vos rentes… ? ». Une variante vise exactement les mêmes critères et garde les mots des valeurs ; l'âge, les enfants ou le travail autonome servent seulement à formuler, jamais à remplir un critère.
- **Déductions sûres ajoutées** : retraité → A12 et A6 = retraite ; A12 = étudiant → A1 = études. Refusées volontairement : âge → A1, parent → A8, autonome → A6.
- **Lecture étendue par règles (`regles_contexte.py`)** : 53 couples sur 65 tranchés sans IA sur son propre corpus, mais **précision de 0,58 au premier jeu adverse**. À ne pas activer avant un corpus annoté par quelqu'un d'autre.
- **Prompts v2** (`prompts_agent2.py`, non activés) : type de preuve obligatoire, liste fermée de déductions, liste de suppositions interdites, québécismes. +27 % de taille de requête. Protocole d'évaluation et critères d'acceptation chiffrés dans son rapport, section E.
- **Budget de tours** : passer à 12 tours, ou sortir D3 de la conversation (une liste de régions se coche plus vite en QCM).
- Deux étiquettes du projet sont des suppositions selon la documentation : P30 (A12 = étudiant tiré de « je termine mon baccalauréat ») et le persona Robert (A8 = 0 tiré de « enfants adultes »).

---

## 6. Intégrations avec d'autres agents (agent 4)

- **Coût mesuré** sur un parcours simulé : 28 appels, environ 95 k jetons d'entrée, **≈ 1,4 ¢ US par profil** (borne haute ≈ 6 ¢). Le coût est négligeable ; la latence du classificateur compte davantage. Tarif tiré d'agrégateurs, la page officielle n'ayant pas pu être lue.
- **Garder l'orchestration maison** pendant le datathon. Strands, AgentCore et Bedrock Agents sont disponibles en us-east-1 avec Haiku 5.5, mais moins réversibles et moins testables hors ligne.
- **Contrat Profil v2** (`/tmp/agent4/agent4/profil_v2.py`, Pydantic, aller-retour sans perte testé sur les 3 personas) : valeur, source, nature, citation, confiance, statut, date, inconnues et réglages prudents. Une `vue_agents()` sans aucune citation sert aux agents suivants (5 k caractères contre 24 k).
- **Agent d'explication à outils** (`agent_explication.py`) : il ne voit que des faits calculés, et le code refuse ticker inventé, règle non étayée, nombre inventé, inconnue masquée, statut contredit et conseil personnalisé ; après une correction refusée, un gabarit déterministe s'affiche. 7 scénarios testés.
- **Agents écartés** : planificateur d'entretien (`pilotage.py` décide déjà) ; reformulateur en direct (plutôt pré-générer 34 questions × 3 niveaux, relues par l'équipe).
- **Gains de latence** : choix oral par expression régulière (« la deuxième ») avec le modèle en repli ; classificateur qui omet les critères sans information ; préfiltre des facultatifs ; consigne dédiée pour le critique du chercheur.
- **Données personnelles** : le concept du chercheur (« l'entreprise de mon mari ») part vers Wikipédia et dans le cache partagé, et la clé `kw_dyn_<slug>` en garde le libellé. Contrôler avant tout appel web, utiliser une clé sans libellé lisible.
- **Après le datathon** : dater chaque valeur (`profil.entree` ne date rien) pour un agent de suivi ; Bedrock Guardrails en seconde couche de conformité.

---

## 7. Moteur d'appariement (agent 5)

Prototype déterministe : `/tmp/agent5/appariement/moteur.py`. Ordre exclusions → plafonds (critères dynamiques au même rang) → seuils → préférences → informations ; verdict = pire critère (exclu > inconnu > à plafonner > compatible), avec une explication qui cite la règle et la phrase de l'utilisateur.

| Cas (111 actifs) | compatible | à plafonner | inconnu | exclu |
|---|---|---|---|---|
| Amira | 52 | 14 | 19 | 26 |
| Mateo | 34 | 19 | 12 | 46 |
| Robert | 56 | 8 | 19 | 28 |
| Amira + Shopify exclu + Musk (recherche complète) + banques ≤ 10 % | 42 | 22 | 19 | 28 |
| Idem, Musk avec seul TSLA vérifié | 0 | 3 | 80 | 28 |

Tests de propriétés (300 profils par famille, 0 échec) : un profil plus prudent n'a jamais plus d'actifs compatibles (sauf E1, signalé) ; un critère incertain ne retire jamais un actif ; un inconnu du chercheur n'est jamais compatible ; les FNB exposés sont plafonnés, pas exclus ; les préférences ne changent aucun verdict ; le moteur est déterministe.

Conventions à valider par l'équipe : un critère incertain transforme une exclusion en « inconnu » ; A10 = essentiel, A3 = coussin de sécurité et C1 = débutant sont en réalité des exclusions ; E2 = « aucune » n'était pas décrit.

**Bornes** : l'écart [8, 15) contre ≤ 15 signalé par la revue est corrigé. Il reste 8 % exactement (« modérée » côté actif, ≤ 8 côté profil) et deux conventions dans le dépôt. Proposition : toute limite du profil est un maximum inclus, toute bande d'actif comparée à une limite est fermée à droite, bornes lues dans un seul fichier, test sur chaque borne.

---

## 8. Ordre de mise en œuvre proposé

| # | Action | Effort | Fichiers |
|---|---|---|---|
| 1 | Résoudre le conflit d'imports d'`app.py` | 5 min | `app.py` |
| 2 | Appliquer le correctif « jamais », puis `sync_grille.py` | 30 min | `synthese.py`, `profil.py`, grille |
| 3 | Corriger `VERS_B6`, la lecture A5, la monotonie de E1, `underwater_days` | 1 h | `simulations.py`, `reponses_directes.py`, `correspondances.json`, grille |
| 4 | Intégrer le moteur d'appariement et ses tests de propriétés | ½ jour | nouveau `mvp_profil/appariement.py`, `lancer_tests.py` |
| 5 | Chercheur : « non concerné » explicites sur la liste courte | 2 à 3 h | `chercheur.py` |
| 6 | Exporter le Profil v2 et brancher l'agent d'explication sur la page finale | ½ jour | `app.py`, nouveaux modules |
| 7 | Statut `non_requis`, question-filtre exclusions, parcours personnalisés | ½ à 1 jour | `criteres.py`, `pilotage.py`, `synthese.py` |
| 8 | Questions contextuelles G02, correction ciblée, attente non bloquante | 2 h | `questions_conversation.py`, `entretien.py`, `moteur_conversation.py` |
| 9 | Déplacer les questions de tri vers l'étape de détail | 1 jour | `criteres.py`, `pilotage.py`, `app.py` |
| 10 | Corpus indépendant, puis lecture étendue et prompts v2 | après mesure réelle | `regles_contexte.py`, `agents.py` |

Validation avec de vrais utilisateurs (agent 3) : test-retest, comparaison voix contre écrit, validité convergente avec l'échelle de Grable et Lytton ; 50 à 100 participants pour une étude, 10 à 20 faisables pendant le datathon.
