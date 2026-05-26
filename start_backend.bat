@echo off
cd /d "%~dp0backend"
echo Installing backend dependencies...
pip install -r requirements.txt
echo Starting FastAPI server...
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
