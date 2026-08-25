#!/bin/bash
set -e

# ─── Colors ───
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

step=0
total=12

progress() {
    step=$((step + 1))
    echo ""
    echo -e "${CYAN}[$step/$total]${NC} ${GREEN}✓${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

fail() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

echo -e "${CYAN}"
echo "╔══════════════════════════════════════╗"
echo "║         NexVE Installer v1.0         ║"
echo "║   Hypervisor Dashboard for Debian    ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# ─── 1. Check root ───
if [ "$EUID" -ne 0 ]; then
    fail "Please run as root: sudo bash install.sh"
fi
progress "Running as root"

# ─── 2. Detect OS ───
if ! grep -qi "debian" /etc/os-release 2>/dev/null; then
    warn "Not running on Debian. Proceeding anyway, but results may vary."
fi
progress "OS check passed"

# ─── 3. System update ───
echo "  → Updating package lists..."
apt update -qq 2>/dev/null || warn "apt update had warnings, continuing..."
progress "System packages updated"

# ─── 4. Core system packages ───
echo "  → Installing Python, Git, build tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    git curl wget build-essential \
    > /dev/null 2>&1
progress "Python + build tools installed"

# ─── 5. Hypervisor packages ───
echo "  → Installing KVM/QEMU + libvirt..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    qemu-kvm qemu-system-x86 qemu-utils \
    libvirt-daemon-system libvirt-clients \
    virtinst virt-manager \
    ovmf \
    > /dev/null 2>&1
progress "KVM/QEMU + libvirt installed"

# ─── 6. Container packages ───
echo "  → Installing LXC + debootstrap..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    lxc lxc-utils debootstrap \
    > /dev/null 2>&1
progress "LXC containers installed"

# ─── 7. Storage packages ───
echo "  → Installing ZFS, LVM, NFS, CIFS tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    zfsutils-linux lvm2 \
    nfs-common cifs-utils \
    > /dev/null 2>&1
progress "Storage tools installed (ZFS, LVM, NFS, CIFS)"

# ─── 8. Networking + security packages ───
echo "  → Installing bridge-utils, nftables, SMART tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    bridge-utils nftables \
    smartmontools net-tools iproute2 \
    > /dev/null 2>&1
progress "Networking + security tools installed"

# ─── 9. Console packages ───
echo "  → Installing noVNC + websockify..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    novnc websockify \
    > /dev/null 2>&1
progress "noVNC browser console installed"

# ─── 10. Cloud-init / ISO tools ───
echo "  → Installing cloud-init + ISO tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    cloud-init genisoimage \
    > /dev/null 2>&1
progress "Cloud-init + ISO tools installed"

# ─── 11. Create directories + Python venv ───
INSTALL_DIR="/opt/nexve"
echo "  → Setting up NexVE in ${INSTALL_DIR}..."
mkdir -p ${INSTALL_DIR}

# Copy project files
if [ -d "$(pwd)" ] && [ -f "$(pwd)/requirements.txt" ]; then
    cp -r "$(pwd)/"* ${INSTALL_DIR}/
else
    fail "Please run install.sh from the NexVE project directory"
fi

cd ${INSTALL_DIR}
mkdir -p data data/backups data/isos data/cloud-init

# Create venv and install Python deps
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q 2>/dev/null
pip install -r requirements.txt -q 2>/dev/null
progress "Python environment ready (${INSTALL_DIR})"

# ─── 12. Systemd service + enable ───
echo "  → Installing systemd service..."

# Generate secret key
SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cat > /etc/systemd/system/nexve.service << EOF
[Unit]
Description=NexVE Hypervisor Dashboard
After=network.target libvirtd.service
Requires=libvirtd.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/backend
Environment=PATH=${INSTALL_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=NEXVE_SECRET=${SECRET}
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now libvirtd 2>/dev/null || warn "libvirtd enable had issues"
systemctl enable --now nexve 2>/dev/null

# Add user to libvirt group
REAL_USER="${SUDO_USER:-$USER}"
if [ "$REAL_USER" != "root" ]; then
    usermod -aG libvirt "$REAL_USER" 2>/dev/null || true
    usermod -aG kvm "$REAL_USER" 2>/dev/null || true
fi

progress "Systemd service installed and started"

# ─── Done ───
echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════╗"
echo "║         NexVE Installed Successfully     ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
IP=$(hostname -I | awk '{print $1}')
echo "║  Dashboard: http://${IP}:8000            ║"
echo "║  Service:   systemctl status nexve       ║"
echo "║  Logs:      journalctl -u nexve -f       ║"
echo "║  Config:    /opt/nexve/                  ║"
echo "║  Data:      /opt/nexve/data/             ║"
echo "║                                          ║"
echo "║  First visit → Setup wizard will appear  ║"
echo "║  Create your admin account and go!       ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
