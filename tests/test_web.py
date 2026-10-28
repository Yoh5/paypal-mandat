"""La démo hébergée : ce qu'un juré peut essayer lui-même, et ce qu'elle ne tient pas.

Les dix gagnants d'*Agents for Humans* filmaient le refus. Le laisser
**déclencher** par un visiteur est un cran au-dessus : il tape 90, il voit
buter, il n'a pas à nous croire.

**La garantie qui rend cette page sûre à exposer est une propriété du produit,
pas une précaution ajoutée : un refus n'appelle personne.** Le serveur
n'interroge donc jamais un fournisseur, ne détient aucun identifiant, et ne
peut faire bouger aucun argent — y compris pour un montant que le mandat
autorise, cas où il le dit au lieu de passer la commande.
"""
from __future__ import annotations

import json

from mandat.web import repondre, verdict


def test_un_montant_au_dessus_du_plafond_est_refuse_avec_sa_regle():
    r = verdict(montant="89.90", marchand="The Corner Bookshop")

    assert r["issue"] == "refused"
    assert r["regle"] == "per-transaction cap"
    assert "40,00" in r["detail"]


def test_un_montant_dans_le_mandat_est_autorise_mais_rien_n_est_paye():
    """Autorisé n'est pas payé, et la page doit le dire.

    Une démo publique qui passerait une vraie commande aurait besoin
    d'identifiants en ligne. On rend le verdict, pas la transaction — et
    `paye` à False est ce que le gabarit lit pour l'écrire noir sur blanc.
    """
    r = verdict(montant="6.40", marchand="The Corner Bookshop")

    assert r["issue"] == "allowed"
    assert r["paye"] is False


def test_un_marchand_hors_mandat_est_refuse_sur_le_marchand():
    r = verdict(montant="6.40", marchand="Somewhere Else")

    assert r["issue"] == "refused"
    assert r["regle"] == "merchant"


def test_une_saisie_illisible_est_refusee_sans_planter():
    """Un juré tapera « douze euros », et une trace de pile serait une réponse."""
    r = verdict(montant="douze euros", marchand="The Corner Bookshop")

    assert r["issue"] == "refused"
    assert r["regle"] == "amount"


def test_le_verdict_est_serialisable_tel_quel():
    """Le gabarit et une éventuelle API lisent la même structure."""
    json.dumps(verdict(montant="89.90", marchand="The Corner Bookshop"))


# ── Le routage, separe de la socket ──────────────────────────────────────
#
# Meme lecon que `jouer()` dans demo.py : un cablage qu'aucun test ne peut
# appeler est un cablage que personne ne verifie. `repondre` est pur, le
# gestionnaire HTTP ne fait que lui passer le chemin et le corps.

def test_health_repond_200_sans_rien_faire_de_lourd():
    """C'est la route que `keep-awake.yml` interroge toutes les deux minutes."""
    code, type_, corps = repondre("GET", "/health", b"")

    assert code == 200
    assert b"ok" in corps.lower()


def test_la_page_porte_le_formulaire_et_le_plafond():
    code, type_, corps = repondre("GET", "/", b"")
    page = corps.decode("utf-8")

    assert code == 200
    assert "text/html" in type_
    assert "<form" in page
    assert "40,00" in page


def test_la_page_dit_qu_aucun_identifiant_n_est_detenu():
    """La phrase n'est pas de l'ornement : c'est la raison pour laquelle cette
    page peut etre exposee. Un test la tient, sinon elle disparait au premier
    remaniement de gabarit."""
    page = repondre("GET", "/", b"")[2].decode("utf-8")

    assert "no payment credentials" in page.lower()


def test_un_envoi_au_dessus_du_plafond_rend_la_regle():
    code, type_, corps = repondre(
        "POST", "/try", b"montant=89.90&marchand=The+Corner+Bookshop")
    page = corps.decode("utf-8")

    assert code == 200
    assert "per-transaction cap" in page
    assert "40,00 allowed" in page


def test_un_chemin_inconnu_rend_404_et_pas_une_trace():
    code, type_, corps = repondre("GET", "/admin", b"")

    assert code == 404


def test_la_saisie_renvoyee_est_echappee():
    """La page reaffiche le marchand saisi : sans echappement, c'est un XSS.

    Ecrit avant l'implementation et non apres l'avoir trouve : le trou est
    evident des qu'on decide de reafficher une entree, et le decouvrir en
    jouant la surprise serait du theatre. Le test est la pour qu'il ne
    reapparaisse pas au prochain remaniement de gabarit.
    """
    page = repondre("POST", "/try",
                    b"montant=6.40&marchand=%3Cscript%3Ealert(1)%3C%2Fscript%3E"
                    )[2].decode("utf-8")

    assert "<script>" not in page
    assert "&lt;script&gt;" in page
