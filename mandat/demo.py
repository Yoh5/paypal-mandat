"""Les scènes de démonstration — le moment où le produit se voit.

Un mandat vérifié par le code est invisible tant que personne ne le regarde
refuser. Ce module ne contient aucune règle : il met en scène celles des autres
modules, pour qu'un spectateur voie en trente secondes ce que les tests
prouvent en silence.

**Propriété du produit, pas commodité de démonstration :** la scène du refus
tourne sans le moindre identifiant PayPal, parce que le refus se produit *avant*
l'appel au fournisseur.
"""
from __future__ import annotations

from typing import Any, Callable

from .mandat import Mandat, Porte, euros
from .paypal import Fournisseur, Passerelle, resume
from .proposition import Proposition, fonder
from .registre import Registre

#: Ce que l'agent a réellement lu. Le prix qui sera refusé vient de cette page,
#: pas du modèle : la scène montre un refus de mandat, pas une hallucination.
PAGE_LUE = (
    "Libraire du coin — Fournitures de bureau\n"
    "Imprimante laser reconditionnée ......... 89,90 EUR\n"
    "Ramette A4, 500 feuilles ................. 6,40 EUR\n"
)


class FournisseurInterdit:
    """Un fournisseur qui ne peut pas être appelé, et le dit fort.

    La scène du refus n'a aucune raison de joindre PayPal. Lui passer un double
    silencieux rendrait la garantie *invisible* ; lui passer celui-ci la rend
    **indestructible** : si la vérification du mandat migrait un jour après
    l'appel, la démonstration ne ralentirait pas, elle casserait en nommant la
    faute.
    """

    def creer(self, centimes: int, devise: str, description: str) -> tuple[str, str]:
        raise AssertionError(
            f"le fournisseur a été appelé pour {euros(centimes)} ({description!r}) : "
            "le mandat a été vérifié après l'appel au lieu d'avant, "
            "et ce n'est donc plus un plafond"
        )


def scene_refus(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> dict[str, Any]:
    """Une dépense au-delà du mandat, refusée avant l'appel au fournisseur.

    Le mandat autorise 40,00 € par transaction ; l'agent lit un prix de 89,90 €
    sur une page réelle et le propose de bonne foi. Le code refuse, et la raison
    est inscrite au registre au même titre qu'un paiement.
    """
    porte = Porte(
        Mandat.emettre(
            "demo-refus",
            devise="EUR",
            par_transaction="40.00",
            total="100.00",
            marchands=("Libraire du coin",),
        )
    )
    passerelle = Passerelle(porte, registre, fournisseur)

    proposition = fonder(
        Proposition.extraite(
            quoi="Imprimante laser reconditionnée",
            montant="89.90",
            devise="EUR",
            marchand="Libraire du coin",
            preuves=("page-libraire",),
        ),
        [PAGE_LUE],
    )

    enregistrement = passerelle.payer(proposition)

    mandat = porte.mandat
    # Filets en ASCII : le terminal Windows par défaut est en cp1252, qui ne
    # connaît pas les caractères semi-graphiques. Une scène qui ne s'affiche pas
    # ne se filme pas.
    ecrire("== Scène B " + "=" * 56)
    ecrire("")
    ecrire(f"  Mandat « {mandat.identifiant} »")
    ecrire(f"      par transaction   {euros(mandat.par_transaction)}")
    ecrire(f"      total             {euros(mandat.total)}")
    ecrire(f"      marchands         {', '.join(sorted(mandat.marchands))}")
    ecrire("")
    ecrire("  Ce que l'agent a lu")
    for ligne in PAGE_LUE.strip().splitlines():
        ecrire(f"      {ligne}")
    ecrire("")
    ecrire("  Ce qu'il propose")
    ecrire(f"      {proposition.quoi} — {euros(proposition.montant_centimes)}"
           f" chez {proposition.marchand}")
    ecrire("      le prix se retrouve dans la page : la proposition est fondée,")
    ecrire("      ce qui suit n'est donc pas une hallucination mais un dépassement")
    ecrire("")
    ecrire(f"  Verdict             {resume(enregistrement)}")
    ecrire("")
    ecrire("  Le fournisseur n'a pas été appelé. Le mandat s'oppose avant l'appel,")
    ecrire("  pas après : un plafond vérifié après coup n'est pas un plafond.")
    ecrire(f"  Inscrit au registre sous la séquence {enregistrement['sequence']},")
    ecrire(f"  chaîné sur {enregistrement['chain'][:16]}…")

    return enregistrement


if __name__ == "__main__":  # pragma: no cover
    import sys
    from pathlib import Path

    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs/demo-refus.jsonl")
    scene_refus(registre=Registre(chemin), fournisseur=FournisseurInterdit())
