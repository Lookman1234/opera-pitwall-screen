"""Shared helpers: config loading, provenance logging, output paths.

Plain-language header: small bookkeeping functions used by every numbered script.
You do not need to open it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os

import yaml


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_config(root, sites_path=None, params_path=None):
    sites = load_yaml(sites_path or os.path.join(root, "config", "sites.yaml"))
    params = load_yaml(params_path or os.path.join(root, "config", "params.yaml"))
    excluded = [s.lower() for s in _exclusions(root, sites)]
    active = []
    for s in sites["sites"]:
        text = " ".join(str(s.get(k) or "") for k in ("operator", "name", "id")).lower()
        if any(e and e in text for e in excluded):
            raise SystemExit(f"Site {s['id']} matches an excluded operator or mine. "
                             "This project screens non-employer pits only; remove it from config/sites.yaml.")
        if s.get("enabled", True):
            active.append(s)
    return active, params


def _exclusions(root, sites):
    """Operators (and mine names) the pipeline must refuse.

    Three sources, merged: exclude_operators in sites.yaml (public), the private file
    config/exclude.local.yaml (git-ignored, never published), and the environment
    variable PITWALL_EXCLUDE (comma-separated; the GitHub runner fills it from a
    repository secret). The private routes keep the author's employer out of the
    public repository while still enforcing the exclusion on every run.
    """
    out = [s for s in (sites.get("exclude_operators") or []) if s and not s.startswith("[")]
    local = os.path.join(root, "config", "exclude.local.yaml")
    if os.path.exists(local):
        out += [s for s in (load_yaml(local) or {}).get("exclude", []) if s]
    out += [s.strip() for s in os.environ.get("PITWALL_EXCLUDE", "").split(",") if s.strip()]
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log_provenance(path, source_url, log_path, note=""):
    """Same line format as scripts/provenance.py."""
    line = " | ".join([dt.date.today().isoformat(), os.path.basename(path),
                       f"{os.path.getsize(path)} bytes", f"sha256:{sha256(path)}",
                       source_url, note]).rstrip(" |")
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a") as f:
        f.write(line + "\n")


def site_dir(root, kind, site_id):
    p = os.path.join(root, "data", kind, site_id)
    os.makedirs(p, exist_ok=True)
    return p
