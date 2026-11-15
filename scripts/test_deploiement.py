"""Exécute le vrai installateur Bash contre de faux services, dans un dossier temporaire.

Aucune commande AWS, systemctl ou curl réelle : les exécutables sont remplacés dans PATH.
Sous Linux (CI), Bash est obligatoire. Sous Windows, Git Bash est utilisé s'il est installé.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

RACINE = Path(__file__).resolve().parents[1]


def bash_disponible() -> str | None:
    if os.name == "nt":
        # Ne pas choisir le lanceur WSL de Windows : il n'offre pas le même système de fichiers.
        for dossier in (os.environ.get("ProgramFiles", "C:/Program Files"),
                        os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")):
            candidat = Path(dossier) / "Git" / "bin" / "bash.exe"
            if candidat.is_file():
                return str(candidat)
        return None
    return shutil.which("bash")


def ecrire_script(chemin: Path, code: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("#!/usr/bin/env bash\nset -eu\n" + code, encoding="utf-8", newline="\n")
    chemin.chmod(0o755)


def cas(bash: str, mode: str) -> None:
    with tempfile.TemporaryDirectory(prefix="alphaforge-deploiement-") as temporaire:
        cible = Path(temporaire).resolve()
        # Toutes les suppressions et déplacements du vrai script restent dans ce répertoire neuf.
        assert cible.parent == Path(tempfile.gettempdir()).resolve()
        installation = cible / "installation"
        anciens = installation / "app"
        for dossier in ("cache", "traces"):
            (anciens / dossier).mkdir(parents=True)
            (anciens / dossier / "conserve.json").write_text("ancien", encoding="utf-8")
        (anciens / "marker").write_text("ancien", encoding="utf-8")
        paquet = cible / "paquet"
        paquet.mkdir()
        (paquet / "marker").write_text("nouveau", encoding="utf-8")
        (paquet / "version_manifest.json").write_text(json.dumps({"version": "profil-test"}), encoding="utf-8")
        (paquet / "requirements.txt").write_text("-c constraints.txt\nstreamlit\n", encoding="utf-8")
        journal = cible / "services.log"
        journal_pip = cible / "pip.log"
        faux_bin = cible / "bin"
        faux_bin.mkdir()
        ecrire_script(faux_bin / "aws", '[ "$MOCK_MODE" != download_failure ] || exit 1\nprintf "archive" > "$4"\n')
        ecrire_script(faux_bin / "unzip", 'mkdir -p "$4"\ncp -R "$MOCK_PACKAGE/." "$4/"\n')
        ecrire_script(faux_bin / "python3", 'exec "$MOCK_PYTHON" "$@"\n')
        ecrire_script(faux_bin / "systemctl", '''
marque=$(cat "$ALPHAFORGE_RACINE/app/marker")
printf '%s:%s\\n' "$*" "$marque" >> "$MOCK_LOG"
if [ "$MOCK_MODE" = restart_always_failure ]; then exit 1; fi
if [ "$MOCK_MODE" = restart_failure ] && [ "$(wc -l < "$MOCK_LOG")" -eq 1 ]; then exit 1; fi
''')
        ecrire_script(faux_bin / "curl", '[ "$MOCK_MODE" != health_failure ]\n')
        ecrire_script(faux_bin / "sleep", ':\n')
        ecrire_script(faux_bin / "timeout", 'shift\nexec "$@"\n')
        ecrire_script(installation / "venv" / "bin" / "python", '''
if [ "${1:-}" = -m ]; then
  [ "$2" = pip ] && [ "$3" = install ] && [ "$4" = -r ]
  [ -f "$5" ]
  printf '%s\\n' "$(cat "$ALPHAFORGE_RACINE/app/marker"):$5" >> "$MOCK_PIP_LOG"
  [ "$MOCK_MODE" != pip_failure ]
  exit $?
fi
cat > /dev/null
mkdir -p traces
printf 'pendant verification' > traces/pendant_verification.json
[ "$MOCK_MODE" != app_failure ]
''')
        env = {**os.environ, "ALPHAFORGE_RACINE": str(installation), "VERSION": "profil-test",
               "MOCK_MODE": mode, "MOCK_PACKAGE": str(paquet), "MOCK_LOG": str(journal), "MOCK_PIP_LOG": str(journal_pip),
               "MOCK_PYTHON": sys.executable, "MOCK_BIN": str(faux_bin),
               "MOCK_INSTALLER": str(RACINE / "scripts" / "installer_serveur.sh")}
        if mode == "version_failure":
            env["VERSION"] = "profil-autre"
        # Git Bash normalise les chemins Windows ; Linux utilise les chemins absolus tels quels.
        commande = '''
set -eu
if command -v cygpath > /dev/null; then
  for nom in ALPHAFORGE_RACINE MOCK_PACKAGE MOCK_LOG MOCK_PIP_LOG MOCK_PYTHON MOCK_BIN MOCK_INSTALLER; do
    printf -v "$nom" '%s' "$(cygpath -u "${!nom}")"
    export "$nom"
  done
fi
export PATH="$MOCK_BIN:$PATH"
exec bash "$MOCK_INSTALLER"
'''
        resultat = subprocess.run([bash, "--noprofile", "--norc", "-c", commande], env=env,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        sorties = resultat.stdout + resultat.stderr
        appels = journal.read_text(encoding="utf-8").splitlines() if journal.exists() else []
        succes = mode == "success"
        assert (resultat.returncode == 0) == succes, (mode, resultat.returncode, sorties)
        assert (installation / "app" / "marker").read_text() == ("nouveau" if succes else "ancien"), (mode, sorties)
        for dossier in ("cache", "traces"):
            assert (installation / "app" / dossier / "conserve.json").read_text() == "ancien", (mode, sorties)
            assert not (installation / "app" / dossier / dossier).exists(), mode
        if mode in ("download_failure", "version_failure", "pip_failure"):
            assert appels == [], (mode, appels, sorties)
            assert not (installation / "app.prev").exists(), mode
        elif succes:
            assert appels == ["restart alphaforge:nouveau"], (mode, appels, sorties)
            assert (installation / "app.prev" / "marker").read_text() == "ancien"
            assert (installation / "app" / "traces" / "pendant_verification.json").exists()
        else:
            assert appels == ["restart alphaforge:nouveau", "restart alphaforge:ancien"], (mode, appels, sorties)
            assert (installation / "app.echec" / "marker").read_text() == "nouveau"
            assert not (installation / "app.prev").exists(), mode
            if mode == "app_failure":
                assert (installation / "app" / "traces" / "pendant_verification.json").exists(), sorties
            if mode == "restart_always_failure":
                assert "redémarrage a échoué" in sorties, sorties
        if mode in ("download_failure", "version_failure"):
            assert not journal_pip.exists(), mode
        else:
            installation_pip = journal_pip.read_text(encoding="utf-8")
            assert installation_pip.startswith("ancien:") and installation_pip.rstrip().endswith("/app.new/requirements.txt"), (mode, installation_pip)


def main() -> None:
    bash = bash_disponible()
    if bash is None and os.name == "nt":
        print("SKIP déploiement : Git Bash est nécessaire sous Windows ; la CI Linux exécute ces régressions.")
        return
    if bash is None:
        raise RuntimeError("Bash est requis pour vérifier le déploiement sous Linux/CI.")
    modes = ("success", "restart_failure", "health_failure", "app_failure", "restart_always_failure",
             "version_failure", "download_failure", "pip_failure")
    for mode in modes:
        cas(bash, mode)
    print(f"Déploiement OK : {len(modes)} scénarios Bash, retour arrière et conservation cache/traces, aucun appel cloud/service réel")


if __name__ == "__main__":
    main()
