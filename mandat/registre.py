"""Relier l'argent qui a bougé au raisonnement qui l'a fait bouger.

Un journal de paiements ordinaire répond « combien » et « quand ». Celui-ci
répond **« pourquoi, et sous quelle autorité »** — et il le fait d'une manière
qu'on peut vérifier plutôt que croire.

Trois propriétés, et la troisième est celle qui compte.

**Les refus sont enregistrés comme les paiements.** Un registre qui ne montre
que les succès ne prouve pas qu'un mandat mordait : c'est l'empreinte des refus
qui le montre.

**Les enregistrements sont chaînés.** Chacun s'engage sur le précédent, donc
retirer ou modifier une ligne se voit. Un journal qu'on peut éditer après coup
est un témoignage, pas une preuve — et dans un litige de paiement, la différence
est tout.

**Un paiement absent du registre est signalé comme une sortie de route.** C'est
le contraire du réflexe habituel, qui rend « introuvable » et passe à autre
chose. Si PayPal a une transaction que ce registre n'a pas, l'argent est parti
**sans passer par le mandat** — et c'est l'information la plus importante que ce
système puisse produire.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

#: Les champs hachés dans la chaîne, et seulement ceux-là présents.
_CORPS = (
    "sequence", "at", "mandat", "intention", "preuves",
    "issue", "regle", "detail", "reference", "depense_apres",
)
_STRUCTURE = ("prev", "chain")


def _canonique(corps: Mapping[str, Any]) -> str:
    return json.dumps(corps, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _empreinte(corps: Mapping[str, Any], prev: str | None) -> str:
    return "sha256:" + hashlib.sha256(((prev or "") + _canonique(corps)).encode("utf-8")).hexdigest()


class HorsRegistre(LookupError):
    """Une référence de transaction que ce registre ne connaît pas.

    Une exception et non un `None` : un appelant qui reçoit `None` l'affiche
    comme « rien à signaler », alors que c'est exactement l'inverse. Un paiement
    que le registre ignore est un paiement qui n'est pas passé par le mandat.
    """


@dataclass
class Registre:
    """Append-only, chaîné, une ligne JSON par décision de paiement."""

    chemin: Path

    def __post_init__(self) -> None:
        self.chemin = Path(self.chemin)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)

    # ── Écriture ────────────────────────────────────────────────────────

    def _lignes(self) -> list[str]:
        if not self.chemin.exists():
            return []
        return [l for l in self.chemin.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _derniere_empreinte(self) -> str | None:
        lignes = self._lignes()
        return json.loads(lignes[-1])["chain"] if lignes else None

    def _inscrire(self, corps: dict[str, Any]) -> dict[str, Any]:
        prev = self._derniere_empreinte()
        corps = {cle: corps[cle] for cle in _CORPS if cle in corps}
        enregistrement = {**corps, "prev": prev, "chain": _empreinte(corps, prev)}
        with self.chemin.open("a", encoding="utf-8") as f:
            f.write(_canonique(enregistrement) + "\n")
        return enregistrement

    def paiement(
        self,
        *,
        at: str,
        mandat: str,
        montant_centimes: int,
        devise: str,
        reference: str,
        preuves: Iterable[str] = (),
        marchand: str | None = None,
        depense_apres: int | None = None,
    ) -> dict[str, Any]:
        """Un paiement parti, avec la référence que le fournisseur a rendue."""
        if not reference:
            raise ValueError(
                "un paiement sans référence de transaction ne peut pas être "
                "rapproché : c'est précisément ce que ce registre existe pour permettre"
            )
        return self._inscrire({
            "sequence": len(self._lignes()) + 1,
            "at": at,
            "mandat": mandat,
            "intention": {"centimes": montant_centimes, "devise": devise, "marchand": marchand},
            "preuves": list(preuves),
            "issue": "paye",
            "reference": reference,
            "depense_apres": depense_apres,
        })

    def refus(
        self,
        *,
        at: str,
        mandat: str,
        montant_centimes: int,
        devise: str,
        regle: str,
        detail: str,
        preuves: Iterable[str] = (),
        marchand: str | None = None,
    ) -> dict[str, Any]:
        """Un paiement que le mandat n'a pas permis.

        Inscrit au même titre qu'un succès. Sans ça, le registre raconte un
        agent exemplaire qui n'a jamais rien tenté d'interdit.
        """
        return self._inscrire({
            "sequence": len(self._lignes()) + 1,
            "at": at,
            "mandat": mandat,
            "intention": {"centimes": montant_centimes, "devise": devise, "marchand": marchand},
            "preuves": list(preuves),
            "issue": "refuse",
            "regle": regle,
            "detail": detail,
        })

    # ── Lecture ─────────────────────────────────────────────────────────

    def enregistrements(self) -> list[dict[str, Any]]:
        return [json.loads(l) for l in self._lignes()]

    def pourquoi(self, reference: str) -> dict[str, Any]:
        """Toute la justification d'un paiement, depuis sa référence.

        Lève `HorsRegistre` quand la référence est inconnue — voir la docstring
        de l'exception : c'est une alarme, pas une absence.
        """
        for e in self.enregistrements():
            if e.get("reference") == reference:
                return e
        raise HorsRegistre(
            f"{reference!r} n'est pas dans ce registre. Si le fournisseur a cette "
            "transaction, l'argent est parti sans passer par le mandat."
        )

    def verifier(self) -> list[str]:
        """Re-chaîne le fichier et nomme le premier enregistrement qui ne tient pas.

        Un champ hors de la liste hachée est signalé plutôt qu'ignoré : un
        vérificateur qui ne peut pas rendre compte d'une partie d'un
        enregistrement n'a pas à le déclarer intact.
        """
        problemes: list[str] = []
        prev: str | None = None

        for position, ligne in enumerate(self._lignes(), start=1):
            brut = json.loads(ligne)
            corps = {cle: brut[cle] for cle in _CORPS if cle in brut}

            if brut.get("prev") != prev:
                problemes.append(
                    f"enregistrement {position} ne suit pas le précédent : "
                    "une ligne a été modifiée, supprimée ou insérée"
                )
            elif _empreinte(corps, prev) != brut.get("chain"):
                problemes.append(f"enregistrement {position} a été modifié depuis son écriture")

            hors = sorted(set(brut) - set(_CORPS) - set(_STRUCTURE))
            if hors:
                problemes.append(
                    f"enregistrement {position} porte {', '.join(hors)}, qu'aucun "
                    "hachage ne couvre"
                )

            prev = brut.get("chain")

        return problemes

    # ── Rapprochement ───────────────────────────────────────────────────

    def sorties_de_route(self, references_du_fournisseur: Iterable[str]) -> list[str]:
        """Les transactions du fournisseur que ce registre ne connaît pas.

        Le cœur du rapprochement. Une transaction chez PayPal absente d'ici est
        un paiement qui n'est pas passé par la porte — soit un chemin de code
        qui contourne le mandat, soit quelque chose de pire. Dans les deux cas
        c'est ce qu'il faut regarder en premier.
        """
        connues = {e["reference"] for e in self.enregistrements() if e.get("reference")}
        return [r for r in references_du_fournisseur if r not in connues]
