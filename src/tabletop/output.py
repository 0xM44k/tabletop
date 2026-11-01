from __future__ import annotations

import json
import os


def to_markdown(ex):
    out = [f"# Tabletop exercise: {ex['title']}", "", f"System: {ex['model']}", "", ex["summary"], "", "## Objectives", ""]
    out += [f"- {o}" for o in ex["objectives"]]
    out += ["", "## Roles in the room", ""] + [f"- {r}" for r in ex["roles"]]
    if ex["roles_defaulted"]:
        out.append("\n(Your model listed no roles, so these are defaults. Replace them with real names.)")
    out += ["", "## Facilitator guidance", "", "- Referee, do not command. Ask the questions; do not supply answers.",
            "- Keep it blameless. Write down every gap, owner and decision.", "- Reveal one inject at a time. Let the room finish before moving on.", ""]
    for i in ex["injects"]:
        out += [f"## Inject {i['n']} (about T+{i['t']} min): {i['title']}", "", i["text"], "", "Questions:", ""]
        out += [f"- {q}" for q in i["questions"]] + ["", "Notes:", "", "Decision / owner / time:", ""]
    out += ["## After-action review", "", "| Gap found | Owner | Due | Fix |", "| --- | --- | --- | --- |", "| | | | |", ""]
    return "\n".join(out)


def to_html(ex):
    with open(os.path.join(os.path.dirname(__file__), "facilitator.html"), "r", encoding="utf-8") as fh:
        tpl = fh.read()
    payload = json.dumps(ex, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace("__DATA__", payload, 1).replace("__TITLE__", "Tabletop facilitator")
