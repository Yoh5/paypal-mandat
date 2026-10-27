"""La scène du refus : ce qu'un juré doit voir en trente secondes.

La *logique* du refus est déjà couverte par `test_paypal.py`, qui prouve que le
compteur d'appels du fournisseur reste à zéro. Ce fichier couvre autre chose :
le **point d'entrée**. Une garantie qu'on ne peut pas exécuter n'existe pas pour
un spectateur, et le règlement demande une démonstration, pas une suite de tests.

Rien ici ne touche le réseau — et c'est une propriété du produit, pas une
commodité de test : un refus se produit *avant* l'appel, donc la scène tourne
sans le moindre identifiant PayPal.
"""
from __future__ import annotations

import pytest

from mandat.demo import (FournisseurInterdit, scene_chaine, jouer, scene_falsification,
                         scene_refus)
from mandat.registre import Registre


class FournisseurEspion:
    """Compte les appels. Dans cette scène, il doit rester à zéro."""

    def __init__(self) -> None:
        self.appels: list[tuple[int, str, str]] = []

    def creer(self, centimes: int, devise: str, description: str) -> tuple[str, str]:
        self.appels.append((centimes, devise, description))
        return f"ORDER{len(self.appels):04d}", "CREATED"


def test_la_scene_refuse_avant_d_appeler_le_fournisseur(tmp_path):
    """Un refus inscrit, et le compteur du fournisseur à zéro.

    Les deux assertions sont une seule garantie vue des deux côtés. La première
    seule laisserait passer une fonction qui ne tente rien ; la seconde seule
    laisserait passer une fonction vide.
    """
    espion = FournisseurEspion()

    enregistrement = scene_refus(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=espion,
        ecrire=lambda *_: None,
    )

    assert enregistrement["issue"] == "refuse"
    assert espion.appels == []


def test_la_scene_nomme_la_regle_qui_a_refuse(tmp_path):
    """Le spectateur doit lire *pourquoi*, pas seulement *que*.

    « Refusé » sans la règle ni les deux montants ne se distingue pas d'une
    panne. C'est la différence entre une démonstration et un écran rouge.
    """
    lignes: list[str] = []

    scene_refus(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=FournisseurEspion(),
        ecrire=lignes.append,
    )

    texte = "\n".join(lignes)
    assert "plafond par transaction" in texte
    assert "89,90" in texte
    assert "40,00" in texte


def test_la_scene_tourne_avec_un_fournisseur_qui_refuse_d_etre_appele(tmp_path):
    """La garantie rendue indestructible plutôt que mesurée.

    `FournisseurInterdit` ne compte pas les appels : il les rend impossibles. Le
    jour où quelqu'un déplacerait la vérification du mandat *après* l'appel, ce
    test ne passerait pas plus lentement — il casserait, en nommant la faute.
    """
    enregistrement = scene_refus(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=FournisseurInterdit(),
        ecrire=lambda *_: None,
    )

    assert enregistrement["issue"] == "refuse"


@pytest.mark.parametrize("scene", [scene_refus, scene_chaine, scene_falsification])
def test_la_scene_s_affiche_sur_une_console_windows(tmp_path, scene):
    """Les tests capturaient dans une liste ; une console, elle, encode.

    La première version dessinait ses filets en caractères semi-graphiques
    (U+2500). `python -m mandat.demo` plantait donc sur `UnicodeEncodeError` en
    cp1252 — l'encodage par défaut du terminal de la machine où la vidéo sera
    filmée. Trois tests verts et une démonstration qui ne démarre pas : un test
    qui n'encode jamais ne peut pas voir ce défaut-là.

    Élargi aux deux scènes volontairement. Ce garde-fou-ci ne décrit pas un
    comportement neuf : il empêche un défaut déjà survenu une fois de revenir
    par la porte d'à côté.
    """
    lignes: list[str] = []

    scene(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=FournisseurEspion(),
        ecrire=lignes.append,
    )

    "\n".join(lignes).encode("cp1252")


def test_la_scene_de_la_chaine_part_de_la_reference_du_paiement(tmp_path):
    """On donne un identifiant de transaction, l'outil rend la justification.

    Le test regarde la **sortie**, pas seulement la valeur de retour : une
    fonction qui paierait sans jamais relire le registre renverrait le même
    enregistrement et satisferait une assertion sur `issue`, tout en étant
    incapable de restituer quoi que ce soit depuis une référence.
    """
    lignes: list[str] = []
    espion = FournisseurEspion()

    enregistrement = scene_chaine(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=espion,
        ecrire=lignes.append,
    )

    texte = "\n".join(lignes)
    assert enregistrement["issue"] == "paye"
    assert enregistrement["reference"] in texte
    assert "page-libraire" in texte


def test_la_scene_de_falsification_fait_nommer_la_ligne_modifiee(tmp_path):
    """La seule scene ou le produit doit echouer pour reussir.

    Un registre qui se declare « correct » apres qu'on a reecrit une ligne ne
    prouve rien du tout. Les deux assertions tiennent ensemble : intact avant,
    rompu apres. Une fonction qui renverrait un rapport sans rien ecrire ni
    falsifier ne pourrait satisfaire la premiere qu'en trichant sur la seconde.
    """
    rapport = scene_falsification(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=FournisseurEspion(),
        ecrire=lambda *_: None,
    )

    assert rapport["avant"] == []
    assert rapport["apres"]
    assert any("enregistrement" in e for e in rapport["apres"])


def test_jouer_enchaine_les_trois_scenes(tmp_path):
    """Le cablage lui-meme, parce qu'il a casse deux fois.

    Les scenes etaient vertes et `python -m mandat.demo` plantait : le point
    d'entree passait a la scene C un fournisseur interdit, alors qu'elle paie
    reellement. Un `__main__` marque « pragma: no cover » n'est pas une raison
    de ne pas le tester — c'est une raison de l'extraire.
    """
    lignes: list[str] = []

    jouer(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=FournisseurEspion(),
        ecrire=lignes.append,
    )

    texte = "\n".join(lignes)
    assert "Scene A" in texte or "Scène A" in texte
    assert "Scene B" in texte or "Scène B" in texte
    assert "Scene C" in texte or "Scène C" in texte
