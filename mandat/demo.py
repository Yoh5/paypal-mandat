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

import json
from pathlib import Path
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


def scene_falsification(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> dict[str, list[str]]:
    """La seule scène où le produit doit échouer pour réussir.

    Deux décisions sont inscrites, le registre se déclare intact, puis une ligne
    est réécrite **directement dans le fichier** — pas via cette bibliothèque,
    parce que personne qui couvre ses traces n'emprunte l'API prévue pour ça.
    Le vérificateur ne doit pas répondre « le journal est correct » : il doit
    nommer la ligne.
    """
    porte = _porte_de_demonstration()
    passerelle = Passerelle(porte, registre, fournisseur)

    passerelle.payer(fonder(
        Proposition.extraite(quoi="Ramette A4, 500 feuilles", montant="6.40",
                             devise="EUR", marchand="Libraire du coin",
                             preuves=("page-libraire",)),
        [PAGE_LUE]))
    passerelle.payer(fonder(
        Proposition.extraite(quoi="Imprimante laser reconditionnée", montant="89.90",
                             devise="EUR", marchand="Libraire du coin",
                             preuves=("page-libraire",)),
        [PAGE_LUE]))

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

    ecrire("== Scène C " + "=" * 56)
    ecrire("")
    ecrire(f"  Avant               {'intact' if not avant else 'ROMPU'} :"
           f" {len(lignes)} enregistrement(s) re-chaînés")
    ecrire("")
    ecrire("  On réécrit le registre comme le ferait quelqu'un qui couvre")
    ecrire("  ses traces — en éditant le fichier, pas en appelant la bibliothèque :")
    ecrire(f"      enregistrement 1, montant {euros(montant_avant)} -> {euros(1)}")
    ecrire("")
    ecrire(f"  Après               {'intact' if not apres else 'ROMPU'}")
    for probleme in apres:
        ecrire(f"      {probleme}")
    ecrire("")
    ecrire("  Le vérificateur ne déclare pas le journal correct : il nomme la ligne.")
    ecrire("  Et recalculer l'empreinte ne sauverait pas le faussaire : le")
    ecrire("  suivant porte celle d'avant, et c'est lui qui dénoncerait la")
    ecrire("  substitution. Il faudrait réécrire toute la suite.")

    return {"avant": avant, "apres": apres}


def _porte_de_demonstration() -> Porte:
    """Le même mandat pour les deux scènes.

    Volontairement partagé : la ramette passe et l'imprimante est refusée *sous
    les mêmes limites*. Deux mandats différents raconteraient deux histoires et
    ne prouveraient rien.
    """
    return Porte(
        Mandat.emettre(
            "demo-libraire",
            devise="EUR",
            par_transaction="40.00",
            total="100.00",
            marchands=("Libraire du coin",),
        )
    )


def scene_chaine(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> dict[str, Any]:
    """Depuis une référence de transaction, toute la justification.

    Un achat que le mandat autorise, puis la chaîne relue **depuis le registre**
    et non depuis la variable qu'on vient de remplir : ce que l'agent a lu, ce
    qu'il a décidé, ce que le mandat permettait à cet instant, et le fait que
    personne n'a réécrit l'enregistrement depuis.
    """
    porte = _porte_de_demonstration()
    passerelle = Passerelle(porte, registre, fournisseur)

    proposition = fonder(
        Proposition.extraite(
            quoi="Ramette A4, 500 feuilles",
            montant="6.40",
            devise="EUR",
            marchand="Libraire du coin",
            preuves=("page-libraire",),
        ),
        [PAGE_LUE],
    )

    paye = passerelle.payer(proposition)
    reference = paye["reference"]

    # Le point de la scène : on repart de la référence, comme le ferait
    # quelqu'un qui tient un relevé et rien d'autre.
    enregistrement = passerelle.pourquoi(reference)
    ecarts = registre.verifier()
    mandat = porte.mandat

    ecrire("== Scène A " + "=" * 56)
    ecrire("")
    ecrire(f"  On ne tient qu'une référence :   {reference}")
    ecrire("")
    ecrire("  Ce que l'agent a lu")
    for ligne in PAGE_LUE.strip().splitlines()[1:]:
        ecrire(f"      {ligne}")
    ecrire(f"      preuves rattachées : {', '.join(enregistrement['preuves'])}")
    ecrire("")
    ecrire("  Ce qu'il a décidé")
    ecrire(f"      {proposition.quoi} pour {euros(enregistrement['intention']['centimes'])}"
           f" {enregistrement['intention']['devise']}")
    ecrire(f"      chez {enregistrement['intention']['marchand']}")
    ecrire("")
    ecrire("  Ce que le mandat permettait à cet instant")
    ecrire(f"      mandat « {enregistrement['mandat']} », {enregistrement['at']}")
    ecrire(f"      par transaction {euros(mandat.par_transaction)}"
           f" / total {euros(mandat.total)}")
    ecrire(f"      dépensé après ce paiement : {euros(enregistrement['depense_apres'])}")
    ecrire("")
    if ecarts:
        ecrire("  Intégrité           ROMPUE")
        for e in ecarts:
            ecrire(f"      {e}")
    else:
        ecrire(f"  Intégrité           registre intact :"
               f" {len(registre.enregistrements())} enregistrement(s) re-chaînés,")
        ecrire("                      aucun écart. Personne n'a réécrit ceci depuis.")

    return enregistrement


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
    porte = _porte_de_demonstration()
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


def jouer(
    *,
    registre: Registre,
    fournisseur: Fournisseur,
    ecrire: Callable[[str], Any] = print,
) -> None:
    """Les trois scenes, dans l'ordre de la video.

    Ca marche, ca refuse, et on ne peut pas reecrire l'histoire. L'ordre est un
    crescendo : la scene C ne vaut que si l'on a d'abord vu ce qu'elle protege.

    **Cette fonction existe parce que le cablage a casse deux fois.** Les trois
    scenes etaient vertes et `python -m mandat.demo` plantait, parce que le
    point d'entree donnait a la scene C un fournisseur interdit alors qu'elle
    paie reellement. Un enchainement qui n'est pas appelable depuis un test
    n'est pas verifie.
    """
    scene_chaine(registre=registre, fournisseur=fournisseur, ecrire=ecrire)
    ecrire("")
    scene_refus(registre=registre, fournisseur=fournisseur, ecrire=ecrire)
    ecrire("")
    # La scene C reecrit son registre : elle travaille donc sur le sien, pour ne
    # pas rompre la chaine que les deux premieres viennent de construire.
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
        print("== Scenes A et C non jouees " + "=" * 40)
        print(f"  Pas d'acces au bac a sable PayPal : {pourquoi}")
        print("  Les scenes A et C inscrivent un vrai paiement ; sans identifiants")
        print("  elles n'ont rien a montrer. La scene B, elle, tourne partout : un")
        print("  refus n'appelle personne, et c'est precisement ce qu'elle demontre.")
        print()
        scene_refus(registre=Registre(chemin), fournisseur=FournisseurInterdit())
    else:
        jouer(registre=Registre(chemin), fournisseur=fournisseur)
