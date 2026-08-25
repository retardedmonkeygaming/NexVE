#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

step=0
total=13

progress() {
    step=$((step + 1))
    echo ""
    echo -e "${CYAN}[$step/$total]${NC} ${GREEN}✓${NC} $1"
}

warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║       NexVE Installer v1.1               ║"
echo "║  Hypervisor Dashboard for Debian 13      ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then fail "Run as root: sudo bash install.sh"; fi
progress "Running as root"

if ! grep -qi "debian" /etc/os-release 2>/dev/null; then
    warn "Not Debian. Proceeding anyway."
fi
progress "OS check passed"

echo "  → Updating package lists..."
apt update -qq 2>/dev/null || warn "apt update had warnings"
progress "System packages updated"

echo "  → Installing Python, Git, build tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    git curl wget build-essential > /dev/null 2>&1
progress "Python + build tools installed"

echo "  → Installing KVM/QEMU + libvirt..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    qemu-kvm qemu-system-x86 qemu-utils \
    libvirt-daemon-system libvirt-clients \
    virtinst virt-manager ovmf > /dev/null 2>&1
progress "KVM/QEMU + libvirt installed"

echo "  → Installing LXC + debootstrap..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    lxc lxc-utils debootstrap > /dev/null 2>&1
progress "LXC containers installed"

echo "  → Installing ZFS, LVM, NFS, CIFS tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    zfsutils-linux lvm2 nfs-common cifs-utils > /dev/null 2>&1
progress "Storage tools installed"

echo "  → Installing networking + firewall..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    bridge-utils nftables smartmontools net-tools iproute2 > /dev/null 2>&1
progress "Networking + firewall installed"

echo "  → Installing noVNC + websockify..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    novnc websockify > /dev/null 2>&1
progress "noVNC console installed"

echo "  → Installing cloud-init + ISO tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -qq \
    cloud-init genisoimage > /dev/null 2>&1
progress "Cloud-init + ISO tools installed"

# ─── NexVE Setup ───
INSTALL_DIR="/opt/nexve"
echo "  → Setting up NexVE in ${INSTALL_DIR}..."
mkdir -p ${INSTALL_DIR}
cp -r $(dirname "$0")/* ${INSTALL_DIR}/ 2>/dev/null || true
mkdir -p ${INSTALL_DIR}/data
mkdir -p ${INSTALL_DIR}/static
mkdir -p ${INSTALL_DIR}/backend/app/templates
mkdir -p ${INSTALL_DIR}/backend/app/routers
mkdir -p ${INSTALL_DIR}/backend/app/models
mkdir -p ${INSTALL_DIR}/backend/app/services
mkdir -p ${INSTALL_DIR}/data/backups
mkdir -p ${INSTALL_DIR}/data/cloud-init
mkdir -p ${INSTALL_DIR}/data/iso
progress "Project directories created"

echo "  → Creating Python virtual environment..."
python3 -m venv ${INSTALL_DIR}/venv
source ${INSTALL_DIR}/venv/bin/activate
pip install --upgrade pip -q
pip install -r ${INSTALL_DIR}/requirements.txt -q
progress "Python dependencies installed"

# ─── Enable services ───
echo "  → Enabling libvirtd..."
systemctl enable --now libvirtd 2>/dev/null || warn "libvirtd not found, skipping"
usermod -aG libvirt $SUDO_USER 2>/dev/null || true
usermod -aG kvm $SUDO_USER 2>/dev/null || true
progress "libvirtd enabled + user added to libvirt group"

# ─── Systemd service ───
echo "  → Installing NexVE systemd service..."
SECRET=$(openssl rand -hex 32)
cat > /etc/systemd/system/nexve.service << EOF
[Unit]
Description=NexVE Hypervisor Dashboard
After=libvirtd.service network.target
Requires=libvirtd.service

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}/backend
Environment=NEXVE_SECRET=${SECRET}
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now nexve
progress "NexVE service installed and started"

IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════╗"
echo "║       NexVE Installed Successfully!      ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Dashboard: http://${IP}:8000            ║"
echo "║  Status:    systemctl status nexve       ║"
echo "║  Logs:      journalctl -u nexve -f       ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
