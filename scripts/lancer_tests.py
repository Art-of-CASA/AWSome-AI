"""Découvre et lance toutes les suites locales, une par processus, sans appeler les vrais services.

Utilisation : python scripts/lancer_tests.py [--lister] [--filtre texte] [--timeout 120]
Python -O est refusé : les assertions des suites ordinaires doivent rester actives.
Les tests Streamlit utilisent une paire de sockets locales pour leur boucle asyncio.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

RACINE = Path(__file__).resolve().parents[1]


def decouvrir(racine: Path = RACINE) -> list[Path]:
    tests = list((racine / "mvp_profil").glob("test_*.py"))
    tests += list((racine / "mvp_profil").glob("test_*.cjs"))
    tests += list((racine / "scripts").glob("test_*.py"))
    return sorted(tests)


def main() -> int:
    if not __debug__:
        print("Exécution refusée : lancez les tests sans -O pour conserver leurs assertions.", file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lister", action="store_true")
    ap.add_argument("--filtre", default="", help="sous-chaîne du chemin d'une suite")
    ap.add_argument("--timeout", type=float, default=120, help="délai maximum par suite en secondes")
    args = ap.parse_args()
    if args.timeout <= 0:
        ap.error("Le délai doit être strictement positif.")
    tests = [p for p in decouvrir() if args.filtre in p.relative_to(RACINE).as_posix()]
    if not tests:
        ap.error("Aucune suite ne correspond au filtre.")
    if args.lister:
        for p in tests:
            print(p.relative_to(RACINE).as_posix())
        print(f"{len(tests)} suites découvertes.")
        return 0
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           "AWS_EC2_METADATA_DISABLED": "true"}
    echecs = []
    for p in tests:
        nom = p.relative_to(RACINE).as_posix()
        exe = sys.executable if p.suffix == ".py" else shutil.which("node")
        if exe is None:
            print(f"ÉCHEC {nom} : Node.js est requis pour cette suite.")
            echecs.append(nom)
            continue
        try:
            r = subprocess.run([exe, str(p)], cwd=RACINE, env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=args.timeout, check=False)
        except subprocess.TimeoutExpired:
            print(f"ÉCHEC {nom} : délai de {args.timeout:g} s dépassé.")
            echecs.append(nom)
            continue
        print(f"{'OK' if r.returncode == 0 else 'ÉCHEC'} {nom}")
        if r.stdout.strip():
            print(r.stdout.rstrip())
        if r.returncode and r.stderr.strip():
            print(r.stderr.rstrip(), file=sys.stderr)
        if r.returncode:
            echecs.append(nom)
    print(f"{len(tests) - len(echecs)}/{len(tests)} suites réussies.")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
