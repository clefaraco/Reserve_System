"""Install a local checkout without assuming a cloud path or Unix venv layout."""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
environment = os.environ.copy()
environment.setdefault("UV_CACHE_DIR", str(ROOT / ".local" / "cache" / "uv"))
environment.setdefault("npm_config_cache", str(ROOT / ".local" / "cache" / "npm"))

for tool in ("uv", "npm", "docker"):
    if shutil.which(tool) is None:
        raise SystemExit(f"Missing prerequisite: {tool}. See docs/local-development.md.")

commands = (
    ["uv", "sync", "--frozen", "--project", "backend"],
    ["npm", "ci", "--prefix", "frontend", "--no-audit", "--no-fund"],
    ["uv", "run", "--frozen", "--project", "backend", "python", "scripts/bootstrap.py"],
    ["npm", "run", "build", "--prefix", "frontend"],
)
for command in commands:
    subprocess.run([shutil.which(command[0]), *command[1:]], cwd=ROOT, env=environment, check=True)
print("Installed. Start the API and frontend using docs/local-development.md.")
