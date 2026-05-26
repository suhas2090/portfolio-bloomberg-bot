# Features

## 1. Excel Ingestion Engine

### Dynamic Field Normalization
Maps 35+ raw Screener.in metric names to standardized internal names via a comprehensive normalization lookup:
- `Sales`/`Revenue`/`Total Income` → `Revenue`
- `Equity Share Capital`/`Share Capital` → `Equity Capital`
- `Receivables`/`Debtors`/`Sundry Debtors` → `Trade Receivables`
- 30+ additional mappings across P&L, Balance Sheet, Cash Flow, and ratios

### Formula-to-Computed-Value Resolution
- Uses OpenPyXL `data_only=True` — extracts cached computed values only
- Detects missing computed values and warns user to open-and-save in Excel first
- Falls back gracefully when values aren't cached

### Section Tracking
- Reads only "Data Sheet" (skips "Quarters" section which contains TTM/quarterly data that corrupts annual metrics)
- Reads "Balance Sheet" sheet separately for pre-computed values (Working Capital, Debtor Days, ROE, ROCE) when cached

### Current Asset / Liability Classification
Auto-classifies line items as current assets (`Trade Receivables`, `Inventory`, `Cash & Bank`) or current liabilities (`Trade Payables`, `Short Term Provisions`, etc.) for ratio computation.

## 2. Ratio Engine (14 Ratios)

All ratios calculated dynamically from normalized data — zero hardcoded values.

### Liquidity
| Ratio | Formula |
|-------|---------|
| Current Ratio | Current Assets / Current Liabilities |
| Quick Ratio | (Current Assets - Inventory) / Current Liabilities |

### Profitability
| Ratio | Formula |
|-------|---------|
| ROE | PAT / Shareholder's Equity |
| ROCE | EBIT / (Equity + Borrowings) |
| EBITDA Margin | EBITDA / Revenue |
| Net Profit Margin | PAT / Revenue |

### Solvency
| Ratio | Formula |
|-------|---------|
| Debt to Equity | Borrowings / Shareholder's Equity |
| Interest Coverage | EBIT / Interest Expense |

### Efficiency
| Ratio | Formula |
|-------|---------|
| Asset Turnover | Revenue / Total Assets |
| Working Capital Turnover | Revenue / Working Capital |

### Market & Others
| Ratio | Formula |
|-------|---------|
| EPS | Direct from export |
| P/E Ratio | Direct from export |
| Debtor Days | (Receivables / Revenue) × 365 |
| Inventory Days | (Inventory / Revenue) × 365 |

### Smart N/A Handling
- Non-computable ratios display a clear reason (`"Current Liability line items not available"`)
- Working Capital falls back to Current Assets when Current Liabilities are unavailable
- EBITDA = PBT + Interest + Depreciation (with direct value priority)
- EBIT = PBT + Interest

## 3. Trend Engine

Computes per-metric:
- **CAGR** over the full period
- **YoY Growth** for each year
- **Trend Direction** (upward/downward/stable) based on last 3 data points
- Margin trends, cash flow vs PAT comparison

## 4. Red Flag Engine (10 Detectors)

| Detector | Severity | Trigger |
|----------|----------|---------|
| Falling Operating Margins | High | EBITDA margin declining over 3+ years |
| Negative Operating Cash Flow | High | Any year with negative OCF |
| Rising Debt Levels | Medium | Total debt up >30% over period |
| Declining Promoter Holding | Medium | Promoter stake decreasing |
| Poor Interest Coverage | High | Interest coverage <1.5x |
| Inventory Buildup | Medium | Inventory days up >20% |
| Debtor Days Deterioration | Medium | Receivable days up >20% |
| PAT Growth Without CF Support | High | Positive PAT but negative OCF in same year |
| Declining Revenue | High | Revenue lower at end vs start |
| Negative Net Worth | High | Shareholder equity negative |

## 5. Scoring Engine

Weighted health score across 5 dimensions:

| Dimension | Weight | Components |
|-----------|--------|------------|
| Profitability | 25% | ROE, Net Profit Margin, ROCE |
| Liquidity | 15% | Current Ratio, Quick Ratio |
| Solvency | 20% | Debt-to-Equity, Interest Coverage |
| Growth | 20% | Revenue growth, PAT growth |
| Cash Flow | 20% | OCF positivity, OCF/PAT ratio |

Red flag penalty: up to 30 points deducted (5 pts per flag, max 30).
Overall score → **Strong** (≥70) | **Moderate** (40–70) | **Weak** (<40)

## 6. AI Insight Engine

**Primary**: Groq API (Llama 3 70B) with strict zero-hallucination prompt — uses only provided metrics.
**Fallback**: Rule-based template engine generates structured analysis across 7 sections (Executive Summary, Revenue & Profitability, Liquidity & Solvency, Cash Flow, Growth, Key Risks, Overall Assessment).

## 7. Dashboard (6 Pages)

| Page | Content |
|------|---------|
| **Executive Summary** | KPI cards, health gauge, revenue/PAT/EBITDA chart, margin trends, risk summary |
| **Ratio Analysis** | 14 ratios grouped by category, trend charts, data tables, enhanced heatmap with benchmark popovers |
| **Trend Analysis** | Multi-metric trend charts with CAGR display |
| **Cash Flow Intelligence** | Waterfall chart, OCF vs PAT comparison, cash flow quality analysis |
| **Red Flag Monitor** | Severity-sorted flag list with explanations |
| **AI Insights** | AI-generated or rule-based institutional commentary |

### Ratio Heatmap
Color-coded matrix of all ratios × years with:
- Hover/click popovers showing benchmark ranges
- N/A indicators with explanation for unavailable ratios
- Color gradient (green → amber → red) based on value vs benchmark

## 8. User Experience

- **Dark/Light mode** toggle with persistent preference
- **Mobile responsive** layout
- **JSON report export** with one-click download
- **Progress indicators** during file upload and analysis
- **Amber info cards** for unavailable ratios with explanation
