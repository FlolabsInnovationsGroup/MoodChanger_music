@echo off
REM Run app in MOCK_MODE (Windows CMD)
set MOCK_MODE=1
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m uvicorn app:app --reload --port 8001
) else (
  python -m uvicorn app:app --reload --port 8001
)
