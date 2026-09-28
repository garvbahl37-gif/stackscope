# The Developer Technology Market, 2017–2025

**Adoption, retention, pay and the generative-AI trust gap**

StackScope research note, 29 September 2026. Evidence base: 664,042 responses to nine annual Stack Overflow
Developer Surveys, 226 countries and territories, 309 harmonised technologies.

## Summary

Like for like, developer usage has spread out across languages, web frameworks and databases since 2018, while concentration rose among cloud platforms. Rust is the fastest-rising established language, and PostgreSQL overtook MySQL in 2023 and keeps widening the gap. Generative AI moved from
experiment to default in two years, yet trust in its output fell in every experience group and is lowest among developers
with 21+ years of experience (27% trust it). The largest adjusted pay premiums are split between languages and platforms (5 of the top 10 are platforms).

## Key findings

- **GenAI adoption reached 80% while trust turned negative.** Developers using AI tools rose from 46% (2023) to 80% (2025) after weighting to a constant respondent mix (44% and 78% unweighted), yet the share who distrust AI output grew from 26% to 44%; net trust fell from +0.16 to -0.24 on a -2..+2 scale.
- **Rust is the fastest-rising established language.** Rust adoption grew from 1.1% (2017) to 15.2% (2025): the odds of a developer using it rose 34% a year (95% CI 26%-42%), and 80% of current users want to keep it.
- **PostgreSQL overtook MySQL in 2023 and keeps widening the gap.** In 2017 MySQL led 55% to 27%; by 2025 PostgreSQL is used by 57% of developers vs 43% for MySQL, and it is the top churn destination for MySQL users.
- **AWS carries the largest pay premium among widely used skills (+6.8%).** Among skills used by at least 5% of developers, and controlling for country, experience, role, company size, education, industry and year, AWS users earn +6.8% (95% CI +5.7% to +7.9%) vs a raw gap of +27%. Niche skills can carry more: Snowflake users earn +9.1%. In India the largest such premium is Go (+14%).
- **52% of Java users don't want to keep using it next year — Rust is their top pick.** Of Java developers who did not pick Java for next year, 26% want to adopt Rust (a language they do not use yet). The largest flows elsewhere run MySQL to PostgreSQL and jQuery to Vue.js.
- **AWS, Azure and Google Cloud consolidated the established cloud market.** Among the 6 platforms listed in both 2018 and 2025, the big three went from 65% to 81% of mentions as Heroku fell from 14% to 5%. Platforms first listed after 2018, led by Cloudflare (12%) and Vercel (7%), now draw 31% of all cloud mentions.
- **Fully-remote work peaked at 45% in 2022 and is receding.** Among professional developers, fully-remote work went from 12% (2017) to a peak of 45% (2022), and has fallen to 33% in 2025 as hybrid grows.
- **Real developer pay rose 27% since 2017 once the country mix is held fixed.** The raw median suggests only +15% (in constant 2025 dollars) because the respondent mix shifted between countries; a fixed-country-mix index shows +27%.
- **Cloud-Native & DevOps is the best-paid developer persona.** Stack-based clustering finds 8 personas; Modern Web Builders is the largest (18%), while Cloud-Native & DevOps earn a median $104,413 vs $60,328 for Classic Web & PHP.
- **Experience, not age, drives AI scepticism.** Holding age, role, region and company size constant, developers with 21+ years of coding have 0.59x the odds of trusting AI output (95% CI 0.54-0.66) vs those with 6-10 years; juniors (0-2 years) have 1.88x.
- **Adoption shares move like a random walk year to year.** Across 5 backtested models (rolling origins 2020-2024) none beat the 'naive' forecast (mean absolute error 1.9 pp one year ahead); forecasts therefore show calibrated uncertainty bands rather than extrapolated trends.

## Recommendations

**Engineering and technology leaders**

- Default new services to technologies in the *Leaders* position of their category (Rust, Go, Python, TypeScript), and treat the *Challengers*
  with the weakest momentum (PHP, R, Java, Dart) as candidates for managed decline rather than new investment.
- Plan migrations along the paths developers already want to take: the largest one-directional flows in 2025 were
  JavaScript to Rust (net 2,076 respondents); HTML/CSS to Rust (net 1,831 respondents); JavaScript to Go (net 1,726 respondents).
- Budget AI-assisted development for verification, not just generation: 80% of developers use AI tools but
  only 35% trust the output's accuracy.

**HR and talent leaders**

- Benchmark pay on purchasing power as well as dollars: the median Indian developer earns $19.8k, but
  $85.7k in PPP terms against $98.3k for Western Europe ($78.9k in dollars).
- Prioritise skills with a significant premium after controls. Widely used (by 5% or more of developers):
  AWS (+6.8%), TypeScript (+5.5%), Redis (+5.3%). Niche but valuable: Snowflake (+9.1%, used by 3.1%), Swift (+8.1%, used by 4.8%), BigQuery (+7.6%, used by 5.0%).
- Expect hybrid, not remote-first, work: fully remote work peaked at 45% in 2022
  and fell to 33% in 2025.

**Technology vendors and product teams**

- Win on retention, not reach: the widely used languages with the highest retention (Rust, TypeScript, Go) are also in statistically significant multi-year growth.
- Close the AI trust gap for senior engineers; developers with 21+ years of experience have
  0.59× the odds of trusting AI output compared with those with 6–10 years.

## Analysis

### Market positions, 2025

| Category | Leaders (highest momentum first) | Challengers |
|---|---|---|
| AI Assistants & Models | Claude, Google Gemini, DeepSeek, Claude Code | Mistral, Grok |
| Cloud Platforms | Cloudflare, AWS, Google Cloud, Microsoft Azure | Vercel |
| Databases | PostgreSQL, Redis, SQLite, Supabase | Firebase Realtime DB, Oracle, Cloud Firestore, H2 |
| DevOps & Infrastructure | Docker, Kubernetes, Terraform | Ansible, Prometheus |
| Languages | Rust, Go, Python, TypeScript | PHP, R, Java, Dart |
| Web Frameworks & Runtimes | React, FastAPI, Node.js, Vue.js | jQuery, WordPress, Flask, Laravel |

Adoption is the composition-weighted share of developers using each technology; momentum averages within-category z-scores
of retention, attraction and wave-on-wave change.

### Fastest risers and decliners (all waves, false-discovery controlled)

| Technology | Category | First → latest | Annual change in odds of use |
|---|---|---|---|
| Visual Studio Code | IDEs & Editors | 20% → 78% | +37.5% |
| Rust | Languages | 1% → 15% | +33.8% |
| PyTorch | Libraries & Frameworks | 2% → 13% | +32.7% |
| TypeScript | Languages | 10% → 44% | +22.4% |
| React | Web Frameworks & Runtimes | 20% → 48% | +15.3% |
| PostgreSQL | Databases | 27% → 57% | +14.4% |
| jQuery | Web Frameworks & Runtimes | 48% → 23% | -20.7% |
| Chef | DevOps & Infrastructure | 2% → 1% | -20.1% |
| Objective-C | Languages | 7% → 2% | -19.8% |
| Couchbase | Databases | 2% → 1% | -19.0% |
| Cordova | Libraries & Frameworks | 11% → 3% | -17.9% |

### What skills are worth (global model, 2023–2025)

| Technology | Used by | Adjusted premium | 95% interval | Raw gap |
|---|---|---|---|---|
| Snowflake | 3% | +9.1% | +6.7% to +11.5% | +69.8% |
| Swift | 5% | +8.1% | +6.0% to +10.3% | +15.5% |
| BigQuery | 5% | +7.6% | +5.4% to +9.9% | +22.2% |
| AWS | 45% | +6.8% | +5.7% to +7.9% | +26.7% |
| Elixir | 3% | +5.7% | +1.5% to +10.0% | +33.2% |
| TypeScript | 46% | +5.5% | +4.5% to +6.6% | +3.7% |
| Cosmos DB | 4% | +5.5% | +3.4% to +7.6% | +16.1% |
| Redis | 23% | +5.3% | +4.2% to +6.5% | +9.0% |
| Go | 16% | +5.0% | +3.7% to +6.3% | +23.5% |
| Scala | 3% | +4.9% | +2.5% to +7.3% | +29.4% |

Premiums come from an OLS model of log real pay with country, experience, role, company size, education, industry, work
arrangement and year controls (71,318 developers, R² 0.68), HC1 robust errors
and Benjamini–Hochberg correction. They are associations, not causal effects.

### Generative AI

| Wave | Use AI tools | Favourable | Trust accuracy | Distrust accuracy |
|---|---|---|---|---|
| 2023 | 46% | 77% | 44% | 26% |
| 2024 | 63% | 73% | 44% | 29% |
| 2025 | 80% | 61% | 35% | 44% |

## Methodology

- **Harmonisation.** Nine files with 924 raw columns were mapped to one schema; 448 distinct raw
  answer labels were mapped to 309 canonical technologies (100% of in-scope mentions).
- **Weighting.** Each wave is raked (iterative proportional fitting) to the average respondent mix by region, respondent type and
  experience, so trends are not artefacts of who answered. Design effects stay between 1.02 and
  1.22. Weighted shares therefore differ by a few points from Stack Overflow's published figures,
  which are unweighted; computed unweighted, the pipeline reproduces them (see the data-quality reconciliation).
- **Uncertainty.** Shares carry Wilson 95% intervals using Kish effective sample sizes; multi-year trends use inverse-variance
  weighted logistic regression; every family of tests is Benjamini–Hochberg controlled.
- **Pay.** Salaries are screened per country-year with a MAD-based modified z-score, deflated with US CPI-U to 2025 dollars and
  converted at World Bank PPP price levels.
- **Forecasts.** 5 models were backtested from rolling origins; none beat the naive forecast
  (one-year error 1.9 pp), so projections are presented as calibrated ranges.
- **Quality.** 29 of 29 automated checks pass; blocking checks stop the build.

## Limitations

- Stack Overflow respondents are not a random sample of all developers; weighting corrects composition drift between waves,
  not self-selection into the survey.
- Question wording, option lists and routing changed across waves. Known breaks (for example, respondents selecting
  14% more languages in 2025, and AI questions moving from tools to model families) are flagged wherever
  they affect a comparison. Concentration trends are measured like for like, so new answer options do not move them.
- Mindshare is not market share: adoption measures developer usage, not revenue or installed base.

*Independent analysis; not affiliated with Gartner or Stack Overflow. Data: Stack Overflow Developer Survey (ODbL),
World Bank World Development Indicators, FRED.*