"""Le budget IA est global, persistant et ne peut pas être désactivé par une mauvaise configuration."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import limites_ia


with tempfile.TemporaryDirectory() as d, patch.object(limites_ia, "DOSSIER", Path(d)), patch.object(limites_ia, "FICHIER", Path(d) / "budget_ia.json"):
    t0 = datetime(2026, 11, 16, 23, 0, tzinfo=timezone.utc)
    with patch.dict(os.environ, {"ALPHAFORGE_MAX_APPELS_IA_JOUR": "2"}):
        assert limites_ia.reserver("profil", t0) == 1
        assert limites_ia.reserver("recommandation", t0) == 2
        try:
            limites_ia.reserver("profil", t0)
            raise AssertionError("Le troisième appel doit être bloqué")
        except limites_ia.LimiteIAAtteinte:
            pass
        # Le lendemain, le budget est de nouveau disponible et le compteur est conservé sur disque.
        assert limites_ia.reserver("profil", t0 + timedelta(days=1)) == 1
        assert '"appels": 1' in (Path(d) / "budget_ia.json").read_text(encoding="utf-8")

with patch.dict(os.environ, {"ALPHAFORGE_MAX_APPELS_IA_JOUR": "invalide"}):
    assert limites_ia.limite_par_jour() == limites_ia.LIMITE_PAR_JOUR_DEFAUT
with patch.dict(os.environ, {"ALPHAFORGE_MAX_APPELS_IA_JOUR": "0"}):
    assert limites_ia.limite_par_jour() == 1

print("Limites IA OK : budget quotidien persistant et réinitialisation UTC")
