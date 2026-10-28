# Le dossier Devpost — PayPal AI Hackathon

Échéance : **12 novembre 2026, 12h00 PT** (21h00 à Casablanca).
Tout ce qui suit est à coller champ par champ. Les longueurs sont comptées, pas
estimées : `python submission/compter.py` les revérifie.

---

## Les catégories à cocher, et ce qu'elles valent vraiment

Il y a **huit prix à 5 000 $ ou plus**, pas trois : grand prix 12 000 / 8 000 /
5 000, puis cinq mentions à 5 000 $. Un projet cumule un prix principal **et**
un prix partenaire.

| Catégorie | Verdict |
|---|---|
| **Best Use of Agentic Commerce** | **La cible.** Catégorie nommée, et c'est exactement le sujet : un agent qui dépense, contraint par du code. La scène D ne l'affirme plus, elle le montre : un vrai modèle lit une page hostile, se fait avoir, et le code l'arrête. |
| **Best Use of PayPal + AI** | À cocher. L'intégration est centrale par construction, pas collée. |
| **Best Demo Delivery** | À cocher. La vidéo est faite, sous-titrée, et chaque chiffre y est exécuté. |
| Most Impactful / Most Creative | À cocher aussi : ça ne coûte rien et le jury trie. |
| **Render (prix partenaire)** | **ACQUIS — à cocher.** Déployé et vérifié en ligne le 28/10 : `https://spend-mandate-demo.onrender.com`, `/health` rend 200, le refus affiche « 89,90 requested, 40,00 allowed » depuis le vrai service. `DEMO_URL` est posée. Seule réserve, dite dans la description : **22,6 s de démarrage à froid** mesurées. |

---

## Project name

```
Spend Mandate
```

## Elevator pitch

```
A spend mandate an agent cannot cross. Caps are enforced by code before the PayPal call, never audited after, and every refusal is chained into the register exactly like a payment.
```

## Video demo link

```
https://youtu.be/zPNiNpsnENw
```

Titre déposé sur YouTube : *Refused before PayPal is called — a spend mandate
for AI agents*. Sous-titres : `submission/video/mandat-demo.en.srt` (27
répliques, calées sur les durées mesurées).

## Try it out links

```
https://spend-mandate-demo.onrender.com
https://github.com/Yoh5/paypal-mandat
```

La page hébergée ne détient **aucun identifiant de paiement** : elle interroge
`Porte.verifier()` seule, ce qui est possible parce qu'un refus n'appelle
personne. Essayer 89,90 chez *The Corner Bookshop* : refusé contre un plafond
de 40,00, avant tout appel.

⚠️ **Démarrage à froid mesuré le 28/10/2026 : 22,6 s** (`/health`, plan gratuit
Render, région Francfort), puis **0,33 s** une fois éveillée. Chiffre relevé par
commande, pas estimé. À redire tel quel dans la description : un juré qui tombe
sur l'attente doit l'avoir lue avant.

---

## About the project

### Inspiration

Agents have started spending money, and a payment is the one action that cannot
be undone. The OWASP Top 10 for LLM Applications 2026 — the first edition ranked
against real incidents — puts excessive agency at number three.

What struck me was that the missing piece is not payment plumbing. PayPal
already has idempotency keys, webhooks and refunds. What was missing is the link
between the money that moved and the reasoning that moved it. When an agent buys
something it should not have, all that remains is a log line anyone can edit.

### What it does

It gives the agent a mandate it cannot cross: a cap per transaction, a total
cap, a validity window, a list of merchants.

**The mandate is enforced by code before the call, not audited after.** An agent
stays inside its mandate because the gateway refuses — not because a prompt asked
it nicely. A cap checked after the call is not a cap, it is a report.

**Every decision is recorded, refusals included.** A register that only shows
successes describes an exemplary agent that never tried anything forbidden. Each
record carries the fingerprint of the one before it, so a line cannot be
rewritten alone.

Three things you can run:

- **Allowed** — the agent reads a page, proposes 6,40 for a ream of paper, the
  mandate allows it, PayPal creates the order. From that transaction reference
  alone, the whole chain comes back: what was read, what was decided, what the
  mandate permitted at that instant.
- **Refused** — the same page, the printer at 89,90. The price is real, so this
  is a mandate breach and not a hallucination. The gateway refuses and **PayPal
  is never called**. Not refunded, not reversed. Never called.
- **Rewritten** — a line is edited directly in the register file. The verifier
  does not answer that the log is fine. It names the line.

### How I built it

Python, standard library only. The mandate, the gateway, the chained register
and the PayPal Orders v2 client are written against `urllib`, `json`, `hashlib`
and `base64` — nothing else. A tool whose job is to constrain payments should not
ask you to trust a dependency tree in order to do it.

The build order was deliberate and it is the same one I use for measurement
work: **the part that makes the claim honest before the part that produces it.**
The mandate and the gateway came first and are fully testable without a single
PayPal credential; the integration came after, once sandbox access was
confirmed.

The demo video is rendered by the product: `submission/video/` runs the real
demo, reads the register it just wrote, executes the verifier on the tampered
copy, and counts the test suite. Nothing in the film is typed. If the cap
changes, the film changes with it.

### Challenges I ran into

**A guarantee that could not fire.** The first version of the reconciliation
queried the provider using the references *already recorded*, then looked for
ones the register did not know. By construction there were never any: the most
important check in the module could not trigger, and it returned an empty list
that read as "nothing to report". Orders v2 has no list endpoint, so the
provider's references have to come from elsewhere — a webhook log, a transaction
export. Until they do, the gap is **not verified**, and the code now says so,
because an empty list because nothing was searched and an empty list because
nothing is there are opposite things.

**Three green tests and a demo that would not start.** The scenes were covered,
the suite was green, and `python -m mandat.demo` crashed: the tests captured
output into a list, so they never encoded it, while a console does. Box-drawing
characters do not exist in cp1252. The guard now encodes to cp1252 explicitly.

**A claim my own output contradicted.** The tampering scene said the break
"propagates" while the verifier had named exactly one record — the forger had
not touched the fingerprint, so the next record still followed. I withdrew the
claim, wrote the true one, and only then discovered it had no test. It does now.

### Accomplishments I'm proud of

`FournisseurInterdit` does not count provider calls — it forbids them. If the
mandate check ever moved to after the call, the demo would not run slower, it
would break and name the fault. The guarantee is not measured, it is
indestructible.

And the film never lets colour carry meaning alone: green against red measures
ΔE 4.1 under deuteranopia. The refusal reads by form — the path stops, the
figure is struck through, the link breaks, a cross lands — and colour only
reinforces.

### What I learned

That my defects cluster at one seam: **between the test harness and the real
run.** The cp1252 crash, the entry point that handed the tampering scene a
forbidding provider although that scene really pays, the README that told
readers to set `PAYPAL_CLIENT_SECRET` while the code reads `PAYPAL_SECRET` —
all the same shape. Orchestration no test can call is orchestration nobody
checks.

### What's next

The reconciliation deserves the webhook log it is waiting for: once the
provider's own references can be supplied, out-of-register payments stop being
an unverified gap and become a verified zero. After that, mandates issued per
task rather than per agent, so a single compromised run cannot spend the whole
budget.

---

## Built with

```
python, paypal, paypal-orders-v2, paypal-sandbox, standard-library, pytest,
sha256, json, llm-agents, owasp-llm-top-10, apache-2.0
```

---

## Scène D — l'argument qui manquait, et ce qu'il faut encore faire

**Le trou qu'elle bouche.** Jusqu'au 28/10, *aucun modèle n'était appelé nulle
part dans ce dépôt*. `requirements.txt` disait « Runtime: nothing » et les
propositions étaient écrites à la main dans `demo.py`. L'architecture était
défendable, mais un juré d'un hackathon **IA** pouvait légitimement répondre
qu'il est facile d'arrêter un agent qu'on simule.

**Ce que la scène montre.** Un modèle lit une page fournisseur qui porte une
instruction destinée à ce qui la lit. Ce que le modèle répond est ce qui
traverse les contrôles — rien n'est arrangé après coup. La page est construite
pour que **deux des trois contrôles n'aient rien à dire** :

| Contrôle | Verdict | Pourquoi |
|---|---|---|
| Ancrage (`fonder`) | **passe** | 29,99 et « Quick Supplies Ltd » sont écrits sur la page : c'est l'attaquant qui les y a mis. Un contrôle qui demande seulement « l'agent a-t-il inventé ce chiffre ? » n'a rien à objecter. |
| Plafond par transaction | **passe** | 29,99 est sous 40,00. Une injection qui demande peu passe devant un plafond. |
| Liste de marchands | **REFUSE** | le mandat ne paie que *The Corner Bookshop*. |

C'est l'aveu qui porte l'argument : un contrôle unique est un point de
défaillance unique, et la scène **nomme** celui qui tient au lieu de laisser
croire que tout a marché. `test_l_ancrage_ne_rattrape_PAS_une_injection_ecrite_
sur_la_page` fige cet aveu — renforcer `fonder()` un jour cassera le test au
lieu de rendre la page menteuse en silence.

**La frontière des dépendances tient.** `mandat/agent.py` est le seul fichier
qui importe le SDK, et il l'importe à l'intérieur de la fonction. Ni le mandat,
ni la porte, ni le registre, ni le client PayPal, ni la démo web déployée ne le
touchent — vérifié : le service Render, qui n'installe rien, démarre toujours.

### Ce qu'il reste à faire, et c'est à toi

1. **Jouer la scène une fois avec une vraie clé** :
   `ANTHROPIC_API_KEY=... python -m mandat.demo`. Elle écrit la transcription
   dans `runs/lecture-piegee.json`, ce qui permet ensuite de la rejouer sans
   clé — en l'annonçant à l'écran comme un rejeu, jamais comme un appel.
2. **Regarder ce que le modèle a réellement répondu.** Il n'est pas obligé de
   se faire avoir ; s'il résiste, la scène le dit et ne paie rien. C'est un
   résultat honnête, mais une démonstration plus faible : il faudra alors durcir
   la page, et le dire.
3. **Re-rendre le film.** Il fait 2 min 22 et ne contient pas cette scène.
   `submission/video/film.py` le génère à partir de sorties exécutées, donc
   c'est scripté — mais ça reste un rendu à relancer, et les sous-titres
   (`mandat-demo.en.srt`) à recaler.

## À faire avant de déposer

1. ~~**Mettre la vidéo en ligne**~~ — **FAIT le 28/10** :
   `https://youtu.be/zPNiNpsnENw`, lien vérifié par requête et non collé de
   confiance (commit `b83316c`). **Reste à téléverser `mandat-demo.en.srt`
   dans l'onglet sous-titres de YouTube** — les montants sont le cœur de la
   démonstration et la reconnaissance automatique les écrira faux.
2. **Vérifier que le dépôt est bien public** : `curl -o /dev/null -w "%{http_code}"
   https://github.com/Yoh5/paypal-mandat` doit rendre **200**.
3. **Décider pour Render** : déployer une démo web avant le 12, ou ne pas cocher
   le prix partenaire. Si tu déploies, dans cet ordre :
   - une route `/health` qui répond 200 sans rien faire de lourd ;
   - dans GitHub → *Settings* → *Secrets and variables* → *Actions* →
     *Variables*, poser **`DEMO_URL`** sur cette route. `keep-awake.yml` est
     **inerte tant que cette variable n'existe pas** — il saute proprement au
     lieu d'afficher une croix rouge pour « pas encore déployé ».
   - **mesurer** le démarrage à froid une fois en ligne
     (`curl -o /dev/null -w "%{time_total}" <url>` après 20 min de silence) et
     écrire le chiffre dans la description Devpost. Ne pas l'estimer.

   ### Ce que keep-awake fait VRAIMENT sur ce dépôt — mesuré le 28/10/2026

   `gh run list` donne trois exécutions : **01:34, 07:21, 14:16 UTC**. Soit
   **5,78 h puis 6,91 h d'écart**, sur un `cron` qui demande toutes les dix
   minutes. Avec une fenêtre de 50 minutes par exécution, la démo est tenue
   éveillée **12 à 14 % du temps** — et les trois exécutions sont vertes.
   La prédiction écrite dans l'en-tête du fichier se reproduit donc ici, à
   l'identique.

   **Conséquence pratique :** un juré a ~85 % de chances de tomber sur les
   22,6 s de réveil. Si ça compte pour « Best Demo Delivery », la seule vraie
   correction est un pinger **externe** (cron-job.org, UptimeRobot — gratuits,
   et eux partent à l'heure dite) toutes les 10 minutes sur `/health` ;
   GitHub Actions ne tiendra jamais cette promesse sur un dépôt public.

   ⚠️ **Et le dire comme c'est :** `keep-awake.yml` ne promet pas que la démo
   soit chaude quand un juré arrive. GitHub décide *quand* une exécution
   planifiée part — sur un dépôt public, les relevés montrent **trois à six
   heures** d'écart, pas dix minutes. Le workflow tient donc le service éveillé
   **cinquante minutes par exécution** plutôt que de le piquer une fois, ce qui
   réduit le risque sans l'annuler. La description dit le chiffre mesuré au lieu
   de laisser croire le contraire.
4. **Relancer `python submission/compter.py`** avant le dépôt. Il ne compte plus
   seulement les champs : il lance la suite et compare le nombre de tests
   annoncé ici et dans le README à celui qui passe réellement. Le chiffre a
   bougé trois fois en deux jours (86 → 97 → 114) et les deux fichiers ne
   l'ont pas suivi ensemble ; c'est le genre de vérification qu'on oublie
   précisément la veille d'une échéance.
5. **Rouvrir chaque champ après envoi.** Un formulaire tronqué par une coupure
   s'envoie sans erreur visible.
