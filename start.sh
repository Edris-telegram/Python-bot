#!/bin/bash
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
python prototype_reply.py
