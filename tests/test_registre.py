"""Le registre doit prouver, et alerter quand il ne peut pas.

Trois décisions épinglées ici :

1. les refus sont inscrits comme les paiements, sinon le registre raconte un
   agent exemplaire qui n'a jamais rien tenté d'interdit ;
2. la chaîne nomme le premier enregistrement qui ne tient pas, et signale un
   champ qu'aucun hachage ne couvre ;
3. **une référence inconnue est une alarme, pas une absence** — si le
   fournisseur a cette transaction, l'argent est parti sans passer par le
   mandat.
"""

from __future__ import annotations

import json

import pytest

from mandat.registre import _CORPS, HorsRegistre, Registre, _empreinte

QUAND = "2026-11-02T10:00:00Z"


def registre(tmp_path) -> Registre:
    return Registre(tmp_path / "paiements.jsonl")


def un_paiement(r: Registre, reference="PAY-1", centimes=2500, **kw):
    return r.paiement(at=QUAND, mandat="m-1", montant_centimes=centimes,
                      devise="EUR", reference=reference, **kw)


# ── Écriture ────────────────────────────────────────────────────────────

def test_un_paiement_s_inscrit_avec_sa_justification(tmp_path):
    r = registre(tmp_path)
    e = un_paiement(r, preuves=["sha256:abc"], marchand="libraire", depense_apres=2500)

    assert e["issue"] == "paye"
    assert e["reference"] == "PAY-1"
    assert e["preuves"] == ["sha256:abc"]
    assert e["intention"]["marchand"] == "libraire"


def test_un_paiement_sans_reference_est_refuse(tmp_path):
    """Sans référence, il ne peut pas être rapproché — et le rapprochement est
    exactement ce que ce registre existe pour permettre."""
    with pytest.raises(ValueError, match="rapproché"):
        registre(tmp_path).paiement(at=QUAND, mandat="m-1", montant_centimes=100,
                                    devise="EUR", reference="")


def test_un_refus_s_inscrit_au_meme_titre(tmp_path):
    """Sans ça, le registre raconte un agent qui n'a jamais rien tenté
    d'interdit."""
    r = registre(tmp_path)
    r.refus(at=QUAND, mandat="m-1", montant_centimes=9999, devise="EUR",
            regle="per-transaction cap", detail="99,99 requested, 25,00 allowed")

    e = r.enregistrements()[0]
    assert e["issue"] == "refuse"
    assert e["regle"] == "per-transaction cap"
    assert "25,00" in e["detail"]


def test_les_deux_coexistent_dans_l_ordre(tmp_path):
    r = registre(tmp_path)
    un_paiement(r, "PAY-1")
    r.refus(at=QUAND, mandat="m-1", montant_centimes=9999, devise="EUR",
            regle="plafond total", detail="plus rien")
    un_paiement(r, "PAY-2")

    issues = [e["issue"] for e in r.enregistrements()]
    assert issues == ["paye", "refuse", "paye"]
    assert [e["sequence"] for e in r.enregistrements()] == [1, 2, 3]


# ── La chaîne ───────────────────────────────────────────────────────────

def test_un_registre_intact_tient(tmp_path):
    r = registre(tmp_path)
    un_paiement(r, "PAY-1")
    un_paiement(r, "PAY-2", centimes=1000)
    assert r.verifier() == []


def test_un_enregistrement_modifie_est_nomme(tmp_path):
    r = registre(tmp_path)
    un_paiement(r, "PAY-1")
    un_paiement(r, "PAY-2", centimes=1000)

    lignes = r.chemin.read_text(encoding="utf-8").splitlines()
    e = json.loads(lignes[1])
    e["intention"]["centimes"] = 1          # on réécrit le montant
    lignes[1] = json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    r.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    problemes = r.verifier()
    assert problemes and "record 2" in problemes[0]


def test_un_champ_hors_hachage_est_signale(tmp_path):
    """Un vérificateur qui ne peut pas rendre compte d'une partie d'un
    enregistrement n'a pas à le déclarer intact."""
    r = registre(tmp_path)
    un_paiement(r, "PAY-1")

    lignes = r.chemin.read_text(encoding="utf-8").splitlines()
    e = json.loads(lignes[0]); e["approuve_par"] = "la direction"
    r.chemin.write_text(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n",
                        encoding="utf-8")

    problemes = r.verifier()
    assert problemes and "approuve_par" in problemes[0]


def test_une_ligne_supprimee_casse_la_suite(tmp_path):
    r = registre(tmp_path)
    for i in range(3):
        un_paiement(r, f"PAY-{i}")
    lignes = r.chemin.read_text(encoding="utf-8").splitlines()
    r.chemin.write_text("\n".join([lignes[0], lignes[2]]) + "\n", encoding="utf-8")

    assert r.verifier(), "retirer une ligne doit se voir"


# ── La justification, et l'alarme ───────────────────────────────────────

def test_pourquoi_rend_toute_la_justification(tmp_path):
    r = registre(tmp_path)
    un_paiement(r, "PAY-7", preuves=["sha256:page"], marchand="libraire")

    e = r.pourquoi("PAY-7")
    assert e["mandat"] == "m-1"
    assert e["preuves"] == ["sha256:page"]
    assert e["intention"]["marchand"] == "libraire"


def test_une_reference_inconnue_est_une_alarme_et_pas_une_absence(tmp_path):
    """Le contraire du réflexe habituel. Un `None` s'affiche comme « rien à
    signaler », alors que c'est l'inverse."""
    r = registre(tmp_path)
    un_paiement(r, "PAY-1")

    with pytest.raises(HorsRegistre, match="sans passer par le mandat"):
        r.pourquoi("PAY-INCONNU")


def test_les_sorties_de_route_sont_nommees(tmp_path):
    """Une transaction chez le fournisseur absente d'ici est un paiement qui
    n'est pas passé par la porte."""
    r = registre(tmp_path)
    un_paiement(r, "PAY-1")
    un_paiement(r, "PAY-2")

    assert r.sorties_de_route(["PAY-1", "PAY-2"]) == []
    assert r.sorties_de_route(["PAY-1", "PAY-9", "PAY-2", "PAY-X"]) == ["PAY-9", "PAY-X"]


def test_un_refus_ne_compte_pas_comme_une_transaction_connue(tmp_path):
    """Un refus n'a pas de référence : il ne doit pas blanchir une transaction
    du fournisseur qui porterait le même nom."""
    r = registre(tmp_path)
    r.refus(at=QUAND, mandat="m-1", montant_centimes=9999, devise="EUR",
            regle="plafond total", detail="plus rien")
    assert r.sorties_de_route(["PAY-1"]) == ["PAY-1"]


def test_un_registre_vide_declare_tout_hors_route(tmp_path):
    assert registre(tmp_path).sorties_de_route(["PAY-1"]) == ["PAY-1"]
    assert registre(tmp_path).verifier() == []


def test_un_faussaire_qui_recalcule_l_empreinte_est_quand_meme_pris(tmp_path):
    """La garantie que la démonstration affiche, et qu'aucun test ne tenait.

    Réécrire un montant se voit — c'est le test précédent. Mais un faussaire
    compétent recalcule l'empreinte de la ligne qu'il vient de modifier, et
    cette ligne-là redevient cohérente avec elle-même.

    Il échoue quand même, et c'est tout l'intérêt du chaînage : **le suivant
    porte l'empreinte d'avant**. La ligne réécrite passe, la suivante dénonce
    la substitution. On ne réécrit donc pas un enregistrement seul — il faudrait
    réécrire toute la suite, et le dernier maillon reste.
    """
    r = registre(tmp_path)
    un_paiement(r, "PAY-1")
    un_paiement(r, "PAY-2", centimes=1000)

    lignes = r.chemin.read_text(encoding="utf-8").splitlines()
    e = json.loads(lignes[0])
    e["intention"]["centimes"] = 1
    # Le faussaire fait son travail proprement : il remet l'empreinte d'accord
    # avec le corps qu'il vient de changer.
    corps = {cle: e[cle] for cle in _CORPS if cle in e}
    e["chain"] = _empreinte(corps, e["prev"])
    lignes[0] = json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    r.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    problemes = r.verifier()

    assert problemes, "une ligne réécrite avec son empreinte refaite a passé la vérification"
    assert "record 2" in problemes[0]
    assert "does not follow" in problemes[0]
