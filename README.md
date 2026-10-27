# Spend mandate — a limit an agent cannot cross, and proof of what it did inside

An agent that buys things is the sharpest case of excessive agency: a payment is
**irreversible**, and the OWASP Top 10 for LLM Applications 2026 — the first
edition ranked against real incidents — puts excessive agency at number three.

What is missing is not payment plumbing. PayPal already has idempotency keys,
webhooks and refunds. **What is missing is the link between the money that moved
and the reasoning that moved it.** When an agent buys something it should not
have, all that remains is a log line anyone can edit.

## What this is

A **spend mandate** the agent cannot cross, and a chained record of what it did
inside one.

- **The mandate is enforced by code before the call, not audited after.** Cap per
  transaction, total cap, validity window, allowed merchants. An agent stays
  inside its mandate because the gateway refuses — not because a prompt asked it
  nicely.
- **Every decision is recorded, refusals included.** A register that only shows
  successes proves nothing: it describes an exemplary agent that never tried
  anything forbidden.
- **The model reads, the code decides.** The model chooses *what* to buy; the
  code decides whether it is *allowed*.

## Two scenes, both runnable

### Scene A — the chain, read back from a reference alone

You hold a transaction reference and nothing else. The tool returns what the
agent read, what it decided, what the mandate permitted at that instant, and the
register's own verdict on whether anyone has rewritten the record since.

```
== Scene A ========================================================

  On ne tient qu'une référence :   0NW87949GN153422L

  Ce que l'agent a lu
      Imprimante laser reconditionnée ......... 89,90 EUR
      Ramette A4, 500 feuilles ................. 6,40 EUR
      preuves rattachées : page-libraire

  Ce qu'il a décidé
      Ramette A4, 500 feuilles pour 6,40 EUR
      chez Libraire du coin

  Ce que le mandat permettait à cet instant
      mandat « demo-libraire », 2026-10-27T21:10:44Z
      par transaction 40,00 / total 100,00
      dépensé après ce paiement : 6,40

  Intégrité           registre intact : 1 enregistrement(s) re-chaînés,
                      aucun écart. Personne n'a réécrit ceci depuis.
```

That reference is a **real PayPal sandbox order**, not a stand-in.

### Scene B — the refusal, before PayPal is ever reached

The same mandate, the same page. The agent reads a printer at 89,90 € — a price
that genuinely appears in the source, so this is a mandate breach and not a
hallucination — and proposes it in good faith. The gateway refuses, and the
reason is written to the register with the same weight as a payment.

```
  Verdict             REFUSÉ  89,90  [plafond par transaction] 89,90 demandés, 40,00 permis

  Le fournisseur n'a pas été appelé. Le mandat s'oppose avant l'appel,
  pas après : un plafond vérifié après coup n'est pas un plafond.
```

**Scene B needs no PayPal credentials at all.** That is not a testing
convenience — it is the product's central claim made observable: a refusal
happens *before* the call, so there is nothing to call.

The test suite holds that claim down from the other side. `FournisseurInterdit`
does not count provider calls, it forbids them: if the mandate check ever moved
to after the call, the demo would not run slower, it would break and name the
fault.

## Running it

```bash
python -m mandat.demo                    # both scenes, onto runs/demo.jsonl
pip install -r requirements.txt          # pytest, for the tests
python -m pytest tests -q                # 82 tests
```

**There are no runtime dependencies.** The mandate, the gateway, the register
and the PayPal client are written against the standard library alone — `urllib`,
`json`, `hashlib`, `base64`. A tool whose job is to constrain payments should not
ask you to trust a dependency tree in order to do it.

Scene A needs PayPal sandbox credentials, from the environment or from a local
`.env` (which is git-ignored):

```
PAYPAL_CLIENT_ID=...
PAYPAL_SECRET=...
```

Without them scene A announces itself as not played and says why, and scene B
runs anyway.

## What it is not, and this is written before anything else is claimed

**It is not protection against a malicious agent.** The mandate constrains the
path that goes through it. An agent with other ways to spend is not covered, and
saying so is the condition for the rest to be believable.

**It is not financial advice.** Nothing here arbitrates what should be bought. It
constrains, and it proves.

**Out-of-register payments are not verified by default.** Orders v2 exposes no
list endpoint: a transaction can only be queried when you already hold its id.
So the reconciliation reports `verifie: false` until a webhook log or a
transaction export is supplied — because an empty list because nothing was
searched and an empty list because nothing is there are opposite things.

## Layout

| File | What it holds |
|---|---|
| `mandat/mandat.py` | The mandate and the gate. Immutable: a cap that can be raised mid-flight is not a cap. |
| `mandat/paypal.py` | The gateway — the only path money can take — and the sandbox client. |
| `mandat/proposition.py` | What the model proposes, and the check that its figures come from what it actually read. |
| `mandat/registre.py` | Append-only chained register, one JSON line per decision. |
| `mandat/demo.py` | The two scenes. No rules live here. |

## Licence

Apache-2.0.
