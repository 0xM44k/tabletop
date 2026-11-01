"""Browser tests for the generated facilitator page (headless Chrome/Chromium via Playwright).

Skipped automatically when Playwright or a browser is not available, so the
rest of the suite still runs with the standard library only. Set
TABLETOP_CHROME to a browser executable to override discovery.
"""
import json, os, shutil, sys, tempfile, unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from tabletop.generate import build, load_catalog
from tabletop.model import load_model
from tabletop.output import to_html

try:
    from playwright.sync_api import sync_playwright
except ImportError:               # pragma: no cover
    sync_playwright = None


def find_browser():
    env = os.environ.get("TABLETOP_CHROME")
    if env and os.path.exists(env):
        return env
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


@unittest.skipIf(sync_playwright is None, "playwright is not installed")
class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        exe = find_browser()
        try:
            cls.browser = cls.pw.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else cls.pw.chromium.launch()
        except Exception as e:                       # no usable browser
            cls.pw.stop()
            raise unittest.SkipTest(f"no usable browser: {str(e)[:80]}")
        cat = {s["id"]: s for s in load_catalog()}
        ex = build(load_model(os.path.join(ROOT, "examples", "acme.json")), cat["ransomware"], 1)
        cls.ex = ex
        cls.path = os.path.join(tempfile.mkdtemp(), "ex.html")
        with open(cls.path, "w", encoding="utf-8") as fh:
            fh.write(to_html(ex))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def open(self, fake_clock=True):
        ctx = self.browser.new_context()
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        self.errors = []
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        if fake_clock:
            page.clock.install()
        page.goto("file://" + self.path)
        return page

    def add_gap(self, page, title, owner="", due=""):
        page.fill("#g-title", title)
        page.fill("#g-owner", owner)
        page.fill("#g-due", due)
        page.press("#g-title", "Enter")

    def test_summary_with_timing_decisions_and_gaps(self):
        page = self.open()
        page.click("#start")
        page.clock.run_for(65_000)
        page.click("#next")
        page.clock.run_for(125_000)
        page.click("#next")
        page.clock.run_for(30_000)
        page.fill("#n0", "Isolated the file server")
        page.fill("#d1", "Call outside counsel - Head of engineering - 10:15")
        self.add_gap(page, "No offline backup", "Alice", "2026-12-01")
        self.add_gap(page, "Nobody owns comms", "alice")
        self.add_gap(page, "Unclear authority")
        s = page.evaluate("window.__tabletop.summary()")
        self.assertEqual((s["elapsed"], s["revealed"], s["total"]), (220, 2, len(self.ex["injects"])))
        r0, r1 = s["rows"]
        self.assertEqual((r0["at"], r0["spent"], r0["notes"], r0["decision"]), (65, 125, True, False))
        self.assertEqual((r1["at"], r1["spent"], r1["notes"], r1["decision"]), (190, 30, False, True))
        self.assertEqual(s["noDecision"], [f"1. {self.ex['injects'][0]['title']}"])
        self.assertEqual((s["gaps"], s["unassigned"], s["noDue"]), (3, 1, 2))
        self.assertEqual(s["owners"], [{"name": "Alice", "count": 2}])            # case-insensitive grouping
        text = page.inner_text("#summary-body")
        self.assertIn("Injects revealed: 2 of", text)
        self.assertIn("01:05", text)
        self.assertIn("02:05", text)
        md = page.evaluate("window.__tabletop.md()")
        self.assertIn("## After-action summary", md)
        self.assertLess(md.index("## After-action summary"), md.index("## Injects"))
        self.assertIn("Gaps by owner: Alice 2", md)
        self.assertIn("| 1 |", md)
        self.assertEqual(self.errors, [])

    def test_visible_summary_updates_as_notes_and_decisions_are_typed(self):
        page = self.open()
        page.click("#next")
        cells = page.locator("#summary-body tbody tr").first.locator("td")
        self.assertEqual((cells.nth(4).inner_text(), cells.nth(5).inner_text()), ("none", "none"))
        page.fill("#n0", "something")
        self.assertEqual(cells.nth(4).inner_text(), "yes")
        page.fill("#d0", "a decision")
        self.assertEqual(cells.nth(5).inner_text(), "yes")
        self.assertIn("1 of 1", page.inner_text("#summary-body"))
        page.fill("#d0", "   ")
        self.assertEqual(cells.nth(5).inner_text(), "none")                     # whitespace is not a decision
        self.assertIn("(no decision recorded for: 1.", page.inner_text("#summary-body"))

    def test_untimed_when_the_clock_never_started(self):
        page = self.open()
        page.click("#next")
        s = page.evaluate("window.__tabletop.summary()")
        self.assertEqual((s["rows"][0]["at"], s["rows"][0]["spent"]), (None, None))
        self.assertIn("not timed", page.inner_text("#summary-body"))

    def test_empty_state(self):
        page = self.open()
        s = page.evaluate("window.__tabletop.summary()")
        self.assertEqual((s["revealed"], s["gaps"], s["rows"], s["noDecision"]), (0, 0, [], []))
        self.assertIn("Injects revealed: 0 of", page.inner_text("#summary-body"))
        self.assertEqual(self.errors, [])

    def test_reload_keeps_timing(self):
        page = self.open()
        page.click("#start")
        page.clock.run_for(20_000)
        page.click("#next")
        page.clock.run_for(10_000)
        page.click("#start")                      # pause: also saves
        page.reload()
        s = page.evaluate("window.__tabletop.summary()")
        self.assertEqual((s["revealed"], s["rows"][0]["at"]), (1, 20))
        self.assertEqual(self.errors, [])

    def test_state_saved_by_an_older_page_still_loads(self):
        page = self.open(fake_clock=False)
        key = f"tabletop:{self.ex['id']}:{self.ex['model']}"
        page.evaluate("([k]) => localStorage.setItem(k, JSON.stringify({revealed: 2, notes: {0: 'old note'}, decisions: {}, gaps: [{title: 'g', owner: '', due: ''}], elapsed: 300}))", [key])
        page.reload()
        s = page.evaluate("window.__tabletop.summary()")
        self.assertEqual((s["revealed"], s["rows"][0]["at"], s["gaps"]), (2, None, 1))
        self.assertTrue(s["rows"][0]["notes"])
        self.assertEqual(self.errors, [])
        # revealing one more inject now records its time
        page.click("#next")
        self.assertEqual(page.evaluate("window.__tabletop.summary().rows[2].at"), 300)

    def test_user_text_is_inert_and_pipes_do_not_break_markdown(self):
        page = self.open()
        self.add_gap(page, "x", "<img src=x onerror=window.__pwned=1>|bob", "soon")
        self.assertEqual(page.locator("#summary-body img").count(), 0)
        self.assertFalse(page.evaluate("!!window.__pwned"))
        self.assertIn("<img", page.inner_text("#summary-body"))
        md = page.evaluate("window.__tabletop.md()")
        line = [l for l in md.splitlines() if l.startswith("- Gaps by owner")][0]
        self.assertNotIn("|", line)
        self.assertEqual(self.errors, [])

    def test_clear_resets_timing(self):
        page = self.open(fake_clock=False)
        page.once("dialog", lambda d: d.accept())
        page.click("#next")
        page.click("#clear")
        page.wait_for_load_state()
        self.assertEqual(page.evaluate("window.__tabletop.summary().revealed"), 0)
        self.assertEqual(page.evaluate("Object.keys(window.__tabletop.state().revealedAt).length"), 0)


if __name__ == "__main__":
    unittest.main()
