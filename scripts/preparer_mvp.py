"""Construit et vérifie le paquet local, sans connexion ni publication AWS."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "mvp_profil"
sys.path.insert(0, str(SOURCE))
from version_profil import empreintes, version_courante


def construire(sortie: Path) -> dict:
    manifest = {"version": version_courante(SOURCE), "fichiers": empreintes(SOURCE)}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(sortie, "w", compression=ZIP_DEFLATED) as archive:
        for nom in manifest["fichiers"]:
            archive.write(SOURCE / nom, nom)
        archive.writestr("version_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    import hashlib
    with ZipFile(sortie) as archive:
        for nom, attendu in manifest["fichiers"].items():
            assert hashlib.sha256(archive.read(nom)).hexdigest() == attendu, nom
        assert json.loads(archive.read("version_manifest.json"))["version"] == manifest["version"]
    return manifest


if __name__ == "__main__":
    sortie = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else RACINE / "mvp_profil.zip"
    m = construire(sortie)
    print(f"Paquet vérifié : {sortie.name} · {m['version']} · {len(m['fichiers'])} fichiers. Aucune publication.")
