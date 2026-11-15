# Script de la vidéo de démonstration (environ 5 minutes)

Préparer avant de tourner : site ouvert, modèle activé. Les propositions s'ouvrent depuis la synthèse par « Découvrir mes propositions ». Prévoir une prise de secours avec « Rédaction des explications par le modèle » coupée (dans « Réglages de la simulation ») : les verdicts et les chiffres sont identiques.

| Temps | À l'écran | À dire |
|---|---|---|
| 0:00 – 0:30 | Accueil du site | « Un investisseur dit ce qu'il accepte de perdre. Ce qu'il fait quand ça baisse est autre chose. AlphaForge mesure les deux, et sait dire non. Tout ce que vous verrez est une simulation, sur des profils fictifs. » |
| 0:30 – 1:10 | Entretien vocal, 20 secondes, puis le replay de 2022 | « L'entretien se fait à la voix. Un agent classe chaque réponse dans une liste fermée, avec la citation exacte ; un second agent la critique ; le code valide. Puis trois mises en situation mesurent le comportement : ici, un marché qui baisse. Le plus prudent du déclaré et du vécu l'emporte. » |
| 1:10 – 1:50 | « Charger Amira », « Découvrir mes propositions », écran « Mini-portefeuille » | « Amira, 26 ans, risque élevé. Budget de perte : 45 %. Le portefeuille fictif compte douze positions, dont 10 % de bitcoin, pas plus. Elle travaille en technologie : son exposition à ce secteur est plafonnée à 25 %, fonds compris. Risque élevé ne veut pas dire que tout est acceptable. » Montrer le tableau « Chaque contrainte, avec sa preuve ». |
| 1:50 – 2:20 | « Recherche d'actif », taper NVDA | « NVIDIA pour Amira : compatible, score 88, mais au plus 10 % du portefeuille. Chaque ligne renvoie à une donnée datée et à sa source. » Ouvrir « Preuves ». |
| 2:20 – 3:30 | « Recommencer », « Charger Robert », « Découvrir mes propositions », « Demande d'un titre », NVDA à 20 %, justification « Tout le monde en parle » | « Robert, 59 ans, prudent, horizon de trois à cinq ans. Il veut 20 % de NVIDIA. Le verdict est calculé et figé avant que le modèle lise sa justification : en tension. La perte de stress du portefeuille passerait de 6,0 % à 18,8 %, pour un budget de 15 %. L'agent explique, cite ses preuves, et ne cède pas. Il dit aussi ce qui resterait compatible : 5 % au plus. » Montrer la ligne « Ordre des actions enregistrées ». |
| 3:30 – 4:05 | « Et si… ? », horizon de Robert à « 10 à 15 ans », puis « Lancer le test de sensibilité » | « Et si Robert visait dix ans plutôt que cinq ? Son budget de perte ne bouge pas : son comportement observé le limite aussi, et l'outil le dit. Seul un actif change de verdict, avec la règle en cause. Le test de sensibilité fait varier l'horizon, les seuils et la période : sans 2022, la perte de stress baisse. Nos seuils sont des hypothèses écrites, pas des vérités. » |
| 4:05 – 4:40 | « Pourquoi ? », onglets « Journal des actions » et « Hypothèses » ; schéma d'architecture | « Deux agents sur Amazon Bedrock appellent des outils ; le code calcule. Un vérificateur rejette tout chiffre qui ne vient pas d'un outil. Le journal des actions est écrit dans DynamoDB. Guardrails, Transcribe, Polly, CloudFront : chaque service a un rôle, et le site se redéploie tout seul à chaque fusion. » |
| 4:40 – 5:00 | Liste des limites | « Les limites : une seule crise dans cinq ans de données, des controverses saisies à la main, des hypothèses à calibrer. Les résultats sont traçables ; ils ne remplacent pas un conseiller. » |

## Questions probables du jury

| Question | Réponse courte |
|---|---|
| Pourquoi ces seuils ? | Ce sont des hypothèses d'équipe, écrites dans trois fichiers et testées en sensibilité. Aucune n'est présentée comme une norme. |
| Que se passe-t-il si une donnée manque ? | Elle est affichée « donnée manquante », jamais remplacée. Sous 60 % de critères évalués, le verdict devient « données insuffisantes ». |
| Pourquoi un FNB obligataire a-t-il baissé en 2022 ? | Les taux ont monté vite : le prix d'une obligation baisse quand les taux montent. C'est pour cela que la perte de stress inclut un choc de taux. |
| Différence avec un robot-conseiller ? | Il ne passe aucun ordre et ne conseille pas. Il mesure le comportement, montre la preuve de chaque conclusion, et dit non avec ses raisons. |
| Le modèle peut-il se tromper ? | Sur le texte, oui. Sur un chiffre, le vérificateur le rejette. Sur un verdict, non : il ne le calcule pas. |
| Et si l'univers change ? | Le moteur relit le fichier des actifs à chaque démarrage ; un test ajoute et retire des actifs. |
