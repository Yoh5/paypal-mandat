"""Ce qu'un agent a le droit de dépenser, vérifié avant l'appel.

Le modèle lit, le code décide. Le modèle choisit *quoi* acheter ; ce module
décide si c'est *permis*, et il le décide **avant** que l'argent parte — pas
dans un audit du lendemain.

La distinction n'est pas de forme. Un paiement est irréversible : une règle
vérifiée après coup constate un dépassement, elle ne l'empêche pas. Et une règle
qui vit dans le prompt n'est pas une règle, c'est une demande polie.

Quatre décisions de conception, chacune prise contre une version plus simple qui
aurait l'air de marcher :

- **Les montants sont en centimes, en entiers.** `0.1 + 0.2 != 0.3` en binaire,
  et un plafond franchi d'un millième par arrondi est un bogue qu'on ne trouve
  qu'en production, sur l'argent de quelqu'un.
- **Un refus est enregistré comme un paiement.** Un mandat dont on ne voit que
  les succès ne prouve rien : c'est l'empreinte des refus qui montre qu'il
  mordait.
- **La raison du refus nomme la règle et le chiffre.** « Refusé » envoie
  chercher au mauvais endroit ; « plafond par transaction : 50,00 € demandés,
  25,00 € permis » se corrige tout seul.
- **Le mandat est immuable.** Un objet qu'on peut élargir en cours de route
  n'est pas un plafond. Changer de mandat veut dire en émettre un autre, et le
  registre porte lequel était en vigueur.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Iterable


class Refus(Exception):
    """Levée quand le mandat ne permet pas l'opération.

    Une exception plutôt qu'un booléen : un appelant qui oublie de tester un
    retour envoie l'argent quand même. Ici, ne rien faire signifie ne pas payer.
    """

    def __init__(self, regle: str, detail: str) -> None:
        super().__init__(f"{regle} — {detail}")
        self.regle = regle
        self.detail = detail


def _centimes(montant: str | int) -> int:
    """Lit un montant en centimes, sans jamais passer par un flottant.

    Accepte un entier (déjà des centimes) ou une chaîne décimale. Refuse un
    flottant : `float("19.99")` vaut 19.989999999999998, et ce chiffre-là
    finira par franchir un plafond qu'il n'aurait pas dû.
    """
    if isinstance(montant, bool):  # bool est un int, et ce n'est pas un montant
        raise TypeError("un booléen n'est pas un montant")
    if isinstance(montant, int):
        return montant
    if isinstance(montant, float):
        raise TypeError(
            "un montant en flottant est refusé : 0.1 + 0.2 != 0.3, et un plafond "
            "franchi par arrondi est un bogue qu'on trouve sur l'argent de quelqu'un. "
            "Passez une chaîne (\"19.99\") ou des centimes (1999)."
        )
    texte = str(montant).strip()
    if texte.count(".") > 1 or not texte.replace(".", "").replace("-", "").isdigit():
        raise ValueError(f"montant illisible : {montant!r}")
    negatif = texte.startswith("-")
    entier, _, decimale = texte.lstrip("-").partition(".")
    decimale = (decimale + "00")[:2]
    valeur = int(entier or "0") * 100 + int(decimale)
    return -valeur if negatif else valeur


def euros(centimes: int) -> str:
    """Pour les messages : 2550 -> « 25,50 »."""
    signe = "-" if centimes < 0 else ""
    c = abs(centimes)
    return f"{signe}{c // 100},{c % 100:02d}"


@dataclass(frozen=True)
class Mandat:
    """Les limites d'un agent, posées avant qu'il agisse.

    Immuable : un plafond qu'on peut relever en cours de route n'est pas un
    plafond. Pour changer les limites, on émet un autre mandat, et le registre
    dit lequel était en vigueur au moment du paiement.
    """

    identifiant: str
    devise: str = "EUR"
    #: Plafond d'une transaction, en centimes. None = pas de plafond propre.
    par_transaction: int | None = None
    #: Plafond cumulé sur toute la vie du mandat, en centimes.
    total: int | None = None
    #: Marchands autorisés. Vide = aucune restriction de marchand.
    marchands: frozenset[str] = frozenset()
    #: Bornes de validité, en ISO 8601 UTC.
    valide_de: str | None = None
    valide_jusqu_a: str | None = None

    @classmethod
    def emettre(
        cls,
        identifiant: str,
        *,
        devise: str = "EUR",
        par_transaction: str | int | None = None,
        total: str | int | None = None,
        marchands: Iterable[str] = (),
        valide_de: str | None = None,
        valide_jusqu_a: str | None = None,
    ) -> "Mandat":
        pt = None if par_transaction is None else _centimes(par_transaction)
        tt = None if total is None else _centimes(total)
        if pt is not None and pt <= 0:
            raise ValueError("un plafond par transaction nul ou négatif interdit tout paiement")
        if tt is not None and tt <= 0:
            raise ValueError("un plafond total nul ou négatif interdit tout paiement")
        if pt is not None and tt is not None and pt > tt:
            raise ValueError(
                f"plafond par transaction ({euros(pt)}) au-dessus du total ({euros(tt)}) : "
                "le premier ne mordrait jamais"
            )
        return cls(identifiant, devise, pt, tt, frozenset(marchands), valide_de, valide_jusqu_a)

    def elargir(self, **_) -> None:
        raise TypeError(
            "un mandat ne s'élargit pas : émettez-en un autre, pour que le registre "
            "puisse dire lequel était en vigueur"
        )


@dataclass
class Porte:
    """Le point de passage obligé. Rien ne paie sans être passé par ici.

    Tient le cumul dépensé, donc une instance par mandat et par agent. Le
    registre des décisions vit ailleurs : cette classe décide, elle n'archive
    pas.
    """

    mandat: Mandat
    depense: int = 0
    refus: list[Refus] = field(default_factory=list)

    def _maintenant(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def verifier(
        self,
        montant: str | int,
        *,
        devise: str = "EUR",
        marchand: str | None = None,
        instant: str | None = None,
    ) -> int:
        """Rend le montant en centimes si le mandat le permet, sinon lève `Refus`.

        L'ordre des contrôles est délibéré : du plus structurel au plus
        circonstanciel, pour que la raison rendue soit la plus utile. Une devise
        qui ne correspond pas est une erreur de programmation ; un plafond
        atteint est une information sur l'état du mandat.
        """
        c = _centimes(montant)
        instant = instant or self._maintenant()

        if c <= 0:
            self._refuser("amount", f"{euros(c)} is not a payment")

        if devise != self.mandat.devise:
            self._refuser(
                "currency",
                f"{devise} requested, the mandate is denominated in {self.mandat.devise}",
            )

        if self.mandat.valide_de and instant < self.mandat.valide_de:
            self._refuser("validity window",
                          f"mandate valid from {self.mandat.valide_de}, it is {instant}")
        if self.mandat.valide_jusqu_a and instant > self.mandat.valide_jusqu_a:
            self._refuser("validity window",
                          f"mandate expired on {self.mandat.valide_jusqu_a}, it is {instant}")

        if self.mandat.marchands and marchand not in self.mandat.marchands:
            permis = ", ".join(sorted(self.mandat.marchands))
            self._refuser("merchant", f"{marchand!r} is not in the mandate ({permis})")

        pt = self.mandat.par_transaction
        if pt is not None and c > pt:
            self._refuser(
                "per-transaction cap",
                f"{euros(c)} requested, {euros(pt)} allowed",
            )

        tt = self.mandat.total
        if tt is not None and self.depense + c > tt:
            reste = tt - self.depense
            self._refuser(
                "total cap",
                f"{euros(c)} requested, {euros(reste)} left of {euros(tt)}",
            )

        return c

    def engager(self, montant: str | int, **contraintes) -> int:
        """Vérifie **puis** retient le montant sur le cumul.

        Séparé de `verifier` parce qu'un appelant peut vouloir savoir sans
        engager. Mais l'engagement précède l'appel au fournisseur : si on
        retenait après, deux paiements concurrents passeraient tous deux un
        plafond qu'un seul aurait dû franchir.
        """
        c = self.verifier(montant, **contraintes)
        self.depense += c
        return c

    def rendre(self, centimes: int) -> None:
        """Rend au cumul ce qu'un paiement échoué n'a pas dépensé.

        Sans ça, un appel refusé par PayPal après engagement consommerait le
        mandat pour rien, et l'agent se retrouverait bridé par de l'argent qui
        n'est jamais parti.
        """
        if centimes < 0:
            raise ValueError("on ne rend pas un montant négatif")
        self.depense = max(0, self.depense - centimes)

    @property
    def reste(self) -> int | None:
        return None if self.mandat.total is None else self.mandat.total - self.depense

    def _refuser(self, regle: str, detail: str) -> None:
        r = Refus(regle, detail)
        self.refus.append(r)
        raise r
