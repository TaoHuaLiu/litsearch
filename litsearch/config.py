"""Where API keys live, so the tool works from any folder once installed.

Lookup order (first value wins): environment, ./.env in the current folder,
the per-user config file, then the legacy .env next to the source code."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# (variable, label, where to get it); the order is the one shown in the GUI
KEYS = [
    ("OPENALEX_EMAIL", "OpenAlex : e-mail (facultatif, accès plus rapide)", "https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication"),
    ("OPENALEX_API_KEY", "OpenAlex : clé (facultative)", "https://openalex.org/settings/api"),
    ("SERPAPI_KEY", "Google Scholar (SerpAPI)", "https://serpapi.com/manage-api-key"),
    ("IEEE_API_KEY", "IEEE Xplore", "https://developer.ieee.org/"),
    ("ELSEVIER_API_KEY", "ScienceDirect (Elsevier)", "https://dev.elsevier.com/apikey/manage"),
    ("ELSEVIER_INSTTOKEN", "ScienceDirect : insttoken (seulement si Elsevier vous en a donné un)", "https://dev.elsevier.com/"),
]


def user_env_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "litsearch" / ".env"


def _legacy_env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def load_keys() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for p in (Path.cwd() / ".env", user_env_path(), _legacy_env_path()):
        if p.is_file():
            load_dotenv(p, override=False)


def read_user_keys() -> dict[str, str]:
    from dotenv import dotenv_values
    p = user_env_path()
    return {k: v or "" for k, v in dotenv_values(p).items()} if p.is_file() else {}


def save_user_keys(values: dict[str, str]) -> Path:
    """Write the keys to the user config file (blank = removed) and apply them to this process."""
    p = user_env_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in read_user_keys().items() if k not in values}
    keep.update({k: v.strip() for k, v in values.items() if v and v.strip()})
    p.write_text("".join(f"{k}={v}\n" for k, v in keep.items()), encoding="utf-8")
    if sys.platform != "win32":
        p.chmod(0o600)
    for k, v in values.items():
        if v and v.strip():
            os.environ[k] = v.strip()
        else:
            os.environ.pop(k, None)
    return p
