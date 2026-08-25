#!/bin/bash
set -e

echo "╔══════════════════════════════════════╗"
echo "║        NexVE Hypervisor Installer     ║"
echo "╚══════════════════════════════════════╝"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./install.sh"
    exit 1
fi

NEXVE_USER="${SUDO_USER:-precision}"
NEXVE_DIR="/opt/nexve"

echo "[1/6] Installing system packages..."
apt update
apt install -y \
    python3 python3-pip python3-venv python3-dev \
    qemu-kvm libvirt-daemon-system libvirt-clients \
    bridge-utils lxc lxc-utils debootstrap \
    zfsutils-linux \
    lvm2 \
    nfs-common cifs-utils \
    nftables \
    smartmontools \
    novnc websockify \
    genisoimage \
    wget curl git \
    ovmf

echo "[2/6] Setting up project..."
mkdir -p "$NEXVE_DIR"
cp -r "$(dirname "$0")/backend" "$NEXVE_DIR/"
cp -r "$(dirname "$0")/frontend" "$NEXVE_DIR/"
mkdir -p "$NEXVE_DIR/data"
mkdir -p /var/lib/nexve/iso
mkdir -p /var/lib/nexve/cloud-init
mkdir -p /var/lib/nexve/backups

echo "[3/6] Creating Python virtual environment..."
python3 -m venv "$NEXVE_DIR/venv"
"$NEXVE_DIR/venv/bin/pip" install --upgrade pip
"$NEXVE_DIR/venv/bin/pip" install -r "$NEXVE_DIR/backend/requirements.txt"

echo "[4/6] Configuring libvirt..."
systemctl enable --now libvirtd
usermod -aG libvirt "$NEXVE_USER"
usermod -aG kvm "$NEXVE_USER"

echo "[5/6] Installing systemd service..."
cat > /etc/systemd/system/nexve.service << EOF
[Unit]
Description=NexVE Hypervisor Dashboard
After=network.target libvirtd.service
Requires=libvirtd.service

[Service]
Type=simple
WorkingDirectory=$NEXVE_DIR/backend
ExecStart=$NEXVE_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=NEXVE_SECRET=$(openssl rand -hex 32)
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now nexve

echo "[6/6] Setting permissions..."
chown -R "$NEXVE_USER:$NEXVE_USER" "$NEXVE_DIR"
chmod 600 /etc/systemd/system/nexve.service

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   ✅ NexVE installed successfully!   ║"
echo "╠══════════════════════════════════════╣"
echo "║  Access: http://$(hostname -I | awk '{print $1}'):8000 ║"
echo "║  Status: systemctl status nexve      ║"
echo "║  Logs:   journalctl -u nexve -f      ║"
echo "╚══════════════════════════════════════╝"
