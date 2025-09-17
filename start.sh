#!/bin/bash
# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers (Chromium only for lightweight setup)
playwright install chromium

# Start the FastAPI server
uvicorn server:app --host 0.0.0.0 --port 10000
