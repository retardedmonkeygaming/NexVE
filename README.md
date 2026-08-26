# NexVE — Open Source Hypervisor Management

<p align="center">
  <strong>Your private cloud. Your rules.</strong><br>
  A modern, open-source alternative to Proxmox VE for managing virtual machines, containers, storage, and networking — with a beautiful web UI.
</p>

---

## Why NexVE?

Proxmox VE is powerful but its web interface feels dated, its setup process is overwhelming for newcomers, and many features require separate tools (Prometheus for monitoring, PBS for backups). NexVE combines the full power of KVM/QEMU and LXC into a single, beautifully designed platform that anyone can set up in minutes.

| Feature | Proxmox VE | NexVE |
|---------|-----------|-------|
| Web UI | Dated, complex modals | Modern, wizard-based |
| Monitoring | Basic graphs | Built-in live charts |
| Backup | Requires PBS (separate) | Integrated scheduling |
| Installation | ISO only | ISO + interactive installer |
| Mobile | Separate apps | Responsive web UI |
| Setup | CLI-heavy | Multi-step web wizard |

## Features

### Virtual Machines (KVM/QEMU)
- Create, start, stop, restart, delete VMs
- CPU type selection (host, qemu64, kvm64, etc.)
- Machine type (q35, i440fx), BIOS (UEFI/SeaBIOS)
- Hot-add CPU/RAM, memory ballooning
- GPU/USB passthrough with IOMMU
- Snapshots (create/restore/delete)
- Full and linked cloning
- Cloud-init provisioning
- noVNC browser-based console
- Disk resize and storage migration
- Convert VM to template

### Containers (LXC)
- Create, start, stop, restart, delete containers
- Template catalog (Debian, Ubuntu, Alpine, Fedora, CentOS)
- Unprivileged container toggle
- Container nesting support
- Mount point configuration
- Resource limits (CPU weight, I/O priority, net rate)
- Container exec and backup/restore

### Storage
- **ZFS**: Pool create/destroy/scrub, datasets, snapshots, replication
- **LVM/LVM-thin**: VG/LV management, thin provisioning
- **BTRFS**: Subvolumes, snapshots, RAID profiles
- **Directory**: Local path binding
- **NFS/CIFS/SMB**: Remote mount management
- **iSCSI**: Target discovery, login/logout
- Disk auto-detection with SMART health monitoring
- Storage quotas and migration

### Networking
- Linux bridges with port management
- VLAN configuration
- NIC bonding (LACP, active-backup, balance-rr)
- Per-host firewall (nftables)
- Per-VM firewall (per-interface rules)
- Security groups with reusable rule sets
- Firewall aliases and rate limiting

### Backup & Recovery
- Manual backup (VM/LXC)
- Scheduled backups with cron
- Configurable retention policies
- Backup verification
- Restore from any backup point
- Backup to NFS/CIFS remote storage

### Monitoring & Alerting
- Real-time CPU/RAM/Disk/Network charts (Chart.js)
- 24-hour historical metrics
- Top processes by CPU/memory
- Storage IOPS and throughput
- Email/webhook notifications
- System health dashboard

### Authentication & Security
- Login with bcrypt password hashing
- Brute-force protection (5 attempts, 15min lockout)
- CSRF protection
- 2FA/TOTP (QR code setup)
- API tokens for programmatic access
- LDAP/Active Directory integration
- Multi-user RBAC (admin, auditor, user roles)
- Activity audit trail

### System Management
- Hostname, DNS, NTP, timezone configuration
- Service management (start/stop/restart)
- System updates checker and one-click upgrade
- Live syslog viewer
- Kernel/OS information display

### Shell
- Web-based terminal (xterm.js + WebSocket PTY)
- Full bash shell access
- Copy/paste, resize, scrollback

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/yourusername/NexVE.git
cd NexVE
sudo bash install.sh
```

The installer will:
1. Check system requirements
2. Install all dependencies
3. Set up the Python virtual environment
4. Create the systemd service
5. Configure system integration

### Manual Install

```bash
# Clone the repository
git clone https://github.com/yourusername/NexVE.git
cd NexVE

# Create virtual environment
python3 -m venv /opt/nexve/venv
source /opt/nexve/venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy files to /opt/nexve
cp -r backend /opt/nexve/
cp -r static /opt/nexve/

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### First Boot

1. Open `http://your-server:8000` in your browser
2. Complete the setup wizard (admin account, hostname, network)
3. Start creating VMs and containers!

## Architecture

```
NexVE/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI application
│       ├── auth.py              # Authentication & sessions
│       ├── security.py          # CSRF & secret management
│       ├── database.py          # SQLAlchemy setup
│       ├── models/              # Database models
│       │   ├── user.py          # User, Session, AuditLog, Task
│       │   ├── vm.py            # VM, Container, BackupSchedule
│       │   ├── storage.py       # Storage backends
│       │   ├── firewall.py      # Firewall rules
│       │   ├── activity.py      # Activity logging
│       │   └── feature_models.py # Tags, pools, LDAP, etc.
│       ├── routers/             # API endpoints
│       │   ├── vms.py           # VM management
│       │   ├── containers.py    # Container management
│       │   ├── storage.py       # Storage operations
│       │   ├── network.py       # Network configuration
│       │   ├── shell.py         # WebSocket terminal
│       │   ├── settings.py      # System settings
│       │   ├── monitor.py       # Monitoring metrics
│       │   └── ...              # Other routers
│       ├── services/            # Business logic
│       │   ├── vm_service.py    # KVM/QEMU operations
│       │   ├── container_service.py # LXC operations
│       │   ├── storage_service.py   # Storage operations
│       │   ├── network_service.py   # Network operations
│       │   ├── monitor_service.py   # Metrics collection
│       │   └── ...              # Other services
│       └── templates/           # Jinja2 HTML templates
├── static/
│   ├── css/nexve.css            # Design system
│   └── images/                  # Static assets
├── install.py                   # Interactive installer
├── install.sh                   # Installer launcher
└── requirements.txt             # Python dependencies
```

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite
- **Frontend**: Vanilla JS, Chart.js, xterm.js, custom CSS
- **Hypervisor**: KVM/QEMU (VMs), LXC (containers)
- **Storage**: ZFS, LVM, BTRFS, NFS, CIFS, iSCSI
- **Networking**: Linux bridges, VLANs, nftables
- **Auth**: bcrypt, TOTP, LDAP, sessions

## API Documentation

Once running, visit `http://your-server:8000/docs` for the auto-generated Swagger API documentation.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `NEXVE_SECRET` | Auto-generated | Secret key for CSRF tokens |
| `NEXVE_DB` | `/opt/nexve/data/nexve.db` | SQLite database path |
| `NEXVE_HOST` | `0.0.0.0` | Server bind address |
| `NEXVE_PORT` | `8000` | Server port |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/NexVE.git
cd NexVE

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run in development mode
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## License

This project is licensed under the AGPL-3.0 License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the shoulders of [Proxmox VE](https://www.proxmox.com/) — the industry-standard open-source hypervisor
- [FastAPI](https://fastapi.tiangolo.com/) for the async web framework
- [Chart.js](https://www.chartjs.org/) for beautiful charts
- [xterm.js](https://xtermjs.org/) for the web terminal
- The open-source community for making this possible

---

<p align="center">
  <strong>NexVE</strong> — Because managing your infrastructure should be a pleasure, not a chore.
</p>
