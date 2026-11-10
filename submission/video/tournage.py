"""Joue la vraie démo, à une vitesse qu'une caméra peut suivre.

Pourquoi ce fichier existe. Le 10/11/2026, Devpost a signalé que la vidéo « ne
montre pas le projet fonctionnant sur l'appareil pour lequel il a été conçu » :
le film d'origine est dessiné image par image (`film.py`). Il faut donc filmer
l'écran pendant que le programme tourne. Ce lanceur ne simule rien :

- il appelle `mandat.demo.jouer`, le même point d'entrée que
  `python -m mandat.demo` ; la scène A passe un **vrai paiement** dans le bac à
  sable PayPal, la scène B refuse sans appeler personne, la scène C falsifie un
  registre et le vérificateur nomme la ligne ;
- il ne fait que **ralentir l'affichage** (une pause par ligne, un écran par
  scène), parce que les quatre scènes défilent en 7 secondes ;
- la scène D est **rejouée** depuis `runs/lecture-piegee.json` (gpt-5.5, 29/10),
  et l'écran le dit (« replayed from a recorded run »). Rejouer est un choix de
  tournage : un appel en direct réécrirait cet enregistrement, qui est la pièce
  qu'un juré sans clé rejoue, et le modèle ne tombe pas dans le piège à chaque
  fois — la scène le dit elle-même.

Les identifiants PayPal sont lus dans `.env` et **jamais affichés**.

Usage (depuis la racine du dépôt, dans le terminal qu'on filme) :
    python submission/video/tournage.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PAUSE_LIGNE = float(os.environ.get("TOURNAGE_PAUSE", "0.11"))  # secondes entre deux lignes
PAUSE_SCENE = float(os.environ.get("TOURNAGE_SCENE", "3.0"))  # secondes sur la fin d une scene


def _charger_paypal() -> None:
    """Met les deux identifiants PayPal dans l'environnement, et rien d'autre."""
    env = RACINE / ".env"
    for ligne in env.read_text(encoding="utf-8").splitlines():
        cle, sep, valeur = ligne.partition("=")
        if sep and cle.strip() in ("PAYPAL_CLIENT_ID", "PAYPAL_SECRET"):
            os.environ[cle.strip()] = valeur.strip().strip('"').strip("'")
    # Coupe la lecture de .env pour tout le reste : aucune clé de modèle n'est
    # trouvée, donc la scène D rejoue l'enregistrement au lieu d'appeler.
    os.environ["MANDAT_SANS_ENV"] = "1"
    for cle in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        os.environ.pop(cle, None)


def _effacer() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def main() -> None:
    sys.path.insert(0, str(RACINE))
    os.chdir(RACINE)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _charger_paypal()

    from mandat.demo import jouer
    from mandat.paypal import PayPal
    from mandat.registre import Registre

    premiere = [True]

    def ecrire(ligne: str = "") -> None:
        if ligne.startswith("== Scene"):
            if not premiere[0]:
                time.sleep(PAUSE_SCENE)
            premiere[0] = False
            _effacer()
        print(ligne, flush=True)
        time.sleep(PAUSE_LIGNE)

    _effacer()
    print("> python -m mandat.demo", flush=True)
    print("  Spend Mandate -- the agent proposes, the code decides.", flush=True)
    time.sleep(2.5)

    # Un registre neuf, hors du dépôt : les numéros de séquence à l'écran
    # partent de 1 et le registre de démonstration du dépôt n'est pas touché.
    dossier = Path(tempfile.mkdtemp(prefix="mandat-tournage-"))
    jouer(registre=Registre(dossier / "demo.jsonl"),
          fournisseur=PayPal.depuis_env(), ecrire=ecrire)
    time.sleep(PAUSE_SCENE)


if __name__ == "__main__":
    main()
