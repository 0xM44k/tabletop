"""Pick applicable scenarios for a model and fill them in. Deterministic for a given seed."""
from __future__ import annotations

import json
import os
import random
import re

DEFAULT_ROLES = ["Incident lead", "Technical lead", "Communications", "Legal or privacy", "Business owner"]
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def load_catalog():
    with open(os.path.join(os.path.dirname(__file__), "catalog.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)["scenarios"]


def _kinds(model, kinds):
    return [a for a in model["assets"] if a["kind"] in kinds]


def applicable(model, scen):
    """Returns (ok, reason)."""
    needs = scen["needs"]
    if "kinds_any" in needs:
        found = _kinds(model, needs["kinds_any"])
        if not found:
            return False, f"needs an asset of kind {', '.join(needs['kinds_any'])}"
    if needs.get("internet_facing"):
        pub = [a for a in model["assets"] if a["internet_facing"]]
        if not pub:
            return False, "needs an internet-facing asset"
        if needs.get("has_data") and not any(a["data"] for a in pub):
            return False, "needs an internet-facing asset that holds a data class"
    return True, "matches your model"


def _connections(model, a):
    return len(a["depends_on"]) + sum(1 for b in model["assets"] if a["id"] in b["depends_on"])


def pick_primary(model, scen, rng):
    rule = scen["pick"]
    if rule == "most_connected":
        pool = _kinds(model, scen["needs"]["kinds_any"])
        pool.sort(key=lambda a: (-len(a["data"]), -_connections(model, a), a["id"]))
    elif rule == "internet_facing_with_data":
        pool = sorted([a for a in model["assets"] if a["internet_facing"] and a["data"]], key=lambda a: (-len(a["data"]), a["id"]))
    elif rule == "internet_facing":
        pool = sorted([a for a in model["assets"] if a["internet_facing"]], key=lambda a: (-_connections(model, a), a["id"]))
    else:
        pool = sorted(_kinds(model, rule.split(":", 1)[1].split(",")), key=lambda a: a["id"])
    top = [a for a in pool if _connections(model, a) == _connections(model, pool[0]) and len(a["data"]) == len(pool[0]["data"])] if rule == "most_connected" else pool[:2]  # ties are broken by the seed
    return rng.choice(top)


def _names(model, ids):
    return [model["data_classes"][i] for i in ids if i in model["data_classes"]]


def fill_values(model, primary, scen, rng):
    by_id = {a["id"]: a for a in model["assets"]}
    deps = [by_id[d]["name"] for d in primary["depends_on"]]
    dependants = [a["name"] for a in model["assets"] if primary["id"] in a["depends_on"]]
    related = dependants or deps
    data = _names(model, primary["data"]) or [n for a in model["assets"] for n in _names(model, a["data"])][:2]
    first = lambda kinds: (_kinds(model, kinds) or [None])[0]
    idp, vendor, storage, repo = first(["idp", "sso", "directory", "email"]), first(["vendor", "supplier", "saas", "dependency"]), first(["storage", "bucket", "share"]), first(["repo", "ci", "pipeline"])
    return {
        "primary": primary["name"],
        "data": " and ".join(data) if data else "sensitive data (none listed in your model: decide what it would be)",
        "dependency": ", ".join(related) if related else "other systems (your model lists no dependants: who would be next?)",
        "idp": (idp or primary)["name"], "vendor": (vendor or primary)["name"], "storage": (storage or primary)["name"], "repo": (repo or primary)["name"],
    }


def fill(text, vals):
    for k, v in vals.items():
        text = text.replace("{" + k + "}", v)
    return text


def probes_for(model, scen, vals):
    have, out = set(model["controls"]), []
    for ctrl, q in scen.get("control_probes", {}).get("present", {}).items():
        if ctrl in have:
            out.append(fill(q, vals))
    for ctrl, q in scen.get("control_probes", {}).get("missing", {}).items():
        if ctrl not in have and not (ctrl == "backups" and "immutable-backups" in have):
            out.append(fill(q, vals))
    return out


def build(model, scen, seed=1):
    rng = random.Random(f"{seed}:{scen['id']}")
    primary = pick_primary(model, scen, rng)
    vals = fill_values(model, primary, scen, rng)
    injects = []
    for n, inj in enumerate(scen["injects"], 1):
        injects.append({"n": n, "t": inj["t"], "title": inj["title"], "text": fill(inj["text"], vals),
                        "questions": [fill(q, vals) for q in inj["questions"]]})
    extra = probes_for(model, scen, vals)
    if extra:
        injects[min(1, len(injects) - 1)]["questions"] += extra
    ex = {"id": scen["id"], "title": fill(scen["title"], vals), "summary": scen["summary"], "model": model["name"],
          "primary_asset": primary["id"], "objectives": scen["objectives"], "roles": model["roles"] or DEFAULT_ROLES,
          "roles_defaulted": not model["roles"], "injects": injects, "control_questions": extra}
    for s in [ex["title"]] + [i["text"] for i in injects] + [q for i in injects for q in i["questions"]]:
        left = PLACEHOLDER.findall(s)
        if left:
            raise ValueError(f"scenario {scen['id']}: unfilled placeholder {left[0]} in {s[:60]!r}")
    return ex


def applicable_list(model):
    out = []
    for s in load_catalog():
        ok, why = applicable(model, s)
        out.append({"id": s["id"], "title": s["title"], "summary": s["summary"], "applies": ok, "reason": why})
    return out
