import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import pyla_main


with open("latest_brawler_data.json", encoding="utf-8") as f:
    pyla_main(json.load(f))
