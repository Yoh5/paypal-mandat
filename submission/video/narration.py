"""The narration, and the only thing that sets this film's rhythm.

**Why the text comes before a single frame.** A scene lasts as long as the
sentence that carries it, plus a tail, with a floor underneath so a movement
stays readable when the phrase is shorter than the gesture. So the cut list is
not a decision taken at the editing table: it is measured from the voice. If the
voice runs four minutes, the storyboard is wrong, and better to learn that now
than after the frames are drawn.

The voice and the rate are the ones already validated on the Glass Box keynote:
`en-US-AndrewNeural` at -6%, because a demo jury watches thirty videos and a
default rate reads as hurried.

Usage:
    python submission/video/narration.py            # measure, print, decide
"""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg

VOIX = "en-US-AndrewNeural"
DEBIT = "-6%"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TRAVAIL = Path(__file__).resolve().parent / "_travail"

#: Un plan par idée, et une seule. **L'ordre de ce dictionnaire EST l'ordre du
#: film** : la piste audio est concaténée dans cet ordre, donc déplacer une clé
#: déplace la scène et son commentaire ensemble. Il n'y a pas de second endroit
#: où le montage pourrait diverger du texte.
#:
#: Révisé une fois, et pour une raison mesurée : `these` ouvrait en position 2.
#: Deux scènes de discours d'affilée repoussaient la première chose *exécutée*
#: à 42 % du film. `mandat` est remonté, `these` est descendu en synthèse — la
#: première exécution tombe maintenant à 33 %.
NARRATION: dict[str, str] = {
    "ouverture":
        "An agent that buys things is the sharpest case of excessive agency. "
        "A payment cannot be undone.",

    "mandat":
        "So the agent is given a mandate. A cap per transaction, a total cap, "
        "a validity window, a list of merchants. And the mandate is enforced "
        "by code before the call, not audited after.",

    "paiement":
        "The agent reads a page and proposes six euros forty for a ream of "
        "paper. The mandate allows it, PayPal creates the order. And from that "
        "transaction reference alone, everything comes back: what was read, "
        "what was decided, what the mandate permitted at that instant.",

    "refus":
        "Now the same page, and the printer at eighty nine ninety. The price "
        "is real; the agent is not hallucinating. But the mandate allows forty "
        "per transaction. Watch where this stops. The gateway refuses, and "
        "PayPal is never called. Not refunded, not reversed. Never called. "
        "A cap checked after the call is not a cap, it is a report.",

    "falsification":
        "A refusal is written to the register exactly like a payment, because "
        "a log that only shows successes describes an agent that never tried "
        "anything forbidden. And if someone rewrites that file, the verifier "
        "does not answer that the log is fine. It names the line.",

    "limites":
        "What this is not. It does not stop a malicious agent: it constrains "
        "the path that goes through it. And out-of-register payments are not "
        "verified unless you supply a webhook log, because an empty list "
        "because nothing was searched is not an empty list because nothing is "
        "there.",

    # Descendue de la position 2 : ici, après la démonstration, la phrase est
    # une synthèse et non un préambule. D'où la bascule finale, sans laquelle
    # « what is missing » sonnerait faux une fois qu'on vient de le montrer.
    "these":
        "None of this is payment plumbing. PayPal already had idempotency "
        "keys, webhooks and refunds. What it did not have was the link between "
        "the money that moved and the reasoning that moved it. That link is "
        "what you just watched.",

    "fin":
        "Eighty six tests, no runtime dependencies, Apache two point zero. "
        "The model reads. The code decides.",
}

#: Le plancher de chaque scène : ce qu'il faut pour que le mouvement reste
#: lisible même si la phrase est plus courte que le geste qu'elle décrit.
MINIMA = {"ouverture": 8.0, "mandat": 15.0, "paiement": 20.0, "refus": 30.0,
          "falsification": 24.0, "limites": 16.0, "these": 12.0, "fin": 10.0}

#: Une clé mal orthographiée dans MINIMA ne lèverait rien : la scène perdrait
#: simplement son plancher et serait cadencée par la voix seule, ce qui ne se
#: voit qu'au visionnage. On le dit tout de suite.
if MINIMA.keys() != NARRATION.keys():
    manque = NARRATION.keys() - MINIMA.keys()
    trop = MINIMA.keys() - NARRATION.keys()
    raise SystemExit(f"MINIMA et NARRATION divergent — sans plancher : "
                     f"{sorted(manque)} ; en trop : {sorted(trop)}")

#: Pas un titre qui s'installe : **une ouverture froide, sans un mot** — le
#: chemin de l'argent qui avance et s'arrête net contre le plafond. Le temps
#: était déjà alloué ; autant qu'il accroche au lieu de patienter.
SILENCE_INITIAL = 3.0
TAIL = 1.0              # ce qui reste après la dernière syllabe


def dire(cle: str) -> Path:
    """Rend la phrase, puis la convertit en wav pour pouvoir la mesurer."""
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    mp3, wav = TRAVAIL / f"{cle}.mp3", TRAVAIL / f"{cle}.wav"
    if not wav.exists():
        # `--rate=-6%` et non `--rate -6%` : argparse lit un débit négatif
        # comme une option courte.
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOIX,
                        f"--rate={DEBIT}", "--text", NARRATION[cle],
                        "--write-media", str(mp3)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([FFMPEG, "-y", "-i", str(mp3), "-ac", "1", "-ar", "48000",
                        str(wav)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return wav


def secondes(wav: Path) -> float:
    with wave.open(str(wav)) as f:
        return f.getnframes() / f.getframerate()


def minuter() -> tuple[dict[str, float], dict[str, float]]:
    """(durée de chaque scène, durée de chaque phrase) — dans l'ordre du film."""
    parle = {cle: secondes(dire(cle)) for cle in NARRATION}
    scenes = {cle: max(parle[cle] + TAIL, MINIMA[cle]) for cle in NARRATION}
    return scenes, parle


def main() -> int:
    scenes, parle = minuter()
    total = SILENCE_INITIAL + sum(scenes.values())

    # La colonne « début » existe parce que je l'ai calculée de tête une fois et
    # que je me suis trompé. Un plan de montage se lit, il ne se devine pas.
    print(f"  {'scène':<16}{'début':>8}{'%':>6}{'parlé':>8}{'scène':>9}"
          f"{'plancher':>11}   ce qui décide")
    print("  " + "-" * 74)
    t = SILENCE_INITIAL
    for cle in NARRATION:
        decide = "plancher" if MINIMA[cle] > parle[cle] + TAIL else "la voix"
        print(f"  {cle:<16}{t:>7.1f}s{t / total * 100:>5.0f}%{parle[cle]:>7.1f}s"
              f"{scenes[cle]:>8.1f}s{MINIMA[cle]:>10.1f}s   {decide}")
        t += scenes[cle]
    print("  " + "-" * 74)
    print(f"  {'silence initial':<16}{'':>8}{SILENCE_INITIAL:>8.1f}s")
    print(f"  {'TOTAL':<16}{'':>8}{total:>8.1f}s  "
          f"= {int(total // 60)} min {total % 60:04.1f} s")

    part = scenes["refus"] / total
    print(f"\n  Le refus occupe {part * 100:.0f} % du film "
          f"({scenes['refus']:.1f}s sur {total:.1f}s).")
    if total > 180:
        print("\n  ARRET : au-dessus des 3 minutes du règlement PayPal.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
