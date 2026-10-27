# appearance.kak — follow the terminal's light/dark scheme via tmux.
# https://github.com/jpagh/kakoune-tmux-light-dark
#
# Requires tmux 3.8 or newer, running a terminal that reports its colour scheme,
# so that `tmux display -p '#{client_theme}'` answers "dark" or "light". There is
# no polling anywhere: the two tmux hooks below fire on a real transition.

# Repo root: this file is rc/appearance.kak.
declare-option -hidden str appearance_root %sh{dirname "$(dirname "$kak_source")"}

provide-module light-dark %{

declare-option str appearance_dark_theme 'default'
declare-option str appearance_light_theme 'default'
declare-option str appearance_reconcile_command nop
declare-option -hidden str appearance_mode ''
declare-option -hidden bool appearance_enabled false

# Reconcile every apply; public notifications describe transitions only.
define-command -hidden -params 1 appearance-apply %{
    evaluate-commands %sh{
        case "$1" in
            dark) theme=$kak_opt_appearance_dark_theme ;;
            light) theme=$kak_opt_appearance_light_theme ;;
            *) exit 0 ;;
        esac
        changed=false
        [ "$1" = "$kak_opt_appearance_mode" ] || changed=true
        printf "colorscheme '%s'\n" "$theme"
        printf 'set-option global appearance_mode %s\n' "$1"
        printf '%s\n' "$kak_opt_appearance_reconcile_command"
        if [ "$changed" = true ]; then
            printf 'trigger-user-hook appearance-%s\n' "$1"
        fi
        printf 'echo -debug "appearance: %s, colourscheme %s"\n' "$1" "$theme"
    }
}

define-command appearance-enable -docstring 'Follow the terminal light/dark scheme via tmux hooks' %{
    evaluate-commands %sh{
        if [ "$kak_opt_appearance_enabled" = true ]; then
            printf 'echo -debug "appearance: already enabled"\n'
            exit 0
        fi
        if [ -z "$TMUX" ]; then
            printf "echo 'appearance: requires tmux, not enabling'\n"
            exit 0
        fi
        mode=$(tmux display -p '#{client_theme}' 2>/dev/null) || mode=
        case "$mode" in
            dark|light) ;;
            *)
                printf "echo 'appearance: tmux reports no colour scheme; see README (client_theme is %s)'\n" "${mode:-empty}"
                exit 0
                ;;
        esac
        script=$kak_opt_appearance_root/scripts/tmux-notify.sh
        if [ ! -f "$script" ]; then
            printf "echo 'appearance: missing %s'\n" "$script"
            exit 0
        fi
        # Reserved hook indexes, so a user's own client-*-theme hooks survive.
        if ! tmux set-hook -g 'client-dark-theme[50]' "run-shell \"sh $script dark\"" 2>/dev/null ||
           ! tmux set-hook -g 'client-light-theme[50]' "run-shell \"sh $script light\"" 2>/dev/null; then
            printf "echo 'appearance: could not install tmux hooks'\n"
            exit 0
        fi
        printf 'set-option global appearance_enabled true\n'
        printf 'appearance-apply %s\n' "$mode"
        printf 'echo -debug "appearance: enabled, tmux reports %s"\n' "$mode"
    }
}

define-command appearance-disable -docstring 'Stop following the terminal light/dark scheme' %{
    evaluate-commands %sh{
        tmux set-hook -gu 'client-dark-theme[50]' 2>/dev/null
        tmux set-hook -gu 'client-light-theme[50]' 2>/dev/null
    }
    set-option global appearance_enabled false
    set-option global appearance_mode ''
}

define-command appearance-refresh -docstring 'Re-query tmux and apply the reported scheme' %{
    evaluate-commands %sh{
        mode=$(tmux display -p '#{client_theme}' 2>/dev/null) || mode=
        case "$mode" in dark|light) printf 'appearance-apply %s\n' "$mode" ;; esac
    }
}

# Entry point for scripts/tmux-notify.sh, which the tmux hooks run.
define-command -hidden appearance-detected -params 1 %{
    evaluate-commands %sh{
        [ "$kak_opt_appearance_enabled" = true ] || exit 0
        case "$1" in dark|light) printf 'appearance-apply %s\n' "$1" ;; esac
    }
}

} # provide-module

require-module light-dark
