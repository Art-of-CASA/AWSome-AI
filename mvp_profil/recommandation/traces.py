"""Journal des actions observables : outils appelés, verdicts figés, contrôles. C'est ce que l'écran « Pourquoi ? » montre.

Stockage : en mémoire toujours ; dans DynamoDB si AWSOME_AI_TABLE_TRACES est défini (sinon fichier local traces/).
On journalise des ACTIONS (outil, entrée, sortie résumée, horodatage), jamais un raisonnement interne de modèle.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from version_profil import version_courante

DOSSIER = Path(os.environ.get("AWSOME_AI_DOSSIER_TRACES", Path(__file__).resolve().parents[1] / "traces"))


@lru_cache(maxsize=1)
def version_chargee() -> str:
    return version_courante()


def pour_stockage(evenement: dict) -> dict:
    """La session peut afficher les entrées ; les journaux persistants ne conservent pas leur texte libre."""
    sensibles = {"question", "texte", "citation", "entree", "erreur", "motif", "infractions", "sans_origine"}
    def nettoyer(obj):
        if isinstance(obj, dict):
            return {k: ({"masque": True, "longueur": len(str(v))} if k in sensibles else nettoyer(v))
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [nettoyer(v) for v in obj]
        return obj
    return nettoyer(evenement)


class Journal:
    def __init__(self, session: str | None = None, persister: bool = True):
        self.session = session or uuid.uuid4().hex[:12]
        self.evenements: list[dict] = []
        self.persister = persister
        self._table = None
        self.erreur_stockage: str | None = None
        # Table créée par infra/awsome-ai-recommandation.yaml. Absente ou inaccessible (poste local, autre compte) :
        # la première écriture échoue et le journal bascule sur un fichier local, sans interrompre le site.
        nom = os.environ.get("AWSOME_AI_TABLE_TRACES", "awsome-ai-traces")
        if persister and nom and os.environ.get("AWSOME_AI_TRACES_LOCALES") != "1":
            try:
                import boto3
                from botocore.config import Config
                self._table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"),
                                             config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1})).Table(nom)
            except Exception as e:  # pas d'AWS : le journal local suffit
                self.erreur_stockage = f"{type(e).__name__}: {e}"

    def noter(self, type_: str, **donnees) -> dict:
        ev = {"session": self.session, "rang": len(self.evenements) + 1,
              "horodatage": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "type": type_, **donnees,
              "version_code": version_chargee()}
        self.evenements.append(ev)
        if self.persister:
            charge = json.dumps(pour_stockage(ev), ensure_ascii=False, default=str)
            try:
                if self._table is not None:
                    self._table.put_item(Item={"session": self.session, "evenement": f"{ev['rang']:04d}#{ev['horodatage']}#{type_}",
                                               "type": type_, "contenu": charge[:350000]})
                else:
                    DOSSIER.mkdir(parents=True, exist_ok=True)
                    with (DOSSIER / f"{self.session}.jsonl").open("a", encoding="utf-8") as f:
                        f.write(charge + "\n")
            except Exception as e:
                self.erreur_stockage = f"{type(e).__name__}: {str(e)[:160]}"
                if self._table is not None:      # DynamoDB indisponible : fichier local pour la suite de la session
                    self._table = None
                    try:
                        DOSSIER.mkdir(parents=True, exist_ok=True)
                        with (DOSSIER / f"{self.session}.jsonl").open("a", encoding="utf-8") as f:
                            f.write(charge + "\n")
                    except OSError:
                        self.persister = False
                else:
                    self.persister = False
        return ev

    def stockage(self) -> str:
        if not self.persister:
            return "mémoire seulement"
        return "Amazon DynamoDB" if self._table is not None else "fichier local (traces/)"

    def de_type(self, *types: str) -> list[dict]:
        return [e for e in self.evenements if e["type"] in types]
