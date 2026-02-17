# Fulcrum: Wilful Defaulter Pattern Detection System

## Project Overview

**Fulcrum** is an AI-powered audit and analysis system designed to identify patterns in wilful defaulter cases in the Indian banking sector. The system analyzes historical financial data to understand what red flags were present before companies became wilful defaulters, creating an early warning framework that could have prevented these failures.

### Core Value Proposition

Instead of predicting future defaults (which requires real-time data), Fulcrum performs **forensic analysis** on known wilful defaulter cases to answer:
- "What financial patterns existed 2-3 years before default?"
- "Could these defaults have been prevented with better due diligence?"
- "Which banks consistently lend to companies showing clear red flags?"
- "Are there repeat offender promoters/directors across multiple defaults?"

### Why This Matters

- **Scale of Problem**: As of 2024, Indian banks have ~₹1.3 lakh crore stuck with wilful defaulters
- **Institutional Failure**: 70%+ of wilful defaulter exposure is with Public Sector Banks
- **Preventable Losses**: Many defaulters showed clear financial distress signals years before classification
- **Regulatory Pressure**: RBI is pushing banks to improve credit risk assessment frameworks

---

## Project Scope

### Initial Scope (First Milestone): 100 Companies

**Focus first on 50 + 50** to validate the pipeline and models before scaling.

| Cohort | Initial target | Full target (later) |
|--------|----------------|---------------------|
| **Wilful Defaulters** | **50** | 150 |
| **Non-Defaulters (control)** | **50** | 150 |
| **Total** | **100** | 300 |

- **Defaulters (50):** From RBI list; prefer companies with CIN and MCA filing history; mix of sectors and sizes.
- **Non-defaulters (50):** From CIBIL or MCA+exclusion; matched by sector/size where possible; exclude anyone on RBI wilful defaulter list.

### Full Target (After Initial Milestone): 300 Companies

**Wilful Defaulters: 150 companies**
- Top 100 by loan amount (high-impact cases)
- 50 diversified across sectors
- Focus on companies with complete MCA filing history

**Non-Defaulters (Control Group): 150 companies**
- Matched case-control design
- Same sector, similar size, similar loan vintage
- Companies that got loans but never defaulted
- Must have 5+ years of continuous operation

### Timeframe of Analysis

- **Data Collection Period**: 2015-2023 (covers multiple economic cycles)
- **Prediction Horizon**: 3 years before wilful defaulter classification
- **Outcome Tracking**: 2-5 years post-loan origination

### How We Get Wilful Defaulters vs Non-Defaulters

| Cohort | Initial (50) | Source | How we get the list |
|--------|--------------|--------|----------------------|
| **Wilful Defaulters** | 50 | **RBI** | RBI **List of Wilful Defaulters** (quarterly PDFs). Scrape/parse with `scripts/rbi_ingest.py`, dedupe by company, then **select 50** with resolvable CIN and MCA filing history (mix of sectors/sizes). Scale to 150 later (top 100 by amount + 50 diversified). |
| **Non-Defaulters (control)** | 50 | **CIBIL or MCA + exclusion** | There is no single public “list of non-defaulters.” We build the control group in one of two ways: **(1) CIBIL:** Use a TransUnion CIBIL (or similar) export of companies that have taken credit and are **not** on the RBI wilful defaulter list—e.g. “performing” or “standard” accounts. **Select 50** matched by sector/size to the defaulter cohort. **(2) MCA + exclusion:** Start from a list of companies that have borrowed (e.g. companies with **charges** on MCA, or a bank’s disclosed large borrowers list). Remove any company that appears on the RBI wilful defaulter list. From the remainder, **select 50** matched by sector/size. Scale to 150 later. |

**Practical flow (current focus):**

1. **Wilful defaulters (50):** RBI PDFs → `rbi_ingest.py` (manifest → download → parse) → CSV → select 50 with CIN → resolve CIN where missing → fetch MCA reports for each.
2. **Non-defaulters (50):** CIBIL export (or MCA-sourced list) → exclude RBI list (fuzzy match) → select 50 matched to defaulter sector/size → fetch MCA reports for each.
3. CIBIL→CIN→MCA pipeline (`scripts/cibil_mca_pipeline.py`) is used for **both** cohorts once we have company name + CIN.

---

## Data Sources (All Free/Public)

### Primary Data Sources

#### 1. Reserve Bank of India (RBI)
**Source**: https://www.rbi.org.in
- **List of Wilful Defaulters** (updated quarterly)
  - Company name, CIN, loan amount, bank name, date of classification
  - Available as PDF downloads
- **Financial Stability Reports**
  - Sector-wise NPA trends
  - Bank-wise exposure data
- **Database on Indian Economy (DBIE)**
  - Credit growth statistics
  - Sectoral lending patterns

**Access Method**: Direct PDF download, no authentication required

#### 2. Ministry of Corporate Affairs (MCA)
**Source**: https://www.mca.gov.in
- **MCA21 Portal**: Public company filings
  - Form AOC-4 (Annual Returns with Financial Statements)
  - Form DIR-12 (Director appointments/resignations)
  - Form CHG-1, CHG-4 (Charges/mortgages)
  
**Critical Data Elements**:
- Complete Balance Sheet (3 years)
- Profit & Loss Statement (3 years)
- Cash Flow Statement (3 years)
- Notes to Accounts (related party transactions, contingent liabilities)
- Auditor's Report (qualifications, concerns)
- Director information (names, DIN, tenure)

**Access Method**: 
- Free search by company name/CIN
- Document downloads require CAPTCHA solving (can be automated with OCR)
- **Rate Limits**: ~100-150 requests per hour per IP (implement delays)

#### 3. SEBI (For Listed Companies)
**Source**: https://www.bse.com, https://www.nseindia.com
- Quarterly financial results
- Annual reports
- Corporate announcements
- Related party transaction disclosures

**Access Method**: Free public access, API available for NSE/BSE

#### 4. News Archives
**Sources**: 
- Economic Times (archives)
- Business Standard
- Moneycontrol
- Google News

**Use Case**: Context on company distress, management changes, sector challenges

---

## Technical Architecture

### Phase 1: Data Collection Infrastructure

**Components**:
1. **RBI Scraper**
   - Parse quarterly PDF lists
   - Extract company names, CIN, amounts, banks
   - Handle format variations across quarters
   - Output: Structured CSV of wilful defaulters

2. **MCA Portal Automation**
   - Web automation (Selenium/Playwright)
   - Company search by CIN
   - Navigate to document repository
   - Download Form AOC-4 for 3 consecutive years
   - CAPTCHA handling (OCR-based or manual intervention)
   - Checkpoint system (resume after interruptions)

3. **PDF Parser**
   - Extract tables from Form AOC-4 PDFs
   - Handle varying formats (different filing years, different chartered accountants)
   - Structured data extraction (JSON format)
   - Validation checks (balance sheet must balance, P&L checks)

4. **Data Storage**
   - SQLite database (lightweight, no server needed)
   - Tables: companies, financials, directors, audit_flags, charges
   - Version control for data pipeline

**Timeline**: 7-10 days
- Scraper development: 2-3 days
- Data collection: 4-5 days (300 companies × 3 years = 900 documents)
- Cleaning and validation: 2-3 days

### Phase 2: Entity Resolution

**Challenge**: Matching company names across data sources

**Examples of Mismatches**:
- RBI: "Kingfisher Airlines Ltd"
- MCA: "Kingfisher Airlines Limited"
- News: "Kingfisher"

**Solution Approach**:
1. **Preprocessing**:
   - Lowercase conversion
   - Remove common suffixes (Ltd, Limited, Pvt, Private, Pvt. Ltd.)
   - Strip extra whitespace, punctuation
   - Standardize abbreviations

2. **Fuzzy Matching**:
   - Use RapidFuzz/FuzzyWuzzy library
   - Calculate similarity scores (Levenshtein distance)
   - Threshold: >90% = auto-match

3. **AI-Assisted Verification** (For 85-90% similarity):
   - Send ambiguous cases to Claude API
   - Provide context: sector, state, directors
   - Binary decision: same company or not
   - Cost: ~$10-15 for entire dataset

4. **Manual Review Queue**:
   - Cases below 85% similarity
   - Build simple UI for quick human verification
   - Budget: 2-3 hours of manual work

**Expected Accuracy**: 95%+ match rate

### Phase 3: Feature Engineering

**Goal**: Transform raw financial data into meaningful predictive features

#### 3.1 Financial Health Indicators (40 features)

**Liquidity Ratios**:
- Current Ratio = Current Assets / Current Liabilities
- Quick Ratio = (Current Assets - Inventory) / Current Liabilities
- Cash Ratio = Cash / Current Liabilities

**Leverage Ratios**:
- Debt-to-Equity = Total Debt / Shareholders' Equity
- Interest Coverage = EBIT / Interest Expense
- Debt Service Coverage = Operating Cash Flow / Total Debt Service

**Profitability Ratios**:
- Net Profit Margin = Net Profit / Revenue
- ROA = Net Income / Total Assets
- ROE = Net Income / Shareholder Equity

**Efficiency Ratios**:
- Asset Turnover = Revenue / Total Assets
- Receivables Turnover = Revenue / Accounts Receivable

**Cash Flow Metrics**:
- Operating Cash Flow (absolute and as % of revenue)
- Free Cash Flow = Operating CF - CapEx
- Cash Flow to Debt = Operating CF / Total Debt

#### 3.2 Temporal Features (30 features)

For each base ratio, calculate:
- **Year-over-Year Change**: (T-1 to T-2), (T-2 to T-3)
- **3-Year Trend**: Linear regression slope
- **Volatility**: Standard deviation across 3 years

**Key Patterns to Detect**:
- Declining margins + increasing debt (danger signal)
- Revenue growth + negative cash flow (unsustainable expansion)
- Stable revenue + spiking related party transactions (fund diversion)

#### 3.3 Corporate Governance Flags (15 features)

**Structural Indicators**:
- Company age (years since incorporation)
- Number of directors
- Director turnover rate (resignations in last 2 years)
- Independent director ratio
- Promoter shareholding change (declining = warning)

**Audit Red Flags**:
- Auditor qualification present (binary)
- Auditor changed recently (binary)
- Delays in filing statements (count)
- Going concern warning mentioned (binary)

**Related Party Concerns**:
- Number of related party transactions
- Related party transaction value / Revenue ratio
- Loans to related parties / Total assets ratio

**Legal/Compliance**:
- Number of secured charges registered
- Contingent liabilities / Net worth ratio
- Pending legal cases (count)

#### 3.4 Composite Scores

- **Altman Z-Score**: Classic bankruptcy prediction model
- **Beneish M-Score**: Earnings manipulation detector
- **Industry-Relative Ratios**: Compare to sector median

**Total Feature Count**: ~85 raw features

### Phase 4: Model Development

#### 4.1 Data Preparation

**Dataset Structure**:
- **Total Samples**: 300 companies
- **Features**: 85 engineered features
- **Target Variable**: Wilful Defaulter (1) or Non-Defaulter (0)

**Train-Validation-Test Split**:
- Training: 210 companies (70%)
- Validation: 45 companies (15%)
- Test: 45 companies (15%)
- **Stratified Split**: Maintain 50-50 class balance in each set

**Handling Missing Data**:
- Forward fill for time-series (use previous year value)
- Industry median for cross-sectional gaps
- Create "data_missing" indicator features

#### 4.2 Model Selection

**Three Models in Parallel**:

1. **Logistic Regression** (Baseline)
   - **Pros**: Interpretable coefficients, fast training, handles small data well
   - **Cons**: Assumes linear relationships
   - **Use Case**: Establish baseline, understand feature relationships

2. **Random Forest** (Primary Model)
   - **Pros**: Handles non-linearity, feature importance, robust to outliers
   - **Cons**: Less interpretable than logistic regression
   - **Configuration**: 200 trees, max depth 15, class weight balanced
   - **Use Case**: Main predictive model

3. **Gradient Boosting** (XGBoost/LightGBM)
   - **Pros**: Typically highest accuracy
   - **Cons**: More prone to overfitting on small data
   - **Use Case**: Performance ceiling check

#### 4.3 Model Training Strategy

**Cross-Validation**:
- 5-fold stratified cross-validation
- Ensures every sample used for training and validation
- Reduces variance in performance estimates

**Hyperparameter Tuning**:
- Grid search on validation set
- Focus on: tree depth, learning rate, regularization strength
- Balance: model complexity vs. overfitting risk

**Feature Selection**:
- Rank features by importance (Random Forest built-in)
- Remove highly correlated features (correlation > 0.9)
- Keep top 30-40 features for final model
- Improves sample-to-feature ratio (10:1 rule)

#### 4.4 Evaluation Metrics

**Primary Metrics**:

1. **Precision** = True Positives / (True Positives + False Positives)
   - "Of companies flagged as risky, what % actually defaulted?"
   - **Target**: >75%
   - **Interpretation**: Minimize false alarms to banks

2. **Recall** = True Positives / (True Positives + False Negatives)
   - "Of actual defaulters, what % did we catch?"
   - **Target**: >85%
   - **Interpretation**: Missing a defaulter is very costly

3. **F1-Score** = 2 × (Precision × Recall) / (Precision + Recall)
   - Harmonic mean balances precision and recall
   - **Target**: >0.80

4. **AUC-ROC** = Area Under Receiver Operating Characteristic Curve
   - Measures discrimination ability across all thresholds
   - **Target**: >0.85

**Cost-Weighted Evaluation**:
- False Negative (miss defaulter) = ₹10 crore loss (high cost)
- False Positive (flag good company) = ₹10 lakh investigation cost (low cost)
- Optimize decision threshold to minimize expected cost

#### 4.5 Model Interpretation

**Feature Importance Analysis**:
- Top 10 predictors from Random Forest
- Direction and magnitude of effects
- Sector-specific patterns

**SHAP (SHapley Additive exPlanations) Values**:
- Explain individual predictions
- "Company X was flagged because: declining cash flow (-0.3), high leverage (+0.4), auditor qualification (+0.2)"
- Makes model actionable for banks

**Decision Rules Extraction**:
- If Interest Coverage < 1.0 AND Debt/Equity > 3.0 → 85% default probability
- Hybrid rule-based + ML system

### Phase 5: Visualization & Insights

#### 5.1 Streamlit Dashboard Components

**Page 1: Executive Summary**
- Total defaulters analyzed, model performance overview
- Sector-wise distribution of defaults
- Timeline of defaults (by year of classification)
- Key findings summary (top 5 patterns)

**Page 2: Company Deep Dive**
- Search/select company from dropdown
- 3-year financial trend charts (liquidity, leverage, profitability)
- Red flag timeline (when warnings appeared)
- Peer comparison (company vs sector median)
- Model explanation (SHAP values for this company)

**Page 3: Bank Analysis**
- Which banks appear most frequently in defaulter list
- Bank-wise lending patterns (sectors, company sizes)
- "Miss rate": % of that bank's loans that became NPAs
- PSU vs Private bank comparison

**Page 4: Pattern Explorer**
- Interactive scatter plots (debt vs cash flow, colored by outcome)
- Filter by sector, size, year
- Identify clusters of risky companies
- Statistical distributions (defaulters vs non-defaulters)

**Page 5: Director Network Analysis**
- Network graph of directors appearing in multiple defaults
- "Serial defaulter promoters" (individuals in 3+ failed companies)
- Group company structures (common promoters)
- Visualization: Node size = number of defaults, edges = shared directors

**Page 6: Predictive Tool (Simulation)**
- Upload hypothetical company financials (CSV format)
- Get real-time risk score (0-100)
- Top 5 risk factors identified
- Recommendation: Approve/Reject/Investigate Further

#### 5.2 Key Insights Report

**Automated Analysis**:
- "78% of defaulters had Interest Coverage < 1.5 for 2+ consecutive years"
- "Average Debt-to-Equity in defaulters (T-3 years): 3.2 vs non-defaulters: 1.4"
- "45% of defaulters had auditor qualifications in last report before default"
- "Related party transactions averaged 23% of revenue in defaulters vs 8% in non-defaulters"

**Sector-Specific Insights**:
- Infrastructure: Long gestation, regulatory delays (distinct risk profile)
- Steel/Metals: Commodity price volatility (external factors)
- Textiles: Working capital intensive (liquidity stress)

---

## Special Challenges & Mitigation Strategies

### Challenge 1: MCA Data Quality

**Problems**:
- **Inconsistent Formats**: Different CAs use different PDF layouts
- **Missing Data**: Some companies skip optional disclosures
- **Filing Delays**: 20-30% of companies file late or not at all
- **Scanned vs Digital**: Older filings are scanned images (OCR required)

**Mitigation**:
1. Build flexible parsers with multiple templates
2. Manual validation on 10% random sample
3. Focus on larger companies (better compliance history)
4. Create data quality score for each company
5. Exclude companies with >30% missing data

**Reality Check**: Expect 15-20% data extraction failure rate. Budget extra time.

### Challenge 2: Attribution Problem

**Problem**: Financial outcomes have confounding variables

**Example**: Company X defaults in 2020
- Was it poor decision at time of loan (2017)?
- Or external shock (COVID-19, sector downturn)?
- Or fraud that was undetectable (hidden from financials)?

**Mitigation**:
1. **Wilful Defaulters Only**: These are cases of deliberate non-payment, not distress
2. **Multiple Years Analysis**: Patterns over 3 years reduce event sensitivity
3. **Sector Controls**: Compare within-industry to normalize external factors
4. **Transparency**: Clearly state model limitations in documentation

**Honesty**: Model predicts **financial stress signals**, not fraud intent. Some defaults may still be unpredictable.

### Challenge 3: Small Sample Size Statistical Concerns

**Concern**: 300 samples with 85 features = risky overfitting

**Evidence It's Okay**:
- Altman Z-Score: Built on 66 companies, used globally for 50+ years
- Financial features are high signal-to-noise (not like image pixels)
- Cross-validation reduces overfitting risk
- Regularization techniques available

**Mitigation**:
1. **Feature Selection**: Reduce to 30-40 most important features
2. **5-Fold Cross-Validation**: Use all data efficiently
3. **Regularization**: L1/L2 penalties in logistic regression
4. **Ensemble Methods**: Random Forest's bootstrap aggregation creates synthetic variation
5. **Simple Models First**: Start with logistic regression before complex models

**Validation Strategy**:
- **Temporal Split**: Train on 2015-2018 defaults, test on 2019-2020 defaults
- If model works across time periods → genuine patterns, not overfitting

### Challenge 4: Entity Resolution Errors

**Problem**: Matching "Kingfisher Airlines Ltd" to "Kingfisher Airlines Limited"

**Impact**: 
- False negative: Miss a defaulter in dataset (model trained on incomplete data)
- False positive: Match wrong companies (noise in training data)

**Mitigation**:
1. **Multiple Match Stages**: Exact → Fuzzy → AI-assisted → Manual
2. **Context Validation**: Check sector, location, directors match
3. **Confidence Scores**: Flag low-confidence matches for review
4. **Sample Validation**: Manually verify 50 random matches
5. **Error Budget**: Accept 5% mismatch rate (better than 20% with simple matching)

**Resource Allocation**: Budget 10-15 hours for entity resolution

### Challenge 5: Temporal Leakage

**Problem**: Using information that wouldn't have been available at decision time

**Example**: Company classified as wilful defaulter in 2020
- Using 2019 financial data (T-1) = **data leakage** (bank didn't have this when approving loan in 2017)
- Using 2017 financial data (T-3) = **correct** (this was available at loan decision time)

**Mitigation**:
1. **Strict Time Boundaries**: Only use data from T-3 years before default classification
2. **Document Lag**: Account for MCA filing delays (use T-4 to be safe)
3. **Audit Trail**: Clearly mark data vintage in feature names
4. **Validation Check**: Ensure test set companies have proper time separation

### Challenge 6: Class Imbalance (Future Extension)

**Problem**: In real world, defaulters are <5% of loans

**Current Status**: Not a problem (we have balanced 150-150 dataset)

**If Scaling Up**: May need to handle imbalance
- **SMOTE**: Synthetic Minority Over-sampling
- **Class Weights**: Penalize misclassification differently
- **Threshold Tuning**: Adjust decision boundary for cost-weighted optimization

### Challenge 7: Interpretability vs. Accuracy Trade-off

**Tension**: Banks need explanations, but complex models perform better

**Resolution**:
1. **Hybrid Approach**: 
   - Use Random Forest for predictions (good balance)
   - Extract decision rules for communication
   - Use SHAP for individual explanations

2. **Rule-Based Alerts**: 
   - Hard rules for obvious cases (Interest Coverage < 1.0)
   - ML for edge cases

3. **Explanation Dashboard**: 
   - Never show raw model outputs without context
   - Always pair prediction with top 3 reasons

**Philosophy**: A 82% accurate explainable model beats a 90% black-box model in banking.

---

## Project Shortcomings & Limitations

### 1. **Survivorship Bias**

**Issue**: We only analyze companies that became wilful defaulters (public record). We miss:
- Companies that defaulted but weren't classified as "wilful"
- Companies that were stressed but recovered
- Companies that were rejected for loans (unknown universe)

**Impact**: Model may underestimate risk if patterns differ between wilful vs accidental defaulters

**Disclosure**: This model identifies wilful defaulter patterns specifically, not general default risk

### 2. **Fraud Detection Gap**

**Issue**: Wilful default often involves fraud (falsified financials, fund diversion)
- If fraud is sophisticated, it won't appear in MCA filings
- Model assumes financial statements are truthful

**Reality**: Cases like Nirav Modi, Mehul Choksi involved years of undetected fraud

**Limitation**: Model can't catch fraud that successfully hides from auditors

### 3. **Sector-Specific Dynamics**

**Issue**: Different industries have different risk profiles
- Infrastructure: Long payback periods, regulatory risks
- MSME: Limited financial data, informal practices
- Retail: Seasonal variations, fashion risks

**With 300 Samples**: Only 20-30 companies per sector (insufficient for sector-specific models)

**Compromise**: Build general model, note sector as feature, acknowledge reduced accuracy for niche sectors

### 4. **Economic Cycle Dependency**

**Issue**: Model trained on 2015-2020 data (includes COVID shock, IL&FS crisis)

**Risk**: Patterns may not hold in different macro conditions
- Low interest rate era vs high interest rate era
- Growth phase vs recession

**Mitigation**: Include economic indicators as features (GDP growth, interest rates, sector credit growth)

### 5. **Regulatory Changes**

**Issue**: IBC (Insolvency and Bankruptcy Code) 2016 changed default dynamics
- Pre-IBC: Promoters could delay indefinitely
- Post-IBC: 180-day resolution timeline

**Impact**: Behavioral changes in borrowers and lenders (patterns may differ pre/post IBC)

**Solution**: Separate analysis for pre-2016 vs post-2016 defaults (if sample size allows)

### 6. **Binary Classification Limitation**

**Issue**: Real world is continuous risk spectrum (0-100%), not binary (safe/risky)

**Model Output**: Probability score (0-1)

**Problem**: Where to set threshold? 
- High threshold (0.8) = fewer false alarms, but miss some defaulters
- Low threshold (0.5) = catch more defaulters, but many false alarms

**Solution**: Let users adjust threshold based on risk appetite (build into dashboard)

### 7. **No Real-Time Data**

**Issue**: MCA filings are 6-12 months delayed
- Company files FY 2023 results in September 2024
- Model uses FY 2023 data in 2024 to flag 2025 risks

**Limitation**: Can't provide real-time early warning (always lagged)

**Context**: Still useful for process improvement, forensic analysis, historical pattern detection

### 8. **Promoter Intent Unknown**

**Issue**: "Wilful" defaulter classification is legal/regulatory judgment
- Some genuine business failures get classified as wilful
- Some actual fraud may not be classified (lack of evidence)

**Uncertainty**: We don't know ground truth of "intent to defraud"

**Practical Impact**: Model predicts financial stress, not moral culpability

---

## Success Criteria & Expected Outcomes

### Quantitative Targets

**Model Performance**:
- **Precision**: >75% (acceptable false alarm rate)
- **Recall**: >85% (catch most defaulters)
- **F1-Score**: >0.80
- **AUC-ROC**: >0.85

**If Achieved**: Model has genuine predictive power, not random guessing

### Qualitative Outcomes

**Primary Deliverables**:
1. **Trained ML Model** (Random Forest, saved as .pkl file)
2. **Interactive Dashboard** (Streamlit app, deployable locally)
3. **Insights Report** (PDF, 15-20 pages)
4. **Clean Dataset** (300 companies, 3 years, structured CSV/SQL)
5. **Codebase** (GitHub repo, documented)

**Key Insights** (Expected):
- Top 5 financial ratios that predict wilful default
- Sector-wise risk patterns
- Bank lending quality comparison (PSU vs Private)
- Director network analysis (serial defaulters)
- Timeline of warning signals (how early can we detect?)

**Practical Value**:
- Framework for forensic analysis of credit decisions
- Training tool for bank credit analysts
- Research contribution (can be published)
- Portfolio piece for ML/data science work

---

## Timeline & Milestones

### Week 1: Infrastructure Setup
- **Day 1-2**: RBI scraper development and testing
- **Day 3-5**: MCA portal automation (Selenium setup)
- **Day 6-7**: PDF parser development and validation
- **Milestone**: Successfully extract data for 20 test companies

### Week 2: Data Collection
- **Day 1-5**: Automated scraping (300 companies × 3 years)
- **Day 6-7**: Data cleaning and storage (SQLite database)
- **Milestone**: 900 documents collected, 85%+ successful extraction rate

### Week 3: Feature Engineering & Modeling
- **Day 1-2**: Entity resolution (fuzzy matching + AI verification)
- **Day 3-4**: Calculate financial ratios and temporal features
- **Day 5-6**: Model training (logistic regression, random forest, XGBoost)
- **Day 7**: Model evaluation and feature importance analysis
- **Milestone**: Model achieves >80% F1-Score on test set

### Week 4: Visualization & Documentation
- **Day 1-3**: Streamlit dashboard development
- **Day 4-5**: Insights report writing
- **Day 6-7**: Final testing, bug fixes, documentation
- **Milestone**: Deployable dashboard + comprehensive report

**Total Duration**: 4 weeks (1 month)

---

## Free Tools & Resources

### Development Tools
- **Python** (3.8+): Programming language
- **Jupyter Notebook**: Interactive development
- **VS Code**: Code editor

### Libraries (All Free/Open Source)
- **Web Scraping**: Selenium, BeautifulSoup, requests
- **PDF Parsing**: pdfplumber, camelot-py, PyPDF2
- **Data Processing**: pandas, numpy
- **Machine Learning**: scikit-learn, XGBoost, LightGBM
- **Visualization**: matplotlib, seaborn, plotly
- **Dashboard**: Streamlit
- **Network Analysis**: NetworkX
- **NLP**: spaCy, NLTK (for text analysis)
- **Entity Matching**: RapidFuzz

### Cloud/Storage (Free Tiers)
- **GitHub**: Code hosting (free for public repos)
- **Google Colab**: Free GPU for training (if needed)
- **SQLite**: Database (local, no server)

### AI Assistance
- **Claude/ChatGPT**: Code generation, debugging, data validation
- **Estimated Cost**: $20-30 for entire project (API calls for entity resolution)

---

## Risk Assessment

### High Risk
1. **MCA Data Access Restrictions**: If portal blocks automation
   - **Mitigation**: Manual download fallback, use VPN/proxy rotation, add delays

2. **Data Quality Issues**: If 40%+ of companies have unusable data
   - **Mitigation**: Expand sample to 400 companies, keep best 300

### Medium Risk
3. **Entity Resolution Failures**: If can't match 20%+ companies
   - **Mitigation**: More aggressive fuzzy matching, larger manual review effort

4. **Model Overfitting**: If test performance << training performance
   - **Mitigation**: More aggressive feature selection, simpler models, more regularization

### Low Risk
5. **Timeline Slippage**: If data collection takes 2x estimated time
   - **Mitigation**: Already conservative timeline, parallel processing possible

6. **Interpretation Challenges**: If patterns aren't clear
   - **Mitigation**: This is actually interesting finding ("defaults are unpredictable")

---

## Future Extensions (Beyond Initial Scope)

### Phase 2 Enhancements
1. **Expand Sample Size**: Scale to 500-1000 companies for robustness
2. **Sector-Specific Models**: Separate models for infra, manufacturing, services
3. **Real-Time Monitoring**: Integrate with live financial data feeds (paid)
4. **Peer Comparison**: Rank companies within sector by risk score
5. **API Development**: RESTful API for programmatic access

### Advanced Features
6. **NLP on Annual Reports**: Sentiment analysis on MD&A sections
7. **News Sentiment Integration**: Track media coverage negativity
8. **Time-Series Forecasting**: Predict trajectory of financial ratios
9. **Graph Neural Networks**: Better director network analysis
10. **Explainable AI**: Advanced LIME/SHAP dashboards

### Commercial Applications
11. **Bank Risk Tool**: Sell as SaaS to regional banks
12. **Forensic Consulting**: Offer as service for legal cases
13. **Research Paper**: Publish in finance/ML journal
14. **Regulatory Tool**: Position as public policy instrument

---

## Ethical Considerations

### Data Privacy
- All data used is **already public** (MCA, RBI mandated disclosures)
- No personal information beyond director names (public officials)
- Company financials are required public disclosures

### Responsible Use
- Model is **diagnostic** (forensic analysis), not **prescriptive** (loan decisions)
- Should not replace human judgment in credit assessment
- Acknowledge limitations clearly (cannot detect sophisticated fraud)

### Bias Concerns
- **Sector Bias**: Some sectors over-represented in defaulters (infrastructure)
- **Size Bias**: Large companies better documented, model may not work for MSMEs
- **Disclosure**: Clearly state model scope and limitations

### Transparency
- Open-source codebase (GitHub)
- Document all assumptions
- Share methodology, not just results

---

## Key Takeaways

### What Makes Fulcrum Unique
1. **Focus on Wilful Defaulters**: Specific, high-impact niche
2. **Forensic Approach**: Learn from failures, not predict future
3. **India-Specific**: Leverages RBI/MCA public data infrastructure
4. **Practical Scale**: 300 companies is feasible yet meaningful
5. **Free Data**: No subscriptions or paid databases required

### Core Hypothesis
**"Financial red flags visible 2-3 years before wilful default are detectable from public filings and can be systematically identified using ML"**

### Success Definition
If Fulcrum can identify 85% of wilful defaulters using only publicly available financial data from 3 years prior, it proves that better due diligence could have prevented most losses.

### Ultimate Goal
Not to replace human judgment, but to provide a systematic, data-driven framework that ensures:
- Red flags aren't missed due to workload
- Consistent standards across loan officers
- Institutional learning from past failures
- Accountability in credit decisions

---

## Contact & Contribution

**Project Name**: Fulcrum  
**Domain**: FinTech, Credit Risk Analytics  
**Geography**: India  
**Status**: In Development (4-week sprint)  

**Open Questions for Community**:
1. Which specific sectors should be prioritized in 300-company sample?
2. What are the most common MCA filing format variations?
3. Best practices for handling missing financial data in small samples?
4. Validation approach for entity resolution accuracy?

**Contributions Welcome**: Data collection strategies, feature engineering ideas, visualization suggestions

---

## Appendix: References & Resources

### Academic Literature
- Altman, E. (1968). "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy"
- Beaver, W. (1966). "Financial Ratios as Predictors of Failure"
- Ohlson, J. (1980). "Financial Ratios and the Probabilistic Prediction of Bankruptcy"

### Indian Context
- RBI Reports on Wilful Defaulters (2020-2024)
