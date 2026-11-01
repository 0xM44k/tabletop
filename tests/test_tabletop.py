import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from tabletop.generate import applicable, applicable_list, build, load_catalog
from tabletop.model import ModelError, load_model, validate
from tabletop.output import to_html, to_markdown

EX = os.path.join(ROOT, "examples", "acme.json")
CAT = {s["id"]: s for s in load_catalog()}


def model():
    return load_model(EX)


class Model(unittest.TestCase):
    def raw(self):
        return json.load(open(EX))

    def test_valid(self):
        self.assertEqual(model()["name"], "Fictional SaaS company (example)")

    def test_validation_errors(self):
        cases = []
        r = self.raw(); r["assets"][0]["depends_on"] = ["ghost"]; cases.append(r)
        r = self.raw(); r["assets"][1]["data"] = ["nope"]; cases.append(r)
        r = self.raw(); r["assets"][1]["id"] = "web"; cases.append(r)
        r = self.raw(); r["assets"][0]["id"] = "bad id!"; cases.append(r)
        r = self.raw(); del r["name"]; cases.append(r)
        r = self.raw(); r["assets"] = []; cases.append(r)
        r = self.raw(); r["controls"] = "mfa"; cases.append(r)
        for c in cases:
            with self.assertRaises(ModelError):
                validate(c)

    def test_bad_file(self):
        with self.assertRaises(ModelError):
            load_model("/nonexistent.json")
        p = os.path.join(tempfile.mkdtemp(), "m.json"); open(p, "w").write("{")
        with self.assertRaises(ModelError):
            load_model(p)


class Generate(unittest.TestCase):
    def test_every_scenario_builds_with_no_placeholders_for_full_model(self):
        for sid, s in CAT.items():
            ex = build(model(), s, 1)
            blob = json.dumps(ex)
            self.assertNotIn("{", blob.replace('{"', "").replace("{\\", ""), sid)   # no leftover {placeholder}
            self.assertGreaterEqual(len(ex["injects"]), 4)

    def test_every_scenario_builds_for_minimal_models_where_applicable(self):
        mini = validate({"name": "m", "assets": [{"id": "a" + k, "name": "Thing " + k, "kind": k} for k in ("server", "idp", "repo", "vendor", "storage")] + [{"id": "p", "name": "Public", "kind": "application", "internet_facing": True}]})
        for sid, s in CAT.items():
            ok, _ = applicable(mini, s)
            if ok:
                build(mini, s, 3)                      # must not raise (e.g. empty data classes)

    def test_applicability_follows_model(self):
        bare = validate({"name": "m", "assets": [{"id": "a", "name": "Laptop", "kind": "endpoint"}]})
        ap = {x["id"]: x["applies"] for x in applicable_list(bare)}
        self.assertTrue(ap["ransomware"])
        self.assertFalse(ap["identity"] or ap["web-exfil"] or ap["vendor"] or ap["storage-exposure"])

    def test_primary_is_data_heavy_asset_and_deterministic(self):
        a, b = build(model(), CAT["ransomware"], 1), build(model(), CAT["ransomware"], 1)
        self.assertEqual(a, b)
        self.assertEqual(a["primary_asset"], "db")
        self.assertIn("Customer web app", a["injects"][1]["text"])          # dependants named

    def test_control_probes_use_the_model(self):
        ex = build(model(), CAT["ransomware"], 1)                           # has edr and backups, lacks immutable backups
        qs = " ".join(ex["control_questions"])
        self.assertIn("EDR", qs)
        self.assertNotIn("immutable backups. When did", qs)
        m = model(); m["controls"] = ["immutable-backups"]
        self.assertIn("When did anyone last restore", " ".join(build(m, CAT["ransomware"], 1)["control_questions"]))
        m["controls"] = []
        self.assertIn("no backups at all", " ".join(build(m, CAT["ransomware"], 1)["control_questions"]))

    def test_missing_roles_flagged_and_defaulted(self):
        m = model(); m["roles"] = []
        ex = build(m, CAT["ddos"], 1)
        self.assertTrue(ex["roles_defaulted"])
        self.assertTrue(ex["roles"])


class Output(unittest.TestCase):
    def test_markdown_has_all_sections(self):
        md = to_markdown(build(model(), CAT["identity"], 1))
        for s in ("## Objectives", "## Roles in the room", "## Inject 1", "## Inject 5", "## After-action review"):
            self.assertIn(s, md)

    def test_html_is_inert_and_self_contained(self):
        m = model(); m["assets"][0]["name"] = "</script><img src=x onerror=alert(1)>"
        h = to_html(build(m, CAT["web-exfil"], 1))
        data = h.split('id="data">')[1].split("</script>")[0]
        self.assertNotIn("<", data)
        self.assertNotRegex(h, r'(src|href)="https?://')
        self.assertNotIn("innerHTML", h)


class Cli(unittest.TestCase):
    def run_cli(self, *a):
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
        return subprocess.run([sys.executable, "-m", "tabletop", *a], capture_output=True, text=True, env=env)

    def test_cli(self):
        self.assertEqual(self.run_cli("list", EX).returncode, 0)
        self.assertEqual(self.run_cli("generate", EX, "--scenario", "ddos", "--format", "md").returncode, 0)
        self.assertEqual(self.run_cli("generate", EX, "--scenario", "nope").returncode, 2)
        bare = os.path.join(tempfile.mkdtemp(), "m.json")
        json.dump({"name": "m", "assets": [{"id": "a", "name": "Laptop", "kind": "endpoint"}]}, open(bare, "w"))
        p = self.run_cli("generate", bare, "--scenario", "identity")
        self.assertEqual(p.returncode, 2)
        self.assertIn("does not fit", p.stderr)


if __name__ == "__main__":
    unittest.main()
