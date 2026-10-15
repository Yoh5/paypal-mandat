"""La passerelle contre le vrai bac à sable PayPal.

Sautés sans identifiants, pour qu'un clone frais passe au vert sans compte.
Ils existent parce qu'un double de test ne prouve pas qu'on parle correctement
à PayPal : il prouve qu'on parle correctement à notre idée de PayPal. Les deux
bogues qu'un double ne pouvait pas attraper — la forme du montant décimal et le
nom exact du champ d'identifiant — ne se voient qu'ici.

    PAYPAL_CLIENT_ID=... PAYPAL_SECRET=... python -m pytest tests/test_paypal_reseau.py

Aucun paiement n'est capturé : une commande créée réserve une intention, et la
capture exige l'approbation d'un acheteur. Rien de réel ne bouge.
"""
from __future__ import annotations

import pytest

from mandat.mandat import Mandat, Porte
from mandat.paypal import EchecFournisseur, PayPal, Passerelle
from mandat.proposition import Proposition
from mandat.registre import Registre


@pytest.fixture(scope="module")
def paypal() -> PayPal:
    try:
        client = PayPal.depuis_env()
    except EchecFournisseur as absent:
        pytest.skip(f"pas d'identifiants bac à sable : {absent.detail}")
    return client


def test_le_jeton_est_delivre(paypal):
    assert paypal._acces(), "aucun jeton d'accès"


def test_une_commande_est_creee_et_relisible(paypal):
    reference, statut = paypal.creer(1_234, "USD", "integration test")
    assert reference and statut == "CREATED"
    assert paypal.references([reference]) == [reference]


def test_une_reference_inventee_nest_pas_reconnue(paypal):
    """Sans ce test, `references` pourrait tout rendre et le rapprochement
    serait un miroir."""
    assert paypal.references(["0" * 17]) == []


def test_la_passerelle_paie_vraiment_et_inscrit_la_vraie_reference(tmp_path, paypal):
    porte = Porte(Mandat.emettre("reseau-1", devise="USD",
                                 par_transaction="50.00", total="100.00"))
    p = Passerelle(porte, Registre(tmp_path / "r.jsonl"), paypal)
    enregistrement = p.payer(
        Proposition("integration test", 1_200, "USD", "boutique", ("preuve-1",)))

    assert enregistrement["issue"] == "paye"
    assert enregistrement["statut_fournisseur"] == "CREATED"
    # La référence inscrite doit être celle que PayPal reconnaît, pas la nôtre.
    assert paypal.references([enregistrement["reference"]]) \
        == [enregistrement["reference"]]
    assert p.registre.verifier() == []
    assert porte.depense == 1_200


def test_un_refus_natteint_jamais_paypal_meme_en_reseau(tmp_path, paypal):
    """La même assertion que dans les tests hors ligne, mais avec un vrai
    client branché : si le refus passait, une commande existerait chez PayPal.
    """
    porte = Porte(Mandat.emettre("reseau-2", devise="USD",
                                 par_transaction="10.00", total="50.00"))
    p = Passerelle(porte, Registre(tmp_path / "r.jsonl"), paypal)
    enregistrement = p.payer(Proposition("trop cher", 9_000, "USD", "boutique"))

    assert enregistrement["issue"] == "refuse"
    assert enregistrement["regle"] == "plafond par transaction"
    assert porte.depense == 0
    inscrites = [e.get("reference") for e in p.registre.enregistrements()]
    assert inscrites == [None] or all(r is None for r in inscrites)


def test_un_montant_hors_forme_est_refuse_par_paypal_pas_par_nous(paypal):
    """Une devise inexistante doit échouer côté PayPal, et notre client doit
    rendre `EchecFournisseur` plutôt que lever quelque chose d'opaque."""
    with pytest.raises(EchecFournisseur) as echec:
        paypal.creer(1_000, "ZZZ", "devise inexistante")
    assert echec.value.code >= 400
