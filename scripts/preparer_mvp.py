"""Construit et vérifie le paquet local complet, sans connexion ni publication AWS."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "mvp_profil"
sys.path.insert(0, str(SOURCE))
from version_profil import FICHIERS, contenu_normalise, version_depuis_empreintes


def verifier_archive(sortie: Path) -> dict:
    """Validation explicite, aussi active avec python -O ; aucun extrait n'est exécuté."""
    with ZipFile(sortie) as archive:
        noms = archive.namelist()
        if len(noms) != len(set(noms)):
            raise ValueError("Le paquet contient des noms de fichiers répétés.")
        manifest = json.loads(archive.read("version_manifest.json"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("fichiers"), dict):
            raise ValueError("Le manifeste du paquet est invalide.")
        fichiers = manifest["fichiers"]
        if set(fichiers) != set(FICHIERS) or set(noms) != set(FICHIERS) | {"version_manifest.json"}:
            raise ValueError("Le manifeste ne décrit pas exactement tous les fichiers de production requis.")
        for nom, attendu in fichiers.items():
            if hashlib.sha256(archive.read(nom)).hexdigest() != attendu:
                raise ValueError(f"Empreinte du paquet incorrecte : {nom}")
        if manifest.get("version") != version_depuis_empreintes(fichiers):
            raise ValueError("La version du manifeste ne correspond pas à ses empreintes.")
    return manifest


def construire(sortie: Path, source: Path = SOURCE) -> dict:
    # Les octets sont lus une seule fois : le zip et son manifeste décrivent le même contenu.
    # Fins de ligne normalisées (LF) : un paquet construit sous Windows ou sous Linux porte la même version.
    contenus = {nom: contenu_normalise((source / nom).read_bytes()) for nom in FICHIERS}
    fichiers = {nom: hashlib.sha256(contenu).hexdigest() for nom, contenu in contenus.items()}
    manifest = {"version": version_depuis_empreintes(fichiers), "fichiers": fichiers}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(sortie, "w", compression=ZIP_DEFLATED) as archive:
        for nom, contenu in contenus.items():
            archive.writestr(nom, contenu)
        archive.writestr("version_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return verifier_archive(sortie)


if __name__ == "__main__":
    sortie = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else RACINE / "mvp_profil.zip"
    m = construire(sortie)
    print(f"Paquet vérifié : {sortie.name} · {m['version']} · {len(m['fichiers'])} fichiers. Aucune publication.")
