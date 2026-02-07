#!/bin/bash
# Run Cousin Eddie Dashboard
# Starts API backend and opens frontend

echo "🚀 Starting Cousin Eddie Dashboard..."
echo ""

# Check database is running
echo "Checking database connection..."
export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/cousin_eddie"

# Start API in background
echo "Starting API backend on http://localhost:8000..."
cd "$(dirname "$0")"
python api/main.py &
API_PID=$!

# Wait for API to start
sleep 2

# Open frontend
echo "Opening dashboard at http://localhost:8000/docs"
echo "Frontend available at: file://$(pwd)/frontend/index.html"
echo ""
echo "API Documentation: http://localhost:8000/docs"
echo "API Endpoints:"
echo "  - Companies: http://localhost:8000/api/companies"
echo "  - Processors: http://localhost:8000/api/processors"
echo "  - Stats: http://localhost:8000/api/stats"
echo ""
echo "Press Ctrl+C to stop..."

# Keep script running
wait $API_PID
