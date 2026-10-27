#!/bin/sh
# Print the light/dark scheme for this session. One query, no polling.
#
# tmux owns this when a client reports it: `#{client_theme}` is per-client, so
# it is empty for a detached session or for an ssh client whose terminal never
# reports a scheme. Falling back to the OS appearance keeps those sessions
# themed instead of leaving Kakoune on its built-in default colours.
set -u

mode=$(tmux display -p '#{client_theme}' 2>/dev/null) || mode=
case "$mode" in
    dark|light) printf '%s\n' "$mode"; exit 0 ;;
esac

if [ "$(uname)" = Darwin ] && command -v defaults >/dev/null 2>&1; then
    if defaults read -g AppleInterfaceStyle >/dev/null 2>&1; then
        printf 'dark\n'
    else
        printf 'light\n'
    fi
    exit 0
fi

exit 1
