#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# NexVE Installer v2.0
# ncurses TUI installer (dialog-based, Proxmox/Debian style)
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Config ──
INSTALL_DIR="/opt/nexve"
LOG="/tmp/nexve-install.log"
HEIGHT=20
WIDTH=70
CHOICE_HEIGHT=14

# ── Ensure dialog is available ──
if ! command -v dialog &>/dev/null; then
    apt-get update -qq 2>/dev/null
    apt-get install -y -qq dialog 2>/dev/null
fi

# ── Helpers ──
log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

do_install() {
    local label="$1"
    shift
    log "Installing: $label"
    "$@" >> "$LOG" 2>&1
}

run_step() {
    local label="$1"
    local cmd="$2"
    log "Running: $label"
    eval "$cmd" >> "$LOG" 2>&1
}

# ── Start ──
export DEBIAN_FRONTEND=noninteractive
: > "$LOG"

# ═══════════════════════════════════════════════════════════════════════
# MAIN MENU — Choose installation type
# ═══════════════════════════════════════════════════════════════════════
show_main_menu() {
    dialog --title "NexVE v2.0 Installer" \
        --backtitle "NexVE Hypervisor Management Platform" \
        --msgbox "\
╔═══════════════════════════════════════════════════════════════╗\n\
║                                                               ║\n\
║              ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗     ║\n\
║              ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝     ║\n\
║              ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗     ║\n\
║              ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║     ║\n\
║              ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║     ║\n\
║              ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝     ║\n\
║                                                               ║\n\
║          Hypervisor Management Platform Installer v2.0        ║\n\
║                                                               ║\n\
╠═══════════════════════════════════════════════════════════════╣\n\
║                                                               ║\n\
║   NexVE is an open-source hypervisor management dashboard     ║\n\
║   inspired by Proxmox VE. It manages KVM virtual machines,   ║\n\
║   LXC containers, storage, networking, and more.             ║\n\
║                                                               ║\n\
║   This installer will:                                       ║\n\
║     • Install all required system packages                    ║\n\
║     • Set up Python virtual environment                       ║\n\
║     • Configure KVM/QEMU + libvirt                            ║\n\
║     • Install storage backends (ZFS, LVM, BTRFS, NFS, etc)  ║\n\
║     • Set up networking, firewall, and console access         ║\n\
║     • Create a systemd service                               ║\n\
║                                                               ║\n\
║   Target: ${INSTALL_DIR}                                      ║\n\
║                                                               ║\n\
╚═══════════════════════════════════════════════════════════════╝" \
        22 74
}

# ═══════════════════════════════════════════════════════════════════════
# COMPONENT SELECTION — Choose what to install
# ═══════════════════════════════════════════════════════════════════════
show_component_menu() {
    # Returns selected components as space-separated tag list
    CHOICES=$(dialog --title "NexVE Installer" \
        --backtitle "Choose components to install" \
        --checklist "\
 Select the components you want to install.\n\
 Use arrow keys to navigate, Space to toggle, Enter to confirm." \
        $HEIGHT $WIDTH $CHOICE_HEIGHT \
        CORE "Core system (Python, FastAPI, Uvicorn)" ON \
        KVM "KVM/QEMU virtualization + libvirt" ON \
        LXC "LXC container runtime" ON \
        ZFS "ZFS storage pools & datasets" ON \
        LVM "LVM volume groups & logical volumes" ON \
        BTRFS "BTRFS filesystem support" ON \
        NFS "NFS client (remote mounts)" ON \
        CIFS "CIFS/SMB client (Windows shares)" ON \
        ISCSI "iSCSI initiator (SAN storage)" ON \
        NET "Bridges, VLANs, bonding, nftables" ON \
        FIREWALL "nftables firewall + rate limiting" ON \
        CONSOLE "noVNC browser console + web terminal" ON \
        CLOUD "Cloud-init provisioning + ISO tools" ON \
        MONITOR "System monitoring (CPU/RAM/disk)" ON \
        BACKUP "Cron scheduler for backup jobs" ON \
        GPU "GPU/USB passthrough detection" ON \
        3>&1 1>&2 2>&3)

    if [ -z "$CHOICES" ]; then
        dialog --title "NexVE Installer" \
            --backtitle "No components selected" \
            --yesno "No components selected. Do you want to install everything?" \
            7 $WIDTH
        if [ $? -eq 0 ]; then
            CHOICES="CORE KVM LXC ZFS LVM BTRFS NFS CIFS ISCSI NET FIREWALL CONSOLE CLOUD MONITOR BACKUP GPU"
        else
            dialog --title "NexVE Installer" --msgbox "Installation cancelled." 5 $WIDTH
            exit 0
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════
# INSTALL LOCATION
# ═══════════════════════════════════════════════════════════════════════
show_location_menu() {
    INSTALL_DIR=$(dialog --title "NexVE Installer" \
        --backtitle "Installation directory" \
        --inputbox "\
 Enter the installation directory for NexVE.\n\
 Default: /opt/nexve" \
        8 $WIDTH "/opt/nexve" \
        3>&1 1>&2 2>&3)

    [ -z "$INSTALL_DIR" ] && INSTALL_DIR="/opt/nexve"
}

# ═══════════════════════════════════════════════════════════════════════
# CONFIRM BEFORE INSTALLING
# ═══════════════════════════════════════════════════════════════════════
show_confirm() {
    COMP_LIST=""
    if echo "$CHOICES" | grep -q "CORE";   then COMP_LIST="${COMP_LIST}  • Core system (Python, FastAPI)\n"; fi
    if echo "$CHOICES" | grep -q "KVM";    then COMP_LIST="${COMP_LIST}  • KVM/QEMU + libvirt\n"; fi
    if echo "$CHOICES" | grep -q "LXC";    then COMP_LIST="${COMP_LIST}  • LXC containers\n"; fi
    if echo "$CHOICES" | grep -q "ZFS";    then COMP_LIST="${COMP_LIST}  • ZFS storage\n"; fi
    if echo "$CHOICES" | grep -q "LVM";    then COMP_LIST="${COMP_LIST}  • LVM storage\n"; fi
    if echo "$CHOICES" | grep -q "BTRFS";  then COMP_LIST="${COMP_LIST}  • BTRFS storage\n"; fi
    if echo "$CHOICES" | grep -q "NFS";    then COMP_LIST="${COMP_LIST}  • NFS client\n"; fi
    if echo "$CHOICES" | grep -q "CIFS";   then COMP_LIST="${COMP_LIST}  • CIFS/SMB client\n"; fi
    if echo "$CHOICES" | grep -q "ISCSI";  then COMP_LIST="${COMP_LIST}  • iSCSI initiator\n"; fi
    if echo "$CHOICES" | grep -q "NET";    then COMP_LIST="${COMP_LIST}  • Networking (bridges, VLANs, bonds)\n"; fi
    if echo "$CHOICES" | grep -q "FIREWALL"; then COMP_LIST="${COMP_LIST}  • Firewall (nftables)\n"; fi
    if echo "$CHOICES" | grep -q "CONSOLE"; then COMP_LIST="${COMP_LIST}  • Console (noVNC + web terminal)\n"; fi
    if echo "$CHOICES" | grep -q "CLOUD";  then COMP_LIST="${COMP_LIST}  • Cloud-init + ISO tools\n"; fi
    if echo "$CHOICES" | grep -q "MONITOR"; then COMP_LIST="${COMP_LIST}  • System monitoring\n"; fi
    if echo "$CHOICES" | grep -q "BACKUP"; then COMP_LIST="${COMP_LIST}  • Backup scheduler\n"; fi
    if echo "$CHOICES" | grep -q "GPU";    then COMP_LIST="${COMP_LIST}  • GPU/USB passthrough\n"; fi

    dialog --title "NexVE Installer" \
        --backtitle "Confirm installation" \
        --yesno "\
╔═══════════════════════════════════════════════════════════╗\n\
║                  Ready to Install                        ║\n\
╠═══════════════════════════════════════════════════════════╣\n\
║                                                           ║\n\
║  Install directory: ${INSTALL_DIR}\n\
║                                                           ║\n\
║  Components to install:                                   ║\n\
$(echo -e "$COMP_LIST")\
║                                                           ║\n\
║  This will install packages and configure services.       ║\n\
║  Root access is required.                                 ║\n\
║                                                           ║\n\
╚═══════════════════════════════════════════════════════════╝\n\
\n\
Proceed with installation?" \
        20 72

    if [ $? -ne 0 ]; then
        dialog --title "NexVE Installer" --msgbox "Installation cancelled by user." 5 $WIDTH
        exit 0
    fi
}

# ═══════════════════════════════════════════════════════════════════════
# INSTALLATION — Runs with progress gauge
# ═══════════════════════════════════════════════════════════════════════
run_installation() {
    TOTAL_STEPS=17

    {
        # ── Step 1: System update ──
        echo "XXX-1"
        echo "1"
        echo "Updating package lists..."
        apt-get update -qq 2>/dev/null || true
        sleep 0.5

        # ── Step 2: Core Python ──
        if echo "$CHOICES" | grep -q "CORE"; then
            echo "XXX-5"
            echo "5"
            echo "Installing Python 3 + build tools..."
            do_install "python3" apt-get install -y -qq python3 python3-pip python3-venv python3-dev libffi-dev libssl-dev libjpeg-dev zlib1g-dev
            do_install "build-essential" apt-get install -y -qq build-essential gcc g++ make
            do_install "tools" apt-get install -y -qq git curl wget jq openssl sudo cron
        else
            echo "XXX-5"; echo "5"; echo "Skipping core (not selected)..."
        fi

        # ── Step 3: KVM/QEMU ──
        if echo "$CHOICES" | grep -q "KVM"; then
            echo "XXX-12"
            echo "12"
            echo "Installing KVM/QEMU + libvirt..."
            do_install "qemu" apt-get install -y -qq qemu-kvm qemu-system-x86 qemu-utils qemu-system
            do_install "libvirt" apt-get install -y -qq libvirt-daemon-system libvirt-clients libvirt-dev
            do_install "virtinst" apt-get install -y -qq virtinst virt-manager ovmf
            do_install "libvirt-py" pip3 install libvirt-python 2>/dev/null || apt-get install -y -qq python3-libvirt
            systemctl enable --now libvirtd 2>/dev/null || true
        else
            echo "XXX-12"; echo "12"; echo "Skipping KVM (not selected)..."
        fi

        # ── Step 4: LXC ──
        if echo "$CHOICES" | grep -q "LXC"; then
            echo "XXX-18"
            echo "18"
            echo "Installing LXC containers..."
            do_install "lxc" apt-get install -y -qq lxc lxc-utils lxc-templates
            do_install "debootstrap" apt-get install -y -qq debootstrap
        else
            echo "XXX-18"; echo "18"; echo "Skipping LXC (not selected)..."
        fi

        # ── Step 5: Storage ──
        echo "XXX-30"
        echo "30"
        echo "Installing storage backends..."
        if echo "$CHOICES" | grep -q "ZFS"; then
            do_install "zfs" apt-get install -y -qq zfsutils-linux
            echo "XXX-33"; echo "33"; echo "ZFS installed..."
        fi
        if echo "$CHOICES" | grep -q "LVM"; then
            do_install "lvm" apt-get install -y -qq lvm2
            echo "XXX-36"; echo "36"; echo "LVM installed..."
        fi
        if echo "$CHOICES" | grep -q "BTRFS"; then
            do_install "btrfs" apt-get install -y -qq btrfs-progs
            echo "XXX-39"; echo "39"; echo "BTRFS installed..."
        fi
        if echo "$CHOICES" | grep -q "NFS"; then
            do_install "nfs" apt-get install -y -qq nfs-common
        fi
        if echo "$CHOICES" | grep -q "CIFS"; then
            do_install "cifs" apt-get install -y -qq cifs-utils samba-common-bin
        fi
        if echo "$CHOICES" | grep -q "ISCSI"; then
            do_install "iscsi" apt-get install -y -qq open-iscsi iscsi-initiator-utils
            systemctl enable iscsid 2>/dev/null || true
            do_install "smart" apt-get install -y -qq smartmontools gdisk hdparm
        fi

        # ── Step 6: Networking ──
        if echo "$CHOICES" | grep -q "NET"; then
            echo "XXX-45"
            echo "45"
            echo "Installing networking..."
            do_install "net" apt-get install -y -qq bridge-utils iproute2 net-tools vlan ethtool ifenslave
        fi
        if echo "$CHOICES" | grep -q "FIREWALL"; then
            do_install "nftables" apt-get install -y -qq nftables
            systemctl enable nftables 2>/dev/null || true
        fi
        if echo "$CHOICES" | grep -q "GPU"; then
            do_install "pci" apt-get install -y -qq pciutils usbutils
        fi

        # ── Step 7: Console ──
        if echo "$CHOICES" | grep -q "CONSOLE"; then
            echo "XXX-52"
            echo "52"
            echo "Installing console access..."
            do_install "novnc" apt-get install -y -qq novnc websockify
            do_install "xterm" apt-get install -y -qq xterm
        fi

        # ── Step 8: Cloud-init + ISO ──
        if echo "$CHOICES" | grep -q "CLOUD"; then
            echo "XXX-56"
            echo "56"
            echo "Installing cloud-init + ISO tools..."
            do_install "cloud" apt-get install -y -qq cloud-init cloud-utils
            do_install "iso" apt-get install -y -qq genisoimage xorriso
        fi

        # ── Step 9: Monitoring + Cron ──
        if echo "$CHOICES" | grep -q "MONITOR"; then
            echo "XXX-60"
            echo "60"
            echo "Installing monitoring tools..."
            do_install "monitor" apt-get install -y -qq sysstat procps
        fi
        if echo "$CHOICES" | grep -q "BACKUP"; then
            do_install "cron" apt-get install -y -qq cron 2>/dev/null || true
            systemctl enable cron 2>/dev/null || true
        fi
        do_install "rsyslog" apt-get install -y -qq rsyslog 2>/dev/null || true

        # ── Step 10: Project files ──
        echo "XXX-65"
        echo "65"
        echo "Setting up NexVE project files..."
        mkdir -p "${INSTALL_DIR}"
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        cp -r "${SCRIPT_DIR}"/backend "${INSTALL_DIR}/" 2>/dev/null || true
        cp -r "${SCRIPT_DIR}"/frontend "${INSTALL_DIR}/" 2>/dev/null || true
        cp -r "${SCRIPT_DIR}"/static "${INSTALL_DIR}/" 2>/dev/null || true
        cp -r "${SCRIPT_DIR}"/docs "${INSTALL_DIR}/" 2>/dev/null || true
        cp -r "${SCRIPT_DIR}"/data "${INSTALL_DIR}/" 2>/dev/null || true
        cp "${SCRIPT_DIR}"/requirements.txt "${INSTALL_DIR}/" 2>/dev/null || true
        mkdir -p "${INSTALL_DIR}"/data/{backups,cloud-init,isos,uploads,metrics}
        mkdir -p "${INSTALL_DIR}"/static/{css,js,images,fonts}
        mkdir -p /var/lib/libvirt/images
        mkdir -p /var/lib/vz/{template/cache,images,rootdir}
        mkdir -p /var/lib/nexve/{backups,iso}

        # ── Step 11: Python venv ──
        echo "XXX-70"
        echo "70"
        echo "Creating Python virtual environment..."
        python3 -m venv "${INSTALL_DIR}/venv"
        source "${INSTALL_DIR}/venv/bin/activate"
        pip install --upgrade pip setuptools wheel -q 2>/dev/null

        echo "XXX-78"
        echo "78"
        echo "Installing Python dependencies..."
        pip install -r "${INSTALL_DIR}/requirements.txt" -q 2>/dev/null

        echo "XXX-80"
        echo "80"
        echo "Installing libvirt Python bindings..."
        pip install libvirt-python -q 2>/dev/null || true

        # ── Step 12: Permissions ──
        echo "XXX-83"
        echo "83"
        echo "Setting user permissions..."
        usermod -aG libvirt "$SUDO_USER" 2>/dev/null || true
        usermod -aG kvm "$SUDO_USER" 2>/dev/null || true

        # ── Step 13: Firewall ──
        echo "XXX-85"
        echo "85"
        echo "Configuring nftables base rules..."
        nft add table inet nexve 2>/dev/null || true
        nft add chain inet nexve input '{ policy accept; }' 2>/dev/null || true
        nft add chain inet nexve forward '{ policy accept; }' 2>/dev/null || true
        nft add chain inet nexve host '{ policy accept; }' 2>/dev/null || true

        # ── Step 14: Systemd service ──
        echo "XXX-88"
        echo "88"
        echo "Creating NexVE systemd service..."
        SECRET=$(openssl rand -hex 32)
        cat > /etc/systemd/system/nexve.service << SVCEOF
[Unit]
Description=NexVE Hypervisor Management Dashboard
Documentation=https://github.com/nexve/nexve
After=network-online.target libvirtd.service iscsid.service
Wants=network-online.target
Requires=libvirtd.service

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}/backend
Environment=NEXVE_SECRET=${SECRET}
Environment=PYTHONUNBUFFERED=1
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.main:app \\
    --host 0.0.0.0 \\
    --port 8000 \\
    --workers 1 \\
    --log-level info
Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60
User=root
Group=root
ProtectSystem=full
ProtectHome=read-only
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
SVCEOF

        # ── Step 15: Start service ──
        echo "XXX-92"
        echo "92"
        echo "Starting NexVE service..."
        systemctl daemon-reload
        systemctl enable nexve 2>/dev/null
        systemctl start nexve 2>/dev/null
        sleep 3

        # ── Step 16: Permissions ──
        echo "XXX-95"
        echo "95"
        echo "Setting file permissions..."
        chmod -R 755 "${INSTALL_DIR}/static" 2>/dev/null || true
        chmod 600 /etc/systemd/system/nexve.service 2>/dev/null || true
        chmod 700 "${INSTALL_DIR}/data" 2>/dev/null || true

        # ── Step 17: Cleanup ──
        echo "XXX-97"
        echo "97"
        echo "Cleaning up..."
        apt-get autoremove -y -qq 2>/dev/null || true
        apt-get clean 2>/dev/null || true

        echo "XXX-100"
        echo "100"
        echo "Installation complete!"
        sleep 1
    } | dialog --title "NexVE Installer" \
        --backtitle "Installing NexVE..." \
        --gauge "\
 Installing NexVE components...\n\
\n\
 This may take several minutes depending on your\n\
 system and internet connection.\n\
\n\
 Do not close this window." \
        14 $WIDTH 0
}

# ═══════════════════════════════════════════════════════════════════════
# POST-INSTALL VERIFICATION — Show results
# ═══════════════════════════════════════════════════════════════════════
show_results() {
    # Build results text
    RESULT="╔═══════════════════════════════════════════════════════════╗\n"
    RESULT="${RESULT}║               Installation Results                       ║\n"
    RESULT="${RESULT}╠═══════════════════════════════════════════════════════════╣\n"

    # Check each installed component
    check_bin() {
        local name="$1"
        local cmd="$2"
        if command -v "$cmd" &>/dev/null; then
            RESULT="${RESULT}║  [✓]  ${name}$(printf '%*s' $((48 - ${#name})) '')║\n"
        else
            RESULT="${RESULT}║  [✗]  ${name}$(printf '%*s' $((48 - ${#name})) '')║\n"
        fi
    }

    check_py() {
        local name="$1"
        local mod="$2"
        if python3 -c "import $mod" 2>/dev/null; then
            RESULT="${RESULT}║  [✓]  ${name}$(printf '%*s' $((48 - ${#name})) '')║\n"
        else
            RESULT="${RESULT}║  [✗]  ${name}$(printf '%*s' $((48 - ${#name})) '')║\n"
        fi
    }

    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}║  System binaries:                                            ║\n"
    check_bin "Python 3" "python3"
    check_bin "QEMU/KVM" "qemu-system-x86_64"
    check_bin "libvirt (virsh)" "virsh"
    check_bin "nftables" "nft"
    check_bin "ZFS" "zpool"
    check_bin "BTRFS" "btrfs"
    check_bin "iSCSI" "iscsiadm"
    check_bin "SMART" "smartctl"
    check_bin "PCI utils" "lspci"
    check_bin "noVNC" "websockify"

    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}║  Python packages:                                            ║\n"
    check_py "FastAPI" "fastapi"
    check_py "SQLAlchemy" "sqlalchemy"
    check_py "psutil" "psutil"
    check_py "bcrypt" "bcrypt"
    check_py "pyotp (2FA)" "pyotp"
    check_py "ldap3" "ldap3"

    RESULT="${RESULT}║                                                               ║\n"

    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    [ -z "$IP" ] && IP="localhost"

    if systemctl is-active --quiet nexve 2>/dev/null; then
        RESULT="${RESULT}║  [✓]  NexVE service is running                               ║\n"
    else
        RESULT="${RESULT}║  [!]  NexVE service may still be starting                     ║\n"
    fi

    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}╠═══════════════════════════════════════════════════════════╣\n"
    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}║  🌐 Dashboard:  http://${IP}:8000                              ║\n"
    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}║  First time? Open the URL above to create your admin         ║\n"
    RESULT="${RESULT}║  account through the setup wizard.                           ║\n"
    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}║  📋 Quick commands:                                          ║\n"
    RESULT="${RESULT}║     systemctl status nexve    — Check service status          ║\n"
    RESULT="${RESULT}║     journalctl -u nexve -f    — View live logs               ║\n"
    RESULT="${RESULT}║     systemctl restart nexve   — Restart service               ║\n"
    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}║  📁 Installed to: ${INSTALL_DIR}$(printf '%*s' $((42 - ${#INSTALL_DIR})) '')║\n"
    RESULT="${RESULT}║  📄 Install log: ${LOG}$(printf '%*s' $((42 - ${#LOG})) '')║\n"
    RESULT="${RESULT}║                                                               ║\n"
    RESULT="${RESULT}╚═══════════════════════════════════════════════════════════╝\n"

    dialog --title "NexVE Installer" \
        --backtitle "Installation complete" \
        --msgbox "$RESULT" \
        24 74
}

# ═══════════════════════════════════════════════════════════════════════
# MAIN FLOW
# ═══════════════════════════════════════════════════════════════════════
main() {
    # Root check
    if [ "$EUID" -ne 0 ]; then
        dialog --title "NexVE Installer" --msgbox "Error: Must be run as root.\n\nUsage: sudo bash install.sh" 7 $WIDTH
        exit 1
    fi

    # OS check
    if ! grep -qiE "debian|ubuntu|linuxmint" /etc/os-release 2>/dev/null; then
        dialog --title "NexVE Installer" \
            --backtitle "Warning" \
            --yesno "Non-Debian/Ubuntu system detected.\nSome features may not work correctly.\n\nContinue anyway?" \
            8 $WIDTH
        [ $? -ne 0 ] && exit 0
    fi

    # Disk space check
    AVAIL=$(df / --output=avail 2>/dev/null | tail -1 | tr -d ' ')
    if [ -n "$AVAIL" ] && [ "$AVAIL" -lt 2097152 ]; then
        dialog --title "NexVE Installer" \
            --backtitle "Warning" \
            --yesno "Less than 2GB free disk space.\nInstallation may fail.\n\nContinue anyway?" \
            8 $WIDTH
        [ $? -ne 0 ] && exit 0
    fi

    # Wizard flow
    show_main_menu
    show_component_menu
    show_location_menu
    show_confirm
    run_installation
    show_results

    clear
    echo ""
    echo -e "  ✅ NexVE installation complete!"
    echo -e "  🌐 Open http://$(hostname -I 2>/dev/null | awk '{print $1}'):8000 in your browser"
    echo ""
}

main "$@"
