---
name: ssr-market-research
description: >-
  Run synthetic consumer market research and purchase intent prediction using
  Semantic Similarity Rating (SSR, Maier et al. arXiv:2510.08338). Use when
  testing products, courses, services, pricing ladders, positioning/copy,
  duration, feature bundles, or checkout order bumps with synthetic panels,
  single or multi-model runs, and Excel/CSV/HTML heatmaps.
---

# SSR Market Research

Synthetic purchase-intent testing via **Semantic Similarity Rating (SSR)** ([arXiv:2510.08338](https://arxiv.org/pdf/2510.08338)). Personas react in free text (never numeric ratings) and responses are projected via embeddings onto multi-anchor Likert distributions.

Methodology, formula, and limits: [references/ssr-paper-summary.md](./references/ssr-paper-summary.md).

## Hard Rules (Anti-Prompt-Poisoning)

1. **Neutral instructions:** Never mention target objections, hypotheses, or missing features in system/batch prompts.
2. **Natural control cards:** Never advertise absent features on control variants (e.g., omit *"does NOT include WhatsApp"* unless a real sales page states it). Add the feature only on the test variant.
3. **One variable per round:** Freeze all other attributes. Never show multiple prices or variants in the same LLM call.
4. **No numeric ratings:** Forbid `4/5` or `8/10` in persona output. Require sentence 1 (`F1`) to state the buying decision in plain words, followed by 2–4 sentences of reasoning. Score SSR primarily on `F1` (`T=0.5`); full-text `T=1.0` is optional reference.
5. **Real alternatives + control group:** Give every persona a realistic default alternative (free tutorials, cheap competitor, doing nothing) and reserve ~10–15% of the panel for a **Skeptic/Control** segment.
6. **Two-stage order-bump math:** Compute bump revenue only over buyers:
   `Expected_Ticket = Base_Price + (Buyer_Take_Rate * Bump_Price)`
   `Relative_Revenue = Base_Top2Box * Expected_Ticket`
7. **Honest labeling:** Always mark outputs as *uncalibrated exploratory synthetic scores*, never real conversion rates.

## Workflow

Confirm user choices at Steps 1, 2, 3, and 5 before executing.

### 1. Product Intake
- Accept a `.md` brief or short description and expand it into a clean Concept Card separating **Fixed Attributes** from **Variables to Test**.
- Confirm policies (price ladder, duration, access, refund guarantee, external tool costs). Optionally ask for 1–2 historical products for panel calibration.

### 2. Personas
- Propose a stratified panel (typically 40–60 personas across 4–6 segments, including 1 Skeptic control group) with age, income, occupation, weekly free time, experience level, pain point, default alternative, and buying style.
- Let the user: (a) supply an existing panel, (b) edit/add specific personas, or (c) approve the auto-generated panel.

### 3. Models & Embeddings
Works with any LLM across Antigravity, Claude Code, Codex CLI, Cursor, Ollama, or Python APIs. Never assume specific subscriptions. Let the user pick:
- **Active agent workspace** (parallel subagents/workflows, ~5–6 personas/batch, 1 variant/call)
- **Local CLIs / local models** (`codex exec`, `claude -p`, Ollama)
- **Cloud APIs** (Gemini, OpenAI, Anthropic — lightweight models like `gpt-4o-mini` / `gemini-2.5-flash` work well)
- **Single model or 2+ models** (cross-model agreement check)

Score **all** models in the **same embedding space** (`ollama:bge-m3` / `nomic-embed-text`, `text-embedding-3-small`, or `gemini-embedding-001`) using [anchors_ptbr.json](./resources/anchors_ptbr.json) or [anchors_en.json](./resources/anchors_en.json).

### 4. Setup, Dry-Run & Execution
- Create `<project>/Pesquisa-SSR/` (or `ssr-study/`) with `personas/`, `experimentos/`, `cache/`, and `resultados/`.
- Reuse [scripts/ssr_core.py](./scripts/ssr_core.py) for neutral prompts, cached embeddings, SSR math, and exporters.
- Always run a dry-run first and inspect 1 Concept Card + prompt to verify zero prompt poisoning. Cache raw batch responses on disk.

### 5. Deliverables
Ask which outputs the user wants:
1. **Excel (`.xlsx`) Heatmap** — plain-language headers, Red→Yellow→Green conditional formatting, relative revenue per 100 prospects, legend, and filterable raw-responses tab (`openpyxl`).
2. **CSV exports** — locale Excel (`;`), Google Sheets (`,`), and full raw responses.
3. **Interactive HTML Dashboard** — single-file viewer ([dashboard.html](./dashboard.html)) with Google Sans typography, Dark/Light toggle, live 1-to-N model switcher, clickable Heatmap quotes, scaled revenue (`Zoom`/`Base 0`) and `0–100%` order-bump charts, plus **`Load JSON` / drag-and-drop** for future rounds.
4. **Executive Markdown Report** — segment breakdown, cross-model comparison, and spontaneous objections mapped to copy/FAQ fixes.

### 6. Next Loop
Highlight cross-model consensus vs. divergence, suggest concrete packaging/copy iterations, and recommend real-world human validation (waitlist or live checkout A/B) for the top 1–2 winners.
