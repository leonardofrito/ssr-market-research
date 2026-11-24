# SSR Paper Summary — arXiv:2510.08338

- **Paper:** *LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings* — Maier et al. (PyMC Labs & Colgate-Palmolive, 2025)
- **PDF:** https://arxiv.org/pdf/2510.08338
- **Code:** https://github.com/pymc-labs/semantic-similarity-rating

## Method

Direct numeric Likert prompting (`1`–`5`) collapses variance and skews positive. SSR fixes this:

1. Elicit a natural free-text reaction from a demographically grounded persona (age and income matter most) without asking for numbers.
2. Embed the response and 5 Likert anchor statements (`1`–`5`), compute cosine similarities $s_1 \dots s_5$, and map to a probability mass function (PMF):

$$d_i = \max(0, s_i - \min_j s_j) + \epsilon, \qquad w_i = d_i^{1/T}, \qquad p_i = \frac{w_i}{\sum_{k=1}^{5} w_k}$$

3. Average PMFs across **6 differently worded anchor sets** to remove phrasing noise.

## Reported Benchmark
- Tested against **57 consumer concept surveys** (**9,300 human responses**, US personal care).
- Achieved **~90% of human test-retest reliability** and **KS distribution similarity > 0.85**.

## Practical Notes & Limits
- **Decision sentence (`F1, T=0.5`):** Scoring the opening decision sentence prevents center-compression when a paragraph mixes praise and objections.
- **Scope:** Validated on US personal-care CPG, not arbitrary digital products. Treat outputs as **uncalibrated exploratory signals** for relative ranking and objection discovery, followed by real buyer tests.
- "90% of human test-retest reliability" is **not** a 90% sales-conversion guarantee.
