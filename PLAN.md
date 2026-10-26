# Plan v5: `kakoune-tmux-light-dark` — OS/terminal light-dark for Kakoune, via tmux

Supersedes v1–v4. The tmux-only scope collapses the design to one backend.
Repo: **public**, `github.com/jpagh/kakoune-tmux-light-dark`, developed at
`~/Projects/kakoune-tmux-light-dark`.

## Scope decision

**The plugin requires tmux.** That is a deliberate limitation, accepted as
reasonable scope. It removes, entirely:

- launchd, LaunchAgents, `WatchPaths`, plist generation, `launchctl`
- the Swift KVO watcher and `swiftc`
- `defaults read -g AppleInterfaceStyle`
- darkman, `dbus-monitor`, `stdbuf`, gsettings
- per-OS code paths, per-session watchers, FIFOs, PID files, watchdogs
- all polling

One backend, identical on macOS and Linux.

## Why tmux is the right requirement (all measured)

tmux is already light/dark aware — it is how `themeblack` / `themeyellow` in your
status line resolve. It exposes both the state and the event:

| Fact | Evidence |
|---|---|
| Current state | `tmux show-options -gv theme` → `detect`; `tmux display -p '#{client_theme}'` → `light` |
| Transition hooks exist | `client-dark-theme`, `client-light-theme` |
| They fire on a real transition | armed both hooks, one forward+backward flip produced **13 fires**, every one carrying the correct `#{client_theme}` (`dark`×6, `light`×7) |
| They do *not* fire on option changes | forcing `theme dark` / `light` / `detect` produced none — only a real client report counts |
| Hook environment is usable | `run-shell` receives the full login `PATH`, so `kak` resolves to `/opt/homebrew/bin/kak` with no absolute-path hack |
| Non-destructive install | `set-hook -g client-dark-theme[50] …` coexists with a user hook at `[0]`, and `set-hook -gu client-dark-theme[50]` removes only ours (verified both ways) |
| Terminal truth, not OS truth | `#{client_theme}` follows what the terminal reports (Ghostty → tmux via mode 2031), which is what the original request asked for |

This also explains two earlier observations:

- **pi tracks Ghostty instantly inside a tmux pane** because it writes
  `ESC[?2031h`, parses `CSI ?997;1|2n`, and reads OSC 11 for the palette — it is
  the TUI and owns the tty.
- **Kakoune cannot do that**: its binaries contain zero occurrences of `2031`,
  `]11;`, `?997`, and a plugin's `%sh{}` has no tty access. But tmux can, and it
  will tell us — so Kakoune doesn't need to.

Note the tmux behaviour also means the `fresh` finding in
`.scratch/terminal-palette-contrast/issues/06-appearance-tracking.md` has a
narrower scope than it states: OSC colour *queries* are indeed swallowed by
tmux, but tmux re-broadcasts the 2031/997 *protocol*, and exposes it as hooks.

## Viability criterion — one command, any machine

```sh
tmux display -p '#{client_theme}'      # dark | light  → supported
                                       # unknown       → not supported
```

That single test decides whether the plugin can work in a given environment, and
`appearance-enable` runs it: if it is not `dark`/`light`, enable refuses once
with the reason and installs nothing. This is how fedora-air gets verified
(needs foot to report its scheme to tmux).

## Interface

```kak
set-option global appearance_dark_theme  'beautiful-tomorrow-night'
set-option global appearance_light_theme 'beautiful-tomorrow-light'
appearance-enable
```

| Option | Default | Notes |
|---|---|---|
| `appearance_dark_theme` | `default` | plugin-owned; Kakoune itself has no theme option (`colorscheme` is a command, `options.asciidoc` has no colour/theme entry) |
| `appearance_light_theme` | `default` | as above |

| Command | Purpose |
|---|---|
| `appearance-enable` | verify tmux + `client_theme`, install hooks, apply current mode |
| `appearance-disable` | remove our two hook indexes |
| `appearance-refresh` | one-shot re-query + apply |
| `appearance-detected <dark\|light>` | entry point the tmux hook calls |

| Hook | Fires after the mode is applied |
|---|---|
| `User appearance-dark` | dark applied |
| `User appearance-light` | light applied |

The theme package uses those hooks for Giallo, so the plugin never learns that
Giallo — or Tomorrow — exists:

```kak
hook global User appearance-dark  %{ tomorrow-giallo-sync beautiful-tomorrow-night }
hook global User appearance-light %{ tomorrow-giallo-sync beautiful-tomorrow-light }
```

## Behaviour

- **Enable**: one `tmux display -p '#{client_theme}'` (a query, not a timer),
  then apply. Installs `client-dark-theme[50]` and `client-light-theme[50]`.
- **Hook payload carries the mode literally** — `run-shell "…/tmux-notify.sh dark"`
  — because the hook *name* is authoritative. No `tmux display` subprocess on the
  event path, and no ambiguity when several clients disagree.
- **Push to every live session**: `kak -l`, skip entries ending in `(dead)`,
  `kak -p` each. The agent therefore needs no session registry.
- **Dedupe**: `appearance-detected` compares against the applied mode and returns
  before calling `colorscheme` if unchanged. This is required, not defensive:
  one transition fires the hook 2–4 times (13 fires for two flips, measured).
- **Disable**: unset only our indexes. No state files, no FIFOs, no PIDs.
- **Refuse when unsupported**: no `$TMUX`, or `client_theme` is `unknown`, or
  tmux lacks the hook → one message, nothing installed, theme untouched.

## Files

```
~/Projects/kakoune-tmux-light-dark/
├── rc/appearance.kak         options, commands, User hooks, enable/disable
├── scripts/tmux-notify.sh    what the tmux hook runs: mode → every live session
├── tests/                    hermetic suite + the no-polling guard
├── README.md
└── PLAN.md
```

That is the whole plugin: one script, one rc file.

## No-polling guard

A test scans the shipped files and fails on any polling shape: `sleep`, a `while`
loop around a detection command, `set-hook … interval`, `StartInterval`,
`WatchPaths`. The constraint stays executable.

## Tests

Hermetic:

- `tmux-notify.sh` against a stub `kak`: pushes `appearance-detected dark` to
  every live session, skips `(dead)` lines, ignores a junk mode, exits 0 when no
  sessions exist, and never calls `tmux` (the mode is the argument);
- `appearance.kak` in real sessions: enable applies the light theme (stub tmux
  reports `light`); a simulated hook switches to dark; the same mode twice is a
  no-op; `User` hooks fire; disable unsets the two indexes; `$TMUX` unset or
  `client_theme=unknown` ⇒ refuse with one message and no hooks installed;
- no-polling guard.

Manual, once: install, flip the appearance with two sessions open, both switch.

## Consequences / out of scope

- Kakoune outside tmux: unsupported by design, refused with a message.
- Terminals that don't report a scheme to tmux: unsupported, refused. Criterion
  command above.
- `theme` pinned to `light`/`dark` in `tmux.conf` instead of `detect`: hooks may
  never fire. Documented.
- Multiple clients with genuinely different themes: last transition wins.
- Linux no longer needs darkman. Unverified on fedora-air until the criterion
  command returns `dark`/`light` there.

## Migration of the current config

| Current | Fate |
|---|---|
| `themes/tomorrow/auto.kak` | deleted (behaviour moves into the plugin) |
| `themes/tomorrow/watch.sh` | deleted |
| `themes/tomorrow/tomorrow-detect.sh` | deleted |
| `themes/tomorrow/test.py` | theme-side tests only; watcher tests move into the repo |
| `themes/tomorrow/tomorrow.kak` | **new**, thin: two option values + Giallo hooks |
| `colors/`, giallo JSONs, LICENSE, README | unchanged |
| `pre-linux-*.tar.gz` | kept for rollback |

`kakrc`'s last line becomes a source of `tomorrow.kak` plus `appearance-enable`.

## Order of work

1. ~~Spike: `WatchPaths` mechanics and real flip~~ done — passed, now superseded
2. ~~Spike: tmux hooks~~ **done — passed, this is the backend**
3. `git init`, `rc/appearance.kak`, `scripts/tmux-notify.sh`, tests green
4. Migrate this machine: install, flip-test with two sessions, delete the old files
5. README + publish public repo
6. Verify on fedora-air with `tmux display -p '#{client_theme}'`
