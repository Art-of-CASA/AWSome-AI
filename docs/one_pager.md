# AWSome AI — une page

**Datathon PolyFinances 2026 · Banque Nationale × AWS · simulation éducative, profils fictifs, aucun conseil financier**

## Le problème
Un investisseur dit ce qu'il accepte de perdre. Ce qu'il fait quand la baisse arrive est souvent différent. Un outil qui écoute seulement la déclaration propose des placements que la personne abandonnera au pire moment. Et un outil qui dit toujours oui n'aide personne : Robert, 59 ans, prudent, veut le titre dont tout le monde parle.

## Notre question
> Quels actifs et quel mini-portefeuille fictif correspondent à la capacité, aux préférences et au comportement observé dans nos simulations, et pourquoi ?

## L'approche agentique
| Étape | Qui décide | Ce qui se passe |
|---|---|---|
| Profil | Agents (Haiku 5.5) + code | Entretien vocal en français, questionnaire, trois mises en situation qui mesurent le comportement (replay de 2022) |
| Contraintes | Code | Exclusions, plafonds, budget de perte : le plus prudent du déclaré et du vécu |
| Appariement | Code | Verdict et score de 0 à 100 pour chacun des 111 actifs, avec ses preuves |
| Portefeuille | Code | Mini-portefeuille fictif ; tension calculée sur le portefeuille et le montant |
| Conversation | Agents Conseiller et Explicateur (Sonnet 5.5) | À l'écrit ou à la voix : « j'aimerais du Nvidia ». L'agent comprend et appelle un outil ; le code ajoute, réduit la part, ou refuse avec des alternatives |

**Le code décide ; les modèles orchestrent et expliquent.**

## Ce qui est original
- **Déclaré et observé** : les choix dans une simulation complètent la tolérance déclarée, sans prouver le comportement avec de l'argent réel.
- **Un « non » argumenté** : le verdict d'une demande est figé avant que le modèle lise la justification de la personne. Dix justifications différentes, dont une tentative de détournement, donnent le même verdict.
- **Restitution contrôlée** : le code impose verdicts, chiffres et avertissements ; le modèle choisit des explications autorisées et ne les réécrit pas librement.
- **Une exclusion ne se rachète pas** : aucune préférence ne compense une exclusion ou une tension.
- **L'inconnu reste visible** : une question sans réponse n'est jamais comblée par une valeur inventée.
- **Des règles, pas un oracle** : nous avons fait construire neuf portefeuilles par le modèle seul. Plausibles, mais différents d'un essai à l'autre et avec un risque estimé à 5,5 points près. Les règles décident ; les agents comprennent et expliquent.

## Deux situations contrastées, même titre
| | Amira, 26 ans, risque élevé, 15 ans et plus | Robert, 59 ans, risque faible à modéré, 3 à 5 ans |
|---|---|---|
| Budget de perte | 45 % | 15 % |
| NVIDIA, fiche d'actif | Compatible, score 88, plafonné à 10 % | À examiner, score 66, plafonné à 5 % |
| Demande de 20 % | En tension : plafond par titre de 10 % | En tension : la perte de stress passerait de 5,3 % à 18,4 % |
| Demande de 5 % | Ajouté, cohérent avec le profil | Ajouté, à surveiller : compatible avec les plafonds, sans acquiescement |
| Bitcoin | Accepté, plafonné à 10 % | Exclu. L'outil nomme les deux réponses qu'il devrait revoir lui-même, et n'y touche pas sans son accord |

Mateo, 41 ans, attentif à l'ESG : controverses graves, placements spéculatifs, tabac et armement sont exclus. Les exclusions de controverses et d'activités s'appliquent aussi aux positions connues des fonds ; la couverture inconnue reste affichée. NVIDIA est exclu pour lui.

## Sources de données
Jeu de départ des organisateurs, étendu à 111 actifs dans 17 devises. Prix et fondamentaux : Yahoo Finance (sous ses conditions d'utilisation). Change : Banque du Canada. Attention médiatique : Wikimedia. Controverses : sources publiques citées une à une. Tout est converti en dollars canadiens et daté.

## Capacité d'explication
Les résultats sont **traçables** : chaque conclusion renvoie à une colonne, une valeur, une date et une source, ou à une réponse du profil avec sa citation, ou à une hypothèse écrite. L'écran « Pourquoi ? » montre les outils appelés et les données lues. L'écran « Et si… ? » montre ce qui change quand une réponse change, et pourquoi.

## Sur AWS
Bedrock (Haiku 5.5, Sonnet 5.5), Transcribe et Polly pour la voix, EC2 et CloudFront pour le site, DynamoDB pour le journal, IAM, CloudFormation et déploiement automatique. Guardrails est créé mais désactivé par défaut. Les derniers correctifs sont locaux et restent à vérifier sur le site hébergé.

## Bénéfices pour l'utilisateur
Il comprend ce qui est cohérent avec sa situation, ce qui ne l'est pas, et ce qu'il faudrait changer pour que la réponse change. Il voit les limites : une seule crise dans les données, des hypothèses écrites, des données manquantes affichées.
