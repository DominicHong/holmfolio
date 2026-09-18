@echo off
echo Starting Portfolio Tracker...
echo.

echo Initializing backend database...
python -m backend.init_data
echo.

echo Starting backend server (FastAPI)...
start cmd /k "uvicorn backend.main:app --reload"
echo Backend started at http://localhost:8000
echo.

echo Starting frontend server (Vue.js)...
cd frontend
start cmd /k "npm run dev"
cd ..
echo Frontend will be available at http://localhost:3000
echo.

echo Both servers are starting...
echo Press any key to exit
pause