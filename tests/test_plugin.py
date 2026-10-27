#!/usr/bin/env python3
"""The plugin inside real Kakoune sessions, with a stub `tmux`.

Nothing here polls, so nothing here waits on a timer: the mode is either queried
once at enable or pushed by `appearance-detected`.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid

REPO = Path(__file__).resolve().parent.parent

# `tmux display -p '#{client_theme}'` answers from a file; hook install/uninstall
# is recorded so the test can see exactly what was registered.
TMUX_STUB = """#!/bin/sh
echo "tmux $*" >> "$TEST_TMUX_LOG"
case "$1" in
    display) cat "$TEST_CLIENT_THEME" ;;
    *) exit 0 ;;
esac
"""


class Session:
    """One Kakoune server with the plugin loaded, plus helpers to poke it."""

    def __init__(self, testcase, *, client_theme="light", tmux=True):
        self.testcase = testcase
        self.tmp = tempfile.TemporaryDirectory(prefix="lt-test-kak-")
        testcase.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config = self.root / "kak"
        (config / "colors").mkdir(parents=True)
        # The colourschemes record which one ran, so assertions do not depend on
        # any palette's RGB values.
        for name in ("test-dark", "test-light"):
            (config / "colors" / f"{name}.kak").write_text(
                f"set-option global test_marker {name}\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        tmux_stub = self.bin / "tmux"
        tmux_stub.write_text(TMUX_STUB)
        tmux_stub.chmod(0o755)
        self.tmux_log = self.root / "tmux.log"
        self.hook_log = self.root / "hooks.log"
        self.theme_file = self.root / "client-theme"
        self.theme_file.write_text(client_theme)
        (config / "kakrc").write_text(f"""
declare-option str test_marker ''
source {REPO}/rc/appearance.kak
set-option global appearance_dark_theme 'test-dark'
set-option global appearance_light_theme 'test-light'
hook global User appearance-dark %{{ nop %sh{{ echo dark >> "$TEST_HOOK_LOG" }} }}
hook global User appearance-light %{{ nop %sh{{ echo light >> "$TEST_HOOK_LOG" }} }}
try %{{ appearance-enable }}
""")
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.root),
                        PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                        TEST_TMUX_LOG=str(self.tmux_log),
                        TEST_HOOK_LOG=str(self.hook_log),
                        TEST_CLIENT_THEME=str(self.theme_file))
        self.env.pop("TMUX", None)
        if tmux:
            self.env["TMUX"] = "/tmp/tmux-501/default,1,0"
        self.kak = shutil.which("kak")
        self.name = "lt-" + uuid.uuid4().hex[:8]
        self.server = subprocess.Popen(
            [self.kak, "-d", "-s", self.name], env=self.env, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        testcase.addCleanup(self._stop)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            listing = subprocess.run([self.kak, "-l"], capture_output=True, text=True,
                                     env=self.env).stdout.splitlines()
            if self.name in listing:
                break
            time.sleep(0.05)
        else:
            testcase.fail("Kakoune session never started")
        time.sleep(0.3)

    def _stop(self):
        if self.server.poll() is None:
            try:
                self.send("kill!")
            except AssertionError:
                self.server.kill()
        try:
            self.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.server.kill()
        self.server.stderr.close()

    def send(self, command):
        result = subprocess.run([self.kak, "-p", self.name], input=command + "\n",
                                text=True, capture_output=True, env=self.env)
        self.testcase.assertEqual(result.returncode, 0, result.stderr)

    def option(self, name):
        out = self.root / f"{uuid.uuid4().hex}.opt"
        self.send(f'echo -to-file {out} "%opt{{{name}}}"')
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if out.exists():
                return out.read_text().strip()
            time.sleep(0.02)
        self.testcase.fail(f"option {name} never read back")

    def hooks(self):
        return self.hook_log.read_text().split() if self.hook_log.exists() else []

    def tmux_calls(self):
        return self.tmux_log.read_text() if self.tmux_log.exists() else ""


class EnableTest(unittest.TestCase):
    def test_enable_applies_the_reported_scheme(self):
        session = Session(self, client_theme="light")
        self.assertEqual(session.option("appearance_enabled"), "true")
        self.assertEqual(session.option("appearance_mode"), "light")
        self.assertEqual(session.option("test_marker"), "test-light")
        self.assertEqual(session.hooks(), ["light"])

    def test_enable_registers_both_hooks_at_reserved_indexes(self):
        session = Session(self)
        calls = session.tmux_calls()
        self.assertIn("[50]", calls)
        self.assertIn("client-dark-theme[50]", calls)
        self.assertIn("client-light-theme[50]", calls)
        self.assertIn("tmux-notify.sh dark", calls)
        self.assertIn("tmux-notify.sh light", calls)

    def test_dark_is_applied_when_tmux_reports_dark(self):
        session = Session(self, client_theme="dark")
        self.assertEqual(session.option("appearance_mode"), "dark")
        self.assertEqual(session.option("test_marker"), "test-dark")

    def test_refuses_without_tmux(self):
        session = Session(self, tmux=False)
        self.assertEqual(session.option("appearance_enabled"), "false")
        self.assertEqual(session.option("appearance_mode"), "")
        self.assertEqual(session.tmux_calls(), "", "must not touch tmux")

    def test_refuses_when_tmux_reports_no_scheme(self):
        session = Session(self, client_theme="unknown")
        self.assertEqual(session.option("appearance_enabled"), "false")
        self.assertEqual(session.option("appearance_mode"), "")


class SwitchTest(unittest.TestCase):
    def test_detected_event_switches_and_is_idempotent(self):
        session = Session(self, client_theme="light")
        session.send("appearance-detected dark")
        self.assertEqual(session.option("appearance_mode"), "dark")
        self.assertEqual(session.option("test_marker"), "test-dark")
        self.assertEqual(session.hooks(), ["light", "dark"])
        # One transition fires the tmux hook several times; repeats must be free.
        session.send("appearance-detected dark")
        session.send("appearance-detected dark")
        self.assertEqual(session.hooks(), ["light", "dark"])
        session.send("appearance-detected light")
        self.assertEqual(session.option("test_marker"), "test-light")
        self.assertEqual(session.hooks(), ["light", "dark", "light"])

    def test_same_mode_refresh_reconciles_without_public_notification(self):
        session = Session(self, client_theme="light")
        session.send("set-option global appearance_reconcile_command 'set-option global test_marker reconciled'")
        session.send("appearance-refresh")
        self.assertEqual(session.option("test_marker"), "reconciled")
        self.assertEqual(session.hooks(), ["light"])

    def test_unknown_mode_is_ignored(self):
        session = Session(self, client_theme="light")
        session.send("appearance-detected purple")
        self.assertEqual(session.option("appearance_mode"), "light")
        self.assertEqual(session.hooks(), ["light"])

    def test_refresh_requeries_tmux(self):
        session = Session(self, client_theme="light")
        session.theme_file.write_text("dark")
        session.send("appearance-refresh")
        self.assertEqual(session.option("appearance_mode"), "dark")

    def test_disable_removes_only_our_hooks(self):
        session = Session(self)
        session.send("appearance-disable")
        self.assertEqual(session.option("appearance_enabled"), "false")
        calls = session.tmux_calls()
        self.assertIn("-gu client-dark-theme[50]", calls)
        self.assertIn("-gu client-light-theme[50]", calls)
        # Events after disabling do nothing.
        session.send("appearance-detected dark")
        self.assertEqual(session.option("appearance_mode"), "")
        self.assertEqual(session.hooks(), ["light"])


if __name__ == "__main__":
    unittest.main()
