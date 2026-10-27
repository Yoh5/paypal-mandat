"""Les plans. Un par idée, et une seule.

**La colonne vertébrale du film est un seul dessin : le chemin de l'argent.**
L'ouverture froide le montre sans un mot, la scène A le montre aboutir, la
scène B le montre buter. Le spectateur apprend le schéma une fois, puis il
reconnaît le même mécanisme donnant deux issues — ce qui vaut mieux que deux
illustrations qu'il faudrait relire.

Le découpage vit dans `narration.py` et les primitives dans `moteur.py`. Ici il
n'y a que du dessin.

Usage :
    python submission/video/film.py                    # rend mandat-demo.mp4
    python submission/video/film.py --fps 24 --apercu  # une image par plan
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from pathlib import Path
from typing import Iterator

import imageio
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import narration as N  # noqa: E402
from moteur import (ACCENT, CRITIQUE, ENCRE, ENCRE_2, ENCRE_3, FFMPEG, H, L,  # noqa: E402
                    MONO, MONO_G, PERMIS, SANS, SANS_G, SANS_L, SURFACE, TRAVAIL,
                    Film, butoir, douce, ecrire, f, fond, jouer_la_demo,
                    melanger, nombre_de_tests, opacite, registre, replier,
                    sortie_cubique, verdict_du_verificateur)

#: Géométrie du chemin de l'argent, partagée par les trois plans qui l'emploient.
VOIE_Y = 560
AGENT_X, PORTE_X, PAYPAL_X = 300, 960, 1620


#: `issue` est une valeur de donnee, pas un libelle. Le registre garde la
#: sienne ; le film affiche la langue du film.
ISSUE = {"paye": "paid", "refuse": "refused"}


def centimes(c: int) -> str:
    """2550 -> « 25,50 ». Même convention que le produit, virgule comprise."""
    return f"{c // 100},{c % 100:02d}"


# ── Le dessin partagé ────────────────────────────────────────────────────

def voie(d: ImageDraw.ImageDraw, *, avance: float, mur: float = 0.0,
         bloque: bool = False, etiquette: str = "", montant: str = "",
         paypal: float = 0.0, neutre: bool = False) -> None:
    """Le chemin de l'argent : agent -> porte -> PayPal.

    `avance` est la position du montant sur la voie (0 = chez l'agent, 1 = chez
    PayPal). `mur` fait apparaître le plafond à la porte. `bloque` barre le
    montant et éteint la portion qui suit la porte — **c'est la forme, pas la
    couleur, qui dit le refus** : un spectateur daltonien doit voir que le trait
    s'arrête et que le chiffre est barré.

    `neutre` sert à l'ouverture froide : mur en encre et stations sans nom. Le
    premier plan doit poser une **question** — « pourquoi l'argent s'arrête-t-il
    là ? » — et non livrer la réponse que la scène B existe pour donner. Une
    ouverture qui déflore son climax laisse un climax sans rien à révéler.
    """
    pt_fin = f(SANS, 26)
    pt_mono = f(MONO_G, 34)
    teinte = ENCRE_2 if neutre else CRITIQUE

    # Les trois stations.
    for x, nom, vif in ((AGENT_X, "AGENT", 1.0), (PORTE_X, "MANDATE", 1.0),
                        (PAYPAL_X, "PAYPAL", paypal if bloque else 1.0)):
        couleur = opacite(ENCRE_2 if vif > 0.4 else ENCRE_3, max(vif, 0.25))
        d.ellipse([x - 9, VOIE_Y - 9, x + 9, VOIE_Y + 9],
                  outline=couleur, width=2)
        if not neutre:
            ecrire(d, (x, VOIE_Y + 34), nom, pt_fin, couleur, centre=True,
                   suivi=3.0)

    # Le trait, en deux portions : avant la porte, puis après.
    d.line([AGENT_X + 9, VOIE_Y, PORTE_X - 9, VOIE_Y],
           fill=opacite(ENCRE_3, 0.9), width=2)
    apres = opacite(ENCRE_3, 0.14 if bloque else 0.9)
    d.line([PORTE_X + 9, VOIE_Y, PAYPAL_X - 9, VOIE_Y], fill=apres, width=2)

    # Le mur : il pousse depuis la voie, il n'apparaît pas d'un coup.
    if mur > 0:
        haut = int(96 * sortie_cubique(mur))
        d.line([PORTE_X, VOIE_Y - haut, PORTE_X, VOIE_Y + haut],
               fill=melanger(SURFACE, teinte, mur), width=5)

    # Le montant qui voyage. La butée tient compte de la LARGEUR du nombre :
    # la première version arrêtait son centre à 40 px du mur, donc son dernier
    # chiffre passait derrière. On s'arrête quand le bord droit touche.
    if montant:
        larg = sum(pt_mono.getlength(c) for c in montant)
        butee = (PORTE_X - 34 - larg / 2 - AGENT_X) / (PAYPAL_X - AGENT_X)
        arrete = bloque and avance >= butee
        t = min(avance, butee) if bloque else avance
        x = AGENT_X + (PAYPAL_X - AGENT_X) * t
        ecrire(d, (x, VOIE_Y - 72), montant, pt_mono,
               teinte if arrete else ENCRE, centre=True)
        if arrete:
            d.line([x - larg / 2 - 6, VOIE_Y - 50, x + larg / 2 + 6, VOIE_Y - 50],
                   fill=teinte, width=3)

    if etiquette:
        ecrire(d, (PORTE_X, VOIE_Y + 108), etiquette, f(SANS, 30),
               ENCRE_2, centre=True)


def titre(d: ImageDraw.ImageDraw, texte: str, sous: str = "", *,
          a: float = 1.0, y: int = 150) -> None:
    ecrire(d, (L // 2, y), texte, f(SANS_G, 64), opacite(ENCRE, a),
           centre=True, suivi=1.5)
    if sous:
        ecrire(d, (L // 2, y + 96), sous, f(SANS_L, 34), opacite(ENCRE_3, a),
               centre=True, suivi=1.0)


def paragraphe(d: ImageDraw.ImageDraw, texte: str, y: int, *, a: float = 1.0,
               taille: int = 38, couleur=ENCRE_2, largeur: int = 1200) -> int:
    fnt = f(SANS, taille)
    for i, ligne in enumerate(replier(texte, fnt, largeur)):
        ecrire(d, (L // 2, y + i * int(taille * 1.5)), ligne, fnt,
               opacite(couleur, a), centre=True)
        y_fin = y + i * int(taille * 1.5)
    return y_fin + int(taille * 1.5)


# ── Les plans ────────────────────────────────────────────────────────────

def ouverture_froide(film: Film) -> Iterator[Image.Image]:
    """Trois secondes muettes : l'argent avance, bute, s'arrête. Pas un mot.

    Le temps était déjà alloué au titre qui s'installe. Autant qu'il accroche.
    """
    film.repere("ouverture froide")

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        voie(d, avance=butoir(min(t * 1.9, 1.0)), montant="89,90",
             mur=max(0.0, min((t - 0.25) * 4, 1.0)), bloque=True,
             paypal=0.0, neutre=True)
        return img

    yield from film.anime(N.SILENCE_INITIAL, dessine)


def scene_ouverture(film: Film) -> Iterator[Image.Image]:
    film.repere("ouverture")
    duree = film.duree("ouverture")

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        a = sortie_cubique(min(t * 3, 1.0))
        titre(d, "A spend mandate for agents",
              "the model reads, the code decides", a=a, y=380)
        if t > 0.45:
            b = sortie_cubique(min((t - 0.45) * 3.2, 1.0))
            ecrire(d, (L // 2, 700), "A payment cannot be undone.",
                   f(SANS, 40), opacite(ENCRE_2, b), centre=True)
        return img

    yield from film.anime(duree, dessine)


def scene_mandat(film: Film) -> Iterator[Image.Image]:
    """Les quatre limites, en cascade. Puis la phrase qui porte le produit."""
    film.repere("mandat")
    duree = film.duree("mandat")
    lignes = [("per transaction", "40,00"), ("total", "100,00"),
              ("validity window", "open"), ("merchants", "The Corner Bookshop")]

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        titre(d, "The mandate", a=sortie_cubique(min(t * 5, 1.0)), y=150)

        x0, y0 = 560, 360
        for i, (cle, val) in enumerate(lignes):
            # Cascade : chaque ligne arrive après la précédente, et glisse un
            # peu — une arrivée sans déplacement ne se lit pas comme une arrivée.
            depart = 0.12 + i * 0.10
            a = sortie_cubique(max(0.0, min((t - depart) * 6, 1.0)))
            if a <= 0:
                continue
            y = y0 + i * 74 + int(18 * (1 - a))
            ecrire(d, (x0, y), cle, f(SANS, 36), opacite(ENCRE_3, a))
            ecrire(d, (x0 + 540, y), val, f(MONO_G, 36), opacite(ENCRE, a))
            d.line([x0, y + 56, x0 + 800, y + 56], fill=opacite(ENCRE_3, a * 0.3),
                   width=1)

        if t > 0.60:
            b = sortie_cubique(min((t - 0.60) * 3.0, 1.0))
            ecrire(d, (L // 2, 760), "enforced by code before the call,",
                   f(SANS_G, 40), opacite(ACCENT, b), centre=True)
            ecrire(d, (L // 2, 812), "not audited after",
                   f(SANS_G, 40), opacite(ACCENT, b), centre=True)
        return img

    yield from film.anime(duree, dessine)


def scene_paiement(film: Film, paye: dict) -> Iterator[Image.Image]:
    """Scène A : le mandat autorise, PayPal crée la commande, et on remonte."""
    film.repere("paiement (scène A)")
    duree = film.duree("paiement")
    montant = centimes(paye["intention"]["centimes"])
    reference = paye["reference"]

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        titre(d, "Allowed", a=sortie_cubique(min(t * 5, 1.0)), y=150)
        voie(d, avance=douce(min(t * 1.5, 1.0)), montant=montant,
             etiquette="within the mandate" if t > 0.35 else "")

        # La remontée : depuis la référence seule, la justification revient.
        if t > 0.52:
            b = sortie_cubique(min((t - 0.52) * 2.4, 1.0))
            ecrire(d, (L // 2, 800), f"order {reference}", f(MONO_G, 34),
                   opacite(ENCRE, b), centre=True, suivi=1.0)
            ecrire(d, (L // 2, 858), "and from that reference alone, the whole "
                   "chain comes back", f(SANS, 32), opacite(ENCRE_3, b),
                   centre=True)
        return img

    yield from film.anime(duree, dessine)


def scene_refus(film: Film, refus: dict) -> Iterator[Image.Image]:
    """Scène B, le temps fort : l'argent bute, et PayPal n'est jamais appelé."""
    film.repere("REFUS (scène B)")
    duree = film.duree("refus")
    montant = centimes(refus["intention"]["centimes"])
    regle, detail = refus["regle"], refus["detail"]

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        titre(d, "Refused", a=sortie_cubique(min(t * 5, 1.0)), y=150)

        # Le mur monte avant que le montant n'arrive : on sait ce qui l'attend.
        voie(d, avance=butoir(min(t * 1.25, 1.0)), montant=montant,
             mur=sortie_cubique(max(0.0, min((t - 0.08) * 5, 1.0))),
             bloque=True, paypal=0.0,
             etiquette=regle if t > 0.34 else "")

        if t > 0.44:
            b = sortie_cubique(min((t - 0.44) * 3.0, 1.0))
            ecrire(d, (L // 2, 790), detail, f(MONO, 34),
                   opacite(ENCRE_2, b), centre=True)
        if t > 0.60:
            c = sortie_cubique(min((t - 0.60) * 2.6, 1.0))
            ecrire(d, (L // 2, 870), "PayPal was never called.",
                   f(SANS_G, 44), opacite(ENCRE, c), centre=True)
            ecrire(d, (L // 2, 932),
                   "Not refunded. Not reversed. Never called.",
                   f(SANS, 32), opacite(ENCRE_3, c), centre=True)
        return img

    yield from film.anime(duree, dessine)


def scene_falsification(film: Film, reg: list[dict],
                        verdict: list[str]) -> Iterator[Image.Image]:
    """Scène C : deux maillons, l'un réécrit, et le vérificateur le nomme.

    Le maillon **se brise** — un vide dans la géométrie, le numéro, une croix.
    La couleur ne fait que renforcer : voir la note de `moteur.py`.
    """
    film.repere("falsification (scène C)")
    duree = film.duree("falsification")
    xs = [L // 2 - 260, L // 2 + 260]

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        titre(d, "The register", a=sortie_cubique(min(t * 6, 1.0)), y=150)

        rompu = t > 0.46
        casse = sortie_cubique(max(0.0, min((t - 0.46) * 4, 1.0)))

        for i, e in enumerate(reg[:2]):
            a = sortie_cubique(max(0.0, min((t - 0.08 - i * 0.08) * 6, 1.0)))
            if a <= 0:
                continue
            x = xs[i]
            abime = (i == 0 and rompu)
            bord = melanger(ENCRE_2, CRITIQUE, casse) if abime else opacite(ENCRE_2, a)
            d.rounded_rectangle([x - 190, 330, x + 190, 540], radius=10,
                                outline=bord, width=3 if abime else 2)
            ecrire(d, (x, 356), f"record {e['sequence']}", f(SANS, 28),
                   opacite(ENCRE_3, a), centre=True, suivi=2.0)
            # Le montant du premier change sous nos yeux : 6,40 -> 0,01.
            val = centimes(1) if abime else centimes(e["intention"]["centimes"])
            ecrire(d, (x, 404), val, f(MONO_G, 52),
                   melanger(ENCRE, CRITIQUE, casse) if abime else opacite(ENCRE, a),
                   centre=True)
            ecrire(d, (x, 480), ISSUE.get(e["issue"], e["issue"]), f(SANS, 28),
                   opacite(ENCRE_3, a), centre=True, suivi=2.0)
            if abime and casse > 0.5:
                # La croix : la forme dit la faute, pas seulement la teinte.
                k = (casse - 0.5) * 2
                for dx, dy in ((-1, -1), (-1, 1)):
                    d.line([x + dx * 34 * k, 404 + 26 + dy * 34 * k,
                            x - dx * 34 * k, 404 + 26 - dy * 34 * k],
                           fill=CRITIQUE, width=4)

        # Le lien entre les deux maillons : plein, puis un vide au milieu.
        a_lien = sortie_cubique(max(0.0, min((t - 0.22) * 5, 1.0)))
        if a_lien > 0:
            g, dr = xs[0] + 190, xs[1] - 190
            if rompu:
                trou = int((dr - g) * 0.34 * casse)
                mi = (g + dr) // 2
                d.line([g, 435, mi - trou, 435], fill=opacite(ENCRE_3, a_lien), width=3)
                d.line([mi + trou, 435, dr, 435], fill=opacite(ENCRE_3, a_lien), width=3)
            else:
                d.line([g, 435, dr, 435], fill=opacite(ENCRE_3, a_lien), width=3)
                ecrire(d, ((g + dr) // 2, 395), "chained", f(SANS, 24),
                       opacite(ENCRE_3, a_lien), centre=True, suivi=2.0)

        if not rompu and t > 0.30:
            b = sortie_cubique(min((t - 0.30) * 4, 1.0))
            ecrire(d, (L // 2, 640), "a refusal is recorded like a payment",
                   f(SANS, 34), opacite(ENCRE_2, b), centre=True)
        if rompu:
            b = sortie_cubique(min((t - 0.52) * 3.4, 1.0))
            ecrire(d, (L // 2, 640), "someone rewrites one line in the file",
                   f(SANS, 34), opacite(ENCRE_3, b), centre=True)
            if t > 0.66:
                c = sortie_cubique(min((t - 0.66) * 3.0, 1.0))
                ecrire(d, (L // 2, 724), verdict[0] if verdict else "",
                       f(MONO_G, 36), opacite(CRITIQUE, c), centre=True)
                ecrire(d, (L // 2, 792),
                       "the verifier does not call the log fine: it names the line",
                       f(SANS, 32), opacite(ENCRE_2, c), centre=True)
        return img

    yield from film.anime(duree, dessine)


def scene_limites(film: Film) -> Iterator[Image.Image]:
    """Les limites, dites calmement. Pas un schéma : du texte qu'on lit."""
    film.repere("limites")
    duree = film.duree("limites")
    points = [
        "It does not stop a malicious agent.",
        "It constrains the path that goes through it.",
        "Out-of-register payments are not verified without a webhook log.",
    ]

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        titre(d, "What this is not", a=sortie_cubique(min(t * 6, 1.0)), y=180)
        for i, p in enumerate(points):
            a = sortie_cubique(max(0.0, min((t - 0.14 - i * 0.16) * 5, 1.0)))
            if a <= 0:
                continue
            y = 430 + i * 110 + int(16 * (1 - a))
            ecrire(d, (L // 2, y), p, f(SANS, 38), opacite(ENCRE_2, a),
                   centre=True)
        return img

    yield from film.anime(duree, dessine)


def scene_these(film: Film) -> Iterator[Image.Image]:
    """La synthèse : le lien entre l'argent et le raisonnement, tracé."""
    film.repere("synthèse")
    duree = film.duree("these")

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        a = sortie_cubique(min(t * 4, 1.0))
        gx, dx_ = L // 2 - 380, L // 2 + 380
        ecrire(d, (gx, 430), "the money that moved", f(SANS_G, 40),
               opacite(ENCRE, a), centre=True)
        ecrire(d, (dx_, 430), "the reasoning that moved it", f(SANS_G, 40),
               opacite(ENCRE, a), centre=True)
        if t > 0.30:
            b = douce(min((t - 0.30) * 2.6, 1.0))
            d.line([gx + 200, 450, gx + 200 + int((dx_ - gx - 420) * b), 450],
                   fill=ACCENT, width=4)
        if t > 0.58:
            c = sortie_cubique(min((t - 0.58) * 3.0, 1.0))
            ecrire(d, (L // 2, 600), "PayPal already had the plumbing.",
                   f(SANS, 36), opacite(ENCRE_3, c), centre=True)
            ecrire(d, (L // 2, 672), "It did not have this link.",
                   f(SANS, 36), opacite(ENCRE_3, c), centre=True)
        if t > 0.78:
            e = sortie_cubique(min((t - 0.78) * 4.0, 1.0))
            ecrire(d, (L // 2, 790), "That link is what you just watched.",
                   f(SANS_G, 44), opacite(ENCRE, e), centre=True)
        return img

    yield from film.anime(duree, dessine)


def scene_fin(film: Film, tests: int) -> Iterator[Image.Image]:
    film.repere("fin")
    duree = film.duree("fin")

    def dessine(t: float) -> Image.Image:
        img = fond()
        d = ImageDraw.Draw(img)
        a = sortie_cubique(min(t * 3, 1.0))
        ecrire(d, (L // 2, 360), "The model reads. The code decides.",
               f(SANS_G, 58), opacite(ENCRE, a), centre=True, suivi=1.0)
        if t > 0.34:
            b = sortie_cubique(min((t - 0.34) * 3.0, 1.0))
            for i, s in enumerate((f"{tests} tests",
                                   "no runtime dependencies",
                                   "Apache-2.0")):
                ecrire(d, (L // 2, 520 + i * 60), s, f(SANS, 34),
                       opacite(ENCRE_3, b), centre=True)
        if t > 0.60:
            c = sortie_cubique(min((t - 0.60) * 3.0, 1.0))
            ecrire(d, (L // 2, 800), "github.com/Yoh5/paypal-mandat",
                   f(MONO_G, 36), opacite(ACCENT, c), centre=True, suivi=1.0)
        return img

    yield from film.anime(duree, dessine)


# ── Montage ──────────────────────────────────────────────────────────────

def images(film: Film, reg: list[dict], verdict: list[str],
           tests: int) -> Iterator[Image.Image]:
    paye = next(e for e in reg if e["issue"] == "paye")
    refus = next(e for e in reg if e["issue"] == "refuse")
    yield from ouverture_froide(film)
    yield from scene_ouverture(film)
    yield from scene_mandat(film)
    yield from scene_paiement(film, paye)
    yield from scene_refus(film, refus)
    yield from scene_falsification(film, reg, verdict)
    yield from scene_limites(film)
    yield from scene_these(film)
    yield from scene_fin(film, tests)


def piste_narration(scenes: dict[str, float]) -> Path:
    """Une seule piste, construite à partir des durées de scène elles-mêmes.

    Le silence qui suit chaque phrase n'est pas choisi : c'est exactement ce
    qui reste de la scène. Il n'existe donc aucun endroit où l'audio et l'image
    pourraient être calés différemment.
    """
    morceaux: list[bytes] = []
    with wave.open(str(TRAVAIL / "ouverture.wav")) as premiere:
        params = premiere.getparams()
    muet = b"\x00" * (params.sampwidth * params.nchannels)
    morceaux.append(muet * round(N.SILENCE_INITIAL * params.framerate))
    for cle in N.NARRATION:
        with wave.open(str(TRAVAIL / f"{cle}.wav")) as w:
            dit = w.getnframes()
            morceaux.append(w.readframes(dit))
        reste = round(scenes[cle] * params.framerate) - dit
        if reste > 0:
            morceaux.append(muet * reste)
    piste = TRAVAIL / "narration.wav"
    with wave.open(str(piste), "wb") as sortie:
        sortie.setparams(params)
        sortie.writeframes(b"".join(morceaux))
    return piste


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--sortie", default="mandat-demo.mp4")
    ap.add_argument("--apercu", action="store_true",
                    help="une image par plan, au lieu du film")
    a = ap.parse_args()

    chemin = jouer_la_demo()
    reg = registre(chemin)
    verdict = verdict_du_verificateur(chemin.with_suffix(".falsifie.jsonl"))
    tests = nombre_de_tests()
    scenes, _ = N.minuter()

    if a.apercu:
        apercu = Path(__file__).resolve().parent / "apercu"
        apercu.mkdir(exist_ok=True)
        film = Film(a.fps, scenes)
        for nom, gen in (("0-froide", ouverture_froide(film)),
                         ("1-ouverture", scene_ouverture(film)),
                         ("2-mandat", scene_mandat(film)),
                         ("3-paiement", scene_paiement(
                             film, next(e for e in reg if e["issue"] == "paye"))),
                         ("4-refus", scene_refus(
                             film, next(e for e in reg if e["issue"] == "refuse"))),
                         ("5-falsification", scene_falsification(film, reg, verdict)),
                         ("6-limites", scene_limites(film)),
                         ("7-these", scene_these(film)),
                         ("8-fin", scene_fin(film, tests))):
            imgs = list(gen)
            imgs[int(len(imgs) * 0.82)].save(apercu / f"{nom}.png")
            print(f"  aperçu {nom:18} ({len(imgs)} images)")
        return 0

    film = Film(a.fps, scenes)
    muet = TRAVAIL / "muet.mp4"
    with imageio.get_writer(str(muet), fps=a.fps, codec="libx264",
                            quality=8, macro_block_size=1) as w:
        for img in images(film, reg, verdict, tests):
            w.append_data(np.asarray(img))

    piste = piste_narration(scenes)
    final = Path(__file__).resolve().parent / a.sortie
    subprocess.run([FFMPEG, "-y", "-i", str(muet), "-i", str(piste),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", str(final)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"\n  {final.name} — {film.n} images, {film.n / a.fps:.1f}s")
    print("\n  Temps forts :")
    for seconde, nom in film.reperes:
        print(f"    {int(seconde // 60)}:{seconde % 60:05.2f}  {nom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
