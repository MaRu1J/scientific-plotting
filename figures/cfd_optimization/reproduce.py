from pathlib import Path
import subprocess
import sys

bundle = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(bundle / "optimization_runner.py"), "--replay", str(bundle)], check=True)
