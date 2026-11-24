# SSR Paper Reference — Concise Summary (arXiv:2510.08338)

- **Title:** *LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings*
- **Authors:** Benjamin F. Maier, Ulf Aslak, Luca Fiaschi, Nina Rismal, Kemble Fletcher, Christian C. Luhmann, Robbie Dow, Kli Pappas, Thomas V. Wiecki (PyMC Labs & Colgate-Palmolive Company)
- **Original PDF:** https://arxiv.org/pdf/2510.08338
- **Abstract Page:** https://arxiv.org/abs/2510.08338
- **Official Open-Source Package:** https://github.com/pymc-labs/semantic-similarity-rating

---

## 1. Core Problem Solved
Prompting an LLM directly for a numeric Likert score (e.g., *"Rate purchase intent from 1 to 5"* — Direct Likert Rating / DLR) fails badly: distributions collapse into narrow, overly polite middle/high bands and miss real human variance.

## 2. The SSR Two-Step Method
1. **Free-Text Elicitation:** Prompt the LLM as a demographically grounded persona (especially **age** and **income**, which drove the strongest alignment in the study) to react naturally in free text to a realistic product Concept Card — **never asking for a numeric score**.
2. **Semantic Projection to Likert PMF:** Embed both the persona's free-text reaction and 5 reference anchor statements (representing Likert levels `1` through `5`). Compute cosine similarities $s_1, \dots, s_5$, shift by the minimum, apply temperature scaling $T$, and normalize into a probability mass function (PMF):

$$d_i = \max(0, s_i - \min_j s_j) + \epsilon, \qquad w_i = d_i^{1/T}, \qquad p_i = \frac{w_i}{\sum_{k=1}^{5} w_k}$$

3. **Multi-Anchor Averaging:** Repeat across **6 differently phrased reference anchor sets** and average the resulting PMFs to eliminate phrasing artifacts.

## 3. Empirical Benchmarks (Personal Care / Colgate Dataset)
- Evaluated across **57 real consumer concept surveys** (**9,300 human responses**).
- Achieved **~90% of human test-retest reliability** and **Kolmogorov-Smirnov (KS) distributional similarity > 0.85**, while retaining rich qualitative explanations of *why* consumers buy or reject.

## 4. Field-Tested Practical Enhancements (Applied in This Skill)
- **Decision-Sentence Scoring (`F1, T=0.5`):** When personas write 4–6 sentences containing both praise and objections in one paragraph, embedding the whole paragraph compresses scores toward `3.0`. Requiring sentence 1 (`F1`) to state the purchase decision clearly and applying SSR to `F1` (`T=0.5`) yields sharp separation and strong cross-model agreement while preserving full qualitative reasoning in sentences 2–5.
- **Anti-Prompt-Poisoning:** Never mention specific missing features or target objections in system instructions, and never advertise absent features on control cards.
- **Multi-Model Cross-Validation:** Running two independent model families (e.g., Gemini + GPT) through the **same** embedding model (`bge-m3` / `text-embedding-3-small`) reveals high-confidence consensus patterns vs. model-specific quirks.

## 5. Known Limitations & Guardrails
- Original validation was on US personal-care CPG concepts, not digital courses/SaaS/services in Brazil — always treat outputs as **exploratory uncalibrated signals**.
- "90% of human test-retest reliability" does **not** mean "predicts 90% of real sales."
- Use SSR in a **funnel**: screen 10–20 offer/price/copy variants synthetically first, then validate the top 1–2 finalists with real human buyers (waitlist, pre-sale, or real checkout A/B test).
