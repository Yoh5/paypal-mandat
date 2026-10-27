"""Compte les champs de `SUBMISSION.md` qui ont une longueur imposée.

**Pourquoi un script et pas un coup d'œil.** Un champ Devpost tronqué ne dit
rien : il accepte le texte et coupe. On s'en aperçoit en relisant la page
publiée, c'est-à-dire trop tard. Ici les longueurs sont lues dans le fichier
lui-même, donc une phrase retouchée est recomptée sans qu'on y pense.

Usage :
    python submission/compter.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent / "SUBMISSION.md"

#: Les plafonds imposés par Devpost, et ceux que je m'impose.
LIMITES = {
    "Project name": 60,
    "Elevator pitch": 200,
}


def bloc(nom: str, texte: str) -> str | None:
    """Le contenu du bloc ``` qui suit le titre `## <nom>`."""
    m = re.search(rf"^## {re.escape(nom)}\s*\n+```\n(.*?)\n```", texte,
                  re.S | re.M)
    return m.group(1).strip() if m else None


def main() -> int:
    texte = DOSSIER.read_text(encoding="utf-8")
    souci = 0

    for nom, plafond in LIMITES.items():
        valeur = bloc(nom, texte)
        if valeur is None:
            print(f"  {nom:<16} INTROUVABLE dans {DOSSIER.name}")
            souci += 1
            continue
        n = len(valeur)
        etat = "OK " if n <= plafond else "TROP"
        print(f"  {nom:<16} {n:>4} / {plafond}   {etat}   marge {plafond - n}")
        if n > plafond:
            print(f"      -> couper {n - plafond} caractères")
            souci += 1

    # Le lien de la vidéo est le seul champ qu'on oublie vraiment.
    lien = bloc("Video demo link", texte) or ""
    if lien.startswith("<"):
        print("\n  Video demo link   PAS ENCORE COLLÉ (le marqueur est toujours là)")
        souci += 1

    return 1 if souci else 0


if __name__ == "__main__":
    raise SystemExit(main())
