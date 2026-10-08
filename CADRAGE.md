# Un mandat de dépense pour agents — cadrage

PayPal AI Hackathon. Échéance **12 novembre 2026, 12h00 PT** (21h00 à
Casablanca). Nom provisoire.

## La cible

**Best Use of Agentic Commerce — 5 000 $.** Catégorie nommée, et il y a sept
autres prix à 5 000 $ ou plus : une mention honorable paie autant que la
troisième place. Un projet cumule un prix principal **et** un prix partenaire,
et **Render est partenaire** — 1 000 / 750 / 500 $ de crédits — alors qu'on y
déploie déjà.

## Le problème, et pourquoi il est réel

Les agents commencent à dépenser de l'argent. Un paiement est **irréversible**,
et l'OWASP LLM Top 10 2026 — classé pour la première fois contre des incidents
réels — place **l'agentivité excessive au troisième rang**.

Ce qui manque n'est pas la plomberie du paiement : PayPal a les clés
d'idempotence, les webhooks, les remboursements. **Ce qui manque est le lien
entre l'argent qui a bougé et le raisonnement qui l'a fait bouger.** Quand un
agent achète quelque chose qu'il n'aurait pas dû, il reste une ligne de journal
que n'importe qui peut modifier.

## Le produit

Un **mandat de dépense** que l'agent ne peut pas franchir, et une preuve de ce
qu'il a fait dedans.

**Le mandat est vérifié par le code avant l'appel, pas audité après.** Plafond
par transaction, plafond total, fenêtre de temps, marchands autorisés. Un agent
ne dépasse pas son mandat parce que le code refuse — pas parce que le prompt le
lui demande gentiment.

C'est le principe qui tient tout le reste de ce travail : **le modèle lit, le
code décide.** Le modèle choisit *quoi* acheter ; le code décide si c'est
*permis*.

**Et chaque décision laisse une trace chaînée** : ce que l'agent a lu, ce qu'il
a conclu, ce que le mandat autorisait, et ce qui a été payé. Un refus est
enregistré au même titre qu'un paiement — un mandat dont on ne voit que les
succès ne prouve rien.

## Le moment de la démonstration

On donne un identifiant de transaction, et l'outil rend la chaîne entière :
quelle page l'agent a lue, pourquoi il a décidé d'acheter, ce que le mandat
permettait à cet instant, et que personne n'a réécrit l'enregistrement depuis.

Puis on montre l'autre moitié : **une tentative au-delà du mandat, refusée avant
l'appel à PayPal**, avec la raison inscrite au registre.

## Ce que ça n'est pas, et qui doit être écrit avant de commencer

**Ce n'est pas Glass Box re-présenté.** Le règlement exige que l'intégration
PayPal soit **centrale**, et un enregistreur générique avec un paiement collé
dessus serait écarté au premier filtre. Le mandat, la passerelle et le
rapprochement avec les transactions du bac à sable sont le produit ; le registre
chaîné est un composant.

**Ce n'est pas une protection contre un agent malveillant.** Le mandat contraint
le chemin qui passe par lui. Un agent qui a d'autres moyens de dépenser n'est
pas couvert, et le dire est la condition pour que le reste soit croyable.

**Et ce n'est pas un conseil financier.** On n'arbitre pas ce qu'il faut
acheter ; on contraint et on prouve.

## Ce qu'il faut vérifier tôt

1. **L'accès au bac à sable PayPal depuis le Maroc** — `developer.paypal.com`,
   compte gratuit. À confirmer avant d'écrire la couche d'intégration : c'est la
   porte qui ferme tout si elle est verrouillée.
2. **Quelles API le bac à sable ouvre sans compte entreprise** — Orders v2 au
   minimum. Le mandat doit se brancher sur ce qui existe vraiment.
3. **Projet neuf ou existant mis à jour** : le règlement accepte les deux, à
   condition d'expliquer ce qui a changé pendant la période. On part neuf.

## L'ordre de construction

Le mandat et la passerelle **d'abord**, avant toute intégration. C'est la partie
qui décide si le produit vaut quelque chose, et elle se teste entièrement sans
le moindre identifiant PayPal. La plomberie ensuite, quand l'accès est confirmé.

Même ordre que sur le banc adverse : la partie qui rend le chiffre honnête avant
la partie qui le produit.
