#!/usr/bin/env python3
"""
Reusable SSR (Semantic Similarity Rating) Core Library — arXiv:2510.08338
Provides:
  - Cached embeddings (Ollama local, OpenAI API, Gemini API)
  - Exact multi-anchor SSR PMF calculation (F1 decision-sentence + full-text)
  - Guaranteed-neutral, anti-prompt-poisoning batch prompt builders
  - Plain-language Excel (.xlsx) native Heatmap exporter
  - Locale-aware CSV exporters (Excel PT-BR ';' and Google Sheets ',')
  - Self-contained Interactive HTML Heatmap Dashboard exporter (clickable quotes)
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = SKILL_ROOT / "resources"


def first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return parts[0] if parts else text.strip()


def load_anchors(lang: str = "pt-BR", kind: str = "purchase") -> list[dict[str, str]]:
    """
    lang: 'pt-BR' or 'en'
    kind: 'purchase' or 'order_bump'
    Returns list of dicts mapping {'1': str, ..., '5': str}.
    """
    if lang.lower().startswith("pt"):
        data = json.loads((RESOURCES_DIR / "anchors_ptbr.json").read_text(encoding="utf-8"))
        key = "conjuntos_intencao_compra" if kind == "purchase" else "conjuntos_order_bump"
        return [item["ancoras"] for item in data[key]]
    data = json.loads((RESOURCES_DIR / "anchors_en.json").read_text(encoding="utf-8"))
    key = "purchase_intent_sets" if kind == "purchase" else "order_bump_sets"
    return [item["anchors"] for item in data[key]]


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {exc.code} at {url}: {body[:400]}") from exc
        except urllib.error.URLError as exc:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"Network error at {url}: {exc}") from exc
    raise RuntimeError("Request failed after retries.")


def get_embedding(
    text: str,
    provider: str = "ollama",
    model: str = "bge-m3",
    cache_dir: Path | None = None,
    api_key: str = "",
) -> list[float]:
    cache_file: Path | None = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(
            json.dumps({"p": provider, "m": model, "t": text}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:24]
        cache_file = cache_dir / f"emb_{digest}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))["embedding"]

    if provider == "ollama":
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        resp = _post_json(f"{host}/api/embeddings", {"Content-Type": "application/json"}, {"model": model, "prompt": text})
        vec = resp["embedding"]
    elif provider == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for openai embeddings.")
        resp = _post_json(
            "https://api.openai.com/v1/embeddings",
            {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            {"model": model, "input": text},
        )
        vec = resp["data"][0]["embedding"]
    elif provider == "gemini":
        key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is required for gemini embeddings.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={key}"
        resp = _post_json(url, {"Content-Type": "application/json"}, {"model": f"models/{model}", "content": {"parts": [{"text": text}]}})
        vec = resp["embedding"]["values"]
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

    if cache_file is not None:
        cache_file.write_text(json.dumps({"embedding": vec}), encoding="utf-8")
    return vec


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if (na > 0.0 and nb > 0.0) else 0.0


def compute_ssr_pmf(
    response_vec: list[float],
    anchor_sets_vecs: list[dict[str, list[float]]],
    temperature: float = 0.5,
    epsilon: float = 0.0,
) -> dict[str, float]:
    """
    Exact SSR probability mass function (arXiv:2510.08338):
      d_i = max(0, cos_i - min(cos)) + eps
      w_i = d_i ** (1 / T)
      p_i = w_i / sum(w)
    Averaged across all reference anchor sets.
    """
    scale = ["1", "2", "3", "4", "5"]
    pmfs = []
    for anchors in anchor_sets_vecs:
        sims = [cosine_similarity(response_vec, anchors[k]) for k in scale]
        s_min = min(sims)
        shifted = [max(0.0, s - s_min) + epsilon for s in sims]
        if sum(shifted) == 0.0:
            pmf = [0.2] * 5
        else:
            inv_t = 1.0 / max(temperature, 1e-6)
            weights = [v**inv_t for v in shifted]
            total = sum(weights)
            pmf = [w / total for w in weights]
        pmfs.append(pmf)
    avg = [sum(p[i] for p in pmfs) / len(pmfs) for i in range(5)]
    return {k: avg[i] for i, k in enumerate(scale)}


def build_neutral_batch_prompt(
    personas_batch: list[dict[str, Any]],
    concept_card: str,
    language: str = "pt-BR",
    order_bump_text: str | None = None,
) -> str:
    """
    Builds a strictly neutral, anti-prompt-poisoning simulation prompt.
    Never names target objections or missing features in instructions.
    """
    profiles_md = []
    for p in personas_batch:
        lines = [f"### PERSONA {p['id']} — {p['nome']} ({p['idade']}, {p.get('cidade_uf', p.get('location', ''))})"]
        for k, v in p.items():
            if k in ("id", "nome", "idade", "cidade_uf", "location", "segmento"):
                continue
            lines.append(f"- {k}: {v}")
        profiles_md.append("\n".join(lines))
    profiles_block = "\n\n".join(profiles_md)

    if language.lower().startswith("pt"):
        if order_bump_text:
            return f"""Você está conduzindo uma simulação realista de pesquisa de mercado (metodologia SSR — arXiv:2510.08338) com fluxo de checkout em 2 etapas.
Abaixo está a oferta principal, um adicional opcional no checkout e {len(personas_batch)} perfis completamente independentes.

REGRAS RIGOROSAS:
1. Para CADA persona, responda em primeira pessoa ("eu..."), em português natural, 100% honesto e pé no chão. NÃO tente agradar o criador da oferta.
2. NUNCA escreva notas numéricas nem escalas ("4/5", "8/10"). Use apenas texto natural.
3. Preencha DOIS campos separados:
   - `resposta_curso_base`: Comece com uma primeira frase clara declarando se compraria ou não a oferta principal hoje, seguida de 2 a 3 frases explicando espontaneamente o que pesou a favor e contra.
   - `resposta_order_bump`: Comece com uma primeira frase clara declarando se marcaria ou não a opção adicional no checkout, seguida de 1 a 2 frases explicando por quê (se não compraria a oferta principal, seja coerente com isso).
4. Retorne exatamente todos os {len(personas_batch)} persona_ids no JSON.

=== OFERTA PRINCIPAL ===
{concept_card}

=== OPÇÃO ADICIONAL NO CHECKOUT ===
{order_bump_text}

=== PERFIS INDEPENDENTES ===
{profiles_block}""".strip()

        return f"""Você está conduzindo uma simulação realista de pesquisa de mercado (metodologia SSR — arXiv:2510.08338).
Abaixo está UMA única oferta e {len(personas_batch)} perfis de consumidores completamente independentes.

REGRAS RIGOROSAS:
1. Para CADA persona, responda em primeira pessoa ("eu..."), em português natural, pensando realisticamente no próprio bolso, rotina e alternativas existentes.
2. Seja 100% honesto e pé no chão. NÃO tente agradar o criador da oferta.
3. NUNCA escreva notas numéricas nem escalas ("4/5", "8/10"). Use apenas texto corrido natural.
4. Comece com uma primeira frase clara declarando se compraria ou não essa oferta hoje (expressando o grau real de intenção em palavras), seguida de 2 a 4 frases explicando espontaneamente o que pesou a favor e o que pesou contra.
5. Retorne exatamente todos os {len(personas_batch)} persona_ids no JSON.

=== OFERTA ===
{concept_card}

=== PERFIS INDEPENDENTES ===
{profiles_block}""".strip()

    # English version
    return f"""You are running a realistic market research simulation (SSR methodology — arXiv:2510.08338).
Below is ONE product offer and {len(personas_batch)} completely independent consumer personas.

STRICT RULES:
1. For EACH persona, respond in first person ("I...") in natural English, realistically weighing budget, daily routine, and default alternatives.
2. Be 100% honest and grounded. Do NOT flatter the creator.
3. NEVER output numeric scores or scales ("4/5", "8/10"). Write natural prose only.
4. Start with a clear first sentence stating whether you would buy this offer today (conveying genuine degree of intent in words), followed by 2–4 sentences explaining spontaneously what worked for you and what held you back.
5. Return all {len(personas_batch)} persona_ids in the requested JSON.

=== OFFER ===
{concept_card}

=== INDEPENDENT PERSONAS ===
{profiles_block}""".strip()


def export_csv_pair(rows: list[dict[str, Any]], out_excel_pt: Path, out_sheets: Path) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    with out_excel_pt.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({k: (str(v).replace(".", ",") if isinstance(v, float) else v) for k, v in r.items()})
    with out_sheets.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=",")
        w.writeheader()
        w.writerows(rows)


def export_excel_heatmap(
    out_xlsx: Path,
    title: str,
    subtitle: str,
    segment_rows: list[dict[str, Any]],
    revenue_rows: list[dict[str, Any]],
    legend_lines: list[str],
    currency: str = "R$",
) -> None:
    """Exports a clean, plain-language Excel workbook with native Red-Yellow-Green Heatmaps."""
    import openpyxl
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Heatmap Segmentos"

    navy = PatternFill("solid", fgColor="1E293B")
    white_bold = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="0F172A")
    sub_font = Font(name="Calibri", size=10, italic=True, color="475569")
    bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
    body_font = Font(name="Calibri", size=10, color="1E293B")
    thin = Side(border_style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws["A1"] = title
    ws["A1"].font = title_font
    ws["A2"] = subtitle
    ws["A2"].font = sub_font

    cols = list(segment_rows[0].keys())
    for c_idx, col in enumerate(cols, 1):
        cell = ws.cell(row=4, column=c_idx, value=col)
        cell.fill = navy
        cell.font = white_bold
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws.row_dimensions[4].height = 40

    pct_cols = []
    for r_idx, row in enumerate(segment_rows, 5):
        is_total = str(row[cols[0]]).upper().startswith("GERAL") or str(row[cols[0]]).upper().startswith("OVERALL")
        for c_idx, col in enumerate(cols, 1):
            val = row[col]
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if (c_idx == 1 or is_total) else body_font
            cell.border = border
            if c_idx > 1:
                cell.alignment = Alignment(horizontal="center")
                if currency in col or "Valor" in col or "Ticket" in col:
                    cell.number_format = f'"{currency} "#,##0.00'
                else:
                    cell.number_format = '0.0"%"'
                    if r_idx == 5:
                        pct_cols.append(c_idx)

    last_r1 = 4 + len(segment_rows)
    if pct_cols:
        heat = ColorScaleRule(
            start_type="num", start_value=15, start_color="F8696B",
            mid_type="num", mid_value=45, mid_color="FFEB84",
            end_type="num", end_value=75, end_color="63BE7B",
        )
        ws.conditional_formatting.add(
            f"{get_column_letter(min(pct_cols))}5:{get_column_letter(max(pct_cols))}{last_r1}", heat
        )

    t2_start = last_r1 + 3
    if revenue_rows:
        ws.cell(row=t2_start, column=1, value="Comparativo de Faturamento Relativo (a cada 100 pessoas avaliadas)").font = title_font
        rcols = list(revenue_rows[0].keys())
        for c_idx, col in enumerate(rcols, 1):
            cell = ws.cell(row=t2_start + 1, column=c_idx, value=col)
            cell.fill = navy
            cell.font = white_bold
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        ws.row_dimensions[t2_start + 1].height = 34
        for idx, row in enumerate(revenue_rows):
            r_num = t2_start + 2 + idx
            for c_idx, col in enumerate(rcols, 1):
                cell = ws.cell(row=r_num, column=c_idx, value=row[col])
                cell.font = bold_font if c_idx == 1 else body_font
                cell.border = border
                if c_idx > 1:
                    cell.alignment = Alignment(horizontal="center")
                    if "%" in col:
                        cell.number_format = '0.0"%"'
                    elif currency in col or "Faturamento" in col or "Valor" in col:
                        cell.number_format = f'"{currency} "#,##0.00'
        last_col_letter = get_column_letter(len(rcols))
        ws.conditional_formatting.add(
            f"{last_col_letter}{t2_start+2}:{last_col_letter}{t2_start+1+len(revenue_rows)}",
            ColorScaleRule(start_type="min", start_color="F8696B", mid_type="percentile", mid_value=50, mid_color="FFEB84", end_type="max", end_color="63BE7B"),
        )
        leg_start = t2_start + 3 + len(revenue_rows)
    else:
        leg_start = last_r1 + 2

    for i, line in enumerate(legend_lines):
        c = ws.cell(row=leg_start + i, column=1, value=line)
        c.font = bold_font if i == 0 else sub_font

    ws.column_dimensions["A"].width = 44
    for c_idx in range(2, max(len(cols), len(revenue_rows[0]) if revenue_rows else 2) + 1):
        ws.column_dimensions[get_column_letter(c_idx)].width = 21

    wb.save(out_xlsx)


def export_interactive_html_heatmap(
    out_html: Path,
    title: str,
    subtitle: str,
    models_data: dict[str, list[dict[str, Any]]],
    revenue_rows: list[dict[str, Any]],
    kpis: list[dict[str, str]] | None = None,
    quotes_by_cell: dict[str, list[dict[str, Any]]] | None = None,
    order_bump_by_segment: list[dict[str, Any]] | None = None,
    methodology_note: str = "Semantic Similarity Rating (SSR) — arXiv:2510.08338 · Prompt neutro anti-viés · Saída sintética exploratória não calibrada.",
    out_data_json: Path | None = None,
    currency: str = "R$",
) -> None:
    """
    Generates a flagship, standalone, model-agnostic interactive HTML Dashboard:
      - Google Sans typography (400/500/600/700 — crisp Windows ClearType rendering)
      - Dark / Light mode toggle
      - Dynamic JSON loader (button + drag-and-drop) so ONE viewer opens any future round without regenerating HTML
      - Automatic 1-model or N-model switcher (works with Claude, GPT, Gemini, Ollama, etc.)
      - Interactive Red->Amber->Green Heatmap (click any cell to inspect verbatim persona quotes)
      - Scaled charts with explicit graduated axes:
          * Relative Revenue chart with [Zoom na diferença | Base 0] toggle + % delta vs lowest
          * Order Bump chart on a true 0–100% gridded scale with average reference line
    """
    full_payload = {
        "title": title,
        "subtitle": subtitle,
        "currency": currency,
        "methodologyNote": methodology_note,
        "modelsData": models_data,
        "revenueRows": revenue_rows,
        "kpis": kpis or [],
        "quotes": quotes_by_cell or {},
        "orderBump": order_bump_by_segment or [],
    }
    if out_data_json is not None:
        out_data_json.write_text(json.dumps(full_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    payload_json = json.dumps(full_payload, ensure_ascii=False).replace("</", "<\\/")

    doc = f"""<!doctype html>
<html lang="pt-BR" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root[data-theme="dark"] {{
  --bg: #0b1120; --surface: #111827; --surface2: #1a2336; --border: #263248;
  --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8; --accent2: #22c55e;
  --chip-bg: #1a2336; --chip-active: #38bdf8; --chip-active-text: #0b1120;
  --gridline: rgba(148, 163, 184, 0.16);
  --shadow: 0 10px 28px rgba(0,0,0,.32);
}}
:root[data-theme="light"] {{
  --bg: #f8fafc; --surface: #ffffff; --surface2: #f1f5f9; --border: #e2e8f0;
  --text: #0f172a; --muted: #475569; --accent: #0284c7; --accent2: #16a34a;
  --chip-bg: #e2e8f0; --chip-active: #0f172a; --chip-active-text: #ffffff;
  --gridline: rgba(15, 23, 42, 0.10);
  --shadow: 0 6px 20px rgba(15,23,42,.07);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 28px 20px 56px; background: var(--bg); color: var(--text);
  font-family: 'Google Sans', 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-weight: 400; font-size: 14px; line-height: 1.5;
  font-variant-numeric: tabular-nums;
  transition: background .2s, color .2s;
}}
body.drag-over::after {{
  content: 'Solte o arquivo .json da rodada SSR aqui para carregar';
  position: fixed; inset: 16px; z-index: 999; display: grid; place-items: center;
  background: rgba(11,17,32,.86); color: #38bdf8; font-size: 20px; font-weight: 600;
  border: 2px dashed #38bdf8; border-radius: 18px; backdrop-filter: blur(4px);
}}
.wrap {{ max-width: 1320px; margin: 0 auto; }}
.topbar {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; margin-bottom: 22px; }}
.actions {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
.badge {{
  display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
  color: var(--accent); background: rgba(56,189,248,.12); border: 1px solid rgba(56,189,248,.28);
  padding: 4px 10px; border-radius: 999px; margin-bottom: 8px;
}}
h1 {{ margin: 0 0 6px; font-size: 25px; font-weight: 700; letter-spacing: -.015em; }}
.sub {{ margin: 0; color: var(--muted); font-size: 14px; font-weight: 400; max-width: 820px; }}
.btn {{
  background: var(--surface); color: var(--text); border: 1px solid var(--border);
  border-radius: 10px; padding: 8px 13px; font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer;
}}
.btn:hover {{ border-color: var(--accent); }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-bottom: 22px; }}
.kpi {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 16px 18px; box-shadow: var(--shadow);
}}
.kpi-label {{ font-size: 11.5px; color: var(--muted); font-weight: 500; text-transform: uppercase; letter-spacing: .04em; }}
.kpi-value {{ font-size: 24px; font-weight: 700; margin: 6px 0 4px; letter-spacing: -.015em; }}
.kpi-sub {{ font-size: 12.5px; color: var(--muted); font-weight: 400; }}
.card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 20px 22px; margin-bottom: 22px; box-shadow: var(--shadow);
}}
.card-head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
.card h2 {{ margin: 0; font-size: 16.5px; font-weight: 600; letter-spacing: -.01em; }}
.hint {{ font-size: 12.5px; color: var(--muted); font-weight: 400; }}
.pills {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.pill {{
  border: 1px solid var(--border); background: var(--chip-bg); color: var(--text);
  padding: 5px 12px; border-radius: 999px; font-family: inherit; font-size: 12.5px; font-weight: 500; cursor: pointer;
}}
.pill.active {{ background: var(--chip-active); color: var(--chip-active-text); border-color: transparent; font-weight: 600; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: separate; border-spacing: 3px; font-size: 13px; min-width: 780px; }}
th {{
  background: var(--surface2); color: var(--text); padding: 10px 8px;
  border-radius: 8px; font-weight: 600; text-align: center; font-size: 12px;
}}
th:first-child {{ text-align: left; padding-left: 12px; min-width: 190px; }}
td {{ padding: 10px 8px; border-radius: 8px; text-align: center; }}
td.seg {{ text-align: left; padding-left: 12px; font-weight: 600; background: var(--surface2); color: var(--text); }}
tr.total-row td.seg {{ border-left: 3px solid var(--accent); }}
td.hm-cell {{
  color: #0b1120; font-weight: 600; font-size: 13px; cursor: pointer;
  transition: transform .12s ease, box-shadow .12s ease;
}}
td.hm-cell:hover {{ transform: scale(1.025); box-shadow: 0 0 0 2px var(--text); position: relative; z-index: 2; }}
td.hm-cell.selected {{ box-shadow: 0 0 0 2.5px var(--text); }}
td.num-cell {{ background: var(--surface2); font-weight: 600; color: var(--text); }}
.legend-bar {{
  display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--muted); margin-top: 12px; flex-wrap: wrap;
}}
.grad {{ width: 150px; height: 9px; border-radius: 999px; background: linear-gradient(90deg, #f87171, #fde047, #4ade80); }}
.quotes-drawer {{
  margin-top: 16px; padding: 16px 18px; background: var(--surface2); border: 1px solid var(--border);
  border-radius: 12px; display: none;
}}
.quotes-head {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }}
.quote-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 10px; }}
.quote-item {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; font-size: 13px; font-weight: 400;
}}
.quote-meta {{ display: flex; justify-content: space-between; gap: 8px; margin-bottom: 6px; font-size: 11.5px; color: var(--muted); font-weight: 500; }}
.tag {{ padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
.tag-hi {{ background: rgba(34,197,94,.16); color: #22c55e; }}
.tag-mid {{ background: rgba(250,204,21,.16); color: #eab308; }}
.tag-lo {{ background: rgba(248,113,113,.16); color: #f87171; }}
.charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 20px; }}
.chart-body {{ position: relative; }}
.bar-row {{ display: grid; grid-template-columns: minmax(175px, 235px) 1fr 125px; gap: 12px; align-items: center; margin: 11px 0; }}
.bar-label {{ font-size: 12.8px; font-weight: 500; }}
.bar-track {{
  position: relative; background: var(--surface2); height: 22px; border-radius: 7px;
  overflow: hidden; border: 1px solid var(--border);
  background-image: repeating-linear-gradient(90deg, transparent, transparent calc(25% - 1px), var(--gridline) calc(25% - 1px), var(--gridline) 25%);
}}
.bar-fill {{ height: 100%; border-radius: 6px; background: linear-gradient(90deg, #38bdf8, #0ea5e9); transition: width .35s ease; }}
.bar-fill.best {{ background: linear-gradient(90deg, #22c55e, #10b981); }}
.bar-fill.ob {{ background: linear-gradient(90deg, #8b5cf6, #38bdf8); }}
.avg-line {{ position: absolute; top: 0; bottom: 0; width: 0; border-left: 1.5px dashed rgba(248,250,252,.65); pointer-events: none; }}
:root[data-theme="light"] .avg-line {{ border-left-color: rgba(15,23,42,.55); }}
.bar-val {{ text-align: right; font-weight: 600; font-size: 13px; white-space: nowrap; }}
.delta {{ font-size: 11px; font-weight: 600; color: #22c55e; margin-left: 4px; }}
.axis-row {{ display: grid; grid-template-columns: minmax(175px, 235px) 1fr 125px; gap: 12px; margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--border); }}
.axis-ticks {{ display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); font-weight: 500; }}
.footer {{ margin-top: 22px; font-size: 12px; color: var(--muted); text-align: center; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <span class="badge">SSR Market Research · arXiv:2510.08338</span>
      <h1 id="pageTitle"></h1>
      <p class="sub" id="pageSub"></p>
    </div>
    <div class="actions">
      <input type="file" id="jsonFileInput" accept=".json" style="display:none">
      <button class="btn" id="loadBtn" title="Abra o arquivo JSON de qualquer outra rodada SSR">📂 Carregar JSON</button>
      <button class="btn" id="themeBtn">☀ Modo Claro</button>
    </div>
  </div>

  <div class="kpi-grid" id="kpiGrid"></div>

  <div class="card">
    <div class="card-head">
      <div>
        <h2>Heatmap de Interesse de Compra por Público</h2>
        <div class="hint">Clique em qualquer célula colorida para ler as respostas reais das personas daquele segmento.</div>
      </div>
      <div class="pills" id="modelPills"></div>
    </div>
    <div class="table-wrap"><table id="hmTable"></table></div>
    <div class="legend-bar">
      <span>Frio (15%)</span><div class="grad"></div><span>Quente (75%+)</span>
      <span>· Escala: Top-2-Box Sintético SSR (%)</span>
    </div>
    <div class="quotes-drawer" id="quotesDrawer">
      <div class="quotes-head">
        <strong id="quotesTitle"></strong>
        <div class="pills" id="quoteFilterPills">
          <button class="pill active" data-f="all">Todas</button>
          <button class="pill" data-f="buy">Mais inclinados</button>
          <button class="pill" data-f="no">Objeções / Recusa</button>
        </div>
      </div>
      <div class="quote-grid" id="quoteGrid"></div>
    </div>
  </div>

  <div class="charts-grid">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>Faturamento Relativo (a cada 100 pessoas)</h2>
          <div class="hint" id="revScaleHint"></div>
        </div>
        <div class="pills" id="revScalePills">
          <button class="pill active" data-s="zoom">Zoom na diferença</button>
          <button class="pill" data-s="zero">Base 0</button>
        </div>
      </div>
      <div id="revChart"></div>
    </div>
    <div class="card" id="obCard" style="display:none">
      <div class="card-head">
        <div>
          <h2>Adesão ao Extra no Checkout (entre compradores)</h2>
          <div class="hint">Escala fixa de 0% a 100% · linha tracejada = média geral</div>
        </div>
      </div>
      <div id="obChart"></div>
    </div>
  </div>

  <div class="footer" id="footerNote"></div>
</div>

<script>
let DATA = {payload_json};
let currentModel = Object.keys(DATA.modelsData)[0];
let selectedCellKey = null;
let quoteFilter = 'all';
let revScaleMode = 'zoom';

const themeBtn = document.getElementById('themeBtn');
themeBtn.addEventListener('click', () => {{
  const root = document.documentElement;
  const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
  root.dataset.theme = next;
  themeBtn.textContent = next === 'dark' ? '☀ Modo Claro' : '☾ Modo Escuro';
}});

function loadNewData(obj) {{
  if (!obj || !obj.modelsData) {{ alert('JSON inválido: falta o campo modelsData.'); return; }}
  DATA = obj;
  currentModel = Object.keys(DATA.modelsData)[0];
  selectedCellKey = null;
  quoteFilter = 'all';
  renderAll();
}}

const fileInput = document.getElementById('jsonFileInput');
document.getElementById('loadBtn').onclick = () => fileInput.click();
fileInput.onchange = (e) => {{
  const f = e.target.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {{ try {{ loadNewData(JSON.parse(reader.result)); }} catch (err) {{ alert('Erro ao ler JSON: ' + err); }} }};
  reader.readAsText(f, 'utf-8');
}};

window.addEventListener('dragover', (e) => {{ e.preventDefault(); document.body.classList.add('drag-over'); }});
window.addEventListener('dragleave', (e) => {{ if (e.relatedTarget === null) document.body.classList.remove('drag-over'); }});
window.addEventListener('drop', (e) => {{
  e.preventDefault(); document.body.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {{ try {{ loadNewData(JSON.parse(reader.result)); }} catch (err) {{ alert('Erro ao ler JSON: ' + err); }} }};
  reader.readAsText(f, 'utf-8');
}});

function pctToColor(v) {{
  const t = Math.max(0, Math.min(1, (v - 15) / 60));
  let r, g, b;
  if (t < 0.5) {{
    const u = t / 0.5;
    r = Math.round(248 + (253 - 248) * u);
    g = Math.round(113 + (224 - 113) * u);
    b = Math.round(113 + (71 - 113) * u);
  }} else {{
    const u = (t - 0.5) / 0.5;
    r = Math.round(253 + (74 - 253) * u);
    g = Math.round(224 + (222 - 224) * u);
    b = Math.round(71 + (128 - 71) * u);
  }}
  return `rgb(${{r}},${{g}},${{b}})`;
}}

function renderHeader() {{
  document.title = DATA.title || 'SSR Dashboard';
  document.getElementById('pageTitle').textContent = DATA.title || 'SSR Market Research';
  document.getElementById('pageSub').textContent = DATA.subtitle || '';
  document.getElementById('footerNote').textContent = DATA.methodologyNote || '';
}}

function renderKPIs() {{
  const g = document.getElementById('kpiGrid');
  g.innerHTML = (DATA.kpis || []).map(k => `
    <div class="kpi">
      <div class="kpi-label">${{k.label}}</div>
      <div class="kpi-value">${{k.value}}</div>
      <div class="kpi-sub">${{k.sub || ''}}</div>
    </div>
  `).join('');
}}

function renderModelPills() {{
  const box = document.getElementById('modelPills');
  const keys = Object.keys(DATA.modelsData);
  box.innerHTML = '';
  if (keys.length <= 1) {{
    if (keys.length === 1) {{
      const span = document.createElement('span');
      span.className = 'pill active';
      span.textContent = keys[0];
      box.appendChild(span);
    }}
    return;
  }}
  keys.forEach(m => {{
    const btn = document.createElement('button');
    btn.className = 'pill' + (m === currentModel ? ' active' : '');
    btn.textContent = m;
    btn.onclick = () => {{ currentModel = m; renderModelPills(); renderHeatmap(); if (selectedCellKey) renderQuotes(); }};
    box.appendChild(btn);
  }});
}}

function renderHeatmap() {{
  const rows = DATA.modelsData[currentModel] || [];
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const tbl = document.getElementById('hmTable');
  let h = '<thead><tr>' + cols.map(c => `<th>${{c}}</th>`).join('') + '</tr></thead><tbody>';
  rows.forEach(row => {{
    const seg = String(row[cols[0]]);
    const isTotal = seg.toUpperCase().startsWith('GERAL') || seg.toUpperCase().startsWith('OVERALL');
    h += `<tr class="${{isTotal ? 'total-row' : ''}}"><td class="seg">${{seg}}</td>`;
    cols.slice(1).forEach(c => {{
      const v = row[c];
      const isMoney = (c.includes('R$') || c.includes('($)')) && (c.includes('Valor') || c.includes('Ticket') || c.includes('médio') || c.includes('Value') || c.includes('Avg'));
      const cur = DATA.currency || 'R$';
      if (typeof v === 'number' && !isMoney) {{
        const key = `${{seg}}||${{c}}`;
        const sel = key === selectedCellKey ? ' selected' : '';
        h += `<td class="hm-cell${{sel}}" style="background:${{pctToColor(v)}}" data-key="${{key.replace(/"/g,'&quot;')}}">${{v.toFixed(1)}}%</td>`;
      }} else if (typeof v === 'number') {{
        const dec = cur === 'R$' ? v.toFixed(2).replace('.', ',') : v.toFixed(2);
        h += `<td class="num-cell">${{cur}} ${{dec}}</td>`;
      }} else {{
        h += `<td class="num-cell">${{v}}</td>`;
      }}
    }});
    h += '</tr>';
  }});
  h += '</tbody>';
  tbl.innerHTML = h;
  tbl.querySelectorAll('td.hm-cell').forEach(td => {{
    td.onclick = () => {{ selectedCellKey = td.dataset.key; renderHeatmap(); renderQuotes(); }};
  }});
}}

function renderQuotes() {{
  const drawer = document.getElementById('quotesDrawer');
  const titleEl = document.getElementById('quotesTitle');
  const grid = document.getElementById('quoteGrid');
  if (!selectedCellKey) {{ drawer.style.display = 'none'; return; }}
  let items = (DATA.quotes && DATA.quotes[selectedCellKey]) || [];
  const modelKeys = Object.keys(DATA.modelsData);
  if (modelKeys.length > 1 && currentModel !== modelKeys[0]) {{
    items = items.filter(x => x.model === currentModel);
  }}
  if (quoteFilter === 'buy') items = items.filter(x => x.t2b >= 50);
  if (quoteFilter === 'no') items = items.filter(x => x.t2b < 50);

  titleEl.textContent = `Falas reais · ${{selectedCellKey.replace('||', ' → ')}} (${{items.length}} exibidas)`;
  if (!items.length) {{
    grid.innerHTML = '<div class="hint">Nenhuma fala corresponde a esse filtro para a célula selecionada.</div>';
  }} else {{
    grid.innerHTML = items.slice(0, 12).map(q => {{
      const cls = q.t2b >= 60 ? 'tag-hi' : (q.t2b >= 35 ? 'tag-mid' : 'tag-lo');
      return `<div class="quote-item">
        <div class="quote-meta">
          <span>${{q.nome}} (${{q.idade}}a · ${{q.renda}}) · ${{q.model}}</span>
          <span class="tag ${{cls}}">SSR ${{q.t2b.toFixed(0)}}%</span>
        </div>
        <div>${{q.text}}</div>
      </div>`;
    }}).join('');
  }}
  drawer.style.display = 'block';
}}

document.querySelectorAll('#quoteFilterPills .pill').forEach(btn => {{
  btn.onclick = () => {{
    quoteFilter = btn.dataset.f;
    document.querySelectorAll('#quoteFilterPills .pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderQuotes();
  }};
}});

document.querySelectorAll('#revScalePills .pill').forEach(btn => {{
  btn.onclick = () => {{
    revScaleMode = btn.dataset.s;
    document.querySelectorAll('#revScalePills .pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderRevenueChart();
  }};
}});

function fmtMoney(v) {{
  const cur = DATA.currency || 'R$';
  const loc = cur === 'R$' ? 'pt-BR' : 'en-US';
  return cur + ' ' + Math.round(v).toLocaleString(loc);
}}

function renderRevenueChart() {{
  const rows = DATA.revenueRows || [];
  if (!rows.length) return;
  const vals = rows.map(r => r.value);
  const rawMin = Math.min(...vals);
  const rawMax = Math.max(...vals);
  let axisMin, axisMax;
  if (revScaleMode === 'zero') {{
    axisMin = 0;
    axisMax = Math.ceil((rawMax * 1.08) / 200) * 200;
    document.getElementById('revScaleHint').textContent = `Escala absoluta (${{fmtMoney(0)}} a ${{fmtMoney(axisMax)}}) · Δ calculado sobre a menor opção`;
  }} else {{
    const pad = Math.max((rawMax - rawMin) * 0.25, rawMax * 0.05);
    axisMin = Math.max(0, Math.floor((rawMin - pad) / 100) * 100);
    axisMax = Math.ceil((rawMax + pad * 0.5) / 100) * 100;
    document.getElementById('revScaleHint').textContent = `Eixo focado (${{fmtMoney(axisMin)}} a ${{fmtMoney(axisMax)}}) para enxergar o ganho real entre opções`;
  }}
  const span = Math.max(axisMax - axisMin, 1);

  const barsHtml = rows.map(r => {{
    const w = Math.max(2, Math.min(100, ((r.value - axisMin) / span) * 100));
    const isBest = r.value === rawMax;
    const delta = rawMin > 0 ? ((r.value / rawMin) - 1) * 100 : 0;
    const deltaTxt = delta > 0.4 ? `<span class="delta">+${{delta.toFixed(1)}}%</span>` : '';
    return `<div class="bar-row">
      <div class="bar-label">${{r.label}}${{isBest ? ' ★' : ''}}</div>
      <div class="bar-track"><div class="bar-fill${{isBest ? ' best' : ''}}" style="width:${{w.toFixed(1)}}%"></div></div>
      <div class="bar-val">${{fmtMoney(r.value)}}${{deltaTxt}}</div>
    </div>`;
  }}).join('');

  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => fmtMoney(axisMin + span * f));
  const axisHtml = `<div class="axis-row"><div></div><div class="axis-ticks">${{ticks.map(t => `<span>${{t}}</span>`).join('')}}</div><div></div></div>`;
  document.getElementById('revChart').innerHTML = barsHtml + axisHtml;
}}

function renderOrderBumpChart() {{
  const rows = DATA.orderBump || [];
  if (!rows.length) {{ document.getElementById('obCard').style.display = 'none'; return; }}
  document.getElementById('obCard').style.display = 'block';
  const avg = rows.reduce((a, b) => a + b.pct, 0) / rows.length;
  const barsHtml = rows.map(r => `
    <div class="bar-row">
      <div class="bar-label">${{r.label}}</div>
      <div class="bar-track">
        <div class="bar-fill ob" style="width:${{Math.min(100, r.pct).toFixed(1)}}%"></div>
        <div class="avg-line" style="left:${{avg.toFixed(1)}}%" title="Média: ${{avg.toFixed(1)}}%"></div>
      </div>
      <div class="bar-val">${{r.pct.toFixed(1)}}%</div>
    </div>
  `).join('');
  const axisHtml = `<div class="axis-row"><div></div><div class="axis-ticks"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div><div></div></div>`;
  document.getElementById('obChart').innerHTML = barsHtml + axisHtml;
}}

function renderAll() {{
  renderHeader();
  renderKPIs();
  renderModelPills();
  renderHeatmap();
  renderQuotes();
  renderRevenueChart();
  renderOrderBumpChart();
}}

renderAll();
</script>
</body></html>"""
    out_html.write_text(doc, encoding="utf-8")
