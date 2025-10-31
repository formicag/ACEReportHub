#!/bin/bash

echo "================================"
echo "  ACE Report Hub - Starting"
echo "================================"
echo ""

cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: python3 -m venv venv"
    exit 1
fi

# Activate venv
source venv/bin/activate

# Check if dependencies installed
if ! python -c "import flask" 2>/dev/null; then
    echo "❌ Flask not installed!"
    echo "Run: pip install -r requirements.txt"
    exit 1
fi

echo "✅ Environment ready"
echo ""
echo "Starting Flask server..."
echo "Open your browser to: http://localhost:5000"
echo ""
echo "Press CTRL+C to stop"
echo "================================"
echo ""

python app.py
