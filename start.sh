#!/bin/bash
# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers (Chromium only for lightweight setup)
playwright install chromium

# Start the Flask server with Gunicorn
gunicorn server:app --bind 0.0.0.0:10000 --workers 1
