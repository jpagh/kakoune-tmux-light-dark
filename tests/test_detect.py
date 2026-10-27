#!/usr/bin/env python3
"""scripts/detect-theme.sh: tmux first, the OS appearance as the fallback."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "detect-theme.sh"


class DetectTest(unittest.TestCase):
    def run_detect(self, tmux_theme, os_theme="light", darwin=True):
        tmp = tempfile.TemporaryDirectory(prefix="detect-")
        self.addCleanup(tmp.cleanup)
        binn = Path(tmp.name) / "bin"
        binn.mkdir()
        stubs = {
            "tmux": f"#!/bin/sh\nprintf '%s\\n' '{tmux_theme}'\n",
            "defaults": ("#!/bin/sh\n"
                         'if [ "${OS_THEME}" = dark ]; then echo Dark; exit 0; fi\n'
                         "exit 1\n"),
            "uname": f"#!/bin/sh\n{'echo Darwin' if darwin else 'echo Linux'}\n",
        }
        for name, body in stubs.items():
            path = binn / name
            path.write_text(body)
            path.chmod(0o755)
        env = dict(os.environ, PATH=f"{binn}{os.pathsep}{os.environ['PATH']}",
                   OS_THEME=os_theme)
        result = subprocess.run(["sh", str(SCRIPT)], capture_output=True, text=True, env=env)
        return result.returncode, result.stdout.strip()

    def test_tmux_wins_when_it_answers(self):
        self.assertEqual(self.run_detect("dark", os_theme="light"), (0, "dark"))
        self.assertEqual(self.run_detect("light", os_theme="dark"), (0, "light"))

    def test_falls_back_to_the_os_when_tmux_is_silent(self):
        self.assertEqual(self.run_detect("", os_theme="dark"), (0, "dark"))
        self.assertEqual(self.run_detect("", os_theme="light"), (0, "light"))

    def test_falls_back_for_an_unknown_client_theme(self):
        self.assertEqual(self.run_detect("unknown", os_theme="dark"), (0, "dark"))

    def test_reports_nothing_when_no_source_answers(self):
        self.assertEqual(self.run_detect("", os_theme="light", darwin=False)[0], 1)


if __name__ == "__main__":
    unittest.main()
