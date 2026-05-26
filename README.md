# Financial Statement Analyzer

Institutional-grade automated financial statement analysis for Indian listed companies using Screener.in Excel exports.

## Quick Start

### Prerequisites

- Python 3.12
- Node.js 18+
- A Screener.in Excel export (`.xlsx`) of any Indian listed company

### Backend

```powershell
cd backend
pip install -r requirements.txt
copy ..\.env.example .env
# Edit .env with your GROQ_API_KEY (optional — rule-based fallback works without it)
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, upload your Screener.in export, and view the analysis.

## One-Click Start

Double-click `start_backend.bat` and `start_frontend.bat` from the project root.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy + SQLite, OpenPyXL |
| Frontend | React 18, Tailwind CSS 3, Recharts, React Router 6 |
| AI | Groq API (Llama 3 70B) with zero-hallucination rule-based fallback |
| Parsing | OpenPyXL `data_only=True` — only cached computed values, no formula strings |

## Project Structure

```
financial-analyzer/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app entry
│       ├── config.py            # Environment config
│       ├── database.py          # SQLAlchemy engine
│       ├── models/models.py     # DB schema (6 tables)
│       ├── schemas/schemas.py   # Pydantic response models
│       ├── routers/
│       │   ├── upload.py        # File upload + parse
│       │   ├── analysis.py      # Full analysis pipeline
│       │   └── reports.py       # JSON report export
│       └── services/
│           ├── excel_parser.py  # Screener.in ingestion engine
│           ├── ratio_engine.py  # 14 financial ratios
│           ├── trend_engine.py  # CAGR, YoY growth, direction
│           ├── red_flag_engine.py # 10 rule-based detectors
│           ├── scoring_engine.py  # Weighted health scoring
│           └── ai_engine.py     # Groq AI / rule-based fallback
├── frontend/
│   └── src/
│       ├── App.jsx              # Router + state
│       ├── pages/               # 6 dashboard pages
│       ├── components/          # Reusable UI + charts
│       └── services/api.js      # Axios client
└── start_backend.bat / start_frontend.bat
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload/` | POST | Upload Screener.in Excel file |
| `/api/analysis/{file_id}` | GET | Full financial analysis |
| `/api/analysis/debug/{file_id}` | GET | Debug endpoint with parsed metrics |
| `/api/reports/json/{file_id}` | GET | Downloadable JSON report |
| `/api/health` | GET | Health check |

## Environment Variables

| Variable | Default | Required |
|----------|---------|----------|
| `GROQ_API_KEY` | — | No (rule-based fallback used when absent) |
| `DATABASE_URL` | `sqlite:///./financial_analyzer.db` | No |
| `UPLOAD_DIR` | `./uploads` | No |
| `AI_MODEL` | `llama3-70b-8192` | No |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | No |
