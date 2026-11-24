---
name: ssr-market-research
description: >-
  Run synthetic consumer market research and purchase intent prediction using
  Semantic Similarity Rating (SSR, Maier et al. arXiv:2510.08338 — Colgate-Palmolive / PyMC Labs).
  Use when the user wants to test a product, course, service, pricing ladder,
  positioning/copy, feature bundle, duration, or checkout order bump/upsell
  using AI-generated consumer panels, multi-model validation (Antigravity native,
  local CLIs like Codex, or APIs), and visual heatmaps (Excel/CSV/HTML).
---

# SSR Market Research (Synthetic Purchase Intent Prediction)

Run realistic, bias-controlled synthetic market experiments based on **Semantic Similarity Rating (SSR)** ([arXiv:2510.08338](https://arxiv.org/pdf/2510.08338)). Instead of asking LLMs for raw 1–5 ratings (which collapse toward artificial optimism), personas react in natural free text and responses are projected via semantic embeddings onto multi-anchor Likert probability distributions.

For the concise paper reference, formula, and methodological limits (without re-reading the full PDF), see [references/ssr-paper-summary.md](./references/ssr-paper-summary.md).

---

## Non-Negotiable Rules (Anti-Prompt-Poisoning & Scientific Rigor)

Never violate these rules when designing or running an SSR study:

1. **Zero Prompt Poisoning in System Instructions:**
   - **NEVER** mention specific objections, missing features, or test hypotheses in the persona prompt instructions (e.g., never write *"react to the lack of WhatsApp"* or *"notice there is no certificate"*).
   - Keep instructions strictly neutral: ask the persona to react honestly in first person considering their budget, routine, and real-world alternatives.
2. **Natural Concept Cards (Never Advertise Missing Features):**
   - In a control variant without a feature (e.g., no WhatsApp group), **never** write *"Does NOT include WhatsApp group"* unless a real sales page would prominently state that. Simply describe what the offer *does* include, and add the feature only in the test variant so any lift is genuine and unprimed.
3. **Strict Causal Isolation (One Variable at a Time):**
   - Change only ONE dimension per round (e.g., price ladder with everything else frozen; or feature toggle with price frozen).
   - **NEVER** show multiple prices or variants in the same LLM call/context (prevents artificial monotonic anchoring).
4. **Never Ask for Numeric Ratings:**
   - Explicitly forbid scores (`4/5`, `8/10`) in persona output.
   - Always require the **first sentence (`F1`)** to state the person's purchase decision clearly in natural words, followed by 2–4 sentences of spontaneous reasoning. Score SSR primarily on `F1` (`T=0.5`) to avoid center-compression when pros and cons appear in the same paragraph (optionally compute full-text `T=1.0` as reference).
5. **Inject Real Opportunity Cost + Skeptic Control Group:**
   - Every persona must have a realistic default alternative (free YouTube/tutorials, cheap competitor, Sebrae/free courses, doing nothing).
   - Reserve ~10–15% of the panel for a **Skeptic / Free-Alternative Control Group** to detect inflated optimism.
6. **Honest Two-Stage Math for Order Bumps / Upsells:**
   - Never compute Order Bump revenue across non-buyers. Use:
     `Expected Ticket = Base_Price + (Buyer_Take_Rate * Bump_Price)`
     `Relative Revenue = Base_Top2Box * Expected_Ticket`
7. **Transparent Epistemic Framing:**
   - Always label outputs as **uncalibrated exploratory synthetic scores** — great for relative ranking, pricing curves, and objection discovery, never guaranteed real-world conversion rates.

---

## Interactive Workflow (Step-by-Step)

Guide the user through these 6 steps concisely. Do not skip user alignment at Steps 1, 2, 3, and 5.

### Step 1 — Product Intake & Experiment Scope
Ask the user:
1. **What are we testing?** Accept either a structured Markdown dossier/brief (`.md`) OR a quick plain-text description (which you expand into a clean, explicit Product Card separating **Fixed Attributes** from **Variables to Test**).
2. **What decisions do you want to test?** (e.g., price ladder, format/duration, positioning/copy, feature inclusion, checkout order bump/upsell, naming).
3. *(Optional Calibration)* Ask if they have 1–2 historical products (a winner and a slower seller) to optionally sanity-check the panel before testing the new offer.

Confirm the exact Concept Card(s) and frozen policies (access duration, refund guarantee, prerequisites, external tool costs) before generating personas.

### Step 2 — Synthetic Consumer Panel (Personas)
Design a demographically stratified panel (typically **40–60 personas** across **4–6 segments**, e.g., 10 per segment, including 1 **Skeptic/Control** segment).
- Per arXiv:2510.08338, **age** and **income bracket** are the strongest drivers of realistic purchase-intent variance. Add concrete domain traits: occupation, weekly free time, current skill/experience level, primary pain point, **default alternative**, and buying style.
- **Always offer the user 3 choices:**
  1. Use an existing persona file they already have;
  2. Review/edit the segments and add specific custom personas they want represented;
  3. Let you generate the full stratified panel automatically and show a quick summary for sign-off.

### Step 3 — Choose Execution Models & Embeddings Backend
This skill follows the open **Agent Skills** format and works with **any LLM** (lightweight or frontier) across **Antigravity, Claude Code, Codex CLI, Cursor, Ollama local models, or standalone Python**. Never assume the user has specific premium subscriptions or heavy reasoning tiers. Check what is available locally and let the user pick:
1. **Current Agent Workspace (Native):** runs parallel subagents/workflows directly inside the active agent environment (zero extra setup; use stratified batches of ~5–6 personas per call, strictly 1 variant per call).
2. **Local Authenticated CLIs / Local Models:** e.g., OpenAI `codex exec`, Claude Code CLI (`claude -p`), or local open models via **Ollama** (`llama3`, `qwen`, `gemma`, etc.) — great for zero-API-cost runs or adding a second independent model.
3. **Direct Cloud APIs (Fast & Cheap):** Gemini API (`gemini-2.5-flash`), OpenAI API (`gpt-4o-mini`), or Anthropic API (`claude-haiku` / `sonnet`) — pennies per full round and ideal for large panels (100–300 personas).
4. **Single vs. Multi-Model:** Running **1 model** already gives strong directional signals; running **2+ independent model families** (e.g., Gemini + GPT, or Claude + local Llama) adds an automatic agreement cross-check!

**Embeddings Backend (Shared Vector Space for ALL Models):**
- Always score every model's responses with the **same embedding model** and **same anchor set** (`resources/anchors_ptbr.json` for pt-BR, `resources/anchors_en.json` for English):
  - **Local & Free:** Ollama (`bge-m3` for multilingual/pt-BR, or `nomic-embed-text` for English). Start `ollama serve` if needed.
  - **Cloud API:** `gemini-embedding-001` or `text-embedding-3-small`.

### Step 4 — Prepare Scripts, Dry-Run & Execute with Disk Cache
Create a clean experiment workspace folder (e.g., `<project>/Pesquisa-SSR/`) containing:
- `personas/` (panel JSON)
- `experimentos/` (round matrix JSON)
- `cache/` (per-batch LLM response cache + embedding cache so re-scoring, changing temperature `T`, or regenerating charts costs zero re-runs)
- `resultados/` (final reports and spreadsheets)

Use [scripts/ssr_core.py](./scripts/ssr_core.py) for shared embedding calls, SSR PMF math, and report generation.
- **Validation rule:** Always run a `--dry-run` (or inspect 1 rendered Concept Card + neutral prompt) before executing full rounds. Verify **zero prompt poisoning** before launching!
- Run models in parallel with batch caching and automatic retries.

### Step 5 — Choose Output & Visualization Formats
Ask the user which deliverables they want (recommend combining **#1 + #3** or **#1 + #4**):

1. **Plain-Language Excel Workbook (`.xlsx`) with Native Color Heatmap** *(Default Favorite)*
   - Built with `ssr_core.py` (requires `openpyxl`).
   - Red → Yellow → Green conditional formatting across segments × variants.
   - Zero marketing jargon in headers (plain local language).
   - Separate comparison table showing **"Relative Revenue per 100 Evaluated Prospects"** in currency (`R$` / `$`) so winning offers jump off the page, plus a plain-language reading legend at the bottom and a filterable raw-responses tab.
2. **Clean CSV Exports**
   - Locale-friendly CSV (`;` with `,` decimals for PT-BR Excel) + standard `,` CSV for Google Sheets + full individual responses CSV.
3. **Interactive Single-File HTML Dashboard (Reusable Viewer + Pre-Filled Export)**
   - Built with `ssr_core.export_interactive_html_heatmap` using **Google Sans** typography (crisp Windows ClearType rendering) and Dark/Light mode toggle.
   - **Works both ways:** opens pre-filled for the current study **AND** includes a **`Load JSON` / Drag-and-Drop** button so a single viewer HTML can dynamically load any future round's JSON file without regenerating the page.
   - **100% Model-Agnostic:** automatically adapts to 1, 2, or N models present in the JSON.
   - Includes a clickable Heatmap (click any cell to inspect verbatim persona quotes), **scaled** Relative Revenue chart (with explicit graduated X-axis + `Zoom` / `Base 0` toggle and `% delta` badges), and a `0–100%` gridded Order Bump chart.
4. **Executive Markdown Report & Copy/FAQ Playbook**
   - Actionable business takeaways, segment-by-segment winners, verbatim buyer/rejector quotes, and a prioritized list of spontaneous objections mapped to landing-page FAQ/copy fixes.

### Step 6 — Deliver Diagnosis & Next Experiment Loop
Present findings clearly:
- Compare models side-by-side (highlight where Model A and Model B agree — high confidence — vs. diverge).
- Translate patterns into concrete product/packaging hypotheses (e.g., 2-layer modular duration, optional checkout Order Bump, jargon removal).
- Propose either the next surgical SSR round OR the **real-world human validation test** (waitlist / real checkout A/B) for the top 1–2 winning offers.

---

## Bundled Files

- [references/ssr-paper-summary.md](./references/ssr-paper-summary.md) — Concise methodology, exact SSR math, PDF link, and limitations.
- [resources/anchors_ptbr.json](./resources/anchors_ptbr.json) — 6 Likert (1–5) anchor sets + 3 Order Bump anchor sets in Brazilian Portuguese.
- [resources/anchors_en.json](./resources/anchors_en.json) — 6 Likert (1–5) anchor sets + 3 Order Bump anchor sets in English.
- [scripts/ssr_core.py](./scripts/ssr_core.py) — Reusable Python module for Ollama/OpenAI/Gemini cached embeddings, SSR PMF calculation (`F1` + full text), plain-language Excel Heatmap export, CSV export, and interactive HTML Heatmap dashboard generator.
