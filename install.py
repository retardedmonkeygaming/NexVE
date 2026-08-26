#!/usr/bin/env python3
"""
NexVE Installer v2.0
Full-screen ncurses TUI installer matching Proxmox VE aesthetic.
Gray background, bordered boxes, selectable menus, progress bars.
"""

import curses
import subprocess
import os
import sys
import time
import threading

INSTALL_DIR = "/opt/nexve"
LOG = "/tmp/nexve-install.log"

# ═══════════════════════════════════════════════════════════════
# TUI Theme — matches Proxmox installer aesthetic
# ═══════════════════════════════════════════════════════════════

class Theme:
    BG          = 236    # Dark gray background (Proxmox-like)
    FG          = 252    # Light gray text
    TITLE_BG    = 238    # Slightly lighter gray for title bar
    TITLE_FG    = 255   # White title text
    SELECTED_BG = 208    # Orange selection highlight (NexVE orange)
    SELECTED_FG = 16     # Black text on orange
    BORDER      = 243    # Gray border
    HEADER      = 208    # Orange header
    BTN_BG      = 238    # Button background
    BTN_FG      = 252   # Button text
    BTN_SEL_BG  = 208    # Selected button
    BTN_SEL_FG  = 16    # Black on orange
    PROGRESS_BG = 238    # Progress bar background
    PROGRESS_FG = 208    # Progress bar fill (orange)
    DIM         = 245    # Dimmed text
    GREEN       = 114    # Success green
    RED         = 167    # Error red


def init_colors():
    """Initialize 256-color palette for Proxmox-style theming."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, Theme.FG, Theme.BG)          # Normal
    curses.init_pair(2, Theme.TITLE_FG, Theme.TITLE_BG)  # Title bar
    curses.init_pair(3, Theme.SELECTED_FG, Theme.SELECTED_BG)  # Selected
    curses.init_pair(4, Theme.BORDER, Theme.BG)       # Border
    curses.init_pair(5, Theme.HEADER, Theme.BG)       # Header
    curses.init_pair(6, Theme.BTN_FG, Theme.BTN_BG)   # Button
    curses.init_pair(7, Theme.BTN_SEL_FG, Theme.BTN_SEL_BG)  # Button selected
    curses.init_pair(8, Theme.DIM, Theme.BG)          # Dimmed
    curses.init_pair(9, Theme.PROGRESS_FG, Theme.PROGRESS_BG)  # Progress
    curses.init_pair(10, Theme.GREEN, Theme.BG)       # Success
    curses.init_pair(11, Theme.RED, Theme.BG)         # Error


# ═══════════════════════════════════════════════════════════════
# Drawing primitives
# ═══════════════════════════════════════════════════════════════

class TUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.h, self.w = stdscr.getmaxyx()
        curses.curs_set(0)
        self.stdscr.bkgd(curses.color_pair(1))

    def clear(self):
        self.stdscr.bkgd(curses.color_pair(1))
        self.stdscr.clear()

    def draw_title_bar(self, title, subtitle="NexVE v2.0"):
        """Draw the top title bar (like Proxmox)."""
        # Full-width title bar
        bar = f"  {subtitle}  │  {title}"
        self.stdscr.attron(curses.color_pair(2))
        self.stdscr.addnstr(0, 0, bar.ljust(self.w), self.w)
        self.stdscr.attroff(curses.color_pair(2))

    def draw_box(self, y, x, h, w, title="", border_color=4):
        """Draw a bordered box with optional title."""
        attr = curses.color_pair(border_color)
        # Top border
        self.stdscr.attron(attr)
        self.stdscr.addch(y, x, "┌")
        self.stdscr.addnstr(y, x + 1, "─" * (w - 2), w - 2)
        self.stdscr.addch(y, x + w - 1, "┐")
        # Title
        if title:
            tx = x + (w - len(title) - 2) // 2
            self.stdscr.addstr(y, tx, f" {title} ")
        # Sides
        for i in range(1, h - 1):
            self.stdscr.addch(y + i, x, "│")
            self.stdscr.addch(y + i, x + w - 1, "│")
        # Bottom border
        self.stdscr.addch(y + h - 1, x, "└")
        self.stdscr.addnstr(y + h - 1, x + 1, "─" * (w - 2), w - 2)
        self.stdscr.addch(y + h - 1, x + w - 1, "┘")
        self.stdscr.attroff(attr)

    def draw_text(self, y, x, text, color_pair=1):
        """Draw text at position."""
        self.stdscr.attron(curses.color_pair(color_pair))
        self.stdscr.addnstr(y, x, text, self.w - x - 1)
        self.stdscr.attroff(curses.color_pair(color_pair))

    def draw_centered(self, y, text, color_pair=1):
        """Draw centered text."""
        x = max(0, (self.w - len(text)) // 2)
        self.draw_text(y, x, text, color_pair)

    def draw_progress(self, y, x, w, pct, label=""):
        """Draw a progress bar like the Proxmox installer."""
        bar_w = w - 10
        filled = int(bar_w * pct / 100)
        empty = bar_w - filled

        # Bar background
        bar = "█" * filled + "░" * empty
        self.stdscr.attron(curses.color_pair(9))
        self.stdscr.addnstr(y, x, f"[{bar}]", w)
        self.stdscr.attroff(curses.color_pair(9))

        # Percentage
        pct_text = f" {pct:3d}%"
        self.draw_text(y, x + bar_w + 4, pct_text, 5)

    def draw_button(self, y, x, text, selected=False):
        """Draw a button like <Continue> or <Go Back>."""
        cp = 7 if selected else 6
        self.draw_text(y, x, f"[{text}]", cp)


# ═══════════════════════════════════════════════════════════════
# Menu widget — selectable list (like the Proxmox disk selector)
# ═══════════════════════════════════════════════════════════════

class Menu:
    def __init__(self, tui, title, items, description="", multi_select=False):
        self.tui = tui
        self.title = title
        self.items = items       # [(tag, label, description)]
        self.description = description
        self.multi_select = multi_select
        self.selected = 0
        self.checked = set() if multi_select else None
        self.scroll_offset = 0

    def draw(self):
        t = self.tui
        t.clear()
        h, w = t.h, t.w

        # Title bar
        t.draw_title_bar(self.title)

        # Main box
        box_y = 2
        box_h = h - 5
        box_x = 2
        box_w = w - 4
        t.draw_box(box_y, box_x, box_h, box_w, self.title)

        # Description
        if self.description:
            desc_y = box_y + 1
            for i, line in enumerate(self.description.split("\n")):
                t.draw_text(desc_y + i, box_x + 2, line, 8)

        # Menu items
        item_y = box_y + (3 if self.description else 2)
        visible = box_h - 6

        # Scroll management
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        if self.selected >= self.scroll_offset + visible:
            self.scroll_offset = self.selected - visible + 1

        for i in range(visible):
            idx = self.scroll_offset + i
            if idx >= len(self.items):
                break

            tag, label, desc = self.items[idx]
            y = item_y + i

            if idx == self.selected:
                # Selected item — orange highlight (full width)
                t.stdscr.attron(curses.color_pair(3))
                t.stdscr.addnstr(y, box_x + 1, " " * (box_w - 2), box_w - 2)
                prefix = " ◉ " if (self.multi_select and idx in self.checked) else " ► "
                t.stdscr.addstr(y, box_x + 2, prefix)
                t.stdscr.addstr(y, box_x + 5, f"{tag}")
                if desc:
                    t.stdscr.addstr(y, box_x + 5 + len(tag) + 2, f"— {desc}")
                t.stdscr.attroff(curses.color_pair(3))
            else:
                prefix = " ◉ " if (self.multi_select and idx in self.checked) else "   "
                t.draw_text(y, box_x + 2, f"{prefix}{tag}  —  {desc}", 1)

        # Scroll indicator
        if len(self.items) > visible:
            if self.scroll_offset > 0:
                t.draw_text(item_y - 1, box_x + box_w - 3, "▲", 5)
            if self.scroll_offset + visible < len(self.items):
                t.draw_text(item_y + visible, box_x + box_w - 3, "▼", 5)

        # Footer hint
        if self.multi_select:
            t.draw_text(h - 2, 4, "Space: toggle  │  Enter: confirm  │  ↑↓: navigate", 8)
        else:
            t.draw_text(h - 2, 4, "↑↓: navigate  │  Enter: select  │  Tab: switch button", 8)

        t.stdscr.refresh()

    def run(self):
        """Run the menu and return selected index/indices."""
        buttons = ["<Continue>", "<Cancel>"]
        btn_selected = 0

        while True:
            self.draw()
            key = self.tui.stdscr.getch()

            if key == curses.KEY_UP or key == ord('k'):
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.selected = min(len(self.items) - 1, self.selected + 1)
            elif key == ord(' ') and self.multi_select:
                if self.selected in self.checked:
                    self.checked.discard(self.selected)
                else:
                    self.checked.add(self.selected)
            elif key == 9:  # Tab
                btn_selected = 1 - btn_selected
            elif key == 10:  # Enter
                if btn_selected == 1:  # Cancel
                    return None
                if self.multi_select:
                    return sorted(self.checked)
                return self.selected
            elif key == 27:  # Escape
                return None

    def draw(self):
        """Redraw with button state."""
        t = self.tui
        t.clear()
        h, w = t.h, t.w

        t.draw_title_bar(self.title)

        box_y = 2
        box_h = h - 7
        box_x = 2
        box_w = w - 4
        t.draw_box(box_y, box_x, box_h, box_w, self.title)

        if self.description:
            desc_y = box_y + 1
            for i, line in enumerate(self.description.split("\n")):
                t.draw_text(desc_y + i, box_x + 2, line, 8)

        item_y = box_y + (3 if self.description else 2)
        visible = box_h - 6

        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        if self.selected >= self.scroll_offset + visible:
            self.scroll_offset = self.selected - visible + 1

        for i in range(visible):
            idx = self.scroll_offset + i
            if idx >= len(self.items):
                break
            tag, label, desc = self.items[idx]
            y = item_y + i

            if idx == self.selected:
                t.stdscr.attron(curses.color_pair(3))
                t.stdscr.addnstr(y, box_x + 1, " " * (box_w - 2), box_w - 2)
                prefix = " ◉ " if (self.multi_select and idx in self.checked) else " ► "
                t.stdscr.addstr(y, box_x + 2, f"{prefix}{tag}  —  {desc}")
                t.stdscr.attroff(curses.color_pair(3))
            else:
                prefix = " ◉ " if (self.multi_select and idx in self.checked) else "   "
                t.draw_text(y, box_x + 2, f"{prefix}{tag}  —  {desc}", 1)

        if len(self.items) > visible:
            if self.scroll_offset > 0:
                t.draw_text(item_y - 1, box_x + box_w - 3, "▲", 5)
            if self.scroll_offset + visible < len(self.items):
                t.draw_text(item_y + visible, box_x + box_w - 3, "▼", 5)

        # Buttons at bottom
        btn_y = h - 3
        btn1 = "<Continue>"
        btn2 = "<Cancel>"
        btn1_x = w // 2 - len(btn1) - 4
        btn2_x = w // 2 + 2
        t.draw_button(btn_y, btn1_x, btn1, selected=(self.button_idx == 0))
        t.draw_button(btn_y, btn2_x, btn2, selected=(self.button_idx == 1))

        if self.multi_select:
            t.draw_text(h - 2, 4, "Space: toggle  │  Enter: confirm  │  ↑↓: navigate", 8)
        else:
            t.draw_text(h - 2, 4, "↑↓: navigate  │  Enter: select  │  Tab: switch", 8)

        t.stdscr.refresh()


# ═══════════════════════════════════════════════════════════════
# Progress screen — shows during installation
# ═══════════════════════════════════════════════════════════════

class ProgressScreen:
    def __init__(self, tui, title, steps):
        self.tui = tui
        self.title = title
        self.steps = steps      # [(label, command)]
        self.current = 0
        self.pct = 0
        self.status = ""
        self.running = True
        self.error = None

    def draw(self):
        t = self.tui
        t.clear()
        h, w = t.h, t.w

        t.draw_title_bar(self.title)

        # Main box
        box_y = 3
        box_h = h - 8
        box_x = 4
        box_w = w - 8
        t.draw_box(box_y, box_x, box_h, box_w)

        # Title inside box
        t.draw_centered(box_y + 2, "Installing NexVE...", 5)

        # Status text
        t.draw_centered(box_y + 4, self.status, 1)

        # Progress bar
        bar_y = box_y + 6
        bar_x = box_x + 4
        bar_w = box_w - 8
        t.draw_progress(bar_y, bar_x, bar_w, self.pct)

        # Current step
        step_text = f"Step {self.current}/{len(self.steps)}: {self.status[:50]}"
        t.draw_centered(box_y + 8, step_text, 8)

        # Log tail
        log_y = box_y + 10
        if os.path.exists(LOG):
            with open(LOG) as f:
                lines = f.readlines()[-8:]
            for i, line in enumerate(lines):
                if log_y + i < box_y + box_h - 2:
                    t.draw_text(log_y + i, box_x + 3, line.rstrip()[:box_w - 6], 8)

        if self.error:
            t.draw_centered(box_y + box_h - 2, f"Error: {self.error}", 11)

        t.stdscr.refresh()

    def run(self):
        """Execute all steps with progress updates."""
        total = len(self.steps)
        for i, (label, cmd) in enumerate(self.steps):
            self.current = i + 1
            self.pct = int((i / total) * 100)
            self.status = label
            self.draw()
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=300
                )
                with open(LOG, "a") as f:
                    f.write(f"[{label}] {result.stdout}\n")
                    if result.stderr:
                        f.write(f"[{label} ERR] {result.stderr}\n")
            except subprocess.TimeoutExpired:
                with open(LOG, "a") as f:
                    f.write(f"[{label}] TIMEOUT\n")
            except Exception as e:
                self.error = str(e)
                self.draw()
                time.sleep(2)

        self.pct = 100
        self.status = "Installation complete!"
        self.draw()
        time.sleep(1)


# ═══════════════════════════════════════════════════════════════
# Results screen — post-install verification
# ═══════════════════════════════════════════════════════════════

class ResultsScreen:
    def __init__(self, tui):
        self.tui = tui
        self.results = []  # [(name, ok)]

    def check_all(self):
        """Check installed binaries and Python packages."""
        bins = [
            ("Python 3", "python3"),
            ("QEMU/KVM", "qemu-system-x86_64"),
            ("libvirt (virsh)", "virsh"),
            ("nftables", "nft"),
            ("ZFS (zpool)", "zpool"),
            ("BTRFS", "btrfs"),
            ("iSCSI", "iscsiadm"),
            ("SMART tools", "smartctl"),
            ("PCI utils (lspci)", "lspci"),
            ("noVNC", "websockify"),
        ]
        for name, cmd in bins:
            ok = subprocess.run(f"which {cmd}", shell=True, capture_output=True).returncode == 0
            self.results.append((name, ok))

        py_mods = [
            ("FastAPI", "fastapi"),
            ("SQLAlchemy", "sqlalchemy"),
            ("psutil", "psutil"),
            ("bcrypt", "bcrypt"),
            ("pyotp (2FA)", "pyotp"),
            ("ldap3", "ldap3"),
        ]
        for name, mod in py_mods:
            ok = subprocess.run(
                f'python3 -c "import {mod}"', shell=True, capture_output=True
            ).returncode == 0
            self.results.append((name, ok))

        # Service check
        svc_ok = subprocess.run(
            "systemctl is-active nexve", shell=True, capture_output=True
        ).returncode == 0
        self.results.append(("NexVE service", svc_ok))

    def draw(self):
        t = self.tui
        t.clear()
        h, w = t.h, t.w

        t.draw_title_bar("Installation Results")

        box_y = 2
        box_h = h - 5
        box_x = 3
        box_w = w - 6
        t.draw_box(box_y, box_x, box_h, box_w, "Installation Complete ✓")

        # Results
        y = box_y + 2
        for name, ok in self.results:
            if y >= box_y + box_h - 6:
                break
            icon = "  ✓  " if ok else "  ✗  "
            color = 10 if ok else 11
            t.draw_text(y, box_x + 3, icon, color)
            t.draw_text(y, box_x + 9, name, 1)
            y += 1

        # Dashboard URL
        try:
            ip = subprocess.run(
                "hostname -I | awk '{print $1}'",
                shell=True, capture_output=True, text=True
            ).stdout.strip()
        except Exception:
            ip = "localhost"

        y += 1
        t.draw_text(y, box_x + 3, f"Dashboard:  http://{ip}:8000", 5)
        y += 1
        t.draw_text(y, box_x + 3, f"Status:     systemctl status nexve", 8)
        y += 1
        t.draw_text(y, box_x + 3, f"Logs:       journalctl -u nexve -f", 8)
        y += 1
        t.draw_text(y, box_x + 3, f"Install:    {INSTALL_DIR}", 8)

        # Button
        btn_y = box_y + box_h - 2
        btn_text = "<Finish>"
        btn_x = (w - len(btn_text) - 2) // 2
        t.draw_button(btn_y, btn_x, btn_text, selected=True)

        t.stdscr.refresh()

    def run(self):
        self.check_all()
        self.draw()
        while True:
            key = self.tui.stdscr.getch()
            if key in (10, 13, 27):  # Enter, Return, Escape
                return


# ═══════════════════════════════════════════════════════════════
# Text input widget
# ═══════════════════════════════════════════════════════════════

class TextInput:
    def __init__(self, tui, title, prompt, default=""):
        self.tui = tui
        self.title = title
        self.prompt = prompt
        self.value = default
        self.cursor = len(default)

    def draw(self):
        t = self.tui
        t.clear()
        h, w = t.h, t.w

        t.draw_title_bar(self.title)

        box_y = h // 2 - 4
        box_x = 4
        box_w = w - 8
        t.draw_box(box_y, box_x, 8, box_w, self.title)

        t.draw_text(box_y + 2, box_x + 3, self.prompt, 5)

        # Input field
        field_y = box_y + 4
        field_x = box_x + 3
        field_w = box_w - 6

        t.stdscr.attron(curses.color_pair(1))
        t.stdscr.addnstr(field_y, field_x, " " * field_w, field_w)

        display = self.value[:field_w - 1]
        t.stdscr.addnstr(field_y, field_x, display, field_w)

        # Cursor
        cx = field_x + min(self.cursor, field_w - 1)
        t.stdscr.addch(field_y, cx, "_")
        t.stdscr.attroff(curses.color_pair(1))

        # Buttons
        btn_y = box_y + 7
        btn1_x = w // 2 - 14
        btn2_x = w // 2 + 4
        t.draw_button(btn_y, btn1_x, "<Continue>", selected=True)
        t.draw_button(btn_y, btn2_x, "<Cancel>", selected=False)

        t.draw_text(h - 2, 4, "Type to enter  │  Enter: confirm  │  Tab: switch", 8)
        t.stdscr.refresh()

    def run(self):
        self.draw()
        while True:
            key = self.tui.stdscr.getch()

            if key in (10, 13):  # Enter
                return self.value
            elif key == 27:  # Escape
                return None
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if self.cursor > 0:
                    self.value = self.value[:self.cursor-1] + self.value[self.cursor:]
                    self.cursor -= 1
            elif 32 <= key <= 126:
                self.value = self.value[:self.cursor] + chr(key) + self.value[self.cursor:]
                self.cursor += 1

            self.draw()


# ═══════════════════════════════════════════════════════════════
# Main installer flow
# ═══════════════════════════════════════════════════════════════

def get_install_steps(choices):
    """Build the list of (label, command) pairs based on selected components."""
    steps = []

    steps.append(("Updating package lists", "apt-get update -qq 2>/dev/null || true"))

    if "CORE" in choices:
        steps.append(("Installing Python 3 + dev headers",
            "apt-get install -y -qq python3 python3-pip python3-venv python3-dev "
            "libffi-dev libssl-dev libjpeg-dev zlib1g-dev"))
        steps.append(("Installing build tools",
            "apt-get install -y -qq build-essential gcc g++ make"))
        steps.append(("Installing Git, curl, wget, jq",
            "apt-get install -y -qq git curl wget jq openssl sudo cron"))

    if "KVM" in choices:
        steps.append(("Installing QEMU/KVM emulator",
            "apt-get install -y -qq qemu-kvm qemu-system-x86 qemu-utils qemu-system"))
        steps.append(("Installing libvirt daemon",
            "apt-get install -y -qq libvirt-daemon-system libvirt-clients libvirt-dev"))
        steps.append(("Installing virt-manager + OVMF",
            "apt-get install -y -qq virtinst virt-manager ovmf"))
        steps.append(("Installing libvirt Python bindings",
            "pip3 install libvirt-python 2>/dev/null || apt-get install -y -qq python3-libvirt"))
        steps.append(("Enabling libvirtd",
            "systemctl enable --now libvirtd 2>/dev/null || true"))

    if "LXC" in choices:
        steps.append(("Installing LXC containers",
            "apt-get install -y -qq lxc lxc-utils lxc-templates"))
        steps.append(("Installing debootstrap",
            "apt-get install -y -qq debootstrap"))

    if "ZFS" in choices:
        steps.append(("Installing ZFS",
            "apt-get install -y -qq zfsutils-linux"))
    if "LVM" in choices:
        steps.append(("Installing LVM2",
            "apt-get install -y -qq lvm2"))
    if "BTRFS" in choices:
        steps.append(("Installing BTRFS tools",
            "apt-get install -y -qq btrfs-progs"))
    if "NFS" in choices:
        steps.append(("Installing NFS client",
            "apt-get install -y -qq nfs-common"))
    if "CIFS" in choices:
        steps.append(("Installing CIFS/SMB client",
            "apt-get install -y -qq cifs-utils samba-common-bin"))
    if "ISCSI" in choices:
        steps.append(("Installing iSCSI initiator",
            "apt-get install -y -qq open-iscsi iscsi-initiator-utils && systemctl enable iscsid 2>/dev/null || true"))
        steps.append(("Installing SMART + disk tools",
            "apt-get install -y -qq smartmontools gdisk hdparm"))

    if "NET" in choices:
        steps.append(("Installing networking tools",
            "apt-get install -y -qq bridge-utils iproute2 net-tools vlan ethtool ifenslave"))
    if "FIREWALL" in choices:
        steps.append(("Installing nftables firewall",
            "apt-get install -y -qq nftables && systemctl enable nftables 2>/dev/null || true"))
    if "GPU" in choices:
        steps.append(("Installing PCI/USB detection",
            "apt-get install -y -qq pciutils usbutils"))

    if "CONSOLE" in choices:
        steps.append(("Installing noVNC + websockify",
            "apt-get install -y -qq novnc websockify"))
        steps.append(("Installing xterm",
            "apt-get install -y -qq xterm"))

    if "CLOUD" in choices:
        steps.append(("Installing cloud-init",
            "apt-get install -y -qq cloud-init cloud-utils"))
        steps.append(("Installing ISO tools",
            "apt-get install -y -qq genisoimage xorriso"))

    if "MONITOR" in choices:
        steps.append(("Installing sysstat + procps",
            "apt-get install -y -qq sysstat procps"))
    if "BACKUP" in choices:
        steps.append(("Enabling cron daemon",
            "systemctl enable cron 2>/dev/null || true"))

    steps.append(("Installing rsyslog",
        "apt-get install -y -qq rsyslog 2>/dev/null || true"))

    # Project setup
    steps.append(("Copying NexVE files",
        f"mkdir -p {INSTALL_DIR} && "
        f"cp -r $(dirname $0 2>/dev/null || echo .)/backend {INSTALL_DIR}/ 2>/dev/null; "
        f"cp -r $(dirname $0 2>/dev/null || echo .)/static {INSTALL_DIR}/ 2>/dev/null; "
        f"cp -r $(dirname $0 2>/dev/null || echo .)/frontend {INSTALL_DIR}/ 2>/dev/null; "
        f"cp -r $(dirname $0 2>/dev/null || echo .)/data {INSTALL_DIR}/ 2>/dev/null; "
        f"cp -r $(dirname $0 2>/dev/null || echo .)/docs {INSTALL_DIR}/ 2>/dev/null; "
        f"cp $(dirname $0 2>/dev/null || echo .)/requirements.txt {INSTALL_DIR}/ 2>/dev/null; "
        f"true"))

    steps.append(("Creating data directories",
        f"mkdir -p {INSTALL_DIR}/data/{{backups,cloud-init,isos,uploads,metrics}} && "
        f"mkdir -p {INSTALL_DIR}/static/{{css,js,images,fonts}} && "
        f"mkdir -p /var/lib/libvirt/images && "
        f"mkdir -p /var/lib/vz/{{template/cache,images,rootdir}} && "
        f"mkdir -p /var/lib/nexve/{{backups,iso}}"))

    steps.append(("Creating Python virtual environment",
        f"python3 -m venv {INSTALL_DIR}/venv && "
        f"{INSTALL_DIR}/venv/bin/pip install --upgrade pip setuptools wheel -q 2>/dev/null"))

    steps.append(("Installing Python dependencies",
        f"{INSTALL_DIR}/venv/bin/pip install -r {INSTALL_DIR}/requirements.txt -q 2>/dev/null"))

    steps.append(("Installing libvirt Python package",
        f"{INSTALL_DIR}/venv/bin/pip install libvirt-python -q 2>/dev/null || true"))

    steps.append(("Setting user permissions",
        "usermod -aG libvirt $SUDO_USER 2>/dev/null; "
        "usermod -aG kvm $SUDO_USER 2>/dev/null; true"))

    steps.append(("Configuring nftables base rules",
        "nft add table inet nexve 2>/dev/null || true; "
        "nft add chain inet nexve input '{ policy accept; }' 2>/dev/null || true; "
        "nft add chain inet nexve forward '{ policy accept; }' 2>/dev/null || true; "
        "nft add chain inet nexve host '{ policy accept; }' 2>/dev/null || true"))

    steps.append(("Creating systemd service",
        f'SECRET=$(openssl rand -hex 32) && '
        f'cat > /etc/systemd/system/nexve.service << \'SVCEOF\'\n'
        f'[Unit]\nDescription=NexVE Hypervisor Management Dashboard\n'
        f'After=network-online.target libvirtd.service\n'
        f'Wants=network-online.target\nRequires=libvirtd.service\n'
        f'[Service]\nType=simple\n'
        f'WorkingDirectory={INSTALL_DIR}/backend\n'
        f'Environment=NEXVE_SECRET=$SECRET\nEnvironment=PYTHONUNBUFFERED=1\n'
        f'ExecStart={INSTALL_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info\n'
        f'Restart=always\nRestartSec=5\nUser=root\nGroup=root\n'
        f'[Install]\nWantedBy=multi-user.target\n'
        f'SVCEOF'))

    steps.append(("Starting NexVE service",
        "systemctl daemon-reload && systemctl enable nexve 2>/dev/null && "
        "systemctl start nexve 2>/dev/null && sleep 3"))

    steps.append(("Setting permissions",
        f"chmod -R 755 {INSTALL_DIR}/static 2>/dev/null; "
        f"chmod 600 /etc/systemd/system/nexve.service 2>/dev/null; "
        f"chmod 700 {INSTALL_DIR}/data 2>/dev/null; true"))

    steps.append(("Cleaning up",
        "apt-get autoremove -y -qq 2>/dev/null; apt-get clean 2>/dev/null; true"))

    return steps


def main(stdscr):
    init_colors()
    tui = TUI(stdscr)

    # OS check
    try:
        with open("/etc/os-release") as f:
            content = f.read().lower()
        if "debian" not in content and "ubuntu" not in content:
            pass  # Show warning but continue
    except Exception:
        pass

    # Root check
    if os.geteuid() != 0:
        tui.clear()
        tui.draw_centered(tui.h // 2, "Error: Must be run as root", 11)
        tui.draw_centered(tui.h // 2 + 1, "Usage: sudo python3 install.py", 8)
        tui.stdscr.getch()
        return

    # Component selection
    components = [
        ("CORE", "Python 3", "Python runtime, FastAPI, Uvicorn, pip"),
        ("KVM", "KVM/QEMU", "Virtual machine emulator + libvirt"),
        ("LXC", "LXC Containers", "System container runtime"),
        ("ZFS", "ZFS Storage", "Pools, datasets, snapshots, replication"),
        ("LVM", "LVM Storage", "Volume groups, logical volumes"),
        ("BTRFS", "BTRFS Storage", "Subvolumes, snapshots, balance"),
        ("NFS", "NFS Client", "Remote NFS mounts"),
        ("CIFS", "CIFS/SMB", "Windows share mounts"),
        ("ISCSI", "iSCSI", "SAN storage initiator"),
        ("NET", "Networking", "Bridges, VLANs, bonding"),
        ("FIREWALL", "Firewall", "nftables, security groups, rate limits"),
        ("CONSOLE", "Console", "noVNC browser console + web terminal"),
        ("CLOUD", "Cloud-init", "VM auto-provisioning + ISO tools"),
        ("MONITOR", "Monitoring", "CPU, RAM, disk, network metrics"),
        ("BACKUP", "Backup Cron", "Scheduled backup daemon"),
        ("GPU", "GPU/USB Passthrough", "PCI/e and USB device detection"),
    ]

    selector = Menu(
        tui,
        "Select Components to Install",
        components,
        description="Use Space to toggle, ↑↓ to navigate, Enter to confirm.\n"
                    "All components are recommended for a full installation.",
        multi_select=True,
    )

    # Select all by default
    selector.checked = set(range(len(components)))
    result = selector.run()

    if result is None:
        return

    selected_tags = [components[i][0] for i in result]

    # Install location
    location_input = TextInput(
        tui,
        "Installation Directory",
        "Enter the installation path for NexVE:",
        default="/opt/nexve"
    )
    global INSTALL_DIR
    install_dir = location_input.run()
    if install_dir:
        INSTALL_DIR = install_dir

    # Confirmation
    confirm_items = [(t, t, d) for t, _, d in components if t in selected_tags]
    confirm = Menu(
        tui,
        "Confirm Installation",
        confirm_items if confirm_items else [("ALL", "ALL", "Install everything")],
        description=f"Directory: {INSTALL_DIR}\n"
                   "Press Enter to begin installation.",
    )
    if confirm.run() is None:
        return

    # Run installation
    steps = get_install_steps(selected_tags)
    progress = ProgressScreen(tui, "Installing NexVE...", steps)
    progress.run()

    # Show results
    results = ResultsScreen(tui)
    results.run()


if __name__ == "__main__":
    # Ensure dialog is not needed — pure Python curses
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
