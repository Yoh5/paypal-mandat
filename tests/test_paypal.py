"""La passerelle : ce qui doit rester vrai quand le mandat et PayPal se touchent.

Le fournisseur est un double qui **compte ses appels**. Toute la valeur de ce
fichier tient dans une seule assertion, répétée sous plusieurs angles : quand le
mandat refuse, ce compteur reste à zéro. Un plafond vérifié après l'appel n'est
pas un plafond, c'est un rapport.

Rien ici ne touche le réseau. Les tests qui parlent vraiment à PayPal vivent
dans `tests/test_paypal_reseau.py` et sont sautés sans identifiants.
"""
from __future__ import annotations

import pytest

from mandat.mandat import Mandat, Porte
from mandat.paypal import EchecFournisseur, PayPal, Passerelle, resume
from mandat.proposition import Proposition
from mandat.registre import Registre


class FournisseurEspion:
    """Compte les appels et rend ce qu'on lui a dit de rendre."""

    def __init__(self, panne: EchecFournisseur | None = None) -> None:
        self.appels: list[tuple[int, str, str]] = []
        self.panne = panne
        self.connues: list[str] = []

    def creer(self, centimes: int, devise: str, description: str) -> tuple[str, str]:
        self.appels.append((centimes, devise, description))
        if self.panne:
            raise self.panne
        reference = f"ORDER{len(self.appels):04d}"
        self.connues.append(reference)
        return reference, "CREATED"

    def references(self, identifiants: list[str]) -> list[str]:
        return [i for i in identifiants if i in self.connues]


def passerelle(tmp_path, **limites) -> tuple[Passerelle, FournisseurEspion]:
    limites.setdefault("par_transaction", "50.00")
    limites.setdefault("total", "100.00")
    porte = Porte(Mandat.emettre("m-1", devise="EUR", **limites))
    espion = FournisseurEspion()
    return Passerelle(porte, Registre(tmp_path / "registre.jsonl"), espion), espion


def proposition(centimes=1200, marchand="papeterie", devise="EUR") -> Proposition:
    return Proposition("ramettes A4", centimes, devise, marchand, ("devis-17",))


# --------------------------------------------------------------------------- #
# Le cœur : un refus n'atteint jamais le réseau
# --------------------------------------------------------------------------- #
def test_un_refus_de_plafond_napelle_pas_le_fournisseur(tmp_path):
    p, espion = passerelle(tmp_path)
    enregistrement = p.payer(proposition(centimes=9_000))
    assert espion.appels == [], "PayPal a été appelé pour un montant refusé"
    assert enregistrement["issue"] == "refuse"
    assert enregistrement["regle"] == "per-transaction cap"


def test_un_marchand_hors_mandat_napelle_pas_le_fournisseur(tmp_path):
    p, espion = passerelle(tmp_path, marchands=["papeterie"])
    enregistrement = p.payer(proposition(marchand="casino-en-ligne"))
    assert espion.appels == []
    assert enregistrement["regle"] == "merchant"


def test_une_devise_etrangere_napelle_pas_le_fournisseur(tmp_path):
    p, espion = passerelle(tmp_path)
    enregistrement = p.payer(proposition(devise="USD"))
    assert espion.appels == []
    assert enregistrement["regle"] == "currency"


def test_le_plafond_total_arrete_le_deuxieme_paiement(tmp_path):
    p, espion = passerelle(tmp_path, par_transaction="60.00", total="100.00")
    p.payer(proposition(centimes=6_000))
    enregistrement = p.payer(proposition(centimes=6_000))
    assert len(espion.appels) == 1, "le second a franchi le total"
    assert enregistrement["regle"] == "total cap"
    assert "40,00" in enregistrement["detail"] or "40.00" in enregistrement["detail"]


# --------------------------------------------------------------------------- #
# Le refus est inscrit, pas seulement renvoyé
# --------------------------------------------------------------------------- #
def test_le_refus_est_au_registre_au_meme_titre_quun_paiement(tmp_path):
    p, _ = passerelle(tmp_path)
    p.payer(proposition(centimes=1_000))
    p.payer(proposition(centimes=9_000))
    issues = [e["issue"] for e in p.registre.enregistrements()]
    assert issues == ["paye", "refuse"]


def test_la_chaine_tient_apres_un_refus_et_un_paiement(tmp_path):
    p, _ = passerelle(tmp_path)
    p.payer(proposition(centimes=1_000))
    p.payer(proposition(centimes=9_000))
    p.payer(proposition(centimes=500))
    assert p.registre.verifier() == []


def test_un_refus_ne_consomme_pas_le_mandat(tmp_path):
    p, _ = passerelle(tmp_path)
    p.payer(proposition(centimes=9_000))
    assert p.porte.depense == 0
    assert p.porte.reste == 10_000


# --------------------------------------------------------------------------- #
# Le chemin qui paie
# --------------------------------------------------------------------------- #
def test_un_paiement_porte_la_reference_du_fournisseur(tmp_path):
    p, espion = passerelle(tmp_path)
    enregistrement = p.payer(proposition(centimes=1_200))
    assert espion.appels == [(1_200, "EUR", "ramettes A4")]
    assert enregistrement["reference"] == "ORDER0001"
    assert enregistrement["issue"] == "paye"
    assert enregistrement["depense_apres"] == 1_200
    assert enregistrement["statut_fournisseur"] == "CREATED"


def test_les_preuves_suivent_jusquau_registre(tmp_path):
    p, _ = passerelle(tmp_path)
    enregistrement = p.payer(proposition())
    assert enregistrement["preuves"] == ["devis-17"]


def test_pourquoi_remonte_la_justification_depuis_la_reference(tmp_path):
    p, _ = passerelle(tmp_path)
    p.payer(proposition(centimes=1_200))
    justification = p.pourquoi("ORDER0001")
    assert justification["intention"]["centimes"] == 1_200
    assert justification["preuves"] == ["devis-17"]


# --------------------------------------------------------------------------- #
# La panne du fournisseur n'est pas un refus
# --------------------------------------------------------------------------- #
def test_une_panne_apres_engagement_rend_largent_au_mandat(tmp_path):
    porte = Porte(Mandat.emettre("m-1", par_transaction="50.00", total="100.00"))
    espion = FournisseurEspion(panne=EchecFournisseur(503, "indisponible"))
    p = Passerelle(porte, Registre(tmp_path / "r.jsonl"), espion)
    with pytest.raises(EchecFournisseur):
        p.payer(proposition(centimes=1_200))
    assert porte.depense == 0, (
        "le plafond a été consommé par un paiement qui n'est jamais parti")


def test_une_panne_laisse_le_mandat_utilisable(tmp_path):
    porte = Porte(Mandat.emettre("m-1", par_transaction="50.00", total="100.00"))
    casse = FournisseurEspion(panne=EchecFournisseur(503, "indisponible"))
    p = Passerelle(porte, Registre(tmp_path / "r.jsonl"), casse)
    with pytest.raises(EchecFournisseur):
        p.payer(proposition(centimes=1_200))
    casse.panne = None
    assert p.payer(proposition(centimes=1_200))["issue"] == "paye"


# --------------------------------------------------------------------------- #
# Rapprochement
# --------------------------------------------------------------------------- #
def test_une_reference_hors_registre_est_signalee(tmp_path):
    """De l'argent qui a bougé sans décision inscrite : l'écart grave."""
    p, _ = passerelle(tmp_path)
    p.payer(proposition(centimes=1_000))
    ecarts = p.rapprocher(["ORDER0001", "ORDER-FANTOME"])
    assert ecarts["verifie"] is True
    assert ecarts["sorties_de_route"] == ["ORDER-FANTOME"]


def test_sans_liste_du_fournisseur_lecart_est_dit_non_verifie(tmp_path):
    """Le défaut que ce test fixe : la première version rendait une liste vide
    parce qu'elle n'avait rien cherché, ce qui se lisait « rien à signaler »."""
    p, _ = passerelle(tmp_path)
    p.payer(proposition(centimes=1_000))
    ecarts = p.rapprocher()
    assert ecarts["verifie"] is False
    assert ecarts["sorties_de_route"] is None, (
        "une liste vide ici serait indiscernable d'un contrôle qui a réussi")
    assert "webhooks" in ecarts["pourquoi_non_verifie"]


def test_le_controle_le_plus_important_peut_echouer(tmp_path):
    """Un garde qui ne peut pas se déclencher n'est pas un garde.

    La première version interrogeait le fournisseur avec les références déjà
    inscrites : par construction, aucune sortie de route n'était trouvable.
    """
    p, _ = passerelle(tmp_path)
    p.payer(proposition(centimes=1_000))
    assert p.rapprocher(["INCONNUE-1", "INCONNUE-2"])["sorties_de_route"] == [
        "INCONNUE-1", "INCONNUE-2"]


def test_une_reference_inscrite_que_le_fournisseur_ignore_est_signalee(tmp_path):
    p, espion = passerelle(tmp_path)
    p.payer(proposition(centimes=1_000))
    espion.connues.clear()                   # la commande a disparu chez PayPal
    assert p.rapprocher()["introuvables"] == ["ORDER0001"]


# --------------------------------------------------------------------------- #
# Conversion centimes → chaîne décimale, au bord et nulle part ailleurs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("centimes,attendu", [
    (1_200, "12.00"), (5, "0.05"), (100, "1.00"), (99, "0.99"),
    (1_000_000, "10000.00"), (1_050, "10.50"),
])
def test_le_montant_envoye_a_paypal_est_exact(centimes, attendu, monkeypatch):
    """Aucun flottant n'entre dans la décision ; la conversion vit au bord."""
    envoye = {}

    def faux_appel(self, chemin, *, entetes, corps=None, methode="GET"):
        if chemin.endswith("/token"):
            return 200, {"access_token": "x"}
        envoye["corps"] = __import__("json").loads(corps)
        return 201, {"id": "ORDER1", "status": "CREATED"}

    monkeypatch.setattr(PayPal, "_appeler", faux_appel)
    PayPal("c", "s").creer(centimes, "EUR", "test")
    assert envoye["corps"]["purchase_units"][0]["amount"]["value"] == attendu


# --------------------------------------------------------------------------- #
# La forme de l'objet, qui est elle-même une garantie
# --------------------------------------------------------------------------- #
def test_la_passerelle_nexpose_aucune_methode_qui_prenne_un_montant(tmp_path):
    """Pas un contrôle : un champ absent.

    Si une méthode publique acceptait un montant, il existerait un chemin vers
    l'argent qui ne passe pas par la proposition — donc pas par la porte. Ce
    test échoue le jour où quelqu'un en ajoute une, ce qui est le bon moment
    pour en discuter.
    """
    import inspect
    p, _ = passerelle(tmp_path)
    for nom in dir(p):
        if nom.startswith("_"):
            continue
        membre = getattr(p, nom)
        if not callable(membre):
            continue
        parametres = set(inspect.signature(membre).parameters)
        assert not parametres & {"montant", "centimes", "montant_centimes"}, (
            f"Passerelle.{nom} accepte un montant : il existe un chemin vers "
            "PayPal qui ne passe pas par le mandat")


def test_resume_dit_le_refus_aussi_clairement_que_le_paiement(tmp_path):
    p, _ = passerelle(tmp_path)
    paye = resume(p.payer(proposition(centimes=1_000)))
    refuse = resume(p.payer(proposition(centimes=9_000)))
    assert paye.startswith("PAID") and "ORDER0001" in paye
    assert refuse.startswith("REFUSED") and "per-transaction cap" in refuse
