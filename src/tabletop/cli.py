from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .generate import applicable_list, build, load_catalog
from .model import ModelError, load_model
from .output import to_html, to_markdown


def main(argv=None):
    p = argparse.ArgumentParser(prog="tabletop", description="Generate incident-response tabletop exercises from your own system model. Offline; reads one JSON file.")
    p.add_argument("--version", action="version", version=f"tabletop {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="show which scenarios fit your model"); ls.add_argument("model")
    g = sub.add_parser("generate", help="build an exercise"); g.add_argument("model"); g.add_argument("--scenario", required=True)
    g.add_argument("--seed", type=int, default=1); g.add_argument("--format", choices=["html", "md", "json"], default="html"); g.add_argument("-o", "--output")
    a = p.parse_args(argv)
    try:
        model = load_model(a.model)
        if a.cmd == "list":
            for s in applicable_list(model):
                print(f"{'yes' if s['applies'] else 'no ':<4}{s['id']:<18}{s['summary'] if s['applies'] else s['reason']}")
            return 0
        cat = {s["id"]: s for s in load_catalog()}
        if a.scenario not in cat:
            raise ModelError(f"unknown scenario {a.scenario!r}; choose from {', '.join(cat)}")
        from .generate import applicable
        ok, why = applicable(model, cat[a.scenario])
        if not ok:
            raise ModelError(f"scenario {a.scenario!r} does not fit this model: {why}")
        ex = build(model, cat[a.scenario], a.seed)
    except (ModelError, ValueError) as e:
        print(f"tabletop: {e}", file=sys.stderr)
        return 2
    body = to_html(ex) if a.format == "html" else to_markdown(ex) if a.format == "md" else json.dumps(ex, indent=2)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"tabletop: wrote {a.output}", file=sys.stderr)
    else:
        sys.stdout.write(body)
    return 0
