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

from mandat.demo import FournisseurInterdit, scene_refus
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


def test_la_scene_s_affiche_sur_une_console_windows(tmp_path):
    """Les tests capturaient dans une liste ; une console, elle, encode.

    La première version dessinait ses filets en caractères semi-graphiques
    (U+2500). `python -m mandat.demo` plantait donc sur `UnicodeEncodeError` en
    cp1252 — l'encodage par défaut du terminal de la machine où la vidéo sera
    filmée. Trois tests verts et une démonstration qui ne démarre pas : un test
    qui n'encode jamais ne peut pas voir ce défaut-là.
    """
    lignes: list[str] = []

    scene_refus(
        registre=Registre(tmp_path / "registre.jsonl"),
        fournisseur=FournisseurInterdit(),
        ecrire=lignes.append,
    )

    "\n".join(lignes).encode("cp1252")
