# Déploiement du MVP sur AWS

Déployé le 14 novembre 2026 dans le compte du datathon (`024848442163`), région us-east-1. Le site appelle Claude Haiku 5.5 sur Amazon Bedrock grâce au **rôle IAM du serveur** : aucune clé ni aucun identifiant à manipuler.

**Adresse : https://d29e3l5vv5fmjy.cloudfront.net** (HTTPS, micro disponible ; adresse directe en HTTP : http://52.90.99.94:8501)

L'accès est limité à l'adresse IP `132.207.3.191` (le réseau d'où le site a été déployé). Depuis un autre réseau, il faut ajouter l'IP au groupe de sécurité (voir plus bas).

## Architecture

```
Navigateur ──HTTP 8501──▶ EC2 t3.small (Streamlit, rôle IAM alphaforge-mvp-ec2)
                              ├──▶ Amazon Bedrock : us.anthropic.claude-haiku-5-5 (classificateur + critique)
                              └──▶ S3 : paquet du site (lu au démarrage)
```

## Ressources créées (toutes étiquetées `projet = alphaforge-mvp`)

| Ressource | Identifiant | Rôle |
|---|---|---|
| Instance EC2 | `i-0ccf3bf86e9f31c07` (t3.small, Amazon Linux 2023) | Fait tourner Streamlit en service systemd (`alphaforge`) |
| Rôle IAM + profil d'instance | `alphaforge-mvp-ec2` | Droits minimaux : `bedrock:InvokeModel` sur Haiku 5.5 seulement, lecture de `s3://…/app/*`, et Session Manager (SSM) pour la maintenance |
| Groupe de sécurité | `sg-0b3d60c8c41de38bb` (`alphaforge-mvp-sg`) | Port 8501 ouvert à une seule IP ; aucun port SSH |
| Bucket S3 | `alphaforge-mvp-024848442163-us-east-1` | Paquet du site (`app/mvp_profil.zip`), accès public bloqué |

Coût indicatif : t3.small environ 0,02 $ US/h, plus les appels Haiku (quelques cents par questionnaire), facturés au compte de l'événement.

Dernière mise à jour du code : 14 novembre 2026, 18 h 20 (conversation vocale mains libres : détection de la parole dans le navigateur, Amazon Transcribe, Amazon Polly, réplique rapide et analyse en arrière-plan ; 29 questions fixes ; 3 mises en situation ; 10 règles de cohérence), via Session Manager.

Le rôle `alphaforge-mvp-ec2` a reçu une seconde politique, `alphaforge-mvp-voix` : `polly:SynthesizeSpeech` et `transcribe:StartStreamTranscription` (voix de l'entretien).

**HTTPS (en place depuis le 14 novembre 2026, 18 h 06) : https://d29e3l5vv5fmjy.cloudfront.net** — c'est l'adresse à utiliser, car le micro du navigateur exige HTTPS.

| Ressource | Identifiant | Rôle |
|---|---|---|
| Distribution CloudFront | `E18YYD3YL1P62Q` (`d29e3l5vv5fmjy.cloudfront.net`) | HTTPS (certificat CloudFront), sans cache (Managed-CachingDisabled), tous les en-têtes transmis (Managed-AllViewer) pour les WebSockets de Streamlit ; origine : l'instance, port 8501 en HTTP |
| Fonction CloudFront | `alphaforge-mvp-filtre-ip` | Ne laisse passer que l'IP `132.207.3.191` ; les autres reçoivent une erreur 403 (testé) |
| Règle du groupe de sécurité | port 8501 ← liste de préfixes `pl-3b927c52` | Autorise les serveurs CloudFront à joindre l'instance |

Pour ajouter un coéquipier sur un autre réseau : ajouter son IP dans la liste `autorisees` de la fonction CloudFront (et la publier), ou au groupe de sécurité pour l'accès direct en HTTP. L'adresse HTTP directe (http://52.90.99.94:8501) reste ouverte à la même IP, sans micro.

## Opérations courantes

- **Donner l'accès à un coéquipier sur un autre réseau :** ajouter son IP (`/32`) à la règle entrante du port 8501 du groupe `alphaforge-mvp-sg`.
- **Mettre le code à jour :**
  1. Recréer `mvp_profil.zip` avec `app.py`, `agents.py`, `criteres.py`, `profil.py`, `simulations.py`, `entretien.py`, `voix_composant.py`, `composant_voix/index.html`, `scenarios.json` et `requirements.txt` à la racine (puis `venv/bin/pip install -r app/requirements.txt` si les dépendances changent).
  2. L'envoyer sur `s3://alphaforge-mvp-024848442163-us-east-1/app/mvp_profil.zip`.
  3. Sur l'instance, via Session Manager, lancer : `cd /opt/alphaforge && aws s3 cp s3://alphaforge-mvp-024848442163-us-east-1/app/mvp_profil.zip app.zip && unzip -o app.zip -d app && systemctl restart alphaforge`
- **Journaux :** `/var/log/alphaforge-setup.log` (installation) et `journalctl -u alphaforge` (site).
- **Mettre en pause :** arrêter l'instance (elle garde tout). Attention : l'IP publique change au redémarrage.
- **Tout supprimer après le datathon :** dans cet ordre, la distribution CloudFront (la désactiver, attendre, puis la supprimer) et sa fonction, l'instance, le groupe de sécurité, le profil d'instance et le rôle, puis le bucket.

## Limites

- HTTP sans chiffrement, et pas de mot de passe : la protection repose sur le filtrage par IP. C'est suffisant pour une démo, pas pour de vrais utilisateurs.
- Une seule instance, sans redémarrage automatique en cas de panne de la machine. Le service redémarre seulement si Streamlit plante.
