"""Own locked offscreen project for trial03 refinement."""
import importlib.util
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis/neighbor_steering'))
spec=importlib.util.spec_from_file_location('refine_launcher',ROOT/'analysis/neighbor_steering/launch.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.PROJECT=ROOT/'simulator/variants/r5_stages_20261122'
from model_validation_map import live_config
module.live_config=live_config
if __name__=='__main__':module.main()
