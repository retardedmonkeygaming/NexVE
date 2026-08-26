#!/usr/bin/env python3
"""
NexVE Installer v3.0
Full-screen ncurses TUI installer with modern dark theme.
Black background, teal accents, bordered boxes, selectable menus, progress bars.
"""

import curses
import subprocess
import os
import sys
import time
import tempfile
import shutil

INSTALL_DIR = "/opt/nexve"
LOG = "/tmp/nexve-install.log"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
# TUI Theme — matches Proxmox installer aesthetic
# ═══════════════════════════════════════════════════════════════

class Theme:
    # Modern black theme with teal accent
    BG          = 234    # Near-black background
    FG          = 252    # Bright text
    TITLE_BG    = 236    # Slightly lighter for title bar
    TITLE_FG    = 255    # White title text
    SELECTED_BG = 36     # Teal accent (cyan)
    SELECTED_FG = 16     # Dark text on selected
    BORDER      = 240    # Subtle gray border
    HEADER      = 36     # Teal accent
    BTN_BG      = 238    # Button background
    BTN_FG      = 252    # Button text
    BTN_SEL_BG  = 36     # Teal accent for selected button
    BTN_SEL_FG  = 16     # Dark text on selected button
    PROGRESS_BG = 238    # Progress bar background
    PROGRESS_FG = 36     # Teal progress bar
    DIM         = 243    # Dimmed text
    GREEN       = 114    # Success green
    RED         = 167    # Error red
    CYAN        = 44     # Bright cyan for highlights


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, Theme.FG, Theme.BG)
    curses.init_pair(2, Theme.TITLE_FG, Theme.TITLE_BG)
    curses.init_pair(3, Theme.SELECTED_FG, Theme.SELECTED_BG)
    curses.init_pair(4, Theme.BORDER, Theme.BG)
    curses.init_pair(5, Theme.HEADER, Theme.BG)
    curses.init_pair(6, Theme.BTN_FG, Theme.BTN_BG)
    curses.init_pair(7, Theme.BTN_SEL_FG, Theme.BTN_SEL_BG)
    curses.init_pair(8, Theme.DIM, Theme.BG)
    curses.init_pair(9, Theme.PROGRESS_FG, Theme.PROGRESS_BG)
    curses.init_pair(10, Theme.GREEN, Theme.BG)
    curses.init_pair(11, Theme.RED, Theme.BG)


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

    def draw_title_bar(self, title, subtitle="NexVE v3.0"):
        bar = f"  {subtitle}  \u2502  {title}"
        self.stdscr.attron(curses.color_pair(2))
        self.stdscr.addnstr(0, 0, bar.ljust(self.w), self.w)
        self.stdscr.attroff(curses.color_pair(2))

    def draw_box(self, y, x, h, w, title="", border_color=4):
        attr = curses.color_pair(border_color)
        self.stdscr.attron(attr)
        self.stdscr.addch(y, x, "\u250c")
        self.stdscr.addnstr(y, x + 1, "\u2500" * (w - 2), w - 2)
        self.stdscr.addch(y, x + w - 1, "\u2510")
        if title:
            tx = x + (w - len(title) - 2) // 2
            self.stdscr.addstr(y, tx, f" {title} ")
        for i in range(1, h - 1):
            self.stdscr.addch(y + i, x, "\u2502")
            self.stdscr.addch(y + i, x + w - 1, "\u2502")
        self.stdscr.addch(y + h - 1, x, "\u2514")
        self.stdscr.addnstr(y + h - 1, x + 1, "\u2500" * (w - 2), w - 2)
        self.stdscr.addch(y + h - 1, x + w - 1, "\u2518")
        self.stdscr.attroff(attr)

    def draw_text(self, y, x, text, color_pair=1):
        self.stdscr.attron(curses.color_pair(color_pair))
        self.stdscr.addnstr(y, x, text, self.w - x - 1)
        self.stdscr.attroff(curses.color_pair(color_pair))

    def draw_centered(self, y, text, color_pair=1):
        x = max(0, (self.w - len(text)) // 2)
        self.draw_text(y, x, text, color_pair)

    def draw_progress(self, y, x, w, pct, label=""):
        bar_w = max(10, w - 10)
        filled = int(bar_w * pct / 100)
        empty = bar_w - filled
        bar = "\u2588" * filled + "\u2591" * empty
        self.stdscr.attron(curses.color_pair(9))
        self.stdscr.addnstr(y, x, f"[{bar}]", w)
        self.stdscr.attroff(curses.color_pair(9))
        pct_text = f" {pct:3d}%"
        self.draw_text(y, x + bar_w + 4, pct_text, 5)

    def draw_button(self, y, x, text, selected=False):
        cp = 7 if selected else 6
        self.draw_text(y, x, f"[{text}]", cp)


# ═══════════════════════════════════════════════════════════════
# Menu widget — selectable list with buttons
# ═══════════════════════════════════════════════════════════════

class Menu:
    def __init__(self, tui, title, items, description="", multi_select=False):
        self.tui = tui
        self.title = title
        self.items = items
        self.description = description
        self.multi_select = multi_select
        self.selected = 0
        self.button_idx = 0
        self.checked = set(range(len(items))) if multi_select else None
        self.scroll_offset = 0

    def draw(self):
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
                prefix = " \u25c9 " if (self.multi_select and idx in self.checked) else " \u25ba "
                t.stdscr.addstr(y, box_x + 2, f"{prefix}{tag}  \u2014  {desc}")
                t.stdscr.attroff(curses.color_pair(3))
            else:
                prefix = " \u25c9 " if (self.multi_select and idx in self.checked) else "   "
                t.draw_text(y, box_x + 2, f"{prefix}{tag}  \u2014  {desc}", 1)

        if len(self.items) > visible:
            if self.scroll_offset > 0:
                t.draw_text(item_y - 1, box_x + box_w - 3, "\u25b2", 5)
            if self.scroll_offset + visible < len(self.items):
                t.draw_text(item_y + visible, box_x + box_w - 3, "\u25bc", 5)

        # Buttons
        btn_y = box_y + box_h - 2
        btn1 = "<Continue>"
        btn2 = "<Cancel>"
        btn1_x = w // 2 - len(btn1) - 4
        btn2_x = w // 2 + 2
        t.draw_button(btn_y, btn1_x, btn1, selected=(self.button_idx == 0))
        t.draw_button(btn_y, btn2_x, btn2, selected=(self.button_idx == 1))

        if self.multi_select:
            t.draw_text(h - 2, 4, "Space: toggle  \u2502  Enter: confirm  \u2502  \u2191\u2193: navigate", 8)
        else:
            t.draw_text(h - 2, 4, "\u2191\u2193: navigate  \u2502  Enter: select  \u2502  Tab: switch", 8)

        t.stdscr.refresh()

    def run(self):
        while True:
            self.draw()
            key = self.tui.stdscr.getch()

            if key == curses.KEY_UP or key == ord('k'):
                self.selected = max(0, self.selected - 1)
                self.button_idx = 0
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.selected = min(len(self.items) - 1, self.selected + 1)
                self.button_idx = 0
            elif key == ord(' ') and self.multi_select:
                if self.selected in self.checked:
                    self.checked.discard(self.selected)
                else:
                    self.checked.add(self.selected)
            elif key == 9:  # Tab
                self.button_idx = 1 - self.button_idx
            elif key == 10:  # Enter
                if self.button_idx == 1:
                    return None
                if self.multi_select:
                    if not self.checked:
                        self.checked = set(range(len(self.items)))
                    return sorted(self.checked)
                return self.selected
            elif key == 27:  # Escape
                return None


# ═══════════════════════════════════════════════════════════════
# Progress screen
# ═══════════════════════════════════════════════════════════════

class ProgressScreen:
    def __init__(self, tui, title, steps):
        self.tui = tui
        self.title = title
        self.steps = steps
        self.current = 0
        self.pct = 0
        self.status = ""
        self.error = None
        self.log_lines = []

    def draw(self):
        t = self.tui
        t.clear()
        h, w = t.h, t.w

        t.draw_title_bar(self.title)

        box_y = 3
        box_h = h - 8
        box_x = 4
        box_w = w - 8
        t.draw_box(box_y, box_x, box_h, box_w)

        t.draw_centered(box_y + 2, "Installing NexVE...", 5)
        t.draw_centered(box_y + 4, self.status, 1)

        bar_y = box_y + 6
        bar_x = box_x + 4
        bar_w = box_w - 8
        t.draw_progress(bar_y, bar_x, bar_w, self.pct)

        step_text = f"Step {self.current}/{len(self.steps)}"
        t.draw_centered(box_y + 8, step_text, 8)

        log_y = box_y + 10
        visible_lines = box_h - 13
        tail = self.log_lines[-visible_lines:]
        for i, line in enumerate(tail):
            if log_y + i < box_y + box_h - 2:
                truncated = line[:box_w - 6]
                t.draw_text(log_y + i, box_x + 3, truncated, 8)

        if self.error:
            t.draw_centered(box_y + box_h - 2, f"Error: {self.error}", 11)

        t.stdscr.refresh()

    def run(self):
        total = len(self.steps)
        for i, (label, cmd) in enumerate(self.steps):
            self.current = i + 1
            self.pct = int((i / total) * 100)
            self.status = label
            self.log_lines.append(f"> {label}")
            self.draw()
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=300
                )
                if result.returncode == 0:
                    self.log_lines.append(f"  \u2713 {label} - done")
                else:
                    self.log_lines.append(f"  \u2717 {label} - failed (rc={result.returncode})")
                    if result.stderr.strip():
                        self.log_lines.append(f"    {result.stderr.strip()[:80]}")
            except subprocess.TimeoutExpired:
                self.log_lines.append(f"  \u2717 {label} - timeout")
            except Exception as e:
                self.error = str(e)
                self.log_lines.append(f"  \u2717 {label} - {e}")

        self.pct = 100
        self.status = "Installation complete!"
        self.draw()
        time.sleep(1)


# ═══════════════════════════════════════════════════════════════
# Results screen
# ═══════════════════════════════════════════════════════════════

class ResultsScreen:
    def __init__(self, tui):
        self.tui = tui
        self.results = []

    def check_all(self):
        """Check installed binaries and Python packages."""
        venv_python = f"{INSTALL_DIR}/venv/bin/python3"
        has_venv = os.path.isfile(venv_python)

        bins = [
            ("Python 3", "python3", None),
            ("QEMU/KVM", "qemu-system-x86_64", None),
            ("libvirt (virsh)", "virsh", None),
            ("nftables", "nft", None),
            ("ZFS (zpool)", "zpool", "Enable contrib: apt install zfsutils-linux"),
            ("BTRFS", "btrfs", "apt install btrfs-progs"),
            ("iSCSI", "iscsiadm", "apt install open-iscsi"),
            ("SMART tools", "smartctl", "apt install smartmontools"),
            ("PCI utils (lspci)", "lspci", None),
            ("noVNC/websockify", "websockify", "pip install websockify"),
        ]
        for name, cmd, fix in bins:
            ok = subprocess.run(
                f"which {cmd}", shell=True, capture_output=True
            ).returncode == 0
            self.results.append((name, ok, fix))

        py_mods = [
            ("FastAPI", "fastapi", None),
            ("SQLAlchemy", "sqlalchemy", None),
            ("psutil", "psutil", None),
            ("bcrypt", "bcrypt", None),
            ("pyotp (2FA)", "pyotp", None),
            ("ldap3", "ldap3", None),
        ]
        for name, mod, fix in py_mods:
            py = venv_python if has_venv else "python3"
            ok = subprocess.run(
                f'{py} -c "import {mod}"', shell=True, capture_output=True
            ).returncode == 0
            self.results.append((name, ok, fix))

        svc_ok = subprocess.run(
            "systemctl is-active nexve", shell=True, capture_output=True
        ).returncode == 0
        self.results.append(("NexVE service", svc_ok,
                            "Check: journalctl -u nexve -f"))

    def draw(self):
        t = self.tui
        t.clear()
        h, w = t.h, t.w

        t.draw_title_bar("Installation Results")

        box_y = 2
        box_h = h - 5
        box_x = 3
        box_w = w - 6
        t.draw_box(box_y, box_x, box_h, box_w, "Installation Complete \u2713")

        y = box_y + 2
        for name, ok, fix in self.results:
            if y >= box_y + box_h - 6:
                break
            icon = "  \u2713  " if ok else "  \u2717  "
            color = 10 if ok else 11
            t.draw_text(y, box_x + 3, icon, color)
            t.draw_text(y, box_x + 9, name, 1)
            if not ok and fix:
                t.draw_text(y + 1, box_x + 14, f"Fix: {fix}", 8)
                y += 2
            else:
                y += 1

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
        t.draw_text(y, box_x + 3, "Status:     systemctl status nexve", 8)
        y += 1
        t.draw_text(y, box_x + 3, "Logs:       journalctl -u nexve -f", 8)
        y += 1
        t.draw_text(y, box_x + 3, f"Install:    {INSTALL_DIR}", 8)

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
            if key in (10, 13, 27):
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

        field_y = box_y + 4
        field_x = box_x + 3
        field_w = box_w - 6

        t.stdscr.attron(curses.color_pair(1))
        t.stdscr.addnstr(field_y, field_x, " " * field_w, field_w)
        display = self.value[:field_w - 1]
        t.stdscr.addnstr(field_y, field_x, display, field_w)
        cx = field_x + min(self.cursor, field_w - 1)
        t.stdscr.addch(field_y, cx, "_")
        t.stdscr.attroff(curses.color_pair(1))

        btn_y = box_y + 7
        btn1_x = w // 2 - 14
        btn2_x = w // 2 + 4
        t.draw_button(btn_y, btn1_x, "<Continue>", selected=True)
        t.draw_button(btn_y, btn2_x, "<Cancel>", selected=False)

        t.draw_text(h - 2, 4, "Type to enter  \u2502  Enter: confirm  \u2502  Tab: switch", 8)
        t.stdscr.refresh()

    def run(self):
        self.draw()
        while True:
            key = self.tui.stdscr.getch()
            if key in (10, 13):
                return self.value
            elif key == 27:
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
# Package installer helper — tries multiple package names
# ═══════════════════════════════════════════════════════════════

def apt_install(*pkgs, extra_args=""):
    """Try to install packages with fallbacks. Always succeeds."""
    pkg_str = " ".join(pkgs)
    return (
        f"apt-get install -y -qq {extra_args} {pkg_str} 2>/dev/null || "
        f"apt-get install -y {extra_args} {pkg_str} 2>/dev/null || "
        f"echo 'Packages not available: {pkg_str}' && true"
    )


def systemd_enable(service_name):
    """Enable a systemd service, ignoring errors."""
    return (
        f"systemctl enable {service_name} 2>/dev/null || true"
    )


# ═══════════════════════════════════════════════════════════════
# Build install steps based on selected components
# ═══════════════════════════════════════════════════════════════

def get_install_steps(choices):
    steps = []
    pip = f"{INSTALL_DIR}/venv/bin/pip"
    venv = f"{INSTALL_DIR}/venv/bin/python3"

    # Step 1: System update
    steps.append(("Updating package lists",
        "apt-get update -qq 2>/dev/null || apt-get update 2>/dev/null || true"))

    # Step 2: Enable contrib/non-free repos for ZFS
    if "ZFS" in choices:
        steps.append(("Enabling contrib/non-free repos",
            "sed -i 's/^# *deb /deb /' /etc/apt/sources.list 2>/dev/null || true; "
            "if [ -f /etc/apt/sources.list.d/debian.sources ]; then "
            "  sed -i 's/Components: main$/Components: main contrib non-free non-free-firmware/' "
            "  /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; "
            "fi; "
            "apt-get update -qq 2>/dev/null || true"))

    # ── CORE ──
    if "CORE" in choices:
        steps.append(("Installing Python 3 + dev headers",
            apt_install("python3", "python3-pip", "python3-venv", "python3-dev",
                        "libffi-dev", "libssl-dev", "libjpeg-dev", "zlib1g-dev")))
        steps.append(("Installing build tools",
            apt_install("build-essential", "gcc", "g++", "make")))
        steps.append(("Installing system utilities",
            apt_install("git", "curl", "wget", "jq", "openssl", "sudo", "cron",
                        "lsb-release", "ca-certificates", "gnupg")))

    # ── KVM/QEMU ──
    if "KVM" in choices:
        steps.append(("Installing QEMU/KVM",
            f"({apt_install('qemu-kvm', 'qemu-system-x86', 'qemu-utils')} || "
            f"{apt_install('qemu-system-x86', 'qemu-utils')}) && true"))
        steps.append(("Installing libvirt daemon",
            f"({apt_install('libvirt-daemon-system', 'libvirt-clients')} || "
            f"{apt_install('libvirt-daemon', 'libvirt-clients')}) && true"))
        steps.append(("Installing virt-manager + OVMF UEFI firmware",
            f"{apt_install('virtinst', 'ovmf')} && true"))
        steps.append(("Enabling libvirtd",
            "systemctl enable --now libvirtd 2>/dev/null || "
            "systemctl enable libvirtd 2>/dev/null || true"))

    # ── LXC ──
    if "LXC" in choices:
        steps.append(("Installing LXC container runtime",
            f"{apt_install('lxc', 'lxc-utils')} && true"))
        steps.append(("Installing debootstrap for containers",
            apt_install("debootstrap")))

    # ── ZFS ──
    if "ZFS" in choices:
        steps.append(("Installing ZFS utilities",
            f"({apt_install('zfsutils-linux')} || "
            f"{apt_install('zfsutils')} || "
            f"echo 'ZFS not available - install zfsutils-linux from contrib repo') && true"))

    # ── LVM ──
    if "LVM" in choices:
        steps.append(("Installing LVM2",
            apt_install("lvm2")))

    # ── BTRFS ──
    if "BTRFS" in choices:
        steps.append(("Installing BTRFS tools",
            apt_install("btrfs-progs")))

    # ── NFS ──
    if "NFS" in choices:
        steps.append(("Installing NFS client",
            apt_install("nfs-common")))

    # ── CIFS ──
    if "CIFS" in choices:
        steps.append(("Installing CIFS/SMB client",
            f"{apt_install('cifs-utils')}; {apt_install('samba-common-bin')} && true"))

    # ── iSCSI ──
    if "ISCSI" in choices:
        steps.append(("Installing iSCSI initiator",
            f"({apt_install('open-iscsi')} || "
            f"{apt_install('iscsi-initiator-utils')}) && "
            f"{systemd_enable('iscsid')} && true"))
        steps.append(("Installing SMART + disk tools",
            f"{apt_install('smartmontools')}; "
            f"{apt_install('gdisk')}; "
            f"{apt_install('hdparm')} && true"))

    # ── NETWORKING ──
    if "NET" in choices:
        steps.append(("Installing networking tools",
            f"{apt_install('bridge-utils', 'iproute2', 'net-tools')}; "
            f"{apt_install('vlan', 'ethtool')} && true"))
        steps.append(("Installing PCI/USB utils for passthrough",
            apt_install("pciutils", "usbutils")))

    # ── FIREWALL ──
    if "FIREWALL" in choices:
        steps.append(("Installing nftables firewall",
            f"{apt_install('nftables')} && "
            f"{systemd_enable('nftables')} && true"))

    # ── CONSOLE ──
    if "CONSOLE" in choices:
        steps.append(("Installing noVNC + websockify",
            f"({apt_install('novnc', 'websockify')} || "
            f"{apt_install('python3-novnc')} || "
            f"({pip} install websockify -q 2>/dev/null || true)) && true"))
        steps.append(("Installing xterm for shell",
            apt_install("xterm")))

    # ── CLOUD-INIT ──
    if "CLOUD" in choices:
        steps.append(("Installing cloud-init",
            f"{apt_install('cloud-init')}; {apt_install('cloud-utils')} && true"))
        steps.append(("Installing ISO creation tools",
            f"{apt_install('genisoimage')}; {apt_install('xorriso')} && true"))

    # ── MONITORING ──
    if "MONITOR" in choices:
        steps.append(("Installing system monitoring tools",
            apt_install("sysstat", "procps")))

    # ── BACKUP ──
    if "BACKUP" in choices:
        steps.append(("Enabling cron daemon",
            f"{systemd_enable('cron')} || "
            f"{systemd_enable('cronie')} || true"))

    # Always install rsyslog
    steps.append(("Installing rsyslog",
        apt_install("rsyslog")))

    # ═══════════════════════════════════════════════════════════
    # Project setup
    # ═══════════════════════════════════════════════════════════

    steps.append(("Copying NexVE files",
        f"mkdir -p {INSTALL_DIR} && "
        f"cp -r {SCRIPT_DIR}/backend {INSTALL_DIR}/ 2>/dev/null || true; "
        f"cp -r {SCRIPT_DIR}/static {INSTALL_DIR}/ 2>/dev/null || true; "
        f"cp -r {SCRIPT_DIR}/frontend {INSTALL_DIR}/ 2>/dev/null || true; "
        f"cp -r {SCRIPT_DIR}/data {INSTALL_DIR}/ 2>/dev/null || true; "
        f"cp -r {SCRIPT_DIR}/docs {INSTALL_DIR}/ 2>/dev/null || true; "
        f"cp {SCRIPT_DIR}/requirements.txt {INSTALL_DIR}/ 2>/dev/null || true; "
        f"cp {SCRIPT_DIR}/install.py {INSTALL_DIR}/ 2>/dev/null || true; "
        f"true"))

    steps.append(("Creating data directories",
        f"mkdir -p {INSTALL_DIR}/data/backups {INSTALL_DIR}/data/cloud-init "
        f"{INSTALL_DIR}/data/isos {INSTALL_DIR}/data/uploads "
        f"{INSTALL_DIR}/data/metrics && "
        f"mkdir -p {INSTALL_DIR}/static/css {INSTALL_DIR}/static/js "
        f"{INSTALL_DIR}/static/images {INSTALL_DIR}/static/fonts && "
        f"mkdir -p /var/lib/libvirt/images 2>/dev/null || true && "
        f"mkdir -p /var/lib/vz/template/cache /var/lib/vz/images "
        f"/var/lib/vz/rootdir 2>/dev/null || true && "
        f"mkdir -p /var/lib/nexve/backups /var/lib/nexve/iso 2>/dev/null || true && "
        f"true"))

    steps.append(("Creating Python virtual environment",
        f"python3 -m venv {INSTALL_DIR}/venv && "
        f"{pip} install --upgrade pip setuptools wheel -q 2>/dev/null"))

    steps.append(("Installing Python dependencies",
        f"{pip} install -r {INSTALL_DIR}/requirements.txt 2>/dev/null || "
        f"{pip} install -r {INSTALL_DIR}/requirements.txt 2>&1 | tail -5"))

    steps.append(("Installing libvirt Python bindings",
        f"{pip} install libvirt-python 2>/dev/null || true"))

    # ═══════════════════════════════════════════════════════════
    # System configuration
    # ═══════════════════════════════════════════════════════════

    _hostname = globals().get('server_hostname', 'nexve')
    _static_ip = globals().get('static_ip', '')
    _gateway = globals().get('gateway', '')
    _dns_servers = globals().get('dns_servers', '1.1.1.1, 8.8.8.8')
    _tz = globals().get('server_tz', 'UTC')

    steps.append(("Setting hostname",
        f"hostnamectl set-hostname '{_hostname}' 2>/dev/null || true; "
        f"grep -q '127.0.1.1' /etc/hosts && sed -i '/127.0.1.1/c\\127.0.1.1\t{_hostname}' /etc/hosts || echo '127.0.1.1\t{_hostname}' >> /etc/hosts 2>/dev/null || true; "
        f"echo 'Hostname set to {_hostname}'"))

    steps.append(("Setting timezone",
        f"timedatectl set-timezone '{_tz}' 2>/dev/null || true; "
        f"echo 'Timezone set to {_tz}'"))

    steps.append(("Configuring DNS",
        f"echo '# NexVE DNS' > /etc/resolv.conf 2>/dev/null || true; "
        f"for s in $(echo '{_dns_servers}' | tr ',' ' '); do echo \"nameserver $s\" >> /etc/resolv.conf; done 2>/dev/null || true; "
        f"echo 'DNS configured: {_dns_servers}'"))

    # ═══════════════════════════════════════════════════════════
    # Permissions & firewall
    # ═══════════════════════════════════════════════════════════

    steps.append(("Setting user permissions",
        "usermod -aG libvirt ${SUDO_USER:-root} 2>/dev/null || true; "
        "usermod -aG kvm ${SUDO_USER:-root} 2>/dev/null || true; true"))

    steps.append(("Configuring nftables base rules",
        "nft add table inet nexve 2>/dev/null || true; "
        "nft add chain inet nexve input '{ policy accept; }' 2>/dev/null || true; "
        "nft add chain inet nexve forward '{ policy accept; }' 2>/dev/null || true; "
        "nft add chain inet nexve host '{ policy accept; }' 2>/dev/null || true; true"))

    # ═══════════════════════════════════════════════════════════
    # Create systemd service file using a proper heredoc
    # ═══════════════════════════════════════════════════════════

    secret = subprocess.run(
        "openssl rand -hex 32", shell=True, capture_output=True, text=True
    ).stdout.strip() or "changeme_generate_a_real_secret"

    svc_content = f"""[Unit]
Description=NexVE Hypervisor Management Dashboard
After=network-online.target libvirtd.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}/backend
Environment=NEXVE_SECRET={secret}
Environment=PYTHONUNBUFFERED=1
ExecStart={INSTALL_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
User=root
Group=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    # Write service file directly from Python (more reliable than heredoc via shell)
    svc_path = "/etc/systemd/system/nexve.service"
    try:
        os.makedirs(os.path.dirname(svc_path), exist_ok=True)
        with open(svc_path, "w") as sf:
            sf.write(svc_content)
        steps.append(("Creating systemd service", "echo 'Service file written' && true"))
    except Exception as e:
        steps.append(("Creating systemd service", f"echo 'Failed to write service file: {e}' && true"))

    steps.append(("Starting NexVE service",
        "systemctl daemon-reload 2>/dev/null || true; "
        "systemctl enable nexve 2>/dev/null || true; "
        "systemctl restart nexve 2>/dev/null || true; "
        "sleep 3; "
        "if systemctl is-active nexve >/dev/null 2>&1; then "
        "  echo 'NexVE service started successfully'; "
        "else "
        "  echo 'Service start may require reboot'; "
        "fi"))

    steps.append(("Setting file permissions",
        f"chmod -R 755 {INSTALL_DIR}/static 2>/dev/null || true; "
        f"chmod 700 {INSTALL_DIR}/data 2>/dev/null || true; true"))

    steps.append(("Cleaning up package cache",
        "apt-get autoremove -y -qq 2>/dev/null || true; "
        "apt-get clean 2>/dev/null || true; true"))

    return steps


def get_uninstall_steps():
    steps = []
    steps.append(("Stopping NexVE service",
        "systemctl stop nexve 2>/dev/null || true; "
        "systemctl disable nexve 2>/dev/null || true"))
    steps.append(("Removing systemd service",
        "rm -f /etc/systemd/system/nexve.service; "
        "systemctl daemon-reload 2>/dev/null || true"))
    steps.append(("Removing NexVE files",
        f"rm -rf {INSTALL_DIR} 2>/dev/null || true"))
    steps.append(("Removing nftables rules",
        "nft delete table inet nexve 2>/dev/null || true"))
    steps.append(("Removing cron jobs",
        "crontab -l 2>/dev/null | grep -v nexve | crontab - 2>/dev/null || true"))
    steps.append(("Removing data directories",
        "rm -rf /var/lib/nexve 2>/dev/null || true"))
    return steps


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main(stdscr):
    global INSTALL_DIR
    init_colors()
    tui = TUI(stdscr)

    if os.geteuid() != 0:
        tui.clear()
        tui.draw_centered(tui.h // 2, "Error: Must be run as root", 11)
        tui.draw_centered(tui.h // 2 + 1, "Usage: sudo python3 install.py", 8)
        tui.stdscr.getch()
        return

    # ── Main menu ──
    main_items = [
        ("INSTALL", "Install NexVE", "Set up NexVE hypervisor management platform"),
        ("UNINSTALL", "Uninstall NexVE", "Remove NexVE and all associated files"),
        ("EXIT", "Exit installer", "Close without doing anything"),
    ]
    main_menu = Menu(
        tui,
        "NexVE v2.1 Installer",
        main_items,
        description="NexVE Hypervisor Management Platform\n"
                   "Choose an action below.",
    )
    choice = main_menu.run()

    if choice is None or choice == 2:
        return

    if choice == 1:
        confirm_items = [
            ("UNINSTALL", "UNINSTALL", "Remove all NexVE files and services"),
        ]
        confirm = Menu(
            tui,
            "Confirm Uninstall",
            confirm_items,
            description=f"This will remove NexVE from: {INSTALL_DIR}\n"
                       "The service will be stopped and removed.\n"
                       "Data in /var/lib/nexve will also be removed.\n\n"
                       "Are you sure?",
        )
        if confirm.run() is None:
            return

        steps = get_uninstall_steps()
        progress = ProgressScreen(tui, "Uninstalling NexVE...", steps)
        progress.run()

        tui.clear()
        tui.draw_title_bar("Uninstall Complete")
        tui.draw_centered(tui.h // 2, "NexVE has been uninstalled.", 10)
        tui.draw_centered(tui.h // 2 + 2, "Press any key to exit.", 8)
        tui.stdscr.getch()
        return

    # ── Install flow ──
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
        description="Use Space to toggle, \u2191\u2193 to navigate, Enter to confirm.\n"
                    "All components are recommended for a full installation.",
        multi_select=True,
    )
    selector.checked = set(range(len(components)))
    result = selector.run()

    if result is None:
        return

    selected_tags = [components[i][0] for i in result]

    # ── Hostname ──
    hostname_input = TextInput(
        tui,
        "Server Hostname",
        "Enter the server hostname (visible in the web UI):",
        default="nexve"
    )
    server_hostname = hostname_input.run() or "nexve"

    # ── Network ──
    # Detect current IP
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        current_ip = s.getsockname()[0]
        s.close()
    except Exception:
        current_ip = "192.168.1.100"

    ip_input = TextInput(
        tui,
        "Network Configuration",
        "Static IP address (leave blank for DHCP):",
        default=current_ip
    )
    static_ip = ip_input.run() or ""

    gw_input = TextInput(
        tui,
        "Network Configuration",
        "Gateway (e.g. 192.168.1.1):",
        default=""
    )
    gateway = gw_input.run() or ""

    dns_input = TextInput(
        tui,
        "DNS Configuration",
        "DNS servers (comma separated):",
        default="1.1.1.1, 8.8.8.8"
    )
    dns_servers = dns_input.run() or "1.1.1.1, 8.8.8.8"

    # ── Timezone ──
    import subprocess as _sp
    try:
        current_tz = _sp.run("timedatectl show --property=Timezone --value 2>/dev/null",
                           shell=True, capture_output=True, text=True).stdout.strip()
    except Exception:
        current_tz = "UTC"

    tz_input = TextInput(
        tui,
        "Timezone",
        "Enter timezone (e.g. America/New_York, Europe/London):",
        default=current_tz or "UTC"
    )
    server_tz = tz_input.run() or "UTC"

    # Install location
    location_input = TextInput(
        tui,
        "Installation Directory",
        "Enter the installation path for NexVE:",
        default=INSTALL_DIR
    )
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
                   f"Components: {len(selected_tags)} selected\n"
                   "Press Enter to begin installation.",
    )
    if confirm.run() is None:
        return

    # Clear log
    with open(LOG, "w") as f:
        f.write("")

    # Run installation
    steps = get_install_steps(selected_tags)
    progress = ProgressScreen(tui, "Installing NexVE...", steps)
    progress.run()

    # Show results
    results = ResultsScreen(tui)
    results.run()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
