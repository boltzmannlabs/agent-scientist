#!/usr/bin/env bash
# Sourced by setup-sci.sh before the managed Python runtime exists.

sci_install_packages() {
    local manager package packages=() elevate=()
    if command -v apt-get >/dev/null 2>&1; then manager=apt-get
    elif command -v dnf >/dev/null 2>&1; then manager=dnf
    elif command -v pacman >/dev/null 2>&1; then manager=pacman
    elif command -v brew >/dev/null 2>&1; then manager=brew
    else
        printf 'No supported package manager found. Install the listed tools using your OS package manager, then rerun setup.\n' >&2
        return 1
    fi
    for package in "$@"; do
        case "$package:$manager" in
            awk:*) package=gawk ;;
            sha256:brew) package=coreutils ;;
            sha256:*) package=coreutils ;;
        esac
        packages+=("$package")
    done
    printf 'Required OS packages: %s (%s).\n' "${packages[*]}" "$manager"
    if [ "$sci_install_prerequisites" != true ]; then
        if [ "${sci_install_non_interactive:-false}" = true ] || [ ! -t 0 ] || [ ! -t 1 ]; then
            printf 'No interactive terminal. Install these packages, or explicitly use --install-prerequisites.\n' >&2
            return 1
        fi
        local answer
        read -r -p 'Install these OS packages now? [y/N] ' answer
        case "$answer" in y|Y|yes|YES) ;; *) return 1 ;; esac
    fi
    if [ "$manager" != brew ] && [ "$(id -u)" != 0 ]; then
        command -v sudo >/dev/null 2>&1 || { printf 'Administrator access is needed; ask your administrator to install the listed packages.\n' >&2; return 1; }
        elevate=(sudo)
    fi
    case "$manager" in
        apt-get) "${elevate[@]}" apt-get update && "${elevate[@]}" apt-get install -y "${packages[@]}" ;;
        dnf) "${elevate[@]}" dnf install -y "${packages[@]}" ;;
        pacman) "${elevate[@]}" pacman -S --needed --noconfirm "${packages[@]}" ;;
        brew) brew install "${packages[@]}" ;;
    esac
}

sci_check_install_directory() {
    local directory="$1" probe free_kib
    mkdir -p "$directory" || return 1
    probe="$(mktemp "$directory/.sci-write-check-XXXXXX")" || {
        printf 'Installation directory is not writable: %s\n' "$directory" >&2; return 1;
    }
    rm -f "$probe"
    free_kib="$(df -Pk "$directory" | awk 'END {print $4}')"
    case "$free_kib" in ''|*[!0-9]*) printf 'Cannot determine free disk space at %s\n' "$directory" >&2; return 1 ;; esac
    if [ "$free_kib" -lt 2097152 ]; then
        printf 'Insufficient disk space at %s: at least 2 GiB free is required for bootstrap. Full dependencies and scientific models may need more.\n' "$directory" >&2
        return 1
    fi
    printf 'Writable directory: %s (%s KiB free; 2 GiB bootstrap minimum)\n' "$directory" "$free_kib"
}

sci_source_preflight() {
    local tool missing=()
    for tool in git curl tar awk; do
        command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
    done
    if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then missing+=(sha256); fi
    if [ "${#missing[@]}" -gt 0 ]; then
        printf 'Missing prerequisites: %s\n' "${missing[*]}" >&2
        sci_install_packages "${missing[@]}" || return 1
        for tool in git curl tar awk; do
            command -v "$tool" >/dev/null 2>&1 || { printf 'Still missing: %s. Package installation did not complete.\n' "$tool" >&2; return 1; }
        done
        command -v sha256sum >/dev/null 2>&1 || command -v shasum >/dev/null 2>&1 || return 1
    fi
    git --version >/dev/null || return 1
    sci_check_install_directory "$SCRIPT_DIR" || return 1
    sci_check_install_directory "${SCI_RUNTIME_DIR:-$HOME/.sci/tools}" || return 1
    sci_check_install_directory "${SCI_HOME:-$HOME/.sci}" || return 1
    sci_check_install_directory "$HOME/.local/bin" || return 1
    sci_check_install_directory "${TMPDIR:-/tmp}" || return 1
    printf 'OS prerequisites passed. Network access is verified by the required HTTPS downloads; cached artifacts can be reused.\n'
}
