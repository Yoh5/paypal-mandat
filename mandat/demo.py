"""The demonstration scenes -- the moment the product becomes visible.

A mandate enforced by code is invisible until someone watches it refuse. This
module holds no rules of its own: it stages the rules of the other modules, so
that a viewer sees in thirty seconds what the tests prove in silence.

**A property of the product, not a convenience of the demo:** the refusal scene
runs without a single PayPal credential, because the refusal happens *before*
the call to the provider.

The code's own identifiers stay French -- `mandat`, `porte`, `registre`. Only
what a reader or a juror sees is in English, because renaming the implementation
would be a large diff that shows a judge nothing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .mandat import Mandat, Porte, euros
from .paypal import Fournisseur, Passerelle, resume
from .proposition import Proposition, fonder
from .registre import Registre

#: What the agent actually read. The price that gets refused comes from this
#: page, not from the model: the scene shows a mandate breach, not a
#: hallucination.
PAGE_LUE = (
    "The Corner Bookshop -- Office supplies\n"
    "Refurbished laser printer ............... 89,90 EUR\n"
    "A4 paper, 500 sheets ..................... 6,40 EUR\n"
)

MARCHAND = "The Corner Bookshop"


class FournisseurInterdit:
    """A provider that cannot be called, and says so loudly.

    The refusal scene has no reason to reach PayPal. Handing it a silent double
    would make the guarantee *invisible*; handing it this one makes it
    **indestructible**: should the mandate check ever move to after the call,
    the demo would not run slower, it would break and name the fault.
    """

    def creer(self, centimes: int, devise: str, description: str) -> tuple[str, str]:
        raise AssertionError(
            f"the provider was called for {euros(centimes)} ({description!r}): "
            "the mandate was checked after the call instead of before, "
            "so it is no longer a cap"
        )


def _porte_de_demonstration() -> Porte:
    """One mandate for all three scenes.

    Deliberately shared: the paper passes and the printer is refused *under the
    same limits*. Two different mandates would be two stories and would prove
    nothing.
    """
    return Porte(
        Mandat.emettre(
            "demo-bookshop",
            devise="EUR",
            par_transaction="40.00",
            total="100.00",
            marchands=(MARCHAND,),
        )
    )


def _ramette() -> Proposition:
    """The purchase the mandate allows: 6,40, grounded in the page."""
    return fonder(
        Proposition.extraite(quoi="A4 paper, 500 sheets", montant="6.40",
                             devise="EUR", marchand=MARCHAND,
                             preuves=("bookshop-page",)),
        [PAGE_LUE])


def _imprimante() -> Proposition:
    """The purchase the mandate refuses: 89,90 against a cap of 40,00."""
    return fonder(
        Proposition.extraite(quoi="Refurbished laser printer", montant="89.90",
                             devise="EUR", marchand=MARCHAND,
                             preuves=("bookshop-page",)),
        [PAGE_LUE])


def scene_chaine(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> dict[str, Any]:
    """From a transaction reference, the whole justification.

    A purchase the mandate allows, then the chain read back **from the register**
    rather than from the variable just filled in: what the agent read, what it
    decided, what the mandate permitted at that instant, and the fact that
    nobody has rewritten the record since.
    """
    porte = _porte_de_demonstration()
    passerelle = Passerelle(porte, registre, fournisseur)
    proposition = _ramette()

    paye = passerelle.payer(proposition)
    reference = paye["reference"]

    # The point of the scene: we start again from the reference, the way someone
    # holding a statement and nothing else would.
    enregistrement = passerelle.pourquoi(reference)
    ecarts = registre.verifier()
    mandat = porte.mandat

    ecrire("== Scene A " + "=" * 56)
    ecrire("")
    ecrire(f"  All we hold is a reference:   {reference}")
    ecrire("")
    ecrire("  What the agent read")
    for ligne in PAGE_LUE.strip().splitlines()[1:]:
        ecrire(f"      {ligne}")
    ecrire(f"      evidence attached: {', '.join(enregistrement['preuves'])}")
    ecrire("")
    ecrire("  What it decided")
    ecrire(f"      {proposition.quoi} for {euros(enregistrement['intention']['centimes'])}"
           f" {enregistrement['intention']['devise']}")
    ecrire(f"      from {enregistrement['intention']['marchand']}")
    ecrire("")
    ecrire("  What the mandate permitted at that instant")
    ecrire(f"      mandate '{enregistrement['mandat']}', {enregistrement['at']}")
    ecrire(f"      per transaction {euros(mandat.par_transaction)}"
           f" / total {euros(mandat.total)}")
    ecrire(f"      spent after this payment: {euros(enregistrement['depense_apres'])}")
    ecrire("")
    if ecarts:
        ecrire("  Integrity           BROKEN")
        for e in ecarts:
            ecrire(f"      {e}")
    else:
        ecrire(f"  Integrity           register intact:"
               f" {len(registre.enregistrements())} record(s) re-chained,")
        ecrire("                      no discrepancy. Nobody has rewritten this since.")

    return enregistrement


def scene_refus(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> dict[str, Any]:
    """A spend beyond the mandate, refused before the provider is called.

    The mandate allows 40,00 per transaction; the agent reads a price of 89,90
    on a real page and proposes it in good faith. The code refuses, and the
    reason is written to the register with the same weight as a payment.
    """
    porte = _porte_de_demonstration()
    passerelle = Passerelle(porte, registre, fournisseur)
    proposition = _imprimante()

    enregistrement = passerelle.payer(proposition)
    mandat = porte.mandat

    # ASCII rules: the default Windows terminal is cp1252, which has no
    # box-drawing characters. A scene that does not display cannot be filmed.
    ecrire("== Scene B " + "=" * 56)
    ecrire("")
    ecrire(f"  Mandate '{mandat.identifiant}'")
    ecrire(f"      per transaction   {euros(mandat.par_transaction)}")
    ecrire(f"      total             {euros(mandat.total)}")
    ecrire(f"      merchants         {', '.join(sorted(mandat.marchands))}")
    ecrire("")
    ecrire("  What the agent read")
    for ligne in PAGE_LUE.strip().splitlines():
        ecrire(f"      {ligne}")
    ecrire("")
    ecrire("  What it proposes")
    ecrire(f"      {proposition.quoi} -- {euros(proposition.montant_centimes)}"
           f" from {proposition.marchand}")
    ecrire("      the price is found in the page, so the proposition is grounded:")
    ecrire("      what follows is not a hallucination but a breach of the mandate")
    ecrire("")
    ecrire(f"  Verdict             {resume(enregistrement)}")
    ecrire("")
    ecrire("  The provider was not called. The mandate stands in the way before")
    ecrire("  the call, not after: a cap checked afterwards is not a cap.")
    ecrire(f"  Written to the register at sequence {enregistrement['sequence']},")
    ecrire(f"  chained on {enregistrement['chain'][:16]}...")

    return enregistrement


def scene_falsification(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> dict[str, list[str]]:
    """The only scene where the product has to fail in order to succeed.

    Two decisions are recorded, the register declares itself intact, then one
    line is rewritten **directly in the file** -- not through this library,
    because nobody covering their tracks uses the API built for it. The verifier
    must not answer "the log is fine": it must name the line.
    """
    porte = _porte_de_demonstration()
    passerelle = Passerelle(porte, registre, fournisseur)

    passerelle.payer(_ramette())
    passerelle.payer(_imprimante())

    avant = registre.verifier()

    chemin = Path(registre.chemin)
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    corps = json.loads(lignes[0])
    montant_avant = corps["intention"]["centimes"]
    corps["intention"]["centimes"] = 1
    lignes[0] = json.dumps(corps, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    apres = registre.verifier()

    ecrire("== Scene C " + "=" * 56)
    ecrire("")
    ecrire(f"  Before              {'intact' if not avant else 'BROKEN'}:"
           f" {len(lignes)} record(s) re-chained")
    ecrire("")
    ecrire("  We rewrite the register the way someone covering their tracks")
    ecrire("  would -- by editing the file, not by calling the library:")
    ecrire(f"      record 1, amount {euros(montant_avant)} -> {euros(1)}")
    ecrire("")
    ecrire(f"  After               {'intact' if not apres else 'BROKEN'}")
    for probleme in apres:
        ecrire(f"      {probleme}")
    ecrire("")
    ecrire("  The verifier does not call the log fine: it names the line. And")
    ecrire("  recomputing the fingerprint would not save the forger: the next")
    ecrire("  record carries the previous one's, and it is the next record that")
    ecrire("  would denounce the substitution. The whole tail would have to go.")

    return {"avant": avant, "apres": apres}


def jouer(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> None:
    """The three scenes, in the order of the video.

    It works, it refuses, and history cannot be rewritten. The order is a
    crescendo: scene C is only worth anything once you have seen what it
    protects.

    **This function exists because the wiring broke twice.** All three scenes
    were green while `python -m mandat.demo` crashed, because the entry point
    handed scene C a forbidding provider although that scene really pays. An
    orchestration no test can call is an orchestration nobody checks.
    """
    scene_chaine(registre=registre, fournisseur=fournisseur, ecrire=ecrire)
    ecrire("")
    scene_refus(registre=registre, fournisseur=fournisseur, ecrire=ecrire)
    ecrire("")
    # Scene C rewrites its register, so it works on its own, to avoid breaking
    # the chain the first two have just built.
    scene_falsification(
        registre=Registre(Path(registre.chemin).with_suffix(".falsifie.jsonl")),
        fournisseur=fournisseur,
        ecrire=ecrire,
    )


if __name__ == "__main__":  # pragma: no cover
    import sys

    from .paypal import PayPal

    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs/demo.jsonl")

    try:
        fournisseur = PayPal.depuis_env()
    except Exception as pourquoi:
        print("== Scenes A and C not played " + "=" * 39)
        print(f"  No access to the PayPal sandbox: {pourquoi}")
        print("  Scenes A and C record a real payment; without credentials they")
        print("  have nothing to show. Scene B runs anywhere: a refusal calls")
        print("  nobody, and that is precisely what it demonstrates.")
        print()
        scene_refus(registre=Registre(chemin), fournisseur=FournisseurInterdit())
    else:
        jouer(registre=Registre(chemin), fournisseur=fournisseur)
