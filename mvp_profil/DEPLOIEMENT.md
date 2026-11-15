# Déploiement du MVP sur AWS

> Les identifiants du compte, des ressources et les adresses IP ont été retirés de ce fichier (remplacés par `<...>`). Ils se retrouvent dans la console AWS, grâce à l'étiquette `projet = alphaforge-mvp`. Ne les remettez pas dans le dépôt.

Déployé le 14 novembre 2026 dans le compte du datathon (`<ID_DU_COMPTE>`), région us-east-1. Le site appelle Claude Haiku 5.5 sur Amazon Bedrock grâce au **rôle IAM du serveur** : aucune clé ni aucun identifiant à manipuler.

**Adresse : https://d29e3l5vv5fmjy.cloudfront.net** (HTTPS, micro disponible ; adresse directe en HTTP : http://<IP_PUBLIQUE_INSTANCE>:8501)

L'accès est limité aux adresses IP de l'équipe : `<IP_EQUIPE_1>` et `<IP_EQUIPE_2>` (ajoutée le 14 novembre 2026). Depuis un autre réseau, il faut ajouter l'IP à la fonction CloudFront et au groupe de sécurité (voir plus bas).

## Architecture

```
Navigateur ──HTTP 8501──▶ EC2 t3.small (Streamlit, rôle IAM alphaforge-mvp-ec2)
                              ├──▶ Amazon Bedrock : us.anthropic.claude-haiku-5-5 (classificateur + critique)
                              └──▶ S3 : paquet du site (lu au démarrage)
```

## Ressources créées (toutes étiquetées `projet = alphaforge-mvp`)

| Ressource | Identifiant | Rôle |
|---|---|---|
| Instance EC2 | `<ID_INSTANCE>` (t3.small, Amazon Linux 2023) | Fait tourner Streamlit en service systemd (`alphaforge`) |
| Rôle IAM + profil d'instance | `alphaforge-mvp-ec2` | Droits minimaux : `bedrock:InvokeModel` sur Haiku 5.5 seulement, lecture de `s3://…/app/*`, et Session Manager (SSM) pour la maintenance |
| Groupe de sécurité | `<ID_GROUPE_SECURITE>` (`alphaforge-mvp-sg`) | Port 8501 ouvert à CloudFront (liste de préfixes) et aux adresses de l'équipe (quatre au 15 novembre 2026) ; aucun port SSH. À faire : retirer les adresses de l'équipe pour ne garder que CloudFront |
| Bucket S3 | `alphaforge-mvp-<ID_DU_COMPTE>-us-east-1` | Paquet du site (`app/mvp_profil.zip`), accès public bloqué |

Coût indicatif : t3.small environ 0,02 $ US/h, plus les appels Haiku (quelques cents par questionnaire), facturés au compte de l'événement.

Dernière mise à jour du code : 14 novembre 2026, 19 h 45 : précisions et question ouverte à la voix (composant vocal unique, en veille pendant les QCM) ; déductions de l'IA, confirmation en une phrase, critères dits au passage, questions déjà connues retirées. Testé sur le serveur : « le crédit pour les études de mon fils » est d'abord déduit, puis confirmé par l'IA et validé à 90 %. La possibilité choisie à l'oral est reconnue en 1,4 s. Mise à jour précédente (19 h 20) : agent chercheur (outils sur nos données et sur Wikipédia, preuves vérifiées, mots-clés `kw_dyn_*` en cache dans `/opt/alphaforge/app/cache/`). Testé sur le serveur : 12 s pour « Elon Musk » (4 outils, preuve tirée de la page Wikipédia de Tesla). L'instance doit pouvoir joindre `fr.wikipedia.org` et `en.wikipedia.org` en HTTPS sortant. Mise à jour précédente (19 h 05 : question ouverte finale et critères dynamiques ; une seule reformulation par critère, puis meilleure réponse retenue), via Session Manager. Testé sur le serveur avec Bedrock : une réponse ouverte en 4 idées a donné 4 critères en 6,3 s ; « rien à ajouter » n'en donne aucun (1,3 s). Version précédente (18 h 20) : conversation vocale mains libres (détection de la parole dans le navigateur, Amazon Transcribe, Amazon Polly, réplique rapide et analyse en arrière-plan), 29 questions fixes, 3 mises en situation et 10 règles de cohérence.

Le rôle `alphaforge-mvp-ec2` a reçu une seconde politique, `alphaforge-mvp-voix` : `polly:SynthesizeSpeech` et `transcribe:StartStreamTranscription` (voix de l'entretien).

**HTTPS (en place depuis le 14 novembre 2026, 18 h 06) : https://d29e3l5vv5fmjy.cloudfront.net** — c'est l'adresse à utiliser, car le micro du navigateur exige HTTPS.

| Ressource | Identifiant | Rôle |
|---|---|---|
| Distribution CloudFront | `<ID_DISTRIBUTION>` (`d29e3l5vv5fmjy.cloudfront.net`) | HTTPS (certificat CloudFront), sans cache (Managed-CachingDisabled), tous les en-têtes transmis (Managed-AllViewer) pour les WebSockets de Streamlit ; origine : l'instance, port 8501 en HTTP |
| Fonction CloudFront | `alphaforge-mvp-filtre-ip` | Ne laisse passer que les IP `<IP_EQUIPE_1>` et `<IP_EQUIPE_2>` ; les autres reçoivent une erreur 403 (testé) |
| Règle du groupe de sécurité | port 8501 ← liste de préfixes `pl-3b927c52` | Autorise les serveurs CloudFront à joindre l'instance |

Pour ajouter un coéquipier sur un autre réseau : ajouter son IP dans la liste `autorisees` de la fonction CloudFront (et la publier), ou au groupe de sécurité pour l'accès direct en HTTP. L'adresse HTTP directe (http://<IP_PUBLIQUE_INSTANCE>:8501) reste ouverte à la même IP, sans micro.

## Opérations courantes

- **Donner l'accès à un coéquipier sur un autre réseau :** ajouter son IP (`/32`) à la règle entrante du port 8501 du groupe `alphaforge-mvp-sg`.
- **Mettre le code à jour :**
  1. Recréer `mvp_profil.zip` avec `app.py`, `agents.py`, `criteres.py`, `criteres_dynamiques.py`, `chercheur.py`, `profil.py`, `simulations.py`, `entretien.py`, `voix_composant.py`, `composant_voix/index.html`, `synthese.py`, `hypotheses_profil.json`, le dossier `personas/`, `scenarios.json`, `vocabulaire_actifs.json`, `donnees_chercheur.json` et `requirements.txt` à la racine (puis `venv/bin/pip install -r app/requirements.txt` si les dépendances changent).
  2. L'envoyer sur `s3://alphaforge-mvp-<ID_DU_COMPTE>-us-east-1/app/mvp_profil.zip`.
  3. Sur l'instance, via Session Manager, lancer : `cd /opt/alphaforge && aws s3 cp s3://alphaforge-mvp-<ID_DU_COMPTE>-us-east-1/app/mvp_profil.zip app.zip && unzip -o app.zip -d app && systemctl restart alphaforge`
- **Journaux :** `/var/log/alphaforge-setup.log` (installation) et `journalctl -u alphaforge` (site).
- **Mettre en pause :** arrêter l'instance (elle garde tout). Attention : l'IP publique change au redémarrage.
- **Tout supprimer après le datathon :** dans cet ordre, la distribution CloudFront (la désactiver, attendre, puis la supprimer) et sa fonction, l'instance, le groupe de sécurité, le profil d'instance et le rôle, puis le bucket.

## Limites

- HTTP sans chiffrement, et pas de mot de passe : la protection repose sur le filtrage par IP. C'est suffisant pour une démo, pas pour de vrais utilisateurs.
- Une seule instance, sans redémarrage automatique en cas de panne de la machine. Le service redémarre seulement si Streamlit plante.
