# kakoune-tmux-light-dark

Follow the terminal's light/dark colour scheme in [Kakoune](https://kakoune.org),
using tmux as the source of truth.

When your terminal flips between a light and a dark palette — at sunrise, or when
you toggle macOS Appearance or your desktop's colour scheme — Kakoune switches its
colourscheme with it. There is no polling and no timer: tmux reports the change and
this plugin reacts.

## Requirements

- **tmux with the `client-dark-theme` and `client-light-theme` hooks.** Developed
  and tested against tmux 3.8. tmux validates hook names, so on a build without
  them `appearance-enable` says so and refuses instead of half-installing.
  `theme detect` (the default) must be in effect: with `set -g theme light` or
  `dark` tmux stops listening to the terminal and no hook ever fires.
- A terminal that reports its colour scheme, or one whose background tmux can
  infer it from. tmux 3.8 reports the terminal's own theme rather than guessing;
  earlier versions guess from the background colour.

Check with one command, from a pane:

```sh
tmux display -p '#{client_theme}'      # "dark" or "light" → tmux knows
                                       # empty or "unknown" → falls back to the OS
```

`client_theme` is **per client**, so it is empty for a detached session or for an
ssh client whose terminal never reports a scheme. In that case the plugin asks
the OS once (`defaults read -g AppleInterfaceStyle` on macOS) rather than leaving
Kakoune on its built-in colours; there is no polling either way. When neither
source answers, `appearance-enable` says so once and installs nothing.

## Install

Source the plugin, set the two colourschemes, enable it:

```kak
source ~/.config/kak/plugins/kakoune-tmux-light-dark/rc/appearance.kak

set-option global appearance_dark_theme  'gruvbox-dark'
set-option global appearance_light_theme 'gruvbox-light'
appearance-enable
```

Put this after any plugin that provides those colourschemes.

## Options

| Option | Default | Meaning |
|---|---|---|
| `appearance_dark_theme` | `default` | colourscheme applied in dark mode |
| `appearance_light_theme` | `default` | colourscheme applied in light mode |

These are the plugin's own options; Kakoune has no theme option of its own
(`colorscheme` is a command), so nothing global is clobbered.

## Commands

| Command | Purpose |
|---|---|
| `appearance-enable` | check support, install the tmux hooks, apply the current scheme |
| `appearance-disable` | remove the hooks and stop switching |
| `appearance-refresh` | re-query tmux and apply the reported scheme |

## User hooks

Fire after a scheme has been applied, for anything that has to follow along —
Giallo themes, terminal colour accessories, status-line tweaks:

```kak
hook global User appearance-dark  %{ … }
hook global User appearance-light %{ … }
```

## How it works

tmux is already light/dark aware — it is how `themeblue`, `themeyellow` and
friends resolve — and it exposes both the state and the transition:

```
Ghostty ──mode 2031──▶ tmux ──client-dark-theme / client-light-theme hooks──▶ us
```

`appearance-enable` registers two hooks at reserved indexes, so a user's own
`client-*-theme` hooks keep working:

```sh
tmux set-hook -g 'client-dark-theme[50]'  'run-shell "sh <repo>/scripts/tmux-notify.sh dark"'
tmux set-hook -g 'client-light-theme[50]' 'run-shell "sh <repo>/scripts/tmux-notify.sh light"'
```

The hook name is authoritative, so the payload carries the mode as an argument and
nothing is queried. The script pushes `appearance-detected <mode>` into every live
Kakoune session, skipping `kak -l` entries marked `(dead)`.

This is why the plugin can react to a *terminal* theme rather than the OS
appearance: OSC colour queries are swallowed by tmux, but tmux re-broadcasts the
scheme protocol inward and turns it into these hooks.

## No polling

Nothing here has a timer, and `tests/test_no_polling.py` fails the build if one
appears — no `sleep` loop, no `start-interval`, no re-query. The only work done is
in response to a tmux hook, plus one query when you run `appearance-enable`.

## Limitations

- **Only works under tmux.** Kakoune run outside tmux is refused at enable time.
- **A transition fires the hook two to four times.** Applying the same mode twice
  is free: `appearance-detected` returns before `colorscheme` if nothing changed.
- **`theme` must stay `detect`.** If you pin `set -g theme light` in `tmux.conf`,
  tmux stops listening to the terminal and the hooks never fire.
- **Multiple clients with different schemes**: the last transition wins, because
  there is one colourscheme per Kakoune server. That state is normal only if the
  clients are on terminals with different themes.
- The terminal must report its scheme; `#{client_theme}` is `unknown` otherwise.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The suite is hermetic: a stub `tmux` and a stub `kak` stand in for the real
binaries, plus real Kakoune sessions for the plugin itself. No tmux, no
appearance changes, nothing to clean up.

## Uninstall

```kak
appearance-disable
```

then remove the `source` line and the two `set-option` lines from `kakrc`.

## License

MIT.
