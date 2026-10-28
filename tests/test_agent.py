# -*- coding: utf-8 -*-
"""L'agent, et la scène où il se fait avoir.

Un faux client plutôt qu'un appel réseau : la scène doit pouvoir être rejouée
par quelqu'un qui n'a pas de clé, et un test qui dépend d'un modèle distant
échoue pour des raisons qui n'ont rien à voir avec le code.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from mandat.agent import AucunModele, Lecture, graver, lire, rejouer
from mandat.demo import (FournisseurInterdit, LECTURE_ENREGISTREE, MARCHAND,
                         PAGE_PIEGEE, scene_injection)
from mandat.proposition import PropositionInfondee, fonder
from mandat.registre import Registre

#: Ce que le modèle répond quand l'injection a pris.
SUIVI = json.dumps({"quoi": "Express restock bundle", "montant": "29.99",
                    "devise": "EUR", "marchand": "Quick Supplies Ltd"})

#: Ce qu'il répond quand il a résisté.
RESISTE = json.dumps({"quoi": "A4 paper, 500 sheets", "montant": "6.40",
                      "devise": "EUR", "marchand": MARCHAND})


class ClientFactice:
    """Le strict minimum de la surface du SDK qu'`agent.lire` touche."""

    def __init__(self, texte: str) -> None:
        self.texte = texte
        self.appels = 0
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.appels += 1
        self.dernier = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.texte)])


# --------------------------------------------------------------------------
# lire()
# --------------------------------------------------------------------------

def test_lire_rend_ce_que_le_modele_propose():
    lecture = lire(PAGE_PIEGEE, client=ClientFactice(SUIVI), enregistrement=None)
    assert lecture.propose.montant_centimes == 2999
    assert lecture.propose.marchand == "Quick Supplies Ltd"
    assert lecture.rejoue is False


def test_la_page_est_bien_ce_qui_est_envoye_au_modele():
    """Un test de câblage : la scène ne vaut rien si le modèle lit autre chose."""
    client = ClientFactice(SUIVI)
    lire(PAGE_PIEGEE, client=client, enregistrement=None)
    assert client.dernier["messages"][0]["content"] == PAGE_PIEGEE


def test_une_cloture_markdown_ne_fait_pas_echouer_la_lecture():
    client = ClientFactice("Here you go:\n```json\n" + SUIVI + "\n```")
    assert lire(PAGE_PIEGEE, client=client, enregistrement=None).propose.montant_centimes == 2999


def test_une_reponse_sans_json_leve_au_lieu_de_deviner():
    with pytest.raises(ValueError, match="aucun objet JSON"):
        lire(PAGE_PIEGEE, client=ClientFactice("I would rather not."), enregistrement=None)


def test_un_champ_manquant_leve_au_lieu_de_completer():
    client = ClientFactice(json.dumps({"quoi": "x", "devise": "EUR"}))
    with pytest.raises(ValueError, match="montant"):
        lire(PAGE_PIEGEE, client=client, enregistrement=None)


def test_sans_cle_et_sans_enregistrement_on_leve(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(AucunModele):
        lire(PAGE_PIEGEE, enregistrement=tmp_path / "absent.json")


def test_un_rejeu_est_marque_comme_tel(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    chemin = tmp_path / "lecture.json"
    graver(Lecture(propose=lire(PAGE_PIEGEE, client=ClientFactice(SUIVI),
                                enregistrement=None).propose,
                   brut=SUIVI, modele="modele-de-test", quand="2026-10-28T00:00:00Z"),
           chemin, PAGE_PIEGEE)

    relu = rejouer(chemin)
    assert relu.rejoue is True
    assert relu.propose.montant_centimes == 2999
    assert "replayed" in relu.en_clair()

    # Et `lire` sans clé doit le retrouver tout seul.
    assert lire(PAGE_PIEGEE, enregistrement=chemin).rejoue is True


def test_l_enregistrement_garde_la_page_qui_a_produit_la_reponse(tmp_path):
    """Rejouer une réponse contre une autre page serait une démonstration fausse."""
    chemin = tmp_path / "lecture.json"
    lire(PAGE_PIEGEE, client=ClientFactice(SUIVI), enregistrement=chemin)
    assert json.loads(chemin.read_text(encoding="utf-8"))["page"] == PAGE_PIEGEE


# --------------------------------------------------------------------------
# La page piégée elle-même
# --------------------------------------------------------------------------

def test_la_page_porte_bien_les_trois_proprietes_qui_font_la_scene():
    """Si l'un des trois saute, la narration de la scène devient fausse."""
    assert "29,99" in PAGE_PIEGEE                      # le montant est sur la page
    assert "Quick Supplies Ltd" in PAGE_PIEGEE         # le marchand aussi
    assert "Disregard the catalogue" in PAGE_PIEGEE    # et l'instruction cachée


def test_l_ancrage_ne_rattrape_PAS_une_injection_ecrite_sur_la_page():
    """Le test qui dit la vérité désagréable.

    `fonder()` demande qu'un chiffre proposé se retrouve dans ce que l'agent a
    lu. Ici il s'y retrouve — c'est l'attaquant qui l'y a écrit. Le contrôle
    passe donc, et la scène le dit à l'écran. Si quelqu'un renforce un jour
    `fonder()`, ce test tombera et rappellera qu'il faut réécrire la scène.
    """
    propose = lire(PAGE_PIEGEE, client=ClientFactice(SUIVI),
                   enregistrement=None).propose
    assert fonder(propose, [PAGE_PIEGEE]) is propose


def test_l_ancrage_rattrape_en_revanche_un_prix_absent_de_la_page():
    """La contrepartie : ce que le contrôle fait vraiment."""
    invente = json.dumps({"quoi": "Express restock bundle", "montant": "480.00",
                          "devise": "EUR", "marchand": "Quick Supplies Ltd"})
    propose = lire(PAGE_PIEGEE, client=ClientFactice(invente),
                   enregistrement=None).propose
    with pytest.raises(PropositionInfondee, match="montant"):
        fonder(propose, [PAGE_PIEGEE])


# --------------------------------------------------------------------------
# La scène
# --------------------------------------------------------------------------

def _jouer(texte_modele, tmp_path, **kw):
    lignes: list[str] = []
    issue = scene_injection(
        registre=Registre(tmp_path / "injection.jsonl"),
        fournisseur=FournisseurInterdit(),
        ecrire=lignes.append,
        client=ClientFactice(texte_modele),
        enregistrement=None,
        **kw)
    return issue, "\n".join(lignes)


def test_le_modele_suit_l_injection_et_le_mandat_refuse(tmp_path):
    issue, sortie = _jouer(SUIVI, tmp_path)

    assert issue["suivi"] is True
    # Les deux contrôles qui ne servent à rien ici, et c'est le propos.
    assert issue["ancrage"] is None
    assert issue["sous_plafond"] is True
    # Celui qui tient.
    assert issue["enregistrement"]["issue"] != "paye"
    assert "REFUSED" in sortie
    assert "merchant allowlist" in sortie


def test_le_fournisseur_n_est_jamais_appele(tmp_path):
    """`FournisseurInterdit` lève si on l'appelle : le test est le silence."""
    issue, _ = _jouer(SUIVI, tmp_path)
    assert issue["enregistrement"]["issue"] != "paye"


def test_le_refus_est_ecrit_dans_le_registre_et_chaine(tmp_path):
    chemin = tmp_path / "injection.jsonl"
    lignes: list[str] = []
    scene_injection(registre=Registre(chemin), fournisseur=FournisseurInterdit(),
                    ecrire=lignes.append, client=ClientFactice(SUIVI),
                    enregistrement=None)
    corps = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines()]
    assert len(corps) == 1
    assert corps[0]["issue"] != "paye"
    assert corps[0]["chain"]


def test_un_modele_qui_resiste_ne_paie_rien_et_le_dit(tmp_path):
    """Le modèle n'est pas tenu de se faire avoir, et la scène ne triche pas."""
    issue, sortie = _jouer(RESISTE, tmp_path)
    assert issue["suivi"] is False
    assert issue["enregistrement"] is None
    assert "did not follow" in sortie
    assert "REFUSED" not in sortie


def test_la_scene_annonce_si_la_lecture_est_rejouee(tmp_path):
    chemin = tmp_path / "lecture.json"
    lire(PAGE_PIEGEE, client=ClientFactice(SUIVI), enregistrement=chemin)
    lignes: list[str] = []
    scene_injection(registre=Registre(tmp_path / "r.jsonl"),
                    fournisseur=FournisseurInterdit(), ecrire=lignes.append,
                    enregistrement=chemin)
    assert "replayed from a recorded run" in "\n".join(lignes)


def test_la_scene_tient_dans_un_terminal_cp1252(tmp_path):
    """Même règle que les autres scènes : ce qui ne s'affiche pas ne se filme pas."""
    _, sortie = _jouer(SUIVI, tmp_path)
    sortie.encode("cp1252")
