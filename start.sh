#!/bin/bash

echo "Starting Portfolio Tracker..."
echo ""

echo "Initializing backend database..."
python -m backend.init_data
echo ""

echo "Starting backend server (FastAPI)..."
gnome-terminal -- bash -c "uvicorn backend.main:app --reload; exec bash" 2>/dev/null || \
xterm -e "uvicorn backend.main:app --reload; exec bash" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && uvicorn backend.main:app --reload"' 2>/dev/null || \
uvicorn backend.main:app --reload &
echo "Backend started at http://localhost:8000"
echo ""

echo "Starting frontend server (Vue.js)..."
cd frontend
gnome-terminal -- bash -c "npm run serve; exec bash" 2>/dev/null || \
xterm -e "npm run dev; exec bash" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && npm run serve"' 2>/dev/null || \
npm run serve &
cd ..
echo "Frontend will be available at http://localhost:3000"
echo ""

echo "Both servers are starting..."
echo "Press Ctrl+C to stop"

wait