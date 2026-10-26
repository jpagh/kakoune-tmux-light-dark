#!/usr/bin/env python3
"""The "never any polling" invariant, as a test.

The plugin's whole premise is that tmux tells us when the scheme changes. A
timer anywhere would defeat that, so this fails the build if one reappears.
"""
import re
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parent.parent
SOURCES = sorted(REPO.glob("rc/*.kak")) + sorted(REPO.glob("scripts/*.sh"))

# Timers and interval mechanisms, from any layer we might reach for.
FORBIDDEN = {
    r"\bsleep\b": "a sleep/timer loop",
    r"\bStartInterval\b": "a launchd StartInterval",
    r"\bWatchPaths\b": "a launchd WatchPaths watch",
    r"set[-_]?[Ii]nterval": "an interval hook",
    r"\brepeat-commands\b": "a repeating command",
    r"--interval\b": "an interval flag",
}


class NoPollingTest(unittest.TestCase):
    def test_sources_exist(self):
        self.assertEqual(len(SOURCES), 2, f"expected rc + script, found {SOURCES}")

    def test_no_timer_anywhere(self):
        for path in SOURCES:
            text = path.read_text()
            for pattern, description in FORBIDDEN.items():
                with self.subTest(file=path.name, pattern=pattern):
                    self.assertIsNone(
                        re.search(pattern, text),
                        f"{path.name} contains {description} ({pattern!r})")

    def test_no_retry_loop_around_a_query(self):
        """A `while` loop wrapping a query is polling by another name."""
        for path in SOURCES:
            text = path.read_text()
            for match in re.finditer(r"while\b.*?\bdone\b", text, re.S):
                body = match.group(0)
                with self.subTest(file=path.name):
                    self.assertNotRegex(
                        body, r"(tmux display|defaults read|darkman|gsettings)",
                        "a loop re-queries the scheme; that is polling")

    def test_the_only_loop_is_over_sessions(self):
        """The one loop allowed iterates Kakoune's session list, once."""
        text = (REPO / "scripts" / "tmux-notify.sh").read_text()
        self.assertEqual(len(re.findall(r"\bwhile\b", text)), 1)
        self.assertIn('"$kak" -l', text)


if __name__ == "__main__":
    unittest.main()
