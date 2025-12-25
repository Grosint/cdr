#!/bin/bash

# CDR Intelligence Platform Stop Script
# Stops all running backend and frontend servers

echo "🛑 Stopping CDR Intelligence Platform servers..."

# Find and kill backend processes (uvicorn/python run.py)
BACKEND_PIDS=$(ps aux | grep -E "(uvicorn|python.*run\.py|python.*main\.py)" | grep -v grep | awk '{print $2}')

# Find and kill frontend processes (http.server on port 8080)
FRONTEND_PIDS=$(lsof -ti:8080 2>/dev/null)

# Kill backend processes
if [ ! -z "$BACKEND_PIDS" ]; then
    echo "   Stopping backend servers..."
    echo "$BACKEND_PIDS" | xargs kill 2>/dev/null
    sleep 1
    # Force kill if still running
    echo "$BACKEND_PIDS" | xargs kill -9 2>/dev/null
fi

# Kill frontend processes
if [ ! -z "$FRONTEND_PIDS" ]; then
    echo "   Stopping frontend server..."
    echo "$FRONTEND_PIDS" | xargs kill 2>/dev/null
    sleep 1
    # Force kill if still running
    echo "$FRONTEND_PIDS" | xargs kill -9 2>/dev/null
fi

# Check if anything is still running
REMAINING=$(ps aux | grep -E "(uvicorn|python.*run\.py|python.*main\.py|http\.server)" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo "✅ All servers stopped"
else
    echo "⚠️  Some processes may still be running:"
    echo "$REMAINING"
fi
