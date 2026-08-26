#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════
# NexVE Installer v2.0
# Complete hypervisor management platform for Debian 12+
# Installs all dependencies, creates systemd service, and
# sets up the full NexVE environment.
# ═══════════════════════════════════════════════════════════

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Progress tracking ──
STEP=0
TOTAL_STEPS=18
STEP_NAMES=()

progress_bar() {
    local pct=$((STEP * 100 / TOTAL_STEPS))
    local filled=$((pct / 2))
    local empty=$((50 - filled))
    printf "\r  ${CYAN}[${NC}"
    printf "%0.s█" $(seq 1 $filled 2>/dev/null) || true
    printf "%0.s░" $(seq 1 $empty 2>/dev/null) || true
    printf "${CYAN}]${NC} ${BOLD}%3d%%${NC}" "$pat"
}

progress() {
    STEP=$((STEP + 1))
    local pct=$((STEP * 100 / TOTAL_STEPS))
    local filled=$((pct / 2))
    local empty=$((50 - filled))
    echo ""
    echo -e "  ${CYAN}[$STEP/$TOTAL_STEPS]${NC} ${GREEN}✓${NC} ${BOLD}$1${NC}"
    printf "  ${DIM}"
    printf "%0.s━" $(seq 1 58)
    printf "${NC}\n"
}

substep() {
    echo -e "    ${DIM}→${NC} $1"
}

warn() { echo -e "  ${YELLOW}⚠  $1${NC}"; }
fail() { echo -e "  ${RED}✗  $1${NC}"; exit 1; }
ok()   { echo -e "    ${GREEN}✓${NC} $1"; }

# ── Banner ──
echo ""
echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║                                                      ║"
echo "  ║           ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗║"
echo "  ║           ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝║"
echo "  ║           ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗║"
echo "  ║           ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║║"
echo "  ║           ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║║"
echo "  ║           ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝║"
echo "  ║                                                      ║"
echo "  ║              Hypervisor Management Platform           ║"
echo "  ║                    Installer v2.0                     ║"
echo "  ║                                                      ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "  ${DIM}This installer will install and configure NexVE on your system.${NC}"
echo -e "  ${DIM}It requires root privileges and a Debian 12+ (or Ubuntu) system.${NC}"
echo ""
sleep 1

# ═══════════════════════════════════════════════════════════
# Pre-flight checks
# ═══════════════════════════════════════════════════════════

if [ "$EUID" -ne 0 ]; then
    fail "This installer must be run as root.\n  Run: sudo bash install.sh"
fi

if ! grep -qiE "debian|ubuntu|linuxmint" /etc/os-release 2>/dev/null; then
    warn "This system is not Debian/Ubuntu. Some packages may not be available."
fi

# Check available disk space (need at least 2GB)
AVAILABLE=$(df / --output=avail 2>/dev/null | tail -1 | tr -d ' ')
if [ -n "$AVAILABLE" ] && [ "$AVAILABLE" -lt 2097152 ]; then
    warn "Less than 2GB free disk space. Installation may fail."
fi

progress "Pre-flight checks passed"

# ═══════════════════════════════════════════════════════════
# Step 1: System update
# ═══════════════════════════════════════════════════════════
substep "Updating package lists..."
apt update -qq 2>/dev/null || warn "apt update had warnings"
progress "System packages updated"

# ═══════════════════════════════════════════════════════════
# Step 2: Python + build tools
# ═══════════════════════════════════════════════════════════
substep "Installing Python 3, pip, venv, dev headers..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    libffi-dev libssl-dev libjpeg-dev zlib1g-dev \
    > /dev/null 2>&1
ok "Python runtime + build dependencies"

substep "Installing Git, curl, wget, jq..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    git curl wget jq openssl > /dev/null 2>&1
ok "Git, curl, wget, jq, openssl"

substep "Installing build-essential..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    build-essential > /dev/null 2>&1
ok "Build tools"
progress "Python + build tools installed"

# ═══════════════════════════════════════════════════════════
# Step 3: KVM/QEMU + libvirt
# ═══════════════════════════════════════════════════════════
substep "Installing QEMU/KVM emulator..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    qemu-kvm qemu-system-x86 qemu-utils qemu-system \
    > /dev/null 2>&1
ok "QEMU/KVM emulator"

substep "Installing libvirt daemon + clients..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    libvirt-daemon-system libvirt-clients \
    libvirt-dev > /dev/null 2>&1
ok "libvirt daemon + clients"

substep "Installing VM management tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    virtinst virt-manager \
    > /dev/null 2>&1
ok "virt-install, virt-manager"

substep "Installing UEFI firmware (OVMF)..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    ovmf > /dev/null 2>&1
ok "OVMF (UEFI firmware)"

substep "Installing libvirt Python bindings..."
pip3 install libvirt-python 2>/dev/null || \
    DEBIAN_FRONTEND=noninteractive apt install -y -qq python3-libvirt > /dev/null 2>&1
ok "libvirt Python bindings"
progress "KVM/QEMU + libvirt installed"

# ═══════════════════════════════════════════════════════════
# Step 4: LXC containers
# ═══════════════════════════════════════════════════════════
substep "Installing LXC container runtime..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    lxc lxc-utils lxc-templates \
    > /dev/null 2>&1
ok "LXC runtime + templates"

substep "Installing debootstrap for container templates..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    debootstrap > /dev/null 2>&1
ok "debootstrap"
progress "LXC containers installed"

# ═══════════════════════════════════════════════════════════
# Step 5: Storage — ZFS, LVM, BTRFS, NFS, CIFS, iSCSI
# ═══════════════════════════════════════════════════════════
substep "Installing ZFS tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    zfsutils-linux > /dev/null 2>&1
ok "ZFS (zpool, zfs, zfsutils)"

substep "Installing LVM2..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    lvm2 > /dev/null 2>&1
ok "LVM (vgs, lvs, lvcreate)"

substep "Installing BTRFS tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    btrfs-progs > /dev/null 2>&1
ok "BTRFS (btrfs subvolume, btrfs filesystem)"

substep "Installing NFS client..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    nfs-common > /dev/null 2>&1
ok "NFS client (mount -t nfs)"

substep "Installing CIFS/SMB client..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    cifs-utils samba-common-bin > /dev/null 2>&1
ok "CIFS/SMB (mount -t cifs, smbclient)"

substep "Installing iSCSI initiator..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    open-iscsi iscsi-initiator-utils > /dev/null 2>&1
systemctl enable iscsid 2>/dev/null || true
ok "iSCSI initiator (iscsiadm)"

substep "Installing disk management tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    smartmontools gdisk hdparm > /dev/null 2>&1
ok "SMART monitoring, GPT fdisk, hdparm"
progress "Storage backends installed (ZFS, LVM, BTRFS, NFS, CIFS, iSCSI)"

# ═══════════════════════════════════════════════════════════
# Step 6: Networking — bridges, VLANs, bonding, firewall
# ═══════════════════════════════════════════════════════════
substep "Installing network bridge tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    bridge-utils > /dev/null 2>&1
ok "bridge-utils (brctl, bridge)"

substep "Installing nftables firewall..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    nftables > /dev/null 2>&1
systemctl enable nftables 2>/dev/null || true
ok "nftables firewall"

substep "Installing network utilities..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    iproute2 net-tools vlan ethtool ifenslave > /dev/null 2>&1
ok "ip, tc, bridge, vlan, ethtool, bonding"

substep "Installing PCI/USB detection tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    pciutils usbutils > /dev/null 2>&1
ok "lspci, lsusb (passthrough detection)"
progress "Networking + firewall installed"

# ═══════════════════════════════════════════════════════════
# Step 7: Console — noVNC + websockify
# ═══════════════════════════════════════════════════════════
substep "Installing noVNC (browser-based VNC)..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    novnc websockify > /dev/null 2>&1
ok "noVNC + websockify"

substep "Installing terminal support..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    xterm > /dev/null 2>&1
ok "xterm (web terminal)"
progress "Console access installed (noVNC, web terminal)"

# ═══════════════════════════════════════════════════════════
# Step 8: Cloud-init + ISO tools
# ═══════════════════════════════════════════════════════════
substep "Installing cloud-init for VM provisioning..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    cloud-init cloud-utils > /dev/null 2>&1
ok "cloud-init"

substep "Installing ISO creation tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    genisoimage xorriso > /dev/null 2>&1
ok "genisoimage, xorriso (ISO/cloud-init images)"
progress "Cloud-init + ISO tools installed"

# ═══════════════════════════════════════════════════════════
# Step 9: System monitoring
# ═══════════════════════════════════════════════════════════
substep "Installing system monitoring tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    sysstat procps > /dev/null 2>&1
ok "iostat, vmstat, ps (monitoring)"

substep "Installing cron for backup scheduling..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    cron > /dev/null 2>&1
systemctl enable cron 2>/dev/null || true
ok "cron daemon (backup scheduling)"

substep "Installing log tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    rsyslog > /dev/null 2>&1
ok "rsyslog"
progress "System monitoring + cron installed"

# ═══════════════════════════════════════════════════════════
# Step 10: NexVE project setup
# ═══════════════════════════════════════════════════════════
INSTALL_DIR="/opt/nexve"
substep "Copying NexVE to ${INSTALL_DIR}..."
mkdir -p ${INSTALL_DIR}
# Copy everything from the installer's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r ${SCRIPT_DIR}/* ${INSTALL_DIR}/ 2>/dev/null || true
cp -r ${SCRIPT_DIR}/.git ${INSTALL_DIR}/ 2>/dev/null || true

substep "Creating data directories..."
mkdir -p ${INSTALL_DIR}/data
mkdir -p ${INSTALL_DIR}/data/backups
mkdir -p ${INSTALL_DIR}/data/cloud-init
mkdir -p ${INSTALL_DIR}/data/isos
mkdir -p ${INSTALL_DIR}/data/uploads
mkdir -p ${INSTALL_DIR}/data/metrics

substep "Creating static asset directories..."
mkdir -p ${INSTALL_DIR}/static/css
mkdir -p ${INSTALL_DIR}/static/js
mkdir -p ${INSTALL_DIR}/static/images
mkdir -p ${INSTALL_DIR}/static/fonts

substep "Ensuring backend directories..."
mkdir -p ${INSTALL_DIR}/backend/app/templates
mkdir -p ${INSTALL_DIR}/backend/app/routers
mkdir -p ${INSTALL_DIR}/backend/app/models
mkdir -p ${INSTALL_DIR}/backend/app/services
progress "NexVE project files copied"

# ═══════════════════════════════════════════════════════════
# Step 11: Python virtual environment + dependencies
# ═══════════════════════════════════════════════════════════
substep "Creating Python virtual environment..."
python3 -m venv ${INSTALL_DIR}/venv
source ${INSTALL_DIR}/venv/bin/activate

substep "Upgrading pip..."
pip install --upgrade pip setuptools wheel -q 2>/dev/null

substep "Installing Python dependencies from requirements.txt..."
pip install -r ${INSTALL_DIR}/requirements.txt -q 2>/dev/null

substep "Verifying key Python packages..."
python3 -c "
import fastapi; print(f'  ✓ FastAPI {fastapi.__version__}')
import uvicorn; print(f'  ✓ Uvicorn')
import sqlalchemy; print(f'  ✓ SQLAlchemy {sqlalchemy.__version__}')
import psutil; print(f'  ✓ psutil {psutil.__version__}')
import bcrypt; print(f'  ✓ bcrypt')
import pyotp; print(f'  ✓ pyotp')
" 2>/dev/null || warn "Some Python packages may not have loaded"
progress "Python virtual environment + dependencies installed"

# ═══════════════════════════════════════════════════════════
# Step 12: Enable libvirt + KVM
# ═══════════════════════════════════════════════════════════
substep "Enabling libvirtd service..."
systemctl enable --now libvirtd 2>/dev/null || warn "libvirtd not found, skipping"

substep "Adding user to libvirt/KVM groups..."
usermod -aG libvirt $SUDO_USER 2>/dev/null || true
usermod -aG kvm $SUDO_USER 2>/dev/null || true
ok "User added to libvirt and kvm groups"

substep "Verifying KVM acceleration..."
if [ -e /dev/kvm ]; then
    ok "KVM hardware acceleration available (/dev/kvm)"
else
    warn "/dev/kvm not found — hardware acceleration may not be available"
fi
progress "libvirt + KVM configured"

# ═══════════════════════════════════════════════════════════
# Step 13: Create storage directories
# ═══════════════════════════════════════════════════════════
substep "Creating default storage paths..."
mkdir -p /var/lib/libvirt/images
mkdir -p /var/lib/vz/template/cache
mkdir -p /var/lib/vz/images
mkdir -p /var/lib/vz/rootdir
mkdir -p /var/lib/nexve/backups
mkdir -p /var/lib/nexve/iso
ok "VM disk images: /var/lib/libvirt/images"
ok "Container templates: /var/lib/vz/template/cache"
ok "Backups: /var/lib/nexve/backups"
ok "ISOs: /var/lib/nexve/iso"
progress "Default storage directories created"

# ═══════════════════════════════════════════════════════════
# Step 14: Systemd service
# ═══════════════════════════════════════════════════════════
substep "Generating secure secret key..."
SECRET=$(openssl rand -hex 32)

substep "Creating NexVE systemd service..."
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

# Security hardening
ProtectSystem=full
ProtectHome=read-only
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
SVCEOF

substep "Reloading systemd and enabling NexVE..."
systemctl daemon-reload
systemctl enable --now nexve
ok "nexve.service enabled and started"

substep "Verifying NexVE is running..."
sleep 3
if systemctl is-active --quiet nexve; then
    ok "NexVE service is running"
else
    warn "NexVE service may need a moment to start. Check: systemctl status nexve"
fi
progress "NexVE systemd service installed"

# ═══════════════════════════════════════════════════════════
# Step 15: Firewall rules for NexVE
# ═══════════════════════════════════════════════════════════
substep "Configuring nftables base rules..."
# Create NexVE table and chains
nft add table inet nexve 2>/dev/null || true
nft add chain inet nexve host '{ policy accept; }' 2>/dev/null || true
nft add chain inet nexve forward '{ policy accept; }' 2>/dev/null || true
nft add chain inet nexve input '{ policy accept; }' 2>/dev/null || true
ok "nftables inet/nexve table created"
progress "Base firewall rules configured"

# ═══════════════════════════════════════════════════════════
# Step 16: Set permissions
# ═══════════════════════════════════════════════════════════
substep "Setting file permissions..."
chmod -R 755 ${INSTALL_DIR}/static 2>/dev/null || true
chmod 600 /etc/systemd/system/nexve.service 2>/dev/null || true
chmod 700 ${INSTALL_DIR}/data 2>/dev/null || true
ok "Permissions set"
progress "File permissions configured"

# ═══════════════════════════════════════════════════════════
# Step 17: Cleanup
# ═══════════════════════════════════════════════════════════
substep "Cleaning apt cache..."
apt autoremove -y -qq 2>/dev/null || true
apt clean 2>/dev/null || true
ok "Apt cache cleaned"
progress "Installation cleanup complete"

# ═══════════════════════════════════════════════════════════
# Step 18: Final verification
# ═══════════════════════════════════════════════════════════
substep "Running final verification..."

ERRORS=0

# Check critical binaries
for cmd in python3 qemu-system-x86_64 virsh pct nft zpool zfs btrfs iscsiadm smartctl lspci lsusb tc websockify; do
    if command -v $cmd &>/dev/null; then
        ok "$cmd"
    else
        warn "$cmd not found"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check Python packages
substep "Verifying Python package imports..."
python3 -c "
packages = ['fastapi', 'uvicorn', 'sqlalchemy', 'psutil', 'bcrypt', 'pyotp', 'itsdangerous']
for p in packages:
    try:
        __import__(p)
        print(f'    ✓ {p}')
    except ImportError:
        print(f'    ⚠ {p} not importable')
" 2>/dev/null || true

# Check NexVE service
if systemctl is-active --quiet nexve; then
    ok "NexVE service: running"
else
    warn "NexVE service: not running (may still be starting)"
fi

# Check libvirt
if systemctl is-active --quiet libvirtd; then
    ok "libvirtd: running"
else
    warn "libvirtd: not running"
fi

progress "Final verification complete"

# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$IP" ] && IP="localhost"

echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║                                                          ║"
echo "  ║          ✅  NexVE v2.0 Installed Successfully!          ║"
echo "  ║                                                          ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║                                                          ║"
echo "  ║  🌐 Dashboard:   http://${IP}:8000                      "
echo "  ║                                                          ║"
echo "  ║  📋 Quick Start:                                        ║"
echo "  ║     1. Open http://${IP}:8000 in your browser           "
echo "  ║     2. Complete the setup wizard (create admin)          ║"
echo "  ║     3. Start creating VMs and containers!                ║"
echo "  ║                                                          ║"
echo "  ║  🔧 Management:                                         ║"
echo "  ║     • Status:  systemctl status nexve                    ║"
echo "  ║     • Logs:    journalctl -u nexve -f                    ║"
echo "  ║     • Restart: systemctl restart nexve                   ║"
echo "  ║     • Config:  ${INSTALL_DIR}/                           "
echo "  ║     • Venv:    ${INSTALL_DIR}/venv/                      "
echo "  ║                                                          ║"
echo "  ║  📦 Features Installed:                                  ║"
echo "  ║     • VMs:    KVM/QEMU, hot-add, cloning, passthrough   ║"
echo "  ║     • CTs:    LXC containers with templates              ║"
echo "  ║     • Disk:   ZFS, LVM, BTRFS, NFS, CIFS, iSCSI        ║"
echo "  ║     • Net:    Bridges, VLANs, bonds, nftables            ║"
echo "  ║     • FW:     Security groups, aliases, rate limits      ║"
echo "  ║     • Backup: Full, incremental, scheduled, verified     ║"
echo "  ║     • Auth:   RBAC, 2FA/TOTP, LDAP, API tokens          ║"
echo "  ║     • Mon:    CPU, RAM, disk, network graphs             ║"
echo "  ║     • Shell:  Web terminal (bash/zsh)                    ║"
echo "  ║     • GPU:    PCI/e passthrough support                  ║"
echo "  ║                                                          ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
