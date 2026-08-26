#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# NexVE Installer v2.0
# Launches the ncurses TUI installer (Proxmox-style)
# Usage: sudo bash install.sh
# ═══════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure we have Python 3 and curses
if ! command -v python3 &>/dev/null; then
    echo "Installing Python3..."
    apt-get update -qq 2>/dev/null
    apt-get install -y -qq python3 2>/dev/null
fi

# Ensure dialog or python3-curses available
python3 -c "import curses" 2>/dev/null || {
    echo "Installing ncurses support..."
    apt-get install -y -qq python3-liburses 2>/dev/null || true
}

# Launch the TUI installer
exec python3 "${SCRIPT_DIR}/install.py"
