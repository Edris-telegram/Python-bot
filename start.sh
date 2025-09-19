#!/bin/bash
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
uvicorn prototype_reply:app --host 0.0.0.0 --port $PORT
