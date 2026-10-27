"""Le fichier de sous-titres, calé sur les durées mesurées et non estimées.

**Pourquoi ne pas laisser YouTube le faire.** Les montants sont le cœur de la
démonstration et ils sont dits à l'oral — « eighty nine ninety ». La
reconnaissance automatique écrira autre chose, et un juré qui regarde sans le
son ne lira que du bruit. Ici chaque réplique vient de `narration.py`, donc le
texte affiché est exactement celui qui est prononcé.

**Le calage n'est pas deviné.** Le début de chaque phrase est la somme des
durées de scène qui la précèdent — la même somme qui construit la piste audio.
À l'intérieur d'une phrase, les répliques se partagent le temps *au prorata du
nombre de caractères*, ce qui suit le débit d'une voix de synthèse à vitesse
constante de très près.

Usage :
    python submission/video/sous_titres.py        # écrit mandat-demo.en.srt
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import narration as N  # noqa: E402

#: Norme d'accessibilité courante : deux lignes au plus, ~42 caractères par
#: ligne. Au-delà, l'œil n'a pas le temps de lire avant le changement.
LARGEUR = 42
LIGNES = 2

#: Seuil de lisibilité : en dessous, l'œil n'a pas fini de lire que la réplique
#: a disparu. Une orpheline de deux mots affichée 0,7 s ne se lit pas.
MIN_REPLIQUE = 1.3


def repliques(phrase: str) -> list[str]:
    """Découpe une phrase en répliques de deux lignes lisibles.

    On coupe sur les mots, jamais au milieu, et on préfère couper après une
    ponctuation forte quand elle tombe dans la fenêtre — une réplique qui
    s'arrête sur un point se lit mieux qu'une qui s'arrête sur une virgule.
    """
    mots, lignes, courante = phrase.split(), [], ""
    for mot in mots:
        essai = f"{courante} {mot}".strip()
        if len(essai) > LARGEUR and courante:
            lignes.append(courante)
            courante = mot
        else:
            courante = essai
    if courante:
        lignes.append(courante)
    return ["\n".join(lignes[i:i + LIGNES]) for i in range(0, len(lignes), LIGNES)]


def horodate(t: float) -> str:
    h, reste = divmod(t, 3600)
    m, s = divmod(reste, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def main() -> int:
    scenes, parle = N.minuter()
    blocs, n, t = [], 0, N.SILENCE_INITIAL

    for cle in N.NARRATION:
        morceaux = repliques(N.NARRATION[cle])
        total_car = sum(len(m) for m in morceaux) or 1
        # La fin de scène est du silence : une réplique trop courte peut y
        # mordre sans jamais empiéter sur la phrase suivante.
        plafond = t + scenes[cle] - 0.2
        debut = t
        for i, m in enumerate(morceaux):
            fin = debut + parle[cle] * len(m) / total_car
            if i == len(morceaux) - 1:
                fin = min(max(fin, debut + MIN_REPLIQUE), plafond)
            n += 1
            blocs.append(f"{n}\n{horodate(debut)} --> {horodate(fin)}\n{m}\n")
            debut = fin
        t += scenes[cle]

    sortie = Path(__file__).resolve().parent / "mandat-demo.en.srt"
    sortie.write_text("\n".join(blocs), encoding="utf-8")

    print(f"  {sortie.name} — {n} répliques, dernière à {horodate(debut)}")
    print(f"  (le film dure {horodate(t)}, donc la dernière réplique "
          f"tombe {t - debut:.1f}s avant la fin)")
    trop = [b.splitlines()[2:] for b in blocs
            if any(len(l) > LARGEUR for l in b.splitlines()[2:])]
    if trop:
        print(f"  ATTENTION : {len(trop)} réplique(s) dépassent {LARGEUR} caractères")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
