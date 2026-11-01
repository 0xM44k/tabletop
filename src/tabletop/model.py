"""System model loading and validation."""
from __future__ import annotations

import json
import re

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class ModelError(Exception):
    pass


def load_model(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except OSError as e:
        raise ModelError(f"{path}: {e.strerror}") from e
    except json.JSONDecodeError as e:
        raise ModelError(f"{path}: not valid JSON ({e.msg} at line {e.lineno})") from e
    return validate(data)


def _strs(v, label):
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ModelError(f"{label}: expected a list of strings")
    return v


def validate(d):
    if not isinstance(d, dict):
        raise ModelError("model must be a JSON object")
    if not isinstance(d.get("name"), str) or not d["name"].strip():
        raise ModelError("name: required, a non-empty string")
    assets = d.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ModelError("assets: required, a non-empty list")
    ids, out_assets = set(), []
    for i, a in enumerate(assets):
        where = f"assets[{i}]"
        if not isinstance(a, dict):
            raise ModelError(f"{where}: expected an object")
        if not isinstance(a.get("id"), str) or not ID_RE.match(a["id"]):
            raise ModelError(f"{where}.id: required, letters, digits, . _ - only")
        if a["id"] in ids:
            raise ModelError(f"{where}.id: duplicate id {a['id']!r}")
        ids.add(a["id"])
        if not isinstance(a.get("name"), str) or not a["name"].strip():
            raise ModelError(f"{where}.name: required")
        out_assets.append({"id": a["id"], "name": a["name"].strip(), "kind": str(a.get("kind", "service")).lower(),
                           "data": _strs(a.get("data", []), f"{where}.data"), "depends_on": _strs(a.get("depends_on", []), f"{where}.depends_on"),
                           "internet_facing": bool(a.get("internet_facing", False))})
    classes = {}
    for i, c in enumerate(d.get("data_classes", [])):
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not isinstance(c.get("name"), str):
            raise ModelError(f"data_classes[{i}]: needs string id and name")
        classes[c["id"]] = c["name"]
    for a in out_assets:
        for dep in a["depends_on"]:
            if dep not in ids:
                raise ModelError(f"assets {a['id']!r} depends_on unknown asset {dep!r}")
        for dc in a["data"]:
            if dc not in classes:
                raise ModelError(f"asset {a['id']!r} lists data class {dc!r} that is not in data_classes")
    roles = _strs(d.get("roles", []), "roles")
    controls = [c.lower() for c in _strs(d.get("controls", []), "controls")]
    return {"name": d["name"].strip(), "assets": out_assets, "data_classes": classes, "roles": roles, "controls": controls}
