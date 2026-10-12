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
    excluded = [s.lower() for s in (sites.get("exclude_operators") or [])]
    active = []
    for s in sites["sites"]:
        op = (s.get("operator") or "").lower()
        if any(e and e in op for e in excluded):
            raise SystemExit(f"Site {s['id']} is run by an excluded operator ({s.get('operator')}). "
                             "This project screens non-employer pits only; remove it from config/sites.yaml.")
        if s.get("enabled", True):
            active.append(s)
    return active, params


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
