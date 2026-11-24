# SSR Market Research — Agent Skill

[![Paper: arXiv:2510.08338](https://img.shields.io/badge/Paper-arXiv%3A2510.08338-b31b1b.svg)](https://arxiv.org/pdf/2510.08338)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Interactive%20Heatmap-22c55e.svg)](https://leonardofrito.github.io/ssr-market-research/dashboard.html)
[![Agent Skills Compatible](https://img.shields.io/badge/Agent%20Skills-Antigravity%20%7C%20Claude%20Code%20%7C%20Codex%20%7C%20Cursor-0ea5e9.svg)](#installation)
[![License: MIT](https://img.shields.io/badge/License-MIT-64748b.svg)](./LICENSE)

An open **Agent Skill** for running bias-controlled **synthetic consumer market research and purchase intent prediction** based on **Semantic Similarity Rating (SSR)** — the methodology published by **Colgate-Palmolive & PyMC Labs** ([Maier et al., arXiv:2510.08338](https://arxiv.org/pdf/2510.08338)).

Test pricing ladders, product positioning, feature bundles, course/SaaS duration, and checkout **Order Bumps** *before* launching — across **any LLM** (Antigravity, Claude Code, Codex CLI, Cursor, Ollama local models, or cloud APIs) — and inspect results in an **interactive clickable HTML Heatmap** or **Excel `.xlsx` Heatmap**.

---

## Why SSR (instead of asking an LLM "rate 1 to 5")?

When you ask an LLM directly *"Rate your likelihood to buy this product from 1 to 5"*, models collapse into overly polite, narrow scores that don't match real buyers.

**Semantic Similarity Rating (SSR)** fixes this in two steps:
1. **Free-text elicitation:** Stratified consumer personas (grounded in age, income, routine, and real-world free alternatives) react naturally in first-person text — **never outputting numbers**.
2. **Multi-anchor semantic projection:** Each persona's decision sentence (`F1`) is embedded and compared via cosine similarity against **6 reference anchor sets** (`1 = definitely would not buy` → `5 = definitely would buy`) to produce a calibrated Likert probability distribution — while preserving verbatim qualitative objections.

### Field-Tested Guardrails Built Into This Skill
- **Anti-Prompt-Poisoning:** Strictly neutral instructions — never prime personas with target objections and never advertise *"does NOT include X"* on control cards.
- **Decision-Sentence Scoring (`F1, T=0.5`):** Eliminates center-compression caused by mixing praise and objections in the same paragraph.
- **Mandatory Skeptic Control Group:** ~10–15% of every panel consists of skeptical / free-alternative users to catch artificial optimism.
- **Honest Two-Stage Checkout Math:** Order Bump / Upsell revenue is computed strictly on buyers (`Base_Intent × (Base_Price + Buyer_Take_Rate × Bump_Price)`), never inflated across non-buyers.
- **Model-Agnostic & Cross-Model Ready:** Works with 1 model (lightweight API, local Ollama, or your active agent) or compares 2+ independent model families in the **same embedding space**.

---

## Interactive HTML Dashboard (`dashboard.html`)

Open the **[Live Interactive Demo](https://leonardofrito.github.io/ssr-market-research/dashboard.html)** (or open [`dashboard.html`](./dashboard.html) locally in any browser):

- **Clickable Segment × Variant Heatmap** — click any cell to inspect verbatim persona quotes (filterable by *Likely Buyers* vs. *Objections*).
- **Live Model Switcher** — automatically adapts to 1, 2, or N models (`Consensus` + individual models).
- **Scaled Charts with Explicit Axes** — Relative Revenue per 100 prospects (with `Zoom` / `Base 0` toggle and `% delta` badges) + `0–100%` gridded Order Bump chart.
- **Reusable Viewer (`📂 Load JSON` / Drag & Drop)** — drop any future round's JSON directly onto the page without regenerating HTML.
- **Google Sans typography + Dark/Light Mode toggle** (clean Windows ClearType & screenshot ready).

---

## Repository Layout

```text
ssr-market-research/
├── SKILL.md                          # Main Agent Skill instructions (6-step interactive workflow)
├── dashboard.html                    # Standalone interactive HTML Heatmap viewer (with sample demo data)
├── references/
│   └── ssr-paper-summary.md          # Concise methodology, SSR math & limits (link to arXiv:2510.08338)
├── resources/
│   ├── anchors_en.json               # 6 Likert (1–5) + 3 Order Bump anchor sets (English)
│   └── anchors_ptbr.json             # 6 Likert (1–5) + 3 Order Bump anchor sets (Portuguese BR)
├── scripts/
│   └── ssr_core.py                   # Reusable Python engine (Ollama/OpenAI/Gemini embeddings, SSR PMF, Excel + CSV + HTML exporters)
├── README.md
└── LICENSE
```

---

## Installation

Works out of the box with any tool supporting the open **Agent Skills** standard:

### Antigravity (Global — available in all workspaces)
```bash
git clone https://github.com/leonardofrito/ssr-market-research ~/.gemini/config/skills/ssr-market-research
```

### Claude Code / Codex CLI / Cursor (Project or Global)
```bash
# Project-local
git clone https://github.com/leonardofrito/ssr-market-research .agents/skills/ssr-market-research

# Or for Claude Code personal skills
git clone https://github.com/leonardofrito/ssr-market-research ~/.claude/skills/ssr-market-research
```

### Optional Dependencies
- **Embeddings (free & local):** [Ollama](https://ollama.com) with `ollama pull bge-m3` (multilingual) or `nomic-embed-text` (English) — or use OpenAI (`text-embedding-3-small`) / Gemini (`gemini-embedding-001`) APIs.
- **Excel Heatmap export (`.xlsx`):** `pip install openpyxl` *(HTML Dashboard and CSV exports require Python standard library only)*.

---

## How to Use

Once installed, simply prompt your agent:

> *"Run an SSR market research test on my new offer. Here's my product brief (`offer.md`). I want to test pricing from $29 to $69 and whether adding a $9 community order bump increases revenue."*

The skill will guide you interactively through:
1. **Product Intake** (`.md` brief or short pitch → fixed attributes vs. variables to isolate)
2. **Synthetic Consumer Panel** (bring your own, customize segments, or auto-generate with a Skeptic control group)
3. **Model & Embedding Selection** (native agent workspace, local CLIs/Ollama, cloud APIs, or 2-model cross-check)
4. **Dry-Run & Cached Execution** (verify zero prompt poisoning before running)
5. **Deliverables** (Interactive HTML Heatmap, native `.xlsx` Excel Heatmap, CSVs, and Executive Objection/FAQ Report)

---

## Methodological Disclaimer

Synthetic SSR scores are **uncalibrated exploratory signals** designed for rapid concept screening, relative ranking between offers, pricing-curve exploration, and uncovering buyer objections before spending ad budget. Always validate your top 1–2 winning variants with real human buyers (waitlist, pre-sale, or live checkout A/B test).

## Reference

- Maier, B. F., Aslak, U., Fiaschi, L., Rismal, N., Fletcher, K., Luhmann, C. C., Dow, R., Pappas, K., & Wiecki, T. V. (2025). *LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings*. [arXiv:2510.08338](https://arxiv.org/pdf/2510.08338).
- Official PyMC Labs package: [pymc-labs/semantic-similarity-rating](https://github.com/pymc-labs/semantic-similarity-rating).
