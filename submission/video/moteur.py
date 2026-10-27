"""Le moteur : surface, typographie, courbes, et les données réelles.

**Rien ici ne décide du film.** Ce module fournit de quoi dessiner et de quoi
lire ; le découpage vit dans `narration.py` et les plans dans `film.py`.

**Pourquoi les chiffres sont exécutés et non tapés.** Une vidéo de hackathon est
une affirmation : « voici ce que fait l'outil ». Le moyen le plus simple de la
rendre fausse est de typographier une sortie recopiée à la main, qui vieillit
dès que le code change. Ici chaque montant, chaque référence, chaque empreinte
et le nombre de tests sont **lus au moment du rendu**. Si le mandat change de
plafond, la vidéo change avec lui ; si la démo casse, le rendu s'arrête au lieu
de montrer la sortie d'hier.

**Les primitives de dessin viennent du moteur de `glassbox`**, du même auteur.
Copiées et non importées, délibérément : ce dépôt est public et doit se rendre
seul, sans dépendre d'un dossier voisin.

**Une décision de couleur qui n'est pas une préférence.** Le temps fort du film
est un refus, et la version paresseuse le peint en rouge sur un chemin vert. Or
vert contre rouge mesure ΔE 4,1 en deutéranopie : un spectateur daltonien ne
verrait rien. Donc le refus se lit d'abord par la **forme** — le chemin bute
contre un mur, la flèche s'arrête, le montant est barré — et la couleur ne fait
que renforcer. Forme, position et texte portent le sens.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parent.parent.parent
TRAVAIL = Path(__file__).resolve().parent / "_travail"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

L, H = 1920, 1080

# Palette validée pour fond sombre, pas choisie à l'œil.
SURFACE = (26, 26, 25)
ENCRE = (255, 255, 255)
ENCRE_2 = (195, 194, 183)
ENCRE_3 = (120, 120, 114)
ACCENT = (57, 135, 229)
CRITIQUE = (208, 59, 59)
PERMIS = (106, 168, 120)      # le vert ne porte jamais seul : il renforce

MONO = "C:/Windows/Fonts/consola.ttf"
MONO_G = "C:/Windows/Fonts/consolab.ttf"
SANS = "C:/Windows/Fonts/segoeui.ttf"
SANS_G = "C:/Windows/Fonts/segoeuib.ttf"
SANS_L = "C:/Windows/Fonts/segoeuil.ttf"

_polices: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_fond_cache: Image.Image | None = None


def f(chemin: str, taille: int) -> ImageFont.FreeTypeFont:
    cle = (chemin, taille)
    if cle not in _polices:
        if not Path(chemin).exists():
            chemin = MONO
        _polices[cle] = ImageFont.truetype(chemin, taille)
    return _polices[cle]


# ── Courbes ──────────────────────────────────────────────────────────────

def sortie_cubique(t: float) -> float:
    """Entrée franche, arrivée posée. Pour ce qui apparaît."""
    return 1 - (1 - t) ** 3


def douce(t: float) -> float:
    """Lent, rapide, lent. Pour ce qui se déplace."""
    return t * t * (3 - 2 * t)


def butoir(t: float) -> float:
    """Avance, bute, et ne repart pas.

    La courbe du refus : l'argent accélère, touche le plafond et s'arrête net,
    sans le petit rebond élastique qui ferait croire à une hésitation. Un
    plafond qui laisse rebondir n'est pas un plafond.
    """
    return 1 - (1 - min(t, 1.0)) ** 4


# ── Surface ──────────────────────────────────────────────────────────────

def fond() -> Image.Image:
    """Dégradé vertical et halo bas, calculés une fois.

    Un aplat pur donne une image morte et fait baver les dégradés de YouTube
    sur les grands aplats ; un gradient très léger suffit à donner de l'air.
    """
    global _fond_cache
    if _fond_cache is None:
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        base = np.array(SURFACE, dtype=np.float32)[None, None, :]
        img = np.repeat(np.repeat(base, H, 0), L, 1)
        img += (y[:, :, None] * 10.0)
        xx = np.linspace(-1, 1, L, dtype=np.float32)[None, :]
        yy = np.linspace(-1.6, 0.7, H, dtype=np.float32)[:, None]
        halo = np.exp(-((xx**2) * 1.6 + (yy**2) * 2.2)) * 16.0
        img += halo[:, :, None] * np.array([0.45, 0.62, 1.0], dtype=np.float32)
        _fond_cache = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return _fond_cache.copy()


def melanger(c: tuple[int, int, int], vers: tuple[int, int, int],
             t: float) -> tuple[int, int, int]:
    t = min(1.0, max(0.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c, vers))


def opacite(c: tuple[int, int, int], a: float) -> tuple[int, int, int]:
    return melanger(SURFACE, c, a)


def ecrire(d: ImageDraw.ImageDraw, xy, texte: str, fnt, couleur, *,
           centre: bool = False, suivi: float = 0.0) -> float:
    """Écrit du texte avec un suivi réglable, et rend sa largeur.

    Le suivi manuel est ce qui sépare une grande typo de présentation d'un
    texte de terminal agrandi : à 60 px, les lettres d'une police d'interface
    sont trop serrées pour un titre.
    """
    x, y = xy
    largeur = sum(fnt.getlength(c) + suivi for c in texte) - (suivi if texte else 0)
    if centre:
        x = x - largeur / 2
    for c in texte:
        d.text((x, y), c, font=fnt, fill=couleur)
        x += fnt.getlength(c) + suivi
    return largeur


def replier(texte: str, fnt, largeur: int) -> list[str]:
    """Coupe un paragraphe à la largeur donnée, en mots entiers."""
    lignes, courante = [], ""
    for mot in texte.split():
        essai = f"{courante} {mot}".strip()
        if fnt.getlength(essai) > largeur and courante:
            lignes.append(courante)
            courante = mot
        else:
            courante = essai
    if courante:
        lignes.append(courante)
    return lignes


# ── Données réelles ──────────────────────────────────────────────────────

def lancer(args: list[str], *, ou: Path | None = None) -> tuple[int, str]:
    """Lance une commande et rend (code, sortie). N'avale jamais une erreur."""
    r = subprocess.run([sys.executable, *args], cwd=str(ou or RACINE),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def jouer_la_demo() -> Path:
    """Rejoue la démo pour produire un registre frais, et rend son chemin.

    Le registre du film n'est pas un fichier d'exemple conservé quelque part :
    c'est celui que la démo vient d'écrire. Si elle échoue, on s'arrête.
    """
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    chemin = TRAVAIL / "film.jsonl"
    for p in (chemin, chemin.with_suffix(".falsifie.jsonl")):
        p.unlink(missing_ok=True)
    code, sortie = lancer(["-m", "mandat.demo", str(chemin)])
    if code != 0 or not chemin.exists():
        raise SystemExit(f"la démo a échoué, rien à filmer :\n{sortie[-1500:]}")
    return chemin


def registre(chemin: Path) -> list[dict]:
    return [json.loads(l) for l in
            chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def nombre_de_tests() -> int:
    """Compte les tests sans les exécuter, pour que le chiffre dit soit le vrai."""
    code, sortie = lancer(["-m", "pytest", "tests", "--collect-only", "-q",
                           "-p", "no:cacheprovider"])
    m = re.search(r"(\d+) tests? collected", sortie)
    if not m:
        raise SystemExit(f"impossible de compter les tests :\n{sortie[-800:]}")
    return int(m.group(1))


def verdict_du_verificateur(chemin_falsifie: Path) -> list[str]:
    """Ce que le vérificateur dit du registre falsifié — exécuté, pas recopié."""
    code, sortie = lancer([
        "-c",
        "import json,sys;from pathlib import Path;"
        "sys.path.insert(0,r'" + str(RACINE) + "');"
        "from mandat.registre import Registre;"
        "print(json.dumps(Registre(Path(sys.argv[1])).verifier()))",
        str(chemin_falsifie)])
    if code != 0:
        raise SystemExit(f"le vérificateur n'a pas pu tourner :\n{sortie[-800:]}")
    return json.loads(sortie.strip().splitlines()[-1])


# ── Le film ──────────────────────────────────────────────────────────────

class Film:
    """Diffuse les images vers l'encodeur au lieu de les garder en mémoire.

    4 300 images uniques en 1920x1080 pèsent une trentaine de gigaoctets. On
    les produit donc une par une, et on note les temps forts au passage pour
    pouvoir caler autre chose dessus plus tard.
    """

    def __init__(self, fps: int, durees: dict[str, float]) -> None:
        self.fps = fps
        self.n = 0
        self.durees = durees
        self.reperes: list[tuple[float, str]] = []

    def duree(self, cle: str) -> float:
        return self.durees[cle]

    def repere(self, nom: str) -> None:
        self.reperes.append((self.n / self.fps, nom))

    def tenir(self, img: Image.Image, secondes: float) -> Iterator[Image.Image]:
        for _ in range(max(1, round(secondes * self.fps))):
            self.n += 1
            yield img

    def anime(self, duree: float, dessine) -> Iterator[Image.Image]:
        total = max(1, round(duree * self.fps))
        for i in range(total):
            self.n += 1
            yield dessine(i / total)
