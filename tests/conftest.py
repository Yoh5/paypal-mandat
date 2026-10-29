# -*- coding: utf-8 -*-
"""Aucun test ne touche un modèle distant, ni ne dépense un centime.

Le jour où `agent.lire` a su lire `.env` et accepter un second fournisseur,
cette suite est devenue à un fichier près d'appeler de vrais modèles : il
suffisait qu'une clé entre dans `.env` pour que
`test_sans_cle_et_sans_enregistrement_on_leve` cesse de lever et parte sur le
réseau. Le test aurait échoué pour une raison invisible, et chaque `pytest`
aurait été facturé.

La garde est donc posée **sur tous les tests**, pas sur ceux qu'on croit
concernés : un test ajouté demain hérite de la protection sans que personne y
pense. Les noms des variables sont écrits ici, jamais leurs valeurs.
"""
from __future__ import annotations

import pytest

from mandat.agent import CLES

#: Tout ce qui pourrait désigner un fournisseur de modèle.
VARIABLES = tuple(v for noms in CLES.values() for v in noms)


@pytest.fixture(autouse=True)
def sans_identifiant_de_modele(monkeypatch):
    """Coupe les clés de l'environnement **et** la lecture de `.env`."""
    for nom in VARIABLES:
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("MANDAT_SANS_ENV", "1")
