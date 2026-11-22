"""Execute a reviewed JSON list sequentially, each in an owned offscreen process."""
import json
from pathlib import Path
import sys
from replay import run, ROOT

if __name__ == "__main__":
    for item in json.loads(Path(sys.argv[1]).read_text()):
        print("START", item["name"], flush=True)
        run(ROOT / item["case"], ROOT / item["model"], item["name"], fast=item.get("fast", False))
