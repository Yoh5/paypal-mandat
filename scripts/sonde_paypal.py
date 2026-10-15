"""Le bac à sable ouvre-t-il vraiment ce dont le mandat a besoin ?

    set PAYPAL_CLIENT_ID=...
    set PAYPAL_SECRET=...
    python scripts/sonde_paypal.py

`CADRAGE.md` posait deux questions avant d'écrire la moindre ligne
d'intégration. La première — l'accès au tableau de bord développeur depuis le
Maroc — est tranchée. Celle-ci est la seconde : **quelles API le bac à sable
ouvre sans compte entreprise.** La documentation PayPal dit qu'un compte
développeur suffit pour tester des intégrations américaines et qu'un compte
Business n'est requis que pour passer en production ou tester hors des
États-Unis. C'est une phrase dans une page, pas une mesure ; ce script la
transforme en fait sur ce compte-ci.

**Ce script n'imprime jamais un secret.** Ni la clé, ni le jeton d'accès, ni
un en-tête d'autorisation. Il dit quel appel a répondu quoi, et rien d'autre :
une sonde qui recopie une crédential dans un terminal est une sonde qui finit
dans une capture d'écran.

Il ne capture aucun paiement non plus. Créer une commande et la relire suffit
à répondre à la question, et une capture exige un parcours d'approbation
d'acheteur qui n'a rien à voir avec ce qu'on cherche à savoir.

Zéro dépendance : `urllib`, comme le reste du dépôt.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"


def appeler(chemin: str, *, entetes: dict[str, str],
            corps: bytes | None = None,
            methode: str = "GET") -> tuple[int, dict]:
    """(code HTTP, corps JSON). Ne lève pas sur un 4xx : un refus est une
    réponse, et c'est précisément ce qu'on est venu mesurer."""
    requete = urllib.request.Request(f"{BASE}{chemin}", data=corps,
                                     headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return reponse.status, json.loads(reponse.read() or b"{}")
    except urllib.error.HTTPError as erreur:
        brut = erreur.read() or b"{}"
        try:
            return erreur.code, json.loads(brut)
        except json.JSONDecodeError:
            return erreur.code, {"corps_non_json": brut[:200].decode(
                "utf-8", "replace")}


def jeton(client: str, secret: str) -> tuple[int, str | None, dict]:
    """Le jeton est rendu pour être utilisé, jamais pour être affiché."""
    panier = base64.b64encode(f"{client}:{secret}".encode()).decode()
    code, corps = appeler(
        "/v1/oauth2/token",
        entetes={"Authorization": f"Basic {panier}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        corps=b"grant_type=client_credentials", methode="POST")
    return code, corps.get("access_token"), corps


def commande_type() -> bytes:
    """Une commande minimale : c'est la forme qu'un mandat devra autoriser."""
    return json.dumps({
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": "12.00"},
            "description": "probe: does Orders v2 answer this account",
        }],
    }).encode()


def lire_env(chemin: Path) -> dict[str, str]:
    """`.env`, lu sans dépendance et sans rien afficher.

    Le fichier est dans `.gitignore`. On ne lit que les deux clés attendues :
    un lecteur d'environnement qui avale tout finit par exporter autre chose
    que ce qu'on croyait.
    """
    valeurs: dict[str, str] = {}
    if not chemin.exists():
        return valeurs
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        cle = cle.strip()
        if cle in ("PAYPAL_CLIENT_ID", "PAYPAL_SECRET"):
            valeurs[cle] = valeur.strip().strip('"').strip("'")
    return valeurs


def main() -> int:
    # L'environnement l'emporte sur le fichier : c'est ce qu'on attend d'un
    # secret, et ça permet d'essayer une autre clé sans éditer le .env.
    fichier = lire_env(Path(__file__).resolve().parent.parent / ".env")
    client = (os.environ.get("PAYPAL_CLIENT_ID")
              or fichier.get("PAYPAL_CLIENT_ID", "")).strip()
    secret = (os.environ.get("PAYPAL_SECRET")
              or fichier.get("PAYPAL_SECRET", "")).strip()
    if not client or not secret:
        print("PAYPAL_CLIENT_ID et PAYPAL_SECRET introuvables, ni dans "
              "l'environnement ni dans .env (qui reste hors de git).")
        return 2

    # Dire ce qu'on tient sans dire ce que c'est : la longueur et les quatre
    # premiers caracteres suffisent a reperer un copier-coller tronque, qui est
    # l'erreur reelle a cet endroit.
    print(f"identifiants lus : client {client[:4]}... ({len(client)} car.), "
          f"secret masque ({len(secret)} car.)\n")

    etapes: list[tuple[str, bool, str]] = []

    code, acces, corps = jeton(client, secret)
    ok = code == 200 and bool(acces)
    etapes.append(("OAuth2 client_credentials", ok,
                   f"HTTP {code}" + ("" if ok else f" — {corps.get('error_description', corps)}")))
    if not ok:
        rendre(etapes)
        print("\nLe jeton n'est pas delivre : rien d'autre ne peut etre teste.")
        print("Verifier que les identifiants sont ceux du bac a sable "
              "(onglet Sandbox), et non ceux de production.")
        return 1

    entetes = {"Authorization": f"Bearer {acces}",
               "Content-Type": "application/json"}

    code, corps = appeler("/v2/checkout/orders", entetes=entetes,
                          corps=commande_type(), methode="POST")
    cree = code in (200, 201)
    identifiant = corps.get("id")
    etapes.append(("Orders v2 — creation", cree,
                   f"HTTP {code}" + (f", commande {identifiant}" if cree
                                     else f" — {corps.get('message', corps)}")))

    if cree and identifiant:
        code, corps = appeler(f"/v2/checkout/orders/{identifiant}",
                              entetes=entetes)
        relu = code == 200
        etapes.append(("Orders v2 — relecture", relu,
                       f"HTTP {code}, statut {corps.get('status')}" if relu
                       else f"HTTP {code}"))

    rendre(etapes)

    if all(ok for _, ok, _ in etapes):
        print("\nLe bac a sable ouvre Orders v2 a ce compte. La question 2 de "
              "CADRAGE.md est tranchee : la couche d'integration peut s'ecrire.")
        return 0
    print("\nUne etape a echoue. C'est une reponse, pas un echec de la sonde : "
          "noter laquelle avant de changer quoi que ce soit.")
    return 1


def rendre(etapes: list[tuple[str, bool, str]]) -> None:
    for nom, ok, detail in etapes:
        print(f"  {'ok    ' if ok else 'ECHEC '} {nom:<26} {detail}")


if __name__ == "__main__":
    raise SystemExit(main())
