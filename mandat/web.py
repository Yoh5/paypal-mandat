"""La démo hébergée — un juré essaie lui-même, et le serveur ne tient rien.

**Pourquoi cette page peut être exposée publiquement sans risque.** Ce n'est pas
une précaution ajoutée, c'est une propriété du produit : **un refus n'appelle
personne**. Le serveur interroge donc `Porte.verifier()`, le contrôle seul, et
ne passe jamais par `Passerelle.payer()`. Conséquences, dans l'ordre
d'importance :

- il ne détient **aucun identifiant PayPal** ;
- il ne peut faire bouger **aucun argent**, même par un bogue ;
- il n'y a donc **rien à limiter en débit** et rien à voler.

Pour un montant que le mandat autorise, la page le **dit** au lieu de passer la
commande. Une démo publique n'a rien à faire avec des moyens de paiement, et
l'écrire vaut mieux que de faire semblant.

**Ce n'est pas un serveur de production.** `http.server` est mono-processus et
n'a jamais prétendu encaisser du trafic. C'est le prix assumé pour tenir
l'engagement du README : **aucune dépendance d'exécution**. Un outil dont le
métier est de contraindre des paiements ne devrait pas demander de faire
confiance à un arbre de dépendances pour se montrer.
"""
from __future__ import annotations

import os
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs

from .demo import _porte_de_demonstration
from .mandat import Refus, euros


def verdict(*, montant: str, marchand: str) -> dict[str, Any]:
    """Ce que le mandat répond, sans qu'aucun fournisseur soit joint.

    Le mandat est **celui du film** — mêmes 40,00 par transaction, même
    marchand — pour qu'un juré qui vient de regarder la vidéo retrouve le
    plafond qu'il y a vu, et non un second jeu de limites à relire.
    """
    porte = _porte_de_demonstration()
    mandat = porte.mandat
    commun = {
        "montant": montant,
        "marchand": marchand,
        "paye": False,          # jamais. Voir la docstring du module.
        "mandat": {
            "identifiant": mandat.identifiant,
            "par_transaction": euros(mandat.par_transaction),
            "total": euros(mandat.total),
            "marchands": sorted(mandat.marchands),
        },
    }

    try:
        centimes = porte.verifier(montant, devise=mandat.devise, marchand=marchand)
    except Refus as refus:
        return {**commun, "issue": "refused",
                "regle": refus.regle, "detail": refus.detail}
    except (ValueError, TypeError) as illisible:
        # « douze euros » est une saisie qu'un juré fera, et une trace de pile
        # serait une réponse. La porte nomme « amount » un montant qui n'est pas
        # un paiement ; une chaîne qu'on ne sait pas lire n'en est pas un non
        # plus, donc elle porte la même règle.
        return {**commun, "issue": "refused", "regle": "amount",
                "detail": str(illisible)}

    return {**commun, "issue": "allowed", "centimes": centimes,
            "detail": f"{euros(centimes)} is within the mandate. This hosted demo "
                      f"returns the decision and does not place the order: a public "
                      f"page has no business holding payment credentials."}


# ── Le routage, séparé de la socket ──────────────────────────────────────

def _page(v: dict[str, Any] | None, mandat: dict[str, Any]) -> str:
    """Le gabarit. Toute valeur venue du visiteur passe par `escape`."""
    limites = (f"{mandat['par_transaction']} per transaction &middot; "
               f"{mandat['total']} total &middot; {', '.join(mandat['marchands'])}")

    if v is None:
        resultat = ""
    elif v["issue"] == "refused":
        resultat = (
            f'<div class="r refused"><div class="v">REFUSED</div>'
            f'<div class="k">{escape(v["regle"])}</div>'
            f'<p>{escape(v["detail"])}</p>'
            f'<p class="n">PayPal was never called. Not refunded, not reversed. '
            f'Never called.</p></div>')
    else:
        resultat = (
            f'<div class="r allowed"><div class="v">ALLOWED</div>'
            f'<p>{escape(v["detail"])}</p></div>')

    saisie_m = escape(v["montant"]) if v else "89.90"
    saisie_c = escape(v["marchand"]) if v else "The Corner Bookshop"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spend Mandate &mdash; try the refusal</title>
<style>
 :root {{ color-scheme: dark; }}
 body {{ margin:0; padding:3rem 1.25rem; background:#1a1a19; color:#fff;
        font:16px/1.6 "Segoe UI",system-ui,sans-serif; }}
 main {{ max-width:40rem; margin:0 auto; }}
 h1 {{ font-size:1.9rem; margin:0 0 .4rem; }}
 .sub {{ color:#787872; margin:0 0 2.2rem; }}
 .lim {{ color:#c3c2b7; font-size:.95rem; border-left:3px solid #3987e5;
         padding-left:.9rem; margin-bottom:2rem; }}
 label {{ display:block; color:#787872; font-size:.9rem; margin:1.1rem 0 .3rem; }}
 input {{ width:100%; box-sizing:border-box; padding:.7rem .8rem; font:inherit;
          background:#232322; color:#fff; border:1px solid #3a3a38; border-radius:6px; }}
 button {{ margin-top:1.5rem; padding:.75rem 1.6rem; font:inherit; font-weight:600;
           background:#3987e5; color:#fff; border:0; border-radius:6px; cursor:pointer; }}
 .r {{ margin:2.2rem 0 0; padding:1.3rem 1.4rem; border-radius:8px;
       border:2px solid #3a3a38; }}
 .r.refused {{ border-color:#d03b3b; }}
 .r.allowed {{ border-color:#6aa878; }}
 .v {{ font-weight:700; letter-spacing:.14em; font-size:1.15rem; }}
 .r.refused .v {{ color:#d03b3b; }}
 .r.allowed .v {{ color:#6aa878; }}
 .k {{ font-family:Consolas,monospace; color:#c3c2b7; margin-top:.3rem; }}
 .r p {{ margin:.7rem 0 0; color:#c3c2b7; }}
 .n {{ color:#fff !important; font-weight:600; }}
 footer {{ margin-top:3rem; color:#787872; font-size:.88rem; }}
 a {{ color:#3987e5; }}
</style></head>
<body><main>
<h1>A spend mandate an agent cannot cross</h1>
<p class="sub">Type an amount. Watch where it stops.</p>
<div class="lim">{limites}<br>enforced by code <strong>before</strong> the call,
 not audited after</div>
<form method="post" action="/try">
 <label for="m">Amount (EUR)</label>
 <input id="m" name="montant" value="{saisie_m}" autocomplete="off">
 <label for="c">Merchant</label>
 <input id="c" name="marchand" value="{saisie_c}" autocomplete="off">
 <button type="submit">Ask the mandate</button>
</form>
{resultat}
<footer>
 This page holds <strong>no payment credentials</strong> and cannot move any
 money. It asks the gate for its decision and never reaches a provider &mdash;
 which is possible because a refusal calls nobody. An allowed amount is
 reported, not charged.<br><br>
 <!-- Pas de nombre de tests ici : un chiffre tape dans un artefact publie
      vieillit des le commit suivant. Le README le porte, et lui est verifie. -->
 <a href="https://github.com/Yoh5/paypal-mandat">Code, tests, Apache-2.0</a>
 &middot; <a href="https://youtu.be/zPNiNpsnENw">2 min demo</a>
</footer>
</main></body></html>"""


def repondre(methode: str, chemin: str, corps: bytes) -> tuple[str, str, bytes]:
    """(code, content-type, corps) — pur, donc testable sans ouvrir de port.

    Même leçon que `jouer()` dans `demo.py` : un câblage qu'aucun test ne peut
    appeler est un câblage que personne ne vérifie.
    """
    if chemin == "/health":
        return 200, "text/plain; charset=utf-8", b"ok"

    mandat = verdict(montant="0", marchand="")["mandat"]

    if methode == "GET" and chemin == "/":
        return 200, "text/html; charset=utf-8", _page(None, mandat).encode("utf-8")

    if methode == "POST" and chemin == "/try":
        champs = parse_qs(corps.decode("utf-8", "replace"))
        v = verdict(montant=(champs.get("montant") or [""])[0],
                    marchand=(champs.get("marchand") or [""])[0])
        return 200, "text/html; charset=utf-8", _page(v, mandat).encode("utf-8")

    return 404, "text/plain; charset=utf-8", b"not found"


class _Gestionnaire(BaseHTTPRequestHandler):
    """La socket, et rien d'autre. Toute la décision est dans `repondre`."""

    server_version = "spend-mandate"

    def _servir(self, methode: str) -> None:
        longueur = int(self.headers.get("Content-Length") or 0)
        corps = self.rfile.read(longueur) if longueur else b""
        code, type_, sortie = repondre(methode, self.path.split("?")[0], corps)
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(sortie)))
        self.end_headers()
        self.wfile.write(sortie)

    def do_GET(self) -> None:      # noqa: N802
        self._servir("GET")

    def do_POST(self) -> None:     # noqa: N802
        self._servir("POST")

    def log_message(self, *_: Any) -> None:
        pass   # pas de journal d'accès : rien à y apprendre, et ça bruite Render


if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", "8000"))
    print(f"spend mandate demo on :{port}  (no credentials held)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), _Gestionnaire).serve_forever()
