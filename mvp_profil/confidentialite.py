"""Masquage des identifiants d'infrastructure dans tout message montré à l'utilisateur (site public).

Les erreurs des services AWS recopient souvent des détails internes : un refus d'accès cite l'ARN du rôle,
le numéro de compte et l'identifiant de l'instance ; une erreur réseau cite un point d'accès ou une adresse.
Ces détails restent dans les journaux du serveur ; l'écran et l'export n'en reçoivent qu'une version masquée.
"""
from __future__ import annotations

import re

_MOTIFS = [
    (re.compile(r"arn:aws[\w-]*:[^\s'\"),;]*"), "[ressource AWS masquée]"),
    (re.compile(r"https?://[^\s'\"]*amazonaws\.com[^\s'\"]*"), "[point d'accès AWS masqué]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[clé masquée]"),
    (re.compile(r"\bsk-ant-[\w-]+"), "[clé masquée]"),
    (re.compile(r"\bi-[0-9a-f]{8,17}\b"), "[instance masquée]"),
    (re.compile(r"\b(?:sg|vpc|subnet|eni|ami|vol|snap|pl)-[0-9a-f]{8,17}\b"), "[ressource masquée]"),
    (re.compile(r"\balphaforge-[\w.-]+"), "[ressource masquée]"),
    (re.compile(r"\b\d{12}\b"), "[compte masqué]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[adresse masquée]"),
    (re.compile(r"(?i)\b(x-amz-[\w-]+|signature|credential|security-token)=[^\s&'\"]+"), r"\1=[masqué]"),
]


def masquer(texte: object) -> str:
    """Renvoie le texte sans ARN, compte, instance, ressource, clé, adresse IP ni signature."""
    s = str(texte)
    for motif, remplacement in _MOTIFS:
        s = motif.sub(remplacement, s)
    return s
