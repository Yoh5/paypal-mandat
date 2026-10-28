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
| **Best Use of Agentic Commerce** | **La cible.** Catégorie nommée, et c'est exactement le sujet : un agent qui dépense, contraint par du code. |
| **Best Use of PayPal + AI** | À cocher. L'intégration est centrale par construction, pas collée. |
| **Best Demo Delivery** | À cocher. La vidéo est faite, sous-titrée, et chaque chiffre y est exécuté. |
| Most Impactful / Most Creative | À cocher aussi : ça ne coûte rien et le jury trie. |
| **Render (prix partenaire)** | **À portée, pas encore acquis.** `render.yaml` (Blueprint, plan gratuit, Francfort, `/health`) et `mandat/web.py` existent et tournent — vérifié en local le 28/10 : `/health` rend 200 en 10 ms, le refus affiche « 89,90 requested, 40,00 allowed », l'autorisation passe, une saisie absurde ne casse rien. Il manque **le déploiement lui-même** et la variable `DEMO_URL`. Tant que l'URL n'existe pas, ne pas cocher. |

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
https://github.com/Yoh5/paypal-mandat
```

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

   ⚠️ **Et le dire comme c'est :** `keep-awake.yml` ne promet pas que la démo
   soit chaude quand un juré arrive. GitHub décide *quand* une exécution
   planifiée part — sur un dépôt public, les relevés montrent **trois à six
   heures** d'écart, pas dix minutes. Le workflow tient donc le service éveillé
   **cinquante minutes par exécution** plutôt que de le piquer une fois, ce qui
   réduit le risque sans l'annuler. La description dit le chiffre mesuré au lieu
   de laisser croire le contraire.
4. **Relancer la suite** avant le dépôt : `python -m pytest tests -q` doit dire
   **97 passed** (mesuré le 28/10 ; les 86 d'avant dataient d'avant
   `tests/test_web.py`). Un dépôt dont les tests sont rouges se voit.
5. **Rouvrir chaque champ après envoi.** Un formulaire tronqué par une coupure
   s'envoie sans erreur visible.
