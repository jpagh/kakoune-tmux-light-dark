#!/usr/bin/env python3
"""Tests for scripts/tmux-notify.sh, the payload of the tmux theme hooks.

A stub `kak` stands in for the real binary, so these run without tokio, tmux or
Kakoune: they check who gets told, and that nothing is queried.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "tmux-notify.sh"

KAK_STUB = """#!/bin/sh
case "$1" in
    -l) cat "$TEST_SESSIONS" ;;
    -p) shift; session=$1; cat >> "$TEST_PUSHED" <<EOF
$session
EOF
        cat > "$TEST_PAYLOADS/$(printf '%s' "$session")" ;;
    *) exit 1 ;;
esac
"""

TMUX_STUB = """#!/bin/sh
echo "tmux $*" >> "$TEST_TMUX_CALLS"
exit 0
"""


class NotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lt-test-notify-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.payloads = self.root / "payloads"
        self.payloads.mkdir()
        self.sessions = self.root / "sessions"
        self.pushed = self.root / "pushed"
        self.pushed.touch()
        self.tmux_calls = self.root / "tmux-calls"
        for name, body in (("kak", KAK_STUB), ("tmux", TMUX_STUB)):
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            TEST_SESSIONS=str(self.sessions),
            TEST_PUSHED=str(self.pushed),
            TEST_PAYLOADS=str(self.payloads),
            TEST_TMUX_CALLS=str(self.tmux_calls),
        )

    def run_notify(self, *args):
        return subprocess.run(["sh", str(SCRIPT), *args], env=self.env,
                              capture_output=True, text=True)

    def sessions_listing(self, *names):
        self.sessions.write_text("".join(name + "\n" for name in names))

    def test_pushes_to_every_live_session(self):
        self.sessions_listing("alpha", "beta")
        result = self.run_notify("dark")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(self.pushed.read_text().split()), ["alpha", "beta"])
        self.assertEqual(self.payloads.joinpath("alpha").read_text(), "appearance-detected dark\n")
        self.assertEqual(self.payloads.joinpath("beta").read_text(), "appearance-detected dark\n")

    def test_skips_dead_sessions(self):
        self.sessions_listing("alive", "gone (dead)")
        result = self.run_notify("light")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pushed.read_text().split(), ["alive"])
        self.assertFalse((self.payloads / "gone").exists())

    def test_mode_comes_from_the_hook_name_not_a_query(self):
        self.sessions_listing("alpha")
        self.run_notify("light")
        self.assertFalse(self.tmux_calls.exists(), "notify must not query tmux")

    def test_unknown_mode_is_ignored(self):
        self.sessions_listing("alpha")
        result = self.run_notify("purple")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pushed.read_text(), "")
        self.sessions_listing("alpha")
        self.assertEqual(self.run_notify().returncode, 0, "no argument must be harmless")
        self.assertEqual(self.pushed.read_text(), "")

    def test_no_sessions_is_harmless(self):
        self.sessions_listing()
        result = self.run_notify("dark")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pushed.read_text(), "")

    def test_missing_kak_is_harmless(self):
        self.sessions_listing("alpha")
        self.env["PATH"] = "/usr/bin:/bin"  # keeps sh, drops the stub
        result = subprocess.run(["sh", str(SCRIPT), "dark"], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
