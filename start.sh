#!/bin/bash

# CDR Intelligence Platform Startup Script
# Usage: ./start.sh [--dev|--prod]
# Default: --dev

# Set default mode to dev if no argument provided
MODE=${1:---dev}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "⚠️  .env file not found. Creating from .env.example..."
        cp .env.example .env
        echo "📝 Please edit .env and add your MongoDB Atlas connection string"
    else
        echo "⚠️  .env file not found. Please create one with your configuration."
    fi
fi

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID 2>/dev/null
        wait $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID 2>/dev/null
        wait $FRONTEND_PID 2>/dev/null
    fi
    echo "✅ Servers stopped"
    exit 0
}

# Set up signal handlers for cleanup
trap cleanup SIGINT SIGTERM

# Start backend server
echo "🌐 Starting FastAPI server..."

if [ "$MODE" == "--dev" ]; then
    echo "🔧 Running in DEVELOPMENT mode"
    echo "   Backend: http://localhost:8000"
    echo "   Frontend: http://localhost:8080"
    echo "   Press Ctrl+C to stop"
    echo ""

    # Run backend in background but capture PID
    cd backend
    python run.py &
    BACKEND_PID=$!
    cd ..

    # Start frontend server in background
    cd frontend
    python -m http.server 8080 > /dev/null 2>&1 &
    FRONTEND_PID=$!
    cd ..

    # Wait for both processes (foreground wait so Ctrl+C works)
    # The trap will handle cleanup on Ctrl+C
    wait $BACKEND_PID $FRONTEND_PID

elif [ "$MODE" == "--prod" ]; then
    echo "🚀 Running in PRODUCTION mode"
    echo "   Backend: http://localhost:${PORT:-8000}"
    echo ""

    # Create logs directory
    mkdir -p logs

    # Run backend in background (production mode)
    cd backend
    PORT=${PORT:-8000} python run.py > ../logs/backend.log 2>&1 &
    BACKEND_PID=$!
    cd ..
    echo "   Backend PID: $BACKEND_PID"
    echo "   Logs: logs/backend.log"

    # Start frontend server in background
    cd frontend
    python -m http.server 8080 > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    echo "   Frontend PID: $FRONTEND_PID"
    echo "   Logs: logs/frontend.log"
    echo ""
    echo "✅ Servers started in background"
    echo "   To stop: kill $BACKEND_PID $FRONTEND_PID"
    echo "   Or use: ./stop.sh"

    # Don't wait in production mode - let it run in background
    exit 0
else
    echo "❌ Invalid mode: $MODE"
    echo "Usage: ./start.sh [--dev|--prod]"
    exit 1
fi
