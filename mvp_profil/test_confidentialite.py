"""Le site public ne montre ni identifiant d'infrastructure, ni clé, ni trace d'erreur.

Lancer : python mvp_profil/test_confidentialite.py
"""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from confidentialite import masquer  # noqa: E402

ICI = Path(__file__).parent

# Message typique d'un refus d'accès AWS : rôle, compte, instance, point d'accès, adresse, clé temporaire.
brut = ("User: arn:aws:sts::123456789012:assumed-role/alphaforge-mvp-ec2/i-0abc123def4567890 is not authorized "
        "to perform: dynamodb:PutItem on resource: arn:aws:dynamodb:us-east-1:123456789012:table/alphaforge-traces "
        "(https://dynamodb.us-east-1.amazonaws.com/ ; 10.0.12.34 ; ASIAABCDEFGHIJKLMNOP ; sg-0123456789abcdef0 ; "
        "X-Amz-Signature=abcdef ; sk-ant-api03-secret)")
propre = masquer(brut)
for fuite in ("123456789012", "arn:aws", "i-0abc", "alphaforge-mvp-ec2", "alphaforge-traces", "amazonaws.com",
              "10.0.12.34", "ASIAABCDEFGHIJKLMNOP", "sg-0123", "abcdef ;", "sk-ant"):
    assert fuite not in propre, (fuite, propre)
assert "is not authorized" in propre and "dynamodb:PutItem" in propre  # le sens du message reste lisible
assert masquer("Délai dépassé ; votre réponse est conservée.") == "Délai dépassé ; votre réponse est conservée."

# Configuration du serveur (installée avec le paquet) : aucune trace d'erreur ni menu de développement.
config = tomllib.loads((ICI / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
assert config["client"]["showErrorDetails"] == "none" and config["client"]["toolbarMode"] == "viewer", config

# Aucun fichier publié ne contient d'identifiant de compte, d'instance, de ressource ou de clé.
from version_profil import FICHIERS  # noqa: E402
import re  # noqa: E402
interdits = re.compile(r"arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}|\bi-0[0-9a-f]{8,}\b|\bsg-0[0-9a-f]{8,}\b|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
                       r"|sk-ant-[\w-]{8,}|alphaforge-mvp-\d{12}")
assert "confidentialite.py" in FICHIERS
for nom in FICHIERS:
    if nom.endswith((".py", ".json", ".toml", ".txt", ".html", ".js", ".css")) and not nom.startswith("confidentialite"):
        trouve = interdits.search((ICI / nom).read_text(encoding="utf-8"))
        assert not trouve, (nom, trouve.group(0))
print("Confidentialité OK : messages d'erreur masqués, configuration de production sans détails, paquet sans identifiants")
