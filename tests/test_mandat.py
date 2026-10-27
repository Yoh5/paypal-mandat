"""Le mandat doit mordre, et dire où il a mordu.

Ces tests épinglent les décisions qui séparent un vrai plafond d'une règle
décorative : les montants en entiers, le refus qui nomme la règle et le chiffre,
l'engagement avant l'appel au fournisseur, et l'immuabilité.
"""

from __future__ import annotations

import pytest

from mandat.mandat import Mandat, Porte, Refus, _centimes, euros


def mandat(**kw) -> Mandat:
    base = {"par_transaction": "25.00", "total": "100.00"}
    base.update(kw)
    return Mandat.emettre("m-1", **base)


# ── Les montants ────────────────────────────────────────────────────────

def test_les_montants_decimaux_sont_lus_en_centimes():
    assert _centimes("19.99") == 1999
    assert _centimes("19.9") == 1990
    assert _centimes("19") == 1900
    assert _centimes(1999) == 1999


def test_un_flottant_est_refuse():
    """0.1 + 0.2 != 0.3, et un plafond franchi par arrondi se découvre sur
    l'argent de quelqu'un."""
    with pytest.raises(TypeError, match="flottant"):
        _centimes(19.99)


def test_un_booleen_n_est_pas_un_montant():
    with pytest.raises(TypeError):
        _centimes(True)


def test_l_affichage_est_lisible():
    assert euros(2550) == "25,50"
    assert euros(5) == "0,05"
    assert euros(-1999) == "-19,99"


# ── Les plafonds ────────────────────────────────────────────────────────

def test_un_paiement_sous_les_plafonds_passe():
    p = Porte(mandat())
    assert p.engager("10.00") == 1000
    assert p.reste == 9000


def test_le_plafond_par_transaction_mord():
    p = Porte(mandat())
    with pytest.raises(Refus) as leve:
        p.engager("25.01")
    assert leve.value.regle == "per-transaction cap"
    assert "25,01" in leve.value.detail and "25,00" in leve.value.detail


def test_le_plafond_total_mord_sur_le_cumul():
    """Quatre paiements de 25 passent, le cinquième non — c'est le cumul qui
    compte, pas chaque montant pris isolément."""
    p = Porte(mandat())
    for _ in range(4):
        p.engager("25.00")
    assert p.reste == 0
    with pytest.raises(Refus) as leve:
        p.engager("0.01")
    assert leve.value.regle == "total cap"


def test_le_refus_nomme_la_regle_et_les_chiffres():
    """« Refusé » envoie chercher au mauvais endroit."""
    p = Porte(mandat(total="30.00", par_transaction="30.00"))
    p.engager("25.00")
    with pytest.raises(Refus) as leve:
        p.engager("10.00")
    d = leve.value.detail
    assert "10,00" in d and "5,00" in d and "30,00" in d


def test_un_montant_nul_ou_negatif_n_est_pas_un_paiement():
    p = Porte(mandat())
    for mauvais in ("0", "-5.00"):
        with pytest.raises(Refus) as leve:
            p.engager(mauvais)
        assert leve.value.regle == "amount"


# ── Devise, marchand, fenêtre ───────────────────────────────────────────

def test_une_autre_devise_est_refusee():
    p = Porte(mandat())
    with pytest.raises(Refus) as leve:
        p.engager("10.00", devise="USD")
    assert leve.value.regle == "currency"


def test_un_marchand_hors_liste_est_refuse():
    p = Porte(mandat(marchands=("libraire", "epicier")))
    assert p.engager("10.00", marchand="libraire") == 1000
    with pytest.raises(Refus) as leve:
        p.engager("10.00", marchand="casino")
    assert leve.value.regle == "merchant"
    assert "epicier" in leve.value.detail, "le refus doit dire ce qui est permis"


def test_sans_liste_tout_marchand_passe():
    p = Porte(mandat())
    assert p.engager("10.00", marchand="n-importe-qui") == 1000


def test_hors_de_la_fenetre_de_validite():
    p = Porte(mandat(valide_de="2026-11-01T00:00:00Z", valide_jusqu_a="2026-11-30T23:59:59Z"))
    assert p.engager("10.00", instant="2026-11-15T12:00:00Z") == 1000
    for dehors in ("2026-10-31T23:59:59Z", "2026-12-01T00:00:00Z"):
        with pytest.raises(Refus) as leve:
            p.engager("10.00", instant=dehors)
        assert leve.value.regle == "validity window"


# ── Engagement, restitution, traces ─────────────────────────────────────

def test_verifier_ne_consomme_pas_le_mandat():
    p = Porte(mandat())
    p.verifier("25.00")
    p.verifier("25.00")
    assert p.depense == 0, "verifier ne doit pas retenir"


def test_engager_retient_avant_l_appel_au_fournisseur():
    """Si on retenait après, deux paiements concurrents franchiraient tous deux
    un plafond qu'un seul aurait dû franchir."""
    p = Porte(mandat(total="30.00"))
    p.engager("25.00")
    assert p.depense == 2500
    with pytest.raises(Refus):
        p.engager("25.00")


def test_un_paiement_echoue_rend_son_engagement():
    """Sans restitution, un refus du fournisseur consommerait le mandat pour de
    l'argent qui n'est jamais parti."""
    p = Porte(mandat())
    c = p.engager("25.00")
    p.rendre(c)
    assert p.depense == 0
    assert p.engager("25.00") == 2500


def test_la_restitution_ne_descend_pas_sous_zero():
    p = Porte(mandat())
    p.engager("10.00")
    p.rendre(99999)
    assert p.depense == 0


def test_les_refus_sont_conserves():
    """Un mandat dont on ne voit que les succès ne prouve rien : ce sont les
    refus qui montrent qu'il mordait."""
    p = Porte(mandat())
    for mauvais in ("30.00", "40.00"):
        with pytest.raises(Refus):
            p.engager(mauvais)
    assert len(p.refus) == 2
    assert all(r.regle == "per-transaction cap" for r in p.refus)


# ── L'immuabilité ───────────────────────────────────────────────────────

def test_un_mandat_ne_s_elargit_pas():
    with pytest.raises(TypeError, match="ne s'élargit pas"):
        mandat().elargir(total="1000.00")


def test_un_mandat_est_gele():
    m = mandat()
    with pytest.raises(Exception):
        m.total = 999999  # type: ignore[misc]


def test_un_plafond_par_transaction_au_dessus_du_total_est_refuse():
    """Il ne mordrait jamais, donc c'est une erreur de configuration et non une
    politique — à dire à l'émission plutôt qu'à découvrir en production."""
    with pytest.raises(ValueError, match="ne mordrait jamais"):
        Mandat.emettre("m", par_transaction="200.00", total="100.00")


def test_un_plafond_nul_est_refuse():
    for mauvais in ({"par_transaction": "0"}, {"total": "0"}):
        with pytest.raises(ValueError, match="interdit tout paiement"):
            Mandat.emettre("m", **mauvais)
