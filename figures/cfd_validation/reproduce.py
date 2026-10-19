from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(root / "cfd_runner.py"),
    "--replay", str(root / "manifest.json"),
    "--template-file", str(root / "plot_template_snapshot.py"),
    "--output-dir", str(root)], check=True)
