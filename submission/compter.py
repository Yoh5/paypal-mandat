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
import subprocess
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent / "SUBMISSION.md"
RACINE = DOSSIER.resolve().parent.parent

#: Les fichiers qui annoncent un nombre de tests au lecteur. Le README le
#: faisait déjà, le dossier le faisait aussi, et c'est le dossier qui était
#: resté à 86 quand le README disait 97 : un garde-fou qui ne couvre que le
#: fichier le plus relu protège le moins exposé.
ANNONCENT_LES_TESTS = ("README.md", "submission/SUBMISSION.md")

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


def compter_les_tests() -> int:
    """Confronte le nombre de tests annoncé dans les textes à celui qui passe.

    Le chiffre a bougé trois fois en deux jours (86, 97, 114) et les fichiers
    ne l'ont pas suivi ensemble. Le relire à la main est exactement le travail
    qu'on oublie de faire la veille d'une échéance.
    """
    try:
        sortie = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                                cwd=RACINE, capture_output=True, text=True,
                                timeout=300).stdout
    except Exception as pourquoi:                      # pragma: no cover
        print(f"\n  Tests             NON LANCÉS ({pourquoi})")
        return 1

    vu = re.search(r"(\d+) passed", sortie)
    if not vu:
        derniere = sortie.strip().splitlines()[-1] if sortie.strip() else "(aucune sortie)"
        print("\n  Tests             LA SUITE N'EST PAS VERTE")
        print(f"      {derniere}")
        return 1

    reel = int(vu.group(1))
    souci = 0
    print(f"\n  Tests             {reel} passed")
    for nom in ANNONCENT_LES_TESTS:
        texte = (RACINE / nom).read_text(encoding="utf-8")
        for annonce in {int(m) for m in re.findall(r"(\d+)\s*(?:passed|tests)\b", texte)}:
            if annonce != reel:
                print(f"      {nom} annonce {annonce}, la suite en passe {reel}")
                souci += 1
    return souci


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

    souci += compter_les_tests()

    # Le lien de la vidéo est le seul champ qu'on oublie vraiment.
    lien = bloc("Video demo link", texte) or ""
    if lien.startswith("<"):
        print("\n  Video demo link   PAS ENCORE COLLÉ (le marqueur est toujours là)")
        souci += 1

    return 1 if souci else 0


if __name__ == "__main__":
    raise SystemExit(main())
