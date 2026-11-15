"""Capacité et échéances des analyses, indépendantes des rendus de l'interface."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from time import monotonic

from agents import AgentError


DELAI_ANALYSE_S = 90


class ExecuteurBorne(ThreadPoolExecutor):
    """Refuse la surcharge plutôt que d'accumuler des réponses dans une file sans limite."""

    def __init__(self, max_workers: int = 4, max_attente: int = 4):
        super().__init__(max_workers=max_workers, thread_name_prefix="profil")
        self._places = BoundedSemaphore(max_workers + max_attente)

    def submit(self, fn, /, *args, **kwargs):
        if not self._places.acquire(blocking=False):
            raise AgentError("Les contrôles sont momentanément occupés. Votre réponse reste conservée.")
        try:
            future = super().submit(fn, *args, **kwargs)
        except BaseException:
            self._places.release()
            raise
        future.add_done_callback(lambda _: self._places.release())
        return future


def expiree(job: dict, maintenant: float | None = None) -> bool:
    """Les anciens états sans horodatage restent lisibles ; les nouvelles tâches sont toutes datées."""
    maintenant = monotonic() if maintenant is None else maintenant
    debut = job.setdefault("soumis_le", maintenant)
    return job.get("termine_le", maintenant) - debut >= DELAI_ANALYSE_S


def suivre_tache(job: dict) -> dict:
    """Date la fin réelle, même si l'utilisateur ne revient lire le résultat que beaucoup plus tard."""
    job.setdefault("soumis_le", monotonic())
    def fin(_):
        job["termine_le"] = monotonic()
    job["future"].add_done_callback(fin)
    return job
