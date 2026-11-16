"""Identité visuelle : logo de l'en-tête, icône de l'onglet, et paquet qui conserve les images intactes.

Lancer : python mvp_profil/test_identite.py
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ICI = Path(__file__).parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent / "scripts"))

from version_profil import FICHIERS, contenu_normalise  # noqa: E402

for nom in ("assets/logo_awsome.png", "assets/icone_awsome.png"):
    octets = (ICI / nom).read_bytes()
    assert nom in FICHIERS and octets.startswith(b"\x89PNG\r\n\x1a\n"), nom
    # La signature PNG contient elle-même \r\n : une normalisation de texte la corromprait.
    assert contenu_normalise(octets, nom) == octets, nom
assert contenu_normalise(b"a\r\nb", "app.py") == b"a\nb"

import interface  # noqa: E402
html = interface.marque()
assert html.startswith('<img class="af-logo-img" src="data:image/png;base64,') and 'alt="AWSome"' in html
assert interface.ICONE.exists() and ".af-logo-img" in (ICI / "design.css").read_text(encoding="utf-8")

import preparer_mvp  # noqa: E402
with tempfile.TemporaryDirectory(prefix="awsome-identite-") as dossier:
    sortie = Path(dossier) / "paquet.zip"
    preparer_mvp.construire(sortie)
    with zipfile.ZipFile(sortie) as archive:
        for nom in ("assets/logo_awsome.png", "assets/icone_awsome.png"):
            assert hashlib.sha256(archive.read(nom)).digest() == hashlib.sha256((ICI / nom).read_bytes()).digest(), nom
print("Identité OK : logo et icône présents, images intactes dans le paquet, en-tête avec le logo")
