#!/bin/bash
echo "========================================"
echo "  Cha Yin Prediction Tool"
echo "========================================"
echo ""

command -v python3 >/dev/null 2>&1 || { echo "[ERROR] Python3 not found"; exit 1; }

echo "[1/2] Installing dependencies..."
pip3 install -r requirements.txt -q 2>/dev/null

echo "[2/2] Starting server..."
echo ""
echo "  Open: http://localhost:5000"
echo "  Press Ctrl+C to stop"
echo ""
python3 app.py
