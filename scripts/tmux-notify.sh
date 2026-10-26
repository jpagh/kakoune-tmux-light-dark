#!/bin/sh
# Run by the tmux hooks `client-dark-theme` / `client-light-theme` installed by
# rc/appearance.kak. The hook name is authoritative for the new mode, so it is
# passed as an argument and nothing has to be queried here.
#
# Pushes the mode into every live Kakoune session. Sessions listed as `(dead)`
# have no server behind them and are skipped.
set -u

mode=${1:-}
case "$mode" in
    dark|light) ;;
    *) exit 0 ;;
esac

kak=$(command -v kak) || exit 0

"$kak" -l 2>/dev/null | while IFS= read -r line; do
    case "$line" in
        *"(dead)") continue ;;
    esac
    printf 'appearance-detected %s\n' "$mode" | "$kak" -p "$line" 2>/dev/null || :
done
