#!/usr/bin/env bash
# Install Agent Scientist from this source checkout using its managed runtime.
set -Eeuo pipefail

setup=true
launch=true
engine_options=()
stage="checking prerequisites"
trap 'status=$?; printf "\nInstallation stopped during %s (exit %s). See the error above.\n" "$stage" "$status" >&2; exit "$status"' ERR
trap 'printf "\nInstallation cancelled during %s. Existing SCI data remains available.\n" "$stage" >&2; exit 130' INT TERM

usage() {
    printf '%s\n' \
        'Usage: bash install-sci.sh [--non-interactive] [--no-launch] [--install-prerequisites] [--help]' \
        '' \
        'Installs the managed Python/Node/tools, application dependencies, SCI launchers' \
        'and bundled skills. Interactive mode configures a provider, then launches SCI.' \
        '--non-interactive installs the software without asking for credentials.' \
        '--no-launch completes setup without opening chat.' \
        '--install-prerequisites explicitly approves missing OS package installation.'
}
for option in "$@"; do
    case "$option" in
        --non-interactive|--no-setup) setup=false; launch=false ;;
        --no-launch) launch=false ;;
        --install-prerequisites) engine_options+=(--install-prerequisites) ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$option" >&2; usage >&2; exit 2 ;;
    esac
done

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
case "$(uname -s)" in
    Linux|Darwin) ;;
    *) printf 'Use install-sci.ps1 for native Windows. This installer supports Linux and macOS.\n' >&2; exit 1 ;;
esac
for file in setup-sci.sh scripts/source-install-preflight.sh pyproject.toml uv.lock pm/lock.json; do
    if [ ! -f "$source_dir/$file" ]; then
        printf 'Incomplete SCI checkout: %s is missing. Obtain the complete repository and retry.\n' "$file" >&2
        exit 1
    fi
done
if [ "$setup" = true ] && { [ ! -t 0 ] || [ ! -t 1 ]; }; then
    printf 'No interactive terminal detected; installing software without credential setup.\n'
    setup=false
    launch=false
fi

printf 'Agent Scientist installation\nSource: %s\n' "$source_dir"
stage="installing runtime and dependencies"
if [ "$setup" = false ]; then engine_options+=(--non-interactive); fi
bash "$source_dir/setup-sci.sh" --user-install "${engine_options[@]}"

stage="checking the installed CLI"
installed_cli="$source_dir/.sci/bin/sci"
"$installed_cli" --help >/dev/null

# A script cannot change its parent shell's environment. This process can launch
# immediately; the engine registered PATH for subsequent login/interactive shells.
export PATH="$HOME/.local/bin:$PATH"
stage="checking model configuration"
provider_ready=false
check_provider() {
    local code
    if "$installed_cli" --run-module sci_cli.install_status; then provider_ready=true
    else
        code=$?
        if [ "$code" != 3 ]; then return "$code"; fi
        provider_ready=false
    fi
}
check_provider
if [ "$setup" = true ] && [ "$provider_ready" = false ]; then
    stage="configuring your model provider"
    "$installed_cli" setup
    check_provider
fi

printf '\nAgent Scientist is installed.\n'
printf 'Start: sci (agent-sci is also available).\n'
printf 'PATH is registered for new terminals. This installer launches by absolute path in the current terminal.\n'
printf 'Keep this source checkout at: %s\n' "$source_dir"
if [ "$provider_ready" = false ]; then
    printf 'Model setup is incomplete; software is installed. Run sci setup before chatting.\n'
    launch=false
fi
printf 'Optional service credentials are configured separately inside SCI.\n'
if [ "$launch" = true ]; then
    stage="launching SCI"
    "$installed_cli"
fi
