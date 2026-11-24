# ssr-market-research

Agent Skill for synthetic purchase-intent testing using **Semantic Similarity Rating (SSR)** ([Maier et al., arXiv:2510.08338](https://arxiv.org/pdf/2510.08338)).

- **Interactive viewer demo:** https://leonardofrito.github.io/ssr-market-research/dashboard.html
- **Compatible with:** Antigravity, Claude Code, Codex CLI, Cursor, or standalone Python.

## How it works

Asking LLMs for direct 1–5 ratings produces collapsed, overly positive scores. SSR avoids that in two steps:

1. Stratified consumer personas react to an offer in natural free text (no numeric ratings).
2. Each persona's opening decision sentence (`F1`) is embedded and compared via cosine similarity against 6 reference Likert anchor sets (`1`–`5`) to produce a probability distribution, while keeping the raw qualitative objections.

Includes built-in anti-prompt-poisoning rules, a skeptic control group, two-stage checkout math for order bumps/upsells, and exporters for Excel (`.xlsx`), CSV, and a standalone HTML heatmap viewer (`dashboard.html`, with drag-and-drop JSON loading).

## Files

```text
├── SKILL.md                       # Agent workflow & rules
├── dashboard.html                 # Reusable interactive HTML heatmap viewer (demo data included)
├── references/ssr-paper-summary.md
├── resources/anchors_en.json      # 6 Likert + 3 order-bump anchor sets (EN)
├── resources/anchors_ptbr.json    # 6 Likert + 3 order-bump anchor sets (PT-BR)
└── scripts/ssr_core.py            # Embeddings (Ollama/OpenAI/Gemini), SSR math, Excel/CSV/HTML exporters
```

## Install

```bash
# Antigravity (global)
git clone https://github.com/leonardofrito/ssr-market-research ~/.gemini/config/skills/ssr-market-research

# Claude Code (personal)
git clone https://github.com/leonardofrito/ssr-market-research ~/.claude/skills/ssr-market-research

# Project-local (Codex / Cursor / Antigravity)
git clone https://github.com/leonardofrito/ssr-market-research .agents/skills/ssr-market-research
```

Optional dependencies:
- **Local embeddings (free):** [Ollama](https://ollama.com) + `ollama pull bge-m3` (or OpenAI/Gemini embedding APIs).
- **Excel export (`.xlsx`):** `pip install openpyxl` *(HTML and CSV use stdlib only)*.

## Usage

Prompt your agent with a product brief (`.md` or plain text) and what you want to test (price ladder, copy, duration, feature toggle, or checkout bump). The skill walks through persona setup, model selection, dry-run checks, execution, and visual exports.

## Note

Synthetic SSR scores are **uncalibrated exploratory signals** for relative ranking and objection discovery — not real conversion forecasts. Validate final winners with real buyers.

## Reference

- Maier et al. (2025). *LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings*. [arXiv:2510.08338](https://arxiv.org/pdf/2510.08338)
- PyMC Labs package: [pymc-labs/semantic-similarity-rating](https://github.com/pymc-labs/semantic-similarity-rating)
