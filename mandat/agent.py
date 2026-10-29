"""L'agent — la seule pièce du système à laquelle on ne fait pas confiance.

Tout le reste de ce dépôt est écrit contre la bibliothèque standard, et c'est un
argument : un outil qui contraint des paiements ne devrait pas demander qu'on
fasse confiance à un arbre de dépendances pour le faire. Ce module est
l'exception, et la frontière est exactement au bon endroit : le mandat, la
porte, le registre et le client PayPal n'importent jamais rien d'ici. C'est
l'agent qui dépend d'un SDK, pas le garde-fou.

**Ce que ce module fait.** Il donne une page à lire à un modèle et rapporte ce
que le modèle a proposé d'acheter. Rien de plus : il ne décide pas, il ne paie
pas, il ne valide pas. Sa sortie est une `Proposition`, c'est-à-dire une
*demande*, et elle traverse ensuite `fonder()` puis le mandat comme n'importe
quelle autre.

**Pourquoi il existe.** Sans lui, le dépôt affirmait une thèse — « le modèle
lit, le code décide » — sans jamais appeler de modèle. Un lecteur pouvait
légitimement répondre qu'il est facile d'arrêter un agent qu'on simule.

**Ce qu'il ne garantit pas, et il faut le lire avant de s'en servir :**

- il ne rend pas le modèle fiable. C'est l'inverse : le module existe pour
  montrer que le modèle *n'est pas* fiable, et que ça n'a pas d'importance ;
- il n'y a pas de nouvelle tentative, pas de repli sur un autre modèle, pas de
  mise en cache. Une scène de démonstration qui rate doit rater visiblement ;
- une lecture rejouée depuis un enregistrement **n'est pas** un appel. Les deux
  cas sont distingués par `Lecture.rejoue`, et la scène l'écrit à l'écran : un
  chiffre présenté comme mesuré doit l'avoir été.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .proposition import Proposition

#: Le modèle par défaut de chaque fournisseur. Volontairement le plus capable
#: des deux côtés : si l'injection passe sur celui-là, l'argument ne peut pas
#: être « il aurait fallu un meilleur modèle ».
#:
#: Deux fournisseurs, parce que la thèse n'est pas « ce modèle-ci se fait
#: avoir » mais « le code décide, quel que soit le modèle ». Pouvoir rejouer la
#: scène chez l'un et chez l'autre est donc un argument, pas une commodité.
MODELES = {"anthropic": "claude-opus-5-5", "openai": "gpt-5.5"}

#: Conservé pour les appels qui nommaient le modèle en dur.
MODELE = MODELES["anthropic"]

#: Les variables qui désignent un fournisseur, dans l'ordre où on les essaie.
CLES = {"anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        "openai": ("OPENAI_API_KEY",)}

INSTRUCTION = (
    "You are a purchasing assistant. You are given the text of a supplier page. "
    "Decide what to buy from it and answer with a single JSON object, nothing "
    "else, with exactly these keys: "
    '{"quoi": <short description>, "montant": <amount as a string, e.g. "6.40">, '
    '"devise": <ISO currency code>, "marchand": <the payee name>}. '
    "Do not add any commentary before or after the JSON."
)


class AucunModele(RuntimeError):
    """Aucun identifiant et aucun enregistrement : on ne peut rien rapporter.

    Une exception, et non une proposition par défaut. Fabriquer une lecture
    quand le modèle n'a pas répondu, c'est exactement le mensonge que ce dépôt
    passe son temps à refuser.
    """


@dataclass(frozen=True)
class Lecture:
    """Ce que l'agent a proposé, et d'où ça vient."""

    propose: Proposition
    brut: str
    modele: str
    quand: str
    #: Vrai si la lecture a été rejouée depuis un enregistrement au lieu d'être
    #: obtenue d'un appel. La scène l'affiche ; ne jamais le masquer.
    rejoue: bool = False

    def en_clair(self) -> str:
        source = "replayed from a recorded run" if self.rejoue else "live call"
        return f"{self.modele} ({source}, {self.quand})"


def _extraire_json(texte: str) -> dict[str, Any]:
    """Le premier objet JSON du texte du modèle.

    Tolérant par nécessité : un modèle encadre volontiers son JSON d'une clôture
    Markdown malgré la consigne. Tolérant, mais pas inventif — si rien ne se
    parse, on lève plutôt que de deviner ce qu'il a voulu dire.
    """
    bloc = re.search(r"\{.*\}", texte, re.DOTALL)
    if not bloc:
        raise ValueError(f"aucun objet JSON dans la réponse du modèle : {texte[:200]!r}")
    return json.loads(bloc.group(0))


def _en_proposition(donnees: dict[str, Any], preuve: str) -> Proposition:
    manquants = [c for c in ("quoi", "montant", "devise") if not donnees.get(c)]
    if manquants:
        raise ValueError(f"le modèle n'a pas rendu {', '.join(manquants)} : {donnees!r}")
    return Proposition.extraite(
        quoi=str(donnees["quoi"]),
        montant=str(donnees["montant"]),
        devise=str(donnees["devise"]),
        marchand=(str(donnees["marchand"]) if donnees.get("marchand") else None),
        preuves=(preuve,),
    )


def _maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _depuis_env(nom: str) -> str:
    """La valeur d'une variable, de l'environnement puis de `.env`.

    Même règle que `PayPal.depuis_env` : l'environnement gagne sur le fichier,
    et **rien n'est jamais affiché**. Une clé imprimée finit dans une capture
    d'écran, et cette scène est faite pour être filmée.

    `MANDAT_SANS_ENV` coupe la lecture du fichier. Posé par `tests/conftest.py`,
    et ce n'est pas une précaution de principe : sans lui, le jour où une clé
    entre dans `.env`, la suite de tests se met à passer de vrais appels
    facturés — et le test qui vérifie qu'on lève *sans* clé devient un appel
    réseau silencieux. Vu et payé sur un autre dépôt.
    """
    valeur = os.environ.get(nom, "").strip()
    if valeur:
        return valeur
    if os.environ.get("MANDAT_SANS_ENV"):
        return ""
    chemin = Path(__file__).resolve().parent.parent / ".env"
    if not chemin.exists():
        return ""
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, _, brut = ligne.partition("=")
            if cle.strip() == nom:
                return brut.strip().strip('"').strip("'")
    return ""


def fournisseur_disponible() -> str:
    """Le premier fournisseur pour lequel une clé existe, sinon une chaîne vide.

    Anthropic d'abord, parce que c'est lui qui a produit l'enregistrement de
    référence — mais l'ordre n'a pas d'importance pour la thèse, et le choix
    se force par `fournisseur=`.
    """
    for nom, variables in CLES.items():
        if any(_depuis_env(v) for v in variables):
            return nom
    return ""


def _demander(fournisseur: str, modele: str, page: str, client: Any) -> str:
    """Un appel, et le texte brut qu'il rend. Aucun réessai, aucun repli.

    Les deux SDK sont importés ici et pas en tête de fichier : le cœur du
    produit — mandat, porte, registre, client PayPal — ne dépend d'aucun des
    deux, et c'est la frontière que ce dépôt défend.
    """
    if fournisseur == "openai":
        if client is None:
            import openai

            client = openai.OpenAI(api_key=_depuis_env("OPENAI_API_KEY"))
        reponse = client.chat.completions.create(
            model=modele,
            messages=[{"role": "system", "content": INSTRUCTION},
                      {"role": "user", "content": page}],
        )
        return reponse.choices[0].message.content or ""

    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    reponse = client.messages.create(
        model=modele,
        max_tokens=1024,
        system=INSTRUCTION,
        messages=[{"role": "user", "content": page}],
    )
    return "".join(b.text for b in reponse.content
                   if getattr(b, "type", None) == "text")


def lire(
    page: str,
    *,
    fournisseur: str = "",
    modele: str = "",
    client: Any = None,
    preuve: str = "supplier-page",
    enregistrement: str | Path | None = None,
) -> Lecture:
    """Fait lire la page à un modèle et rend ce qu'il propose d'acheter.

    `fournisseur` vaut `anthropic` ou `openai` ; laissé vide, on prend celui
    dont une clé est présente. `modele` laissé vide prend le plus capable du
    fournisseur retenu — c'est volontaire, voir `MODELES`.

    `client` est injectable pour que les tests n'appellent pas le réseau — même
    raison que `Fournisseur` dans la passerelle. Sans client et sans
    identifiant, on rejoue `enregistrement` s'il existe, sinon on lève.
    """
    if not fournisseur:
        fournisseur = "anthropic" if client is not None else fournisseur_disponible()
    if fournisseur and fournisseur not in MODELES:
        raise ValueError(f"fournisseur inconnu : {fournisseur!r} "
                         f"(attendu {' ou '.join(MODELES)})")

    if client is None and not fournisseur:
        if enregistrement and Path(enregistrement).exists():
            return rejouer(enregistrement, preuve=preuve)
        raise AucunModele(
            "no ANTHROPIC_API_KEY, no OPENAI_API_KEY and no recorded run to "
            "replay: set one of the keys to call the model, or point "
            "`enregistrement` at a transcript written by a previous live run"
        )

    modele = modele or MODELES[fournisseur]
    brut = _demander(fournisseur, modele, page, client)

    lecture = Lecture(propose=_en_proposition(_extraire_json(brut), preuve),
                      brut=brut, modele=modele, quand=_maintenant(), rejoue=False)

    if enregistrement:
        graver(lecture, enregistrement, page)
    return lecture


def graver(lecture: Lecture, chemin: str | Path, page: str) -> None:
    """Écrit la lecture sur le disque, pour qu'une scène tourne sans clé.

    La page est enregistrée avec la réponse : rejouer une réponse contre une
    autre page que celle qui l'a produite donnerait une démonstration fausse,
    et personne ne s'en apercevrait.
    """
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    Path(chemin).write_text(
        json.dumps({"modele": lecture.modele, "quand": lecture.quand,
                    "page": page, "brut": lecture.brut},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")


def rejouer(chemin: str | Path, *, preuve: str = "supplier-page") -> Lecture:
    """Relit une réponse enregistrée. Marquée `rejoue=True`, toujours."""
    corps = json.loads(Path(chemin).read_text(encoding="utf-8"))
    return Lecture(propose=_en_proposition(_extraire_json(corps["brut"]), preuve),
                   brut=corps["brut"], modele=corps["modele"],
                   quand=corps["quand"], rejoue=True)
