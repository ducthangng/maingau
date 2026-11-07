<div align="center">

# ⚡ MAINGAU Next Best Action

**The right offer, on the right channel, for the right reason, and a human approves every one.**

A need-first decision engine for energy and mobility marketing. It reads each customer's data, works out what they actually need, drops everything a rule forbids, and ranks what is left by expected gain in customer lifetime value (ΔCLV).

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/UI-React%20%2B%20TypeScript-61DAFB?logo=react&logoColor=black)
![Tailwind](https://img.shields.io/badge/Tailwind-CSS-06B6D4?logo=tailwindcss&logoColor=white)
![Status](https://img.shields.io/badge/Futury%20Build%20Days-Oct%202026-F59E0B)

[Quick start](#-quick-start) · [How it decides](#-how-it-decides) · [Results](#-results-on-the-mock-data) · [Docs](#-docs)

</div>

---

## ✨ What it does

| | |
|---|---|
| 🧭 **Need first** | 13 signals → needs → offers, through a knowledge graph. Offers that matched a real need converted at **6.8%**, against **2.1%** for the rest (mock history, descriptive only). |
| 🛡️ **Compliance built in** | Consent per channel, double opt-in, dunning, open tickets, cancellations: hard rules that marketing cannot loosen. |
| 💶 **Value-ranked** | Every offer × channel is scored by **ΔCLV = p·(CLV if bought − CLV now) + (1 − p)·(CLV if not − CLV now) − contact cost**. |
| 💬 **Ready to send** | A German message from an approved template, a send time, and a full explanation path for every choice. |
| 🎛️ **Rule Center** | Marketers change frequency caps and cooldowns, add their own rules, and preview the effect (what-if) before applying it. |
| 🙋 **Human in the loop** | Urgency-ranked worklist and bulk approval. **Nothing is sent automatically.** |

## 🔍 How it decides

```text
 Data ─▶ Signals ─▶ Need ─▶ Offers ─▶ Hard rules ─▶ ΔCLV ranking ─▶ Business rules ─▶ Proposal ─▶ 👤 Approve
         S1–S13      KG               tier 1 (C-*)                  tier 2 (B-*)        message,
                                                                                         time, why
```

**Example: MG-100023.** Bought a Wallbox but has no Autostrom contract → need: *EV charging* → **MAINGAU Autostrom** by portal pop-up at the next login, ΔCLV ≈ **+€7.12**. E-mail is blocked because consent was withdrawn, and the newsletter is held back by the e-mail cap.

## 📊 Results on the mock data

<div align="center">

| 750 customers | ~5 s build | 519 act now | 146 waiting | 85 no action |
|:---:|:---:|:---:|:---:|:---:|
| one card each | full pipeline | ΔCLV **€8,897** | for a rule, ΔCLV €1,706 | nothing worth sending |

</div>

The audit of 2,022 legacy sends found **829** that went out without channel consent.

## 🚀 Quick start

```bash
git clone https://github.com/ducthangng/maingau && cd maingau
make setup                                          # Python 3.12 venv + dependencies
make build                                          # decide for all 750 customers → out/
make api                                            # API on http://localhost:8000/docs
make web                                            # UI on http://localhost:5173 (Node 18+)
```

Approve a decision from the command line:

```bash
curl -s -X POST localhost:8000/api/customers/MG-100068/decision \
     -H 'Content-Type: application/json' -d '{"action": "approve", "user": "Anna"}'
```

Run the tests with `make test` (about 90 s).

## 🗂️ Project layout

```text
nba/       engine: kg/ (signals, rules, triage) · engine/ (CLV, ranking, content) · profile/ · learn/ · ai/
api/       FastAPI app: customers, decisions, rules, what-if, event replay
web/       React + TypeScript + Tailwind dashboard (static on Vercel, or live against the API)
kg/        ontology, policy and data contract (YAML)
config/    tunable business rules and model settings
data/      mock workbook and event stream (synthetic, from MAINGAU's challenge)
```

## 📚 Docs

- **[How it works and how to run it](docs/nba-guide.md)**: full walkthrough, CLI options, troubleshooting
- **[API reference](docs/api.md)** · **[Rule Center](docs/rule-center.md)** · **[Rule provenance](docs/rules-provenance.md)** · **[Databricks](docs/databricks.md)**
- **[Build brief](docs/build-brief.md)**: the full spec and source of truth (every "README §x" reference in the code points here)

---

<div align="center">
<sub>Built at Futury Build Days, 26–27 Oct 2026. All data is synthetic mock data. No real customer data is used.</sub>
</div>
