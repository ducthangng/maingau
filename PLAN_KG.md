# PLAN_KG: Agent KG build plan (knowledge graph, ontology, signals, rules, triage)

**Owner:** Agent KG, run by Claude in the main session. Agent KG also reviews Agent CARDS and Agent NBA.

**Status:** 26 Oct 2026. This plan details README §7.1. If it disagrees with `README.md`, the README wins, and this plan gets fixed in the same PR.

## 1. Scope and outputs

For every customer at `eval_time` (default 2026-09-30 23:59:59), Agent KG returns:

| Function (`nba/kg/`) | Returns | README |
|---|---|---|
| `load_policy()` | `Policy`, parsed and validated from `kg/policy.yaml` + `config/kg.yaml` | §6.1–§6.4, §6.12 |
| `extract_signals(state, policy)` | `list[Signal]`: S1–S13 with evidence row refs | §6.3 |
| `generate_candidates(state, signals, policy, tone)` | `(list[Candidate], list[Blocked])`: tuples that passed every gate; `valuation = None` | §6.1–§6.4, §6.12 |
| `triage(state, signals, policy, pop)` | `Triage`: archetype, urgency tier and score, reasons, deadline, flags, outlier | §6.13 |
| `explain(state, candidate, policy)` | `list[PathStep]` with `ui_ref` | §5.4, §6.11 |
| `customer_graph(state, policy)` | `networkx.MultiDiGraph`: policy layer + customer instance layer | §6.11 |
| `data_quality(state)` | `list[DataQuality]`: FRESH-CDR, FRESH-HEMS, FRESH-VALUE, SNAPSHOT-INCONSISTENT | §6.9 |

**Not in scope for Agent KG:**
- ΔCLV, p_accept and ranking (Agent NBA);
- the profile and the UI (Agent CARDS);
- learning loops.

## 2. What changed from the earlier draft of this file

The earlier `PLAN_KG.md` assumed deep dive A, rdflib/SPARQL and Streamlit. The team direction is now set by the MAINGAU-consulted spec and README.

| Earlier draft | Now | Why |
|---|---|---|
| Deep dive A: online feedback loop, Thompson sampling, simulator | Deep dive B (event freshness/replay) as KG's stretch goal; learning shown only as a concept | Control data is too thin for per-offer uplift (5/248 conversions); README §11 |
| rdflib + TTL + SPARQL | YAML policy + NetworkX graph built per customer; rules are named Python predicates | Small graph (18 offers, 13 signals); README §6.11, §11 |
| Streamlit app | Static React + TypeScript + Tailwind on Vercel (Agent CARDS) | Team decision; `prompts/agent-cards.md` |
| KG plan also covered value, learning, decide, explain, replay | KG stops at candidates, triage and paths; Agent NBA values and ranks | Three agents in parallel; clear ownership |
| Own signal list (GasHeating, NoMobile, NoInternet…) | Spec signals S1–S11 + service triggers S12–S13; everything else only via the generic path | Spec adopted in full; P-IN-01 and P-EN-04 are `DATA-MISSING` |
| Exclusions allow retention (P-EN-02) | Exclusions block sales, upsell, retention and one-off; only service passes | README §6.2, K10 |
| No profiling → contract-based eligibility | No profiling → **no signal for marketing**; generic catalog offers at the catalog-average p; owned products removed with contract data | Decision D1 (26 Oct) |
| Learning segments (lines × tenure × CLV band) | Rule-based **archetypes** A0–A5 for triage and the worklist | README §6.13; no ML clustering |
| Channel order fixed for non-profiled customers | Every consented and available channel becomes a tuple; ΔCLV decides | README §6.12, K11 |
| HEMS device offline is a service trigger | HEMS offline is a data-freshness flag (`FRESH-HEMS`), not P-SV-01 | Catalog: P-SV-01 targets complaint, dunning, cancellation |

**Kept from the draft:**
- Aggregate high-volume rows (charge sessions, portal sessions, telemetry) into signal facts instead of graph nodes.
- Store `source_table` + row IDs on every signal (`evidence`).
- Mark behavioural signals (`purpose: behavioural`).
- Export the graph as `kg_nodes` / `kg_edges` tables, which supports the Databricks / Delta story on the architecture slide.
- Flag legacy sends with `consent_checked = 0`. Whether p should exclude them is Agent NBA's question, Q-NBA-10.

## 3. Files

| Path | Content |
|---|---|
| `kg/ontology.yaml` | Node and edge types with properties and ID patterns (§4) |
| `kg/policy.yaml` | Needs, signals (metadata + predicate name), offers (needs, preconditions, generic flag), channels, consent map, exclusions; `version` |
| `config/kg.yaml` | Switches: enabled signals, profiling-off behaviour, generic offers and channels, exclusion scope, unsubscribe scope, contact cap |
| `nba/kg/policy.py` | `load_policy()` plus integrity checks |
| `nba/kg/predicates.py` | Named predicates referenced by the YAML: `gas_meter_deregistered`, `failed_charges_30d`, `wallbox_without_autostrom`, … |
| `nba/kg/signals.py` | `extract_signals()` |
| `nba/kg/rules.py` | Gates, generic tuples, `generate_candidates()` |
| `nba/kg/segments.py` | `triage()`: archetypes, urgency, flags |
| `nba/kg/paths.py` | `explain()` |
| `nba/kg/graph.py` | `customer_graph()`, `export_graph()` → `out/kg/kg_nodes.jsonl`, `out/kg/kg_edges.jsonl` |
| `nba/kg/quality.py` | `data_quality()` |
| `nba/kg/events.py` | Stretch: event replay |
| `scripts/export_schema.py` | `docs/schema/*.json` from `nba/contracts.py` |
| `scripts/kg_report.py` | `out/kg_report.md`: signal, archetype, tier and flag counts; test-customer table |
| `tests/test_kg_*.py` | Policy integrity, signals, gates, triage, paths, invariants |

## 4. Ontology

- **Policy layer** (static YAML): SignalType, Need, Offer, Channel, ConsentType, ExclusionRule, Archetype.
- **Customer layer** (built per customer):

  | Node | ID |
  |---|---|
  | Customer | `customer_id` |
  | Contract (Energy / Mobile / Autostrom) | `contract_id` |
  | Device | `device_id` |
  | Order | `order_id` + line |
  | Ticket | `ticket_id` |
  | Session | only sessions cited as evidence |
  | Consent | customer + type |
  | Exclusion | active rule instance |
  | Action | history `action_id` |
  | Signal | customer + Sx |

- **Edges (spec):** HOLDS, OWNS_DEVICE, PLACED, RAISED, EMITTED, INDICATES, ADDRESSED_BY, DELIVERED_VIA, REQUIRES, BLOCKS, RECEIVED, RESPONDED.
- **Extension edges:** EVIDENCED_BY (Signal → evidence row), HAS_SESSION (Contract → Session), IN_ARCHETYPE (Customer → Archetype).

**Explanation path for a signal tuple:**

`Customer –EMITTED→ Signal –INDICATES→ Need –ADDRESSED_BY→ Offer –DELIVERED_VIA→ Channel –REQUIRES→ Consent`

**Explanation path for a generic tuple:** `Customer → Offer (generic, catalog average) → Channel → Consent`. Each node carries a `ui_ref` (README §5.4).

## 5. Signals

Exact definitions are in README §6.3 (S1–S13). Implementation notes:
- **Dates:** `eval_time.date()` is the reference. Windows are (eval − N days, eval].
- **Evidence refs:** `contract:<id>`, `order:<order_id>`, `ticket:<id>`, `session:<id>`, `device:<id>`, `click:<campaign_id>`. Every ref resolves to a graph node (`tests/test_kg_graph.py`).
- **S10 reinforces only:** it attaches to an existing N-HEAT-PUMP / N-ENERGY-MANAGEMENT signal and never creates a tuple.
- **Counts** (README §6.3, `tests/test_kg_signals.py`): S1 12, S2 2 (MG-100009, MG-100659), S3 16, S4 143, S5 11, S6 80, S7 66, S8 33, S9 48, S10 33, S11 161, S12 29, S13 39.

## 6. Gates (applied before any ranking)

The gate order is fixed, and each failure is one `Blocked` row with `rule_id`, a plain reason, the source and a date where one exists:

1. **Data missing:** P-EN-04 and P-IN-01 → `DATA-MISSING`, once per customer.
2. **Exclusions** (§6.2) → block every non-service tuple.
3. **Holding preconditions** (§6.4) → `HOLDING-PRECONDITION`, e.g. "P-SL-02 needs a home battery".
4. **Profiling:** without `profiling_analytics = granted`, every marketing signal is reported as blocked (`CONSENT-PROFILING`, e.g. "S3 wallbox purchase ignored: no profiling consent") and only service and generic tuples remain.
5. **Channel consent and availability** per tuple (§6.1) → `CONSENT-CHANNEL` / `CHANNEL-AVAILABLE`, e.g. "marketing_phone withdrawn 2025-03-02".
6. **Contact cap:** ≥ 2 marketing contacts in 30 days → `CONTACT-CAP`. Service is exempt.

Every surviving tuple carries `checks` (all ✓), `origin`, `personalised`, `need`, `signals`, the `why` facts (e.g. "Gas meter deregistered on 2026-09-10 [S1]") and its `path`.

**Generic tuples:**
- built from `generic.offers` minus owned products (contract data only);
- every allowed channel; tone Sie; `personalised = false`;
- for profiled customers, built as a separate tier that Agent NBA uses only as a fallback (README §6.12).

## 7. Triage

Rules, counts and the score formula are in README §6.13. Implementation:
- archetype precedence is A4 > A1 > A3 > A5 > A2 > A0;
- urgency tiers are P1 > … > P5;
- `urgency_score = 100 × (5 − tier) + min(99, max(0, clv) × churn / 10)`;
- `urgency_reasons` are plain sentences with IDs;
- the flags are listed in §6.13;
- `outlier` = any of `service_critical`, `no_marketing_channel`, `negative_clv`, `annoyed_before`, `prefers_en`.

## 8. Tests (`tests/test_kg_*.py`)

- **Policy integrity:** catalog IDs exist; every signal except S10 → need → offer; channel ↔ consent is one-to-one; predicates resolve; no orphan nodes.
- **Signals:** the sanity counts above; per-test-customer expectations (README §9).
- **Gates, invariant over all 750 customers:**
  - no tuple without consent and availability;
  - no non-service tuple while an exclusion is active;
  - no signal tuple without profiling;
  - no owned product;
  - the contact cap is respected.
- **Triage:** counts in README §6.13; MG-100325 → A1, MG-100001 → A2; every customer has a triage.
- **Paths:** every tuple has a path that ends at a granted consent (or `service_agent`); every `ui_ref` is valid.
- **Determinism:** two runs give identical output.

## 9. Build order and checkpoints

| Step | Output | Checkpoint |
|---|---|---|
| 1 | `data.py`, `state.py`, `contracts.py` v1, configs | Done, 26 Oct |
| 2 | `ontology.yaml`, `policy.yaml`, `policy.py` (+ integrity tests) | Done 26 Oct: `pytest tests/test_kg_policy.py` |
| 3 | `predicates.py`, `signals.py` | Done: signal counts reproduce |
| 4 | `rules.py` (gates + generic) | Done: invariants green on 750 customers |
| 5 | `segments.py` | Done: triage counts reproduce |
| 6 | `paths.py`, `graph.py`, `quality.py` | Done: paths valid; graph export 10,781 nodes / 17,185 edges |
| 7 | `scripts/export_schema.py`, `scripts/kg_report.py` | Done: `docs/schema/`, `out/kg_report.md` |
| 8 | Push, then log in `log/agent-kg.md` | Agent NBA swaps its stub for the real KG |
| 9 (stretch) | `events.py` replay | Demo customers MG-100003, MG-100465, MG-100125, MG-100009 |

## 10. Review duties (Agent KG checks the other two)

**Agent NBA:**
- CLV within 3.05 € and churn exact on 718 customers;
- p levels and modes match README §6.6;
- one-off margins counted once;
- no double churn effect;
- ΔCLV ≤ 0 dropped;
- tiers per §6.12;
- `why` and `notes` are honest (no causal claims);
- strict acceptance tests pass;
- output is deterministic.

**Agent CARDS:**
- renders only engine values, never the archetype draft's ranges;
- every number has a source tooltip;
- outliers are distinct;
- bulk approval excludes outliers and failing checklists;
- no "send" button;
- "nicht personalisiert" is shown;
- no CLV trend;
- works as a static Vercel build.

Review results go into `log/agent-kg.md`, each with evidence: file, line, command and result.
