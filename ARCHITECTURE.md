# Architecture

## System Overview

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Screener.in  │────▶│   Backend        │────▶│   Frontend        │
│ Excel Export │     │   FastAPI :8000  │     │   Vite :5173      │
└─────────────┘     └──────────────────┘     └──────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   SQLite DB   │
                    │ (persistence) │
                    └──────────────┘
```

## Data Flow

### Upload Pipeline

```
Excel File Upload
       │
       ▼
OpenPyXL load_workbook(data_only=True)
       │
       ├──► Data Sheet: primary source
       │      ├── Section tracking (skip Quarters)
       │      ├── Field name normalization (35+ mappings)
       │      ├── Year extraction from Report Date row
       │      └── Structured records [{metric_name, year, value}]
       │
       ├──► Balance Sheet sheet: secondary (pre-computed values)
       │      └── Working Capital, Debtor Days, ROE, ROCE (when cached)
       │
       └──► Company meta extraction (name, sector)
              │
              ▼
       SQLite persistence (6 tables)
```

### Analysis Pipeline

```
Parsed Data
    │
    ▼
RatioEngine ──────────► 14 financial ratios
    │
    ▼
TrendEngine ──────────► CAGR, YoY growth, trend direction
    │
    ▼
RedFlagEngine ────────► 10 rule-based detectors
    │
    ▼
ScoringEngine ────────► Weighted health score (5 dimensions)
    │
    ▼
AIEngine ─────────────► Groq AI or rule-based fallback
    │
    ▼
JSON Response ────────► React Dashboard (Recharts)
```

## Backend Architecture

### Layer 1: Web Server (FastAPI + Uvicorn)

**File**: `app/main.py`

- Single-process FastAPI application with CORS middleware
- Three routers: upload, analysis, reports
- Health check endpoint at `/api/health`
- Database initialization on startup

### Layer 2: Service Layer

#### Excel Parser (`app/services/excel_parser.py`)

Central ingestion engine with four responsibilities:

1. **Workbook Loading**: Opens `.xlsx` with `data_only=True` to get cached computed values, never raw formulas
2. **Field Normalization**: Maps 35+ raw Screener.in names to standardized names (`Sales` → `Revenue`, `Equity Share Capital` → `Equity Capital`)
3. **Data Extraction**: Two readers —
   - `read_data_sheet()`: primary reader with section tracking, year extraction, metadata skip
   - `read_balance_sheet()`: secondary reader for pre-computed values
4. **Query Helpers**: `get_metric_value()`, `get_metric_series()` with exact-match priority over substring fallback

Key design decisions:
- `data_only=True` throughout — formulas are resolved to cached computed values; users must open-and-save in Excel if values are missing
- "Quarters" section explicitly skipped to prevent TTM data from corrupting annual metrics
- Fuzzy substring matching only as last resort (exact match first)

#### Ratio Engine (`app/services/ratio_engine.py`)

Computes 14 ratios from normalized records using:
- `_try()`: returns first matching value from keyword groups
- `_sum()`: sums values across multiple keyword groups (used for Shareholder Equity = Equity Capital + Reserves)
- `_safe_div()`: division with None/zero protection
- Current Asset/Liability detection via set-membership lookup

EBITDA = PBT + Interest + Depreciation (derived when direct value unavailable).

#### Trend Engine (`app/services/trend_engine.py`)

- CAGR via geometric mean: `(val_last / val_first) ^ (1/periods) - 1`
- YoY growth: `(val_current - val_previous) / |val_previous|`
- Trend direction: last 3 data points comparison

#### Red Flag Engine (`app/services/red_flag_engine.py`)

10 stateless detectors, each returning a list of flag dicts or None. Sorted by severity (high → medium → low). Each detector is a single method with clear threshold logic.

#### Scoring Engine (`app/services/scoring_engine.py`)

Five weighted sub-scores (Profitability 25%, Liquidity 15%, Solvency 20%, Growth 20%, Cash Flow 20%) with red flag penalty (5 pts × count, max 30 penalty). All sub-scores start at 50/100 baseline and adjust based on ratio values.

#### AI Engine (`app/services/ai_engine.py`)

Two modes:
1. **Groq AI** (primary): Sends structured metrics/ratios/flags/scores as JSON via zero-hallucination prompt to Llama 3 70B
2. **Rule-based fallback** (default when no API key): Template engine with 7 sections, uses actual metric values and ratio data

### Layer 3: Data Layer

#### SQLite Schema (6 tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `uploaded_files` | File metadata | id, filename, company_name, file_path |
| `sheet_data` | Raw parsed records | file_id, sheet_name, metric_name, year, value |
| `financial_metrics` | Denormalized for quick lookup | file_id, metric_name, year_1..5 values |
| `calculated_ratios` | Cached ratio results | file_id, ratio_name, year, value |
| `red_flags` | Detected flags | file_id, flag_name, severity, explanation |
| `health_scores` | Scoring results | file_id, overall_score, dimension scores |
| `ai_analysis` | AI/fallback commentary | file_id, content, model_name |

All tables use UUID primary keys and foreign key to `uploaded_files`.

## Frontend Architecture

### Component Tree

```
App.jsx
├── Navbar
├── FileUpload (landing page)
└── [analysis loaded]
    ├── Sidebar (navigation + export)
    └── Routes
        ├── ExecutiveSummary
        │   ├── KPICard (×4)
        │   ├── TrendChart
        │   ├── RatioGauge (×5)
        │   └── Risk Summary
        ├── RatioAnalysis
        │   ├── InfoPopover (per ratio)
        │   ├── TrendChart
        │   ├── DataTable
        │   └── HeatMap
        │       └── NotePopover (per row)
        ├── TrendAnalysis
        │   └── TrendChart (multi-metric)
        ├── CashFlowIntelligence
        │   └── WaterfallChart
        ├── RedFlagMonitor
        └── AIInsights
```

### State Management

- File ID and analysis result held in `App.jsx` state, passed as props to child pages
- Theme preference persisted via React Context (`ThemeContext.jsx`)
- No global state library — prop drilling sufficient for this scope

### API Client

Axios instance with:
- Base URL: `/api` (proxied via Vite to backend)
- 120s timeout (analysis computation can take time)
- Upload progress callback for FileUpload component

### Charts (Recharts)

- **TrendChart**: Line chart for time-series metrics/ratios
- **RatioGauge**: Semi-circular gauge for health sub-scores
- **HeatMap**: Color-coded ratio × year matrix with benchmark popovers
- **WaterfallChart**: Sequential value breakdown for cash flow

## Key Design Decisions

### Why `data_only=True`?
Screener.in exports contain formulas in cells. By using `data_only=True`, we extract the cached computed values (which Excel saves). This avoids reimplementing Screener's formula engine. Users must open the file in Excel once if values aren't cached.

### Why exact-match-first in `get_metric_value`?
Substring matching caused false positives (e.g., "Equity Capital" matched by "Reserves" keywords). The function now tries exact match first, then exact match any year, then substring match as last resort.

### Why skip the "Quarters" section?
Screener.in includes both annual and quarterly data. The quarterly section uses different date labels and can overwrite/corrupt annual metric values during lookup. Annual data is sufficient for institutional analysis.

### Why not use the DB for live analysis?
The analysis endpoint re-parses the `.xlsx` file rather than reading from the DB. This ensures the analysis always uses fresh data and avoids deserialization issues. The DB primarily serves as an audit trail and for caching export data.

### Python 3.12 requirement
The application uses Python 3.12-specific async patterns and socket behavior. Using other versions (e.g., 3.14 on PATH) may cause runtime errors.
