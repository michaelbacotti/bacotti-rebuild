"""Helpers for sourcing the public-com broker env. Idempotent. 
Sourced from .openclaw/tmp/public-com.env (chmod 600, Mike-owned).
PUBLIC_COM_SECRET + PUBLIC_COM_ACCOUNT_ID are exported into os.environ
so subprocess scripts and direct SDK calls can both use them.
"""
import os
from pathlib import Path

ENV_FILE = Path("/Users/mike/.openclaw/workspace-bacottibot/.openclaw/tmp/public-com.env")

def load_env():
    """Source the public-com env file. Fails loud if missing/malformed."""
    if not ENV_FILE.exists():
        raise FileNotFoundError(f"public-com env file not found: {ENV_FILE}")
    loaded = {}
    with ENV_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            # Handle 'export FOO=bar' shell-style lines.
            if k.startswith("export "):
                k = k[len("export "):].strip()
            v = v.strip().strip('"').strip("'")
            os.environ[k] = v
            loaded[k] = v
    if "PUBLIC_COM_SECRET" not in loaded or "PUBLIC_COM_ACCOUNT_ID" not in loaded:
        raise RuntimeError(f"env file missing required vars: {ENV_FILE}")
    return loaded
