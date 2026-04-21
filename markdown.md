Part 1 — Risk analysis credibility (the stuff that makes analysts trust it)
Ranked by impact on "this feels real":

1. Show peer benchmarks, always. Every ratio in the report should render as "3.2x vs. sector median 1.1x (85th percentile)". You already have 100 companies across 21 sectors in decisioning_output_latest.csv — compute sector medians/percentiles at startup, display next to every ratio. Without this, the numbers look like floating trivia.

2. Add the canonical scores as a reference panel — even if not in the model. Your feature_spec.yaml already defines Altman Z and Beneish M. Compute and display them on every report, labeled "Reference scores (not in model)". Every credit committee expects these. Free credibility.

3. Map the 0–100 score to a rating band. "Score 71 → equivalent to B-/BB zone based on the training cohort's default rate in this range." Makes it commercially legible. Panel sees "71" and shrugs; panel sees "B- equivalent, implied 1Y PD 14%" and leans in.

4. 3-year trajectory panel. You have 3Y data in the cohort. Every key ratio should show a sparkline with direction arrow (↗ leverage rising, ↘ margin falling). Credit analysts read trajectory before levels.

5. Make the engine vs audit disagreement loud. When models disagree, put it at the top of the report in amber, not buried in the decision bucket. "Primary engine: elevated risk. Audit model: moderate risk. Manual review recommended." That two-model cross-check is your best architectural story — surface it.

6. Backtesting slide in the presentation (not the app). One chart: "Had we scored these 50 defaulters one year before their default event, we caught X of 50." You have this data. This is the single most convincing artifact you can show.

7. Source-grounded citations in the memo. Every claim in the analyst memo should be clickable → opens the PDF page/snippet. The infrastructure is there (SourceRef in report_contract.py). Even doing this for 3–4 sections is enough.

8. Confidence badges on extracted fields. Field value with a small "confidence: 0.94" chip. Low-confidence fields render amber with "verify against source". Signals that you respect the extraction can be wrong.

9. Validation panel as a first-class section, not a footer. "2 fields required manual reconciliation, 1 unit mismatch resolved, scale detected: Rs. crore from page 87." This is what a real data-quality review looks like.

10. Model card page at /fulcrum/methodology — training data, cohort definition, metrics, known limitations, feature definitions, version pin. Panels love a methodology link.

Part 2 — Frontend polish (what makes it look production)
The visual language should steal from Stripe / Linear / Moody's, not "student dashboard."

1. Score visualization. Replace any "71/100" text with a real gauge: semicircle arc, color bands (green < 40, amber 40–70, red > 70), animated fill on load. Single biggest visual upgrade.

2. Ratio cards with: value, benchmark line, YoY delta chip, 3Y sparkline, sector-percentile bar. Four data points per card, not just the number.

3. Sector heatmap on /fulcrum — grid of sectors colored by urgent-review rate. Currently it's probably a list.

4. Typography hierarchy. Use one variable font (Inter or similar), tabular numerals for all numbers (font-variant-numeric: tabular-nums), generous line-height in memo, tight leading in tables. This alone elevates the feel.

5. Consistent risk semantics. Pick 4 colors (green/amber/red/neutral) and use them everywhere — bucket chips, ratio deltas, confidence badges, model-alignment pills. One tokenized palette.

6. Streaming UX. The 10-step processing page should feel calm, not chaotic. Each step: icon → label → small subtext → checkmark. Linear-style. Current version might already do this — pressure-test it.

7. Empty/error/loading states. What does /fulcrum/report/new look like on first visit? What if Gemini fails at step 4? Pre-build these states — panels will try to break it.

8. "Analyst workspace" framing. Add a collapsible left rail: recent reports, saved filters, cohort search. Even if half is placeholder, it signals this isn't a toy.

9. Export. "Download analyst memo (PDF)" + "Export ratios (CSV)" on the report. Real tools export.

10. Demo dataset density. Upload 4–5 reports before the demo so the history sidebar and /fulcrum dashboard look populated. Sparse dashboards scream prototype.

Part 3 — The "market-testable" narrative moves
These cost no code but change how it's received:

Open the demo with the problem, not the tech. "Indian banks lost ₹10 lakh crore to wilful defaults over the past decade. Every one of these companies filed audited annual reports showing the risk. No one read them fast enough."
Compliance framing. Mention Basel III credit-risk categorization and RBI master directions on wilful defaulters once. Signals you know the regulatory environment.
Honest limitations slide. "300-row cohort, India-listed only, standalone financials preferred, not a replacement for human credit analysis." Named limitations = trust.
V2 roadmap with dates (even aspirational): Q3 — expand cohort to 1000, Q4 — MCA integration, Q1 — multi-year report ingestion.
If you can only do 3 things right now
Peer benchmarks on every ratio (biggest analyst credibility win)
Score gauge + consistent color system (biggest visual win)
Pre-populate the app with 5 completed reports before demo (biggest "feels real" win)
Want me to build any of these? The benchmark display + gauge are both 30-60 min each.

