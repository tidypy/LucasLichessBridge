#!/bin/bash
# Force Python to run unbuffered
export PYTHONUNBUFFERED=1

source /home/dev/Documents/ChessDB/Lichess_Lucas_Bot/LucasAPIv3/venv/bin/activate
exec python -u /home/dev/Documents/ChessDB/Lichess_Lucas_Bot/LucasAPIv3/UCIbridgeForLucas.py
