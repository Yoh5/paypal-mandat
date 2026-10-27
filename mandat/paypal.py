"""La passerelle : le seul chemin par lequel de l'argent peut partir.

Le mandat, la proposition et le registre existent déjà et se testent sans la
moindre clé. Ce module est la plomberie — et il est écrit de façon à ce que la
plomberie ne puisse pas court-circuiter la décision.

## Ce qui est structurel plutôt que vérifié

Un contrôle a des bogues ; un champ absent n'en a pas. La `Passerelle` **tient**
le client PayPal en attribut privé et n'expose aucune méthode qui paie sans
passer par la porte. Il n'existe pas de chemin où l'on pourrait appeler le
fournisseur avec un montant que le mandat n'a pas approuvé, parce qu'aucune
fonction publique n'accepte un montant : elle accepte une `Proposition`, et
c'est la porte qui en extrait le centime.

## L'ordre des trois gestes, et pourquoi il ne peut pas changer

1. **Engager** sur le mandat. L'engagement précède l'appel au fournisseur : si
   l'on retenait après, deux paiements concurrents franchiraient tous deux un
   plafond qu'un seul aurait dû passer.
2. **Appeler PayPal**, et seulement si 1 a réussi. Un refus du mandat n'atteint
   jamais le réseau : c'est la moitié de la démonstration, et c'est aussi la
   seule façon qu'un plafond soit autre chose qu'un contrôle a posteriori.
3. **Inscrire**, succès comme refus. Un registre qui ne porte que les paiements
   partis raconte un agent exemplaire qui n'a jamais rien tenté d'interdit.

Et si PayPal refuse après l'engagement, le montant est **rendu** au mandat :
sans ça, un appel échoué consommerait le plafond pour rien et l'agent se
retrouverait bridé par de l'argent qui n'est jamais parti.

## Ce que ce module ne fait pas

Il ne capture pas. Créer une commande réserve l'intention côté PayPal ; la
capture exige l'approbation d'un acheteur, qui est un parcours humain et non
une décision d'agent. Le mandat gouverne ce que l'agent peut *engager*, et
c'est exactement la frontière qu'il doit garder.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .mandat import Porte, Refus, euros
from .proposition import Proposition
from .registre import Registre

SANDBOX = "https://api-m.sandbox.paypal.com"
PRODUCTION = "https://api-m.paypal.com"


class EchecFournisseur(Exception):
    """Le fournisseur n'a pas créé la commande.

    Distincte de `Refus` exprès : un refus vient du mandat et est une décision ;
    ceci est une panne. Les confondre ferait passer une coupure réseau pour une
    limite de dépense, et un plafond atteint pour un incident.
    """

    def __init__(self, code: int, detail: str) -> None:
        super().__init__(f"HTTP {code} — {detail}")
        self.code, self.detail = code, detail


class Fournisseur(Protocol):
    """Ce que la passerelle attend. Un protocole, pour que les tests puissent
    substituer un double sans toucher au réseau."""

    def creer(self, centimes: int, devise: str, description: str) -> tuple[str, str]:
        """Rend (référence, statut). Lève `EchecFournisseur` si rien n'est créé."""


@dataclass
class PayPal:
    """Orders v2, en urllib. Aucune dépendance, et lisible en entier.

    Pour un projet dont l'argument est l'auditabilité, un client qu'on peut
    lire d'un bout à l'autre n'est pas une coquetterie : c'est la condition
    pour que quelqu'un vérifie ce qu'on envoie vraiment.
    """

    client: str
    secret: str
    base: str = SANDBOX
    _jeton: str | None = field(default=None, repr=False, init=False)

    @classmethod
    def depuis_env(cls, racine: Path | None = None, base: str = SANDBOX) -> "PayPal":
        """Les identifiants viennent de l'environnement, sinon de `.env`.

        `.env` est dans `.gitignore`. Rien ici n'affiche une valeur : ce module
        n'a aucune raison d'imprimer un secret, et un secret imprimé finit dans
        une capture d'écran.
        """
        racine = racine or Path(__file__).resolve().parent.parent
        fichier: dict[str, str] = {}
        chemin = racine / ".env"
        if chemin.exists():
            for ligne in chemin.read_text(encoding="utf-8").splitlines():
                ligne = ligne.strip()
                if ligne and not ligne.startswith("#") and "=" in ligne:
                    cle, _, valeur = ligne.partition("=")
                    if cle.strip() in ("PAYPAL_CLIENT_ID", "PAYPAL_SECRET"):
                        fichier[cle.strip()] = valeur.strip().strip('"').strip("'")
        client = (os.environ.get("PAYPAL_CLIENT_ID")
                  or fichier.get("PAYPAL_CLIENT_ID", "")).strip()
        secret = (os.environ.get("PAYPAL_SECRET")
                  or fichier.get("PAYPAL_SECRET", "")).strip()
        if not client or not secret:
            raise EchecFournisseur(0, "PAYPAL_CLIENT_ID / PAYPAL_SECRET absents "
                                      "de l'environnement et de .env")
        return cls(client, secret, base)

    # ── réseau ──────────────────────────────────────────────────────────
    def _appeler(self, chemin: str, *, entetes: dict[str, str],
                 corps: bytes | None = None,
                 methode: str = "GET") -> tuple[int, dict[str, Any]]:
        requete = urllib.request.Request(f"{self.base}{chemin}", data=corps,
                                         headers=entetes, method=methode)
        try:
            with urllib.request.urlopen(requete, timeout=30) as reponse:
                return reponse.status, json.loads(reponse.read() or b"{}")
        except urllib.error.HTTPError as erreur:
            brut = erreur.read() or b"{}"
            try:
                return erreur.code, json.loads(brut)
            except json.JSONDecodeError:
                return erreur.code, {"corps": brut[:300].decode("utf-8", "replace")}
        except urllib.error.URLError as erreur:
            raise EchecFournisseur(0, f"réseau injoignable : {erreur.reason}") from erreur

    def _acces(self) -> str:
        if self._jeton:
            return self._jeton
        panier = base64.b64encode(f"{self.client}:{self.secret}".encode()).decode()
        code, corps = self._appeler(
            "/v1/oauth2/token",
            entetes={"Authorization": f"Basic {panier}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            corps=b"grant_type=client_credentials", methode="POST")
        jeton = corps.get("access_token")
        if code != 200 or not jeton:
            raise EchecFournisseur(code, corps.get("error_description", "jeton refusé"))
        self._jeton = jeton
        return jeton

    def creer(self, centimes: int, devise: str, description: str) -> tuple[str, str]:
        corps = json.dumps({
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": devise,
                           # PayPal veut une chaîne décimale ; le mandat compte
                           # en centimes. La conversion vit ici, au bord, pour
                           # qu'aucun flottant n'entre dans la décision.
                           "value": f"{centimes // 100}.{centimes % 100:02d}"},
                "description": description[:127],
            }],
        }).encode()
        code, reponse = self._appeler(
            "/v2/checkout/orders",
            entetes={"Authorization": f"Bearer {self._acces()}",
                     "Content-Type": "application/json"},
            corps=corps, methode="POST")
        if code not in (200, 201) or not reponse.get("id"):
            raise EchecFournisseur(code, str(reponse.get("message") or reponse)[:200])
        return reponse["id"], reponse.get("status", "?")

    def references(self, identifiants: list[str]) -> list[str]:
        """Les commandes que PayPal reconnaît, parmi celles qu'on lui soumet.

        Orders v2 n'offre pas de liste : on ne peut interroger qu'une commande
        connue. C'est une limite réelle du rapprochement, et elle est dite ici
        plutôt que contournée par un chiffre inventé.
        """
        vivantes = []
        for identifiant in identifiants:
            code, _ = self._appeler(
                f"/v2/checkout/orders/{identifiant}",
                entetes={"Authorization": f"Bearer {self._acces()}"})
            if code == 200:
                vivantes.append(identifiant)
        return vivantes


@dataclass
class Passerelle:
    """Mandat + registre + fournisseur. Rien ne paie en dehors d'ici.

    Le fournisseur est détenu, pas reçu à chaque appel : un appelant ne peut
    pas lui tendre un montant directement, parce qu'il n'y a pas d'argument
    pour ça dans la seule méthode publique qui paie.
    """

    porte: Porte
    registre: Registre
    _fournisseur: Fournisseur

    def _maintenant(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def payer(self, proposition: Proposition) -> dict[str, Any]:
        """Le seul chemin vers l'argent.

        Rend l'enregistrement inscrit — paiement ou refus. Lève uniquement
        quand le fournisseur a échoué, parce qu'un refus du mandat est une
        réponse normale du produit et non une erreur de l'appelant.
        """
        at = self._maintenant()
        commun = {
            "at": at,
            "mandat": self.porte.mandat.identifiant,
            "montant_centimes": proposition.montant_centimes,
            "devise": proposition.devise,
            "marchand": proposition.marchand,
            "preuves": proposition.preuves,
        }

        # 1. Engager. Un refus s'arrête ici, et PayPal n'est jamais appelé.
        try:
            centimes = self.porte.engager(
                proposition.montant_centimes,
                devise=proposition.devise,
                marchand=proposition.marchand,
                instant=at,
            )
        except Refus as refus:
            return self.registre.refus(regle=refus.regle, detail=refus.detail,
                                       **commun)

        # 2. Appeler. 3. Inscrire.
        try:
            reference, statut = self._fournisseur.creer(
                centimes, proposition.devise, proposition.quoi)
        except EchecFournisseur:
            # L'argent n'est pas parti : le mandat ne doit pas le compter.
            self.porte.rendre(centimes)
            raise

        enregistrement = self.registre.paiement(
            reference=reference, depense_apres=self.porte.depense, **commun)
        enregistrement["statut_fournisseur"] = statut
        return enregistrement

    def pourquoi(self, reference: str) -> dict[str, Any]:
        """Depuis un identifiant de transaction, toute la justification."""
        return self.registre.pourquoi(reference)

    def rapprocher(self,
                   references_du_fournisseur: list[str] | None = None
                   ) -> dict[str, Any]:
        """Ce que le registre dit, confronté à ce que le fournisseur connaît.

        Deux écarts, et ils ne disent pas la même chose :

        - `sorties_de_route` : une référence chez le fournisseur que le registre
          ignore. C'est de l'argent qui a bougé sans décision enregistrée, et
          c'est le seul écart vraiment grave.
        - `introuvables` : une référence inscrite que le fournisseur ne
          reconnaît plus. Plus probablement une commande expirée qu'une
          falsification, mais ça se signale au lieu de se taire.

        **Pourquoi `references_du_fournisseur` doit venir de l'appelant.** La
        première version de cette méthode interrogeait le fournisseur avec les
        références *déjà inscrites*, puis cherchait parmi les réponses celles
        que le registre ignorait. Par construction il n'y en avait jamais : le
        contrôle le plus important du module ne pouvait pas se déclencher, et
        il rendait une liste vide qui se lisait comme « rien à signaler ».

        Orders v2 n'offre aucun point de liste — on ne peut interroger qu'une
        commande dont on tient déjà l'identifiant. Les références du
        fournisseur viennent donc d'ailleurs : journal de webhooks, export de
        recherche de transactions, relevé. Tant qu'on ne les a pas, cet écart
        **n'est pas vérifié**, et c'est ce que dit `verifie` — parce qu'une
        liste vide parce qu'on n'a rien cherché et une liste vide parce qu'il
        n'y a rien sont deux choses opposées.
        """
        inscrites = [e["reference"] for e in self.registre.enregistrements()
                     if e.get("issue") == "paye" and e.get("reference")]
        connues = self._fournisseur.references(inscrites) \
            if hasattr(self._fournisseur, "references") else inscrites
        ecarts: dict[str, Any] = {
            "introuvables": [r for r in inscrites if r not in connues],
            "verifie": references_du_fournisseur is not None,
        }
        if references_du_fournisseur is None:
            ecarts["sorties_de_route"] = None
            ecarts["pourquoi_non_verifie"] = (
                "aucune liste de références du fournisseur n'a été fournie, et "
                "Orders v2 n'en expose pas : sans journal de webhooks ou export "
                "de transactions, un paiement hors registre ne peut pas être vu")
        else:
            ecarts["sorties_de_route"] = self.registre.sorties_de_route(
                references_du_fournisseur)
        return ecarts


def resume(enregistrement: dict[str, Any]) -> str:
    """Une ligne lisible, pour la démonstration et les journaux."""
    montant = euros(enregistrement["intention"]["centimes"])
    if enregistrement["issue"] == "paye":
        return (f"PAID    {montant} -> {enregistrement['reference']}"
                f"  ({enregistrement['intention']['marchand'] or 'no merchant'})")
    return (f"REFUSED {montant}  [{enregistrement['regle']}] "
            f"{enregistrement['detail']}")
