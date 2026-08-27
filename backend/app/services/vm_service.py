import subprocess
import os
import json
import uuid
import re
from typing import List, Optional
from datetime import datetime
from ..models.vm import VM

# Lazy import: only load libvirt when first needed
try:
    import libvirt
    HAS_LIBVIRT = True
except ImportError:
    libvirt = None
    HAS_LIBVIRT = False


def _check_libvirt_prereqs() -> dict:
    """Check libvirt prerequisites and return diagnostics."""
    diag = {
        "libvirt_python_installed": HAS_LIBVIRT,
        "libvirtd_running": False,
        "virsh_available": False,
        "user_in_libvirt_group": False,
        "user_in_kvm_group": False,
        "kvm_available": False,
        "issues": [],
    }

    # Check virsh
    try:
        r = subprocess.run(["virsh", "--version"], capture_output=True, text=True, timeout=5)
        diag["virsh_available"] = r.returncode == 0
        diag["virsh_version"] = r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        pass

    # Check libvirtd
    try:
        r = subprocess.run(["systemctl", "is-active", "libvirtd"], capture_output=True, text=True, timeout=5)
        diag["libvirtd_running"] = r.stdout.strip() == "active"
    except Exception:
        pass

    # Check user groups
    try:
        r = subprocess.run(["groups"], capture_output=True, text=True, timeout=5)
        groups = r.stdout.strip()
        diag["user_in_libvirt_group"] = "libvirt" in groups
        diag["user_in_kvm_group"] = "kvm" in groups
    except Exception:
        pass

    # Check /dev/kvm
    diag["kvm_available"] = os.path.exists("/dev/kvm")

    # Build issues list
    if not HAS_LIBVIRT:
        diag["issues"].append("libvirt-python not installed. Run: pip install libvirt-python")
    if not diag["libvirtd_running"]:
        diag["issues"].append("libvirtd is not running. Run: systemctl start libvirtd && systemctl enable libvirtd")
    if not diag["virsh_available"]:
        diag["issues"].append("virsh not found. Run: apt install libvirt-clients")
    if not diag["kvm_available"]:
        diag["issues"].append("/dev/kvm not found. Ensure KVM is enabled in BIOS/UEFI and the kvm module is loaded.")
    if not diag["user_in_libvirt_group"]:
        diag["issues"].append("User not in libvirt group. Run: usermod -aG libvirt $USER")
    if not diag["user_in_kvm_group"]:
        diag["issues"].append("User not in kvm group. Run: usermod -aG kvm $USER")

    return diag


def _get_libvirt_conn():
    """Get a libvirt connection with multiple fallback URLs and detailed errors."""
    if not HAS_LIBVIRT:
        return None

    urls = [
        "qemu:///system",
        "qemu:///session",
    ]

    last_error = None
    for url in urls:
        try:
            conn = libvirt.open(url)
            if conn:
                return conn
        except libvirt.libvirtError as e:
            last_error = str(e)
            continue
        except Exception as e:
            last_error = str(e)
            continue

    return None


class VMService:
    def __init__(self):
        self.conn = _get_libvirt_conn()
        self._diag = None

    def get_diagnostics(self) -> dict:
        """Get detailed libvirt diagnostics for troubleshooting."""
        if self._diag is None:
            self._diag = _check_libvirt_prereqs()
        return self._diag

    def _ensure_conn(self):
        """Ensure we have a valid libvirt connection, reconnecting if needed."""
        if self.conn is None:
            self.conn = _get_libvirt_conn()
        else:
            try:
                self.conn.getVersion()
            except Exception:
                self.conn = _get_libvirt_conn()
        return self.conn

    def get_all_vms(self, db) -> List[dict]:
        db_vms = db.query(VM).all()
        result = []
        for vm in db_vms:
            live_status = self._get_vm_status(vm.name)
            result.append({
                "id": vm.id,
                "name": vm.name,
                "status": live_status,
                "vcpu": vm.vcpu,
                "cpu_type": vm.cpu_type or "host",
                "memory_mb": vm.memory_mb,
                "disk_gb": vm.disk_gb,
                "disk_interface": vm.disk_interface or "virtio",
                "os_type": vm.os_type or "linux",
                "machine_type": vm.machine_type or "q35",
                "bios_type": vm.bios_type or "seabios",
                "boot_order": vm.boot_order or "c",
                "ip_address": vm.ip_address,
                "mac_address": vm.mac_address,
                "notes": vm.notes or "",
                "serial_console": vm.serial_console,
                "agent_enabled": vm.agent_enabled,
                "balloon": vm.balloon,
                "hotplug_cpu": vm.hotplug_cpu,
                "hotplug_ram": vm.hotplug_ram,
                "is_template": vm.is_template,
                "linked_from": vm.linked_from,
                "created_at": vm.created_at.isoformat() if vm.created_at else None,
                "last_started": vm.last_started.isoformat() if vm.last_started else None,
            })
        return result

    def get_vm(self, db, vm_id: int) -> Optional[dict]:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return None
        live_status = self._get_vm_status(vm.name)
        return {
            "id": vm.id,
            "name": vm.name,
            "status": live_status,
            "vcpu": vm.vcpu,
            "cpu_type": vm.cpu_type or "host",
            "memory_mb": vm.memory_mb,
            "disk_gb": vm.disk_gb,
            "disk_interface": vm.disk_interface or "virtio",
            "os_type": vm.os_type or "linux",
            "machine_type": vm.machine_type or "q35",
            "bios_type": vm.bios_type or "seabios",
            "boot_order": vm.boot_order or "c",
            "ip_address": vm.ip_address,
            "mac_address": vm.mac_address,
            "notes": vm.notes or "",
            "serial_console": vm.serial_console,
            "agent_enabled": vm.agent_enabled,
            "balloon": vm.balloon,
            "hotplug_cpu": vm.hotplug_cpu,
            "hotplug_ram": vm.hotplug_ram,
            "is_template": vm.is_template,
            "linked_from": vm.linked_from,
            "created_at": vm.created_at.isoformat() if vm.created_at else None,
            "last_started": vm.last_started.isoformat() if vm.last_started else None,
        }

    def create_vm(self, db, config: dict) -> dict:
        name = config["name"]
        existing = db.query(VM).filter(VM.name == name).first()
        if existing:
            return {"success": False, "error": f"VM '{name}' already exists"}

        mac = self._generate_mac()
        vm = VM(
            name=name,
            vcpu=config.get("vcpu", 2),
            cpu_type=config.get("cpu_type", "host"),
            memory_mb=config.get("memory_mb", 2048),
            disk_gb=config.get("disk_gb", 50),
            disk_interface=config.get("disk_interface", "virtio"),
            os_type=config.get("os_type", "linux"),
            machine_type=config.get("machine_type", "q35"),
            bios_type=config.get("bios_type", "seabios"),
            boot_order=config.get("boot_order", "c"),
            mac_address=mac,
            notes=config.get("notes", ""),
            serial_console=config.get("serial_console", False),
            agent_enabled=config.get("agent_enabled", True),
            balloon=config.get("balloon", False),
            hotplug_cpu=config.get("hotplug_cpu", False),
            hotplug_ram=config.get("hotplug_ram", False),
            is_template=config.get("is_template", False),
            linked_from=config.get("linked_from", None),
        )
        db.add(vm)
        db.commit()
        db.refresh(vm)

        result = self._create_libvirt_vm(vm, config)
        return {
            "success": True,
            "vm": {"id": vm.id, "name": vm.name, "status": "stopped", "mac_address": mac},
            "libvirt": result,
        }

    def update_vm(self, db, vm_id: int, config: dict) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}

        for key in [
            "name", "vcpu", "cpu_type", "memory_mb", "disk_gb",
            "disk_interface", "os_type", "machine_type", "bios_type",
            "boot_order", "notes", "serial_console", "agent_enabled",
            "balloon", "hotplug_cpu", "hotplug_ram",
        ]:
            if key in config:
                setattr(vm, key, config[key])

        db.commit()
        db.refresh(vm)

        live_status = self._get_vm_status(vm.name)
        if live_status == "running":
            self._update_libvirt_config(vm)

        return {"success": True, "vm": self.get_vm(db, vm_id)}

    def delete_vm(self, db, vm_id: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}

        live_status = self._get_vm_status(vm.name)
        if live_status == "running":
            self._stop_libvirt_vm(vm.name)

        self._undefine_libvirt_vm(vm.name)

        disk_path = f"/var/lib/libvirt/images/{vm.name}.qcow2"
        if os.path.exists(disk_path):
            os.remove(disk_path)

        db.delete(vm)
        db.commit()
        return {"success": True}

    def start_vm(self, db, vm_id: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if vm.is_template:
            return {"success": False, "error": "Cannot start a template. Clone it first."}
        result = self._start_libvirt_vm(vm.name)
        if result["success"]:
            vm.last_started = datetime.utcnow()
            db.commit()
        return result

    def stop_vm(self, db, vm_id: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        return self._stop_libvirt_vm(vm.name)

    def restart_vm(self, db, vm_id: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        self._stop_libvirt_vm(vm.name)
        result = self._start_libvirt_vm(vm.name)
        if result["success"]:
            vm.last_started = datetime.utcnow()
            db.commit()
        return result

    def clone_vm(self, db, vm_id: int, new_name: str, linked: bool = False) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if db.query(VM).filter(VM.name == new_name).first():
            return {"success": False, "error": f"VM '{new_name}' already exists"}

        new_vm = VM(
            name=new_name, vcpu=vm.vcpu, cpu_type=vm.cpu_type,
            memory_mb=vm.memory_mb, disk_gb=vm.disk_gb, disk_interface=vm.disk_interface,
            os_type=vm.os_type, machine_type=vm.machine_type, bios_type=vm.bios_type,
            boot_order=vm.boot_order, notes=f"{'Linked' if linked else 'Full'} clone of {vm.name}",
            serial_console=vm.serial_console, agent_enabled=vm.agent_enabled,
            balloon=vm.balloon, mac_address=self._generate_mac(),
            linked_from=vm.id if linked else None,
        )
        db.add(new_vm)
        db.commit()
        db.refresh(new_vm)

        src_disk = f"/var/lib/libvirt/images/{vm.name}.qcow2"
        dst_disk = f"/var/lib/libvirt/images/{new_name}.qcow2"
        if os.path.exists(src_disk):
            if linked:
                cmd = f"qemu-img create -f qcow2 -b {src_disk} -F qcow2 {dst_disk}"
            else:
                cmd = f"cp {src_disk} {dst_disk}"
            subprocess.run(cmd, shell=True, capture_output=True)

        self._create_libvirt_vm(new_vm, {"vcpu": new_vm.vcpu, "memory_mb": new_vm.memory_mb})
        return {"success": True, "vm": {"id": new_vm.id, "name": new_vm.name}}

    def resize_disk(self, db, vm_id: int, new_size_gb: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}

        disk_path = f"/var/lib/libvirt/images/{vm.name}.qcow2"
        if not os.path.exists(disk_path):
            return {"success": False, "error": "Disk file not found"}

        result = subprocess.run(
            f"qemu-img resize {disk_path} {new_size_gb}G",
            shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip()}

        vm.disk_gb = new_size_gb
        db.commit()
        return {"success": True}

    def get_vm_config(self, vm_name: str) -> dict:
        conn = self._ensure_conn()
        if not conn:
            diag = self.get_diagnostics()
            error_msg = "libvirt is not available."
            if diag["issues"]:
                error_msg += " Issues found:\n" + "\n".join(f"  • {i}" for i in diag["issues"])
            return {"error": error_msg, "diagnostics": diag}
        try:
            dom = conn.lookupByName(vm_name)
            xml = dom.XMLDesc(0)
            return {"xml": xml}
        except libvirt.libvirtError as e:
            return {"error": str(e)}

    def create_snapshot(self, db, vm_id: int, name: str) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}

        live_status = self._get_vm_status(vm.name)
        if live_status != "running":
            return {"success": False, "error": "VM must be running to snapshot"}

        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}

        try:
            dom = conn.lookupByName(vm.name)
            flags = libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC
            xml = f"<domainsnapshot><description>Snapshot: {name}</description></domainsnapshot>"
            dom.snapshotCreateXML(xml, flags)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def list_snapshots(self, vm_id: int, db) -> list:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return []
        conn = self._ensure_conn()
        if not conn:
            return []
        try:
            dom = conn.lookupByName(vm.name)
            snapshots = dom.snapshotListFlags(0)
            return [{"name": snap.getName(), "creation_time": datetime.fromtimestamp(snap.getInfo()[3]).isoformat()} for snap in snapshots]
        except libvirt.libvirtError:
            return []

    def restore_snapshot(self, vm_id: int, snap_name: str, db) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            snap = dom.snapshotLookupByName(snap_name, 0)
            dom.revertToSnapshot(snap, libvirt.VIR_DOMAIN_SNAPSHOT_REVERT_RUNNING)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def delete_snapshot(self, vm_id: int, snap_name: str, db) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            snap = dom.snapshotLookupByName(snap_name, 0)
            snap.delete(0)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def hotplug_cpu(self, db, vm_id: int, vcpus: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if not vm.hotplug_cpu:
            return {"success": False, "error": "CPU hotplug not enabled. Enable it in VM settings first."}
        if self._get_vm_status(vm.name) != "running":
            return {"success": False, "error": "VM must be running for hot-add"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            dom.setVcpus(vcpus)
            vm.vcpu = vcpus
            db.commit()
            return {"success": True, "vcpu": vcpus}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def hotplug_ram(self, db, vm_id: int, memory_mb: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if not vm.hotplug_ram:
            return {"success": False, "error": "Memory hotplug not enabled. Enable it in VM settings first."}
        if self._get_vm_status(vm.name) != "running":
            return {"success": False, "error": "VM must be running for hot-add"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            dom.setMemory(memory_mb * 1024)
            vm.memory_mb = memory_mb
            db.commit()
            return {"success": True, "memory_mb": memory_mb}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def import_ovf(self, filepath: str) -> dict:
        try:
            import xml.etree.ElementTree as ET
            if filepath.endswith(".ova"):
                import tarfile
                ova_dir = filepath + "_extracted"
                os.makedirs(ova_dir, exist_ok=True)
                with tarfile.open(filepath, "r") as tar:
                    tar.extractall(ova_dir)
                ovf_path = None
                for root, dirs, files in os.walk(ova_dir):
                    for f in files:
                        if f.endswith(".ovf"):
                            ovf_path = os.path.join(root, f)
                if not ovf_path:
                    return {"success": False, "error": "No OVF file found in OVA"}
                filepath = ovf_path

            tree = ET.parse(filepath)
            root = tree.getroot()
            ns = {"ovf": "http://schemas.dmtf.org/ovf/envelope/1"}
            name = "imported-vm"
            vcpu = 2
            memory_mb = 2048

            name_el = root.find(".//ovf:Name", ns)
            if name_el is not None:
                name = name_el.text or name

            for section in root.findall(".//ovf:VirtualHardwareSection", ns):
                for item in section.findall(".//ovf:Item", ns):
                    res_type = item.get("{" + ns["ovf"] + "}resourceType", "")
                    if res_type == "3":
                        count = item.find("ovf:VirtualQuantity", ns)
                        if count is not None:
                            vcpu = int(count.text or 2)
                    elif res_type == "4":
                        size = item.find("ovf:VirtualQuantity", ns)
                        if size is not None:
                            memory_mb = int(int(size.text or 2048) // 1024)

            name = re.sub(r'[^a-zA-Z0-9_-]', '-', name)[:55]
            return {"success": True, "vm": {"name": name, "vcpu": vcpu, "memory_mb": memory_mb, "disk_gb": 50, "source": filepath}, "message": "OVF parsed. Review and create VM."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_pci_devices(self, device_class: str = "0300") -> List[dict]:
        result = subprocess.run("lspci -nn -D", shell=True, capture_output=True, text=True)
        devices = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    addr, cls = parts[0], parts[1]
                    if device_class and not cls.startswith(device_class):
                        continue
                    name = " ".join(parts[2:])
                    ids_match = re.search(r'\[([0-9a-f]{4}:[0-9a-f]{4})\]', line)
                    devices.append({"address": addr, "class": cls, "name": name, "vendor_product": ids_match.group(1) if ids_match else ""})
        return devices

    def list_usb_devices(self) -> List[dict]:
        result = subprocess.run("lsusb", shell=True, capture_output=True, text=True)
        devices = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    ids_match = re.search(r'ID\s+([0-9a-f]{4}:[0-9a-f]{4})', line)
                    devices.append({"bus": parts[1], "device": parts[3].rstrip(":"), "ids": ids_match.group(1) if ids_match else "", "name": " ".join(parts[6:]) if len(parts) > 6 else ""})
        return devices

    def attach_pci_device(self, db, vm_id: int, pci_addr: str) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if self._get_vm_status(vm.name) == "running":
            return {"success": False, "error": "VM must be stopped to attach PCI devices"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            xml = dom.XMLDesc(0)
            parts = pci_addr.split(":")
            bus, slot = parts[0] if len(parts) > 0 else "00", parts[1] if len(parts) > 1 else "00"
            hostdev_xml = f"<hostdev mode='subsystem' type='pci' managed='yes'><source><address domain='0x0000' bus='0x{bus}' slot='0x{slot}' function='0x0'/></source></hostdev>"
            xml = xml.replace("</devices>", hostdev_xml + "</devices>")
            conn.defineXML(xml)
            return {"success": True, "pci_addr": pci_addr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def attach_usb_device(self, db, vm_id: int, vendor_id: str, product_id: str) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            xml = dom.XMLDesc(0)
            hostdev_xml = f"<hostdev mode='subsystem' type='usb' managed='yes'><source><vendor id='0x{vendor_id}'/><product id='0x{product_id}'/></source></hostdev>"
            xml = xml.replace("</devices>", hostdev_xml + "</devices>")
            conn.defineXML(xml)
            return {"success": True, "vendor_id": vendor_id, "product_id": product_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def detach_pci_device(self, db, vm_id: int, device_addr: str) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            xml = dom.XMLDesc(0)
            xml = re.sub(r'<hostdev[^>]*>.*?</hostdev>', '', xml, flags=re.DOTALL)
            conn.defineXML(xml)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def convert_to_template(self, db, vm_id: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if self._get_vm_status(vm.name) == "running":
            return {"success": False, "error": "VM must be stopped before converting to template"}
        vm.is_template = True
        db.commit()
        return {"success": True}

        # -- Phase 1: Hot-plug Disk --

    def hotplug_disk(self, db, vm_id: int, size_gb: int, interface: str = "virtio", backend: str = "local") -> dict:
        """Add a disk to a running VM while it's live."""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if self._get_vm_status(vm.name) != "running":
            return {"success": False, "error": "VM must be running for hot-plug"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        existing = json.loads(vm.extra_disks or "[]")
        idx = len(existing) + 1
        dev_letter = chr(ord("b") + idx)
        disk_path = f"/var/lib/libvirt/images/{vm.name}-disk{idx}.qcow2"
        try:
            r = subprocess.run(f"qemu-img create -f qcow2 {disk_path} {size_gb}G", shell=True, capture_output=True, text=True)
            if r.returncode != 0:
                return {"success": False, "error": r.stderr.strip()}
            dom = conn.lookupByName(vm.name)
            device_xml = f"""<disk type='file' device='disk'><driver name='qemu' type='qcow2'/><source file='{disk_path}'/><target dev='vd{dev_letter}' bus='{interface}'/></disk>"""
            dom.attachDeviceFlags(device_xml, libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG)
            existing.append({"index": idx, "size_gb": size_gb, "interface": interface, "backend": backend, "path": disk_path})
            vm.extra_disks = json.dumps(existing)
            db.commit()
            return {"success": True, "disk": {"index": idx, "device": f"vd{dev_letter}", "size_gb": size_gb}}
        except libvirt.libvirtError as e:
            if os.path.exists(disk_path):
                os.remove(disk_path)
            return {"success": False, "error": str(e)}

    def detach_disk(self, db, vm_id: int, disk_index: int) -> dict:
        """Remove a hot-plugged disk from a VM."""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        existing = json.loads(vm.extra_disks or "[]")
        disk = next((d for d in existing if d["index"] == disk_index), None)
        if not disk:
            return {"success": False, "error": f"Disk index {disk_index} not found"}
        try:
            dom = conn.lookupByName(vm.name)
            dev_letter = chr(ord("b") + disk_index)
            device_xml = f"""<disk type='file' device='disk'><driver name='qemu' type='qcow2'/><source file='{disk["path"]}'/><target dev='vd{dev_letter}' bus='{disk["interface"]}'/></disk>"""
            flags = libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG if self._get_vm_status(vm.name) == "running" else libvirt.VIR_DOMAIN_AFFECT_CONFIG
            dom.detachDeviceFlags(device_xml, flags)
            existing = [d for d in existing if d["index"] != disk_index]
            vm.extra_disks = json.dumps(existing)
            db.commit()
            if os.path.exists(disk.get("path", "")):
                os.remove(disk["path"])
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    # -- Phase 1: Hot-plug NIC --

    def hotplug_nic(self, db, vm_id: int, bridge: str = "vmbr0", model: str = "virtio") -> dict:
        """Add a NIC to a running VM."""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if self._get_vm_status(vm.name) != "running":
            return {"success": False, "error": "VM must be running for hot-plug"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        existing = json.loads(vm.extra_nics or "[]")
        idx = len(existing) + 1
        mac = self._generate_mac()
        try:
            dom = conn.lookupByName(vm.name)
            nic_xml = f"""<interface type='bridge'><source bridge='{bridge}'/><mac address='{mac}'/><model type='{model}'/></interface>"""
            dom.attachDeviceFlags(nic_xml, libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG)
            existing.append({"index": idx, "bridge": bridge, "model": model, "mac": mac})
            vm.extra_nics = json.dumps(existing)
            db.commit()
            return {"success": True, "nic": {"index": idx, "bridge": bridge, "mac": mac}}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def detach_nic(self, db, vm_id: int, nic_index: int) -> dict:
        """Remove a NIC from a VM."""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        existing = json.loads(vm.extra_nics or "[]")
        nic = next((n for n in existing if n["index"] == nic_index), None)
        if not nic:
            return {"success": False, "error": f"NIC index {nic_index} not found"}
        try:
            dom = conn.lookupByName(vm.name)
            nic_xml = f"""<interface type='bridge'><source bridge='{nic["bridge"]}'/><mac address='{nic["mac"]}'/><model type='{nic["model"]}'/></interface>"""
            flags = libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG if self._get_vm_status(vm.name) == "running" else libvirt.VIR_DOMAIN_AFFECT_CONFIG
            dom.detachDeviceFlags(nic_xml, flags)
            existing = [n for n in existing if n["index"] != nic_index]
            vm.extra_nics = json.dumps(existing)
            db.commit()
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    # -- Phase 1: Deploy from Template --

    def deploy_from_template(self, db, template_id: int, new_name: str) -> dict:
        """Deploy a new VM from a template."""
        template = db.query(VM).filter(VM.id == template_id).first()
        if not template:
            return {"success": False, "error": "Template not found"}
        if not template.is_template:
            return {"success": False, "error": "VM is not a template"}
        if db.query(VM).filter(VM.name == new_name).first():
            return {"success": False, "error": f"VM '{new_name}' already exists"}
        mac = self._generate_mac()
        new_vm = VM(name=new_name, vcpu=template.vcpu, cpu_type=template.cpu_type, memory_mb=template.memory_mb,
                     disk_gb=template.disk_gb, disk_interface=template.disk_interface, os_type=template.os_type,
                     machine_type=template.machine_type, bios_type=template.bios_type, boot_order=template.boot_order,
                     mac_address=mac, serial_console=template.serial_console, agent_enabled=template.agent_enabled,
                     balloon=template.balloon, tpm_enabled=template.tpm_enabled, secure_boot=template.secure_boot,
                     scsi_hw=template.scsi_hw, numa=template.numa, notes=f"From template: {template.name}")
        db.add(new_vm)
        db.commit()
        db.refresh(new_vm)
        src_disk = f"/var/lib/libvirt/images/{template.name}.qcow2"
        dst_disk = f"/var/lib/libvirt/images/{new_name}.qcow2"
        if os.path.exists(src_disk):
            subprocess.run(f"qemu-img create -f qcow2 -b {src_disk} -F qcow2 {dst_disk}", shell=True, capture_output=True)
        self._create_libvirt_vm(new_vm, {"vcpu": new_vm.vcpu, "memory_mb": new_vm.memory_mb})
        return {"success": True, "vm": {"id": new_vm.id, "name": new_vm.name}}

    # -- Phase 1: Cloud-init --

    def apply_cloud_init(self, db, vm_id: int) -> dict:
        """Generate and attach cloud-init ISO."""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if not vm.cloud_init:
            return {"success": False, "error": "Cloud-init not enabled"}
        ci_iso = f"/var/lib/libvirt/images/{vm.name}-cloudinit.iso"
        ci_user = vm.cloud_init_user or "root"
        user_data = f"#cloud-config\nusers:\n  - name: {ci_user}\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n"
        if vm.cloud_init_sshkey:
            user_data += f"ssh_authorized_keys:\n  - {vm.cloud_init_sshkey}\n"
        if vm.cloud_init_ip:
            user_data += f"network:\n  version: 2\n  ethernets:\n    ens3:\n      addresses:\n        - {vm.cloud_init_ip}\n      gateway4: {vm.cloud_init_gateway or ''}\n      nameservers:\n        addresses: [{vm.cloud_init_dns or '8.8.8.8'}]\n"
        meta_data = f"instance-id: {vm.name}\nlocal-hostname: {vm.name}\n"
        try:
            ci_tmp = f"/tmp/nexve-ci-{vm.name}"
            os.makedirs(ci_tmp, exist_ok=True)
            with open(f"{ci_tmp}/user-data", "w") as f:
                f.write(user_data.replace("\n", "\n"))
            with open(f"{ci_tmp}/meta-data", "w") as f:
                f.write(meta_data.replace("\n", "\n"))
            r = subprocess.run(f"genisoimage -output {ci_iso} -volid cidata -joliet -rock {ci_tmp}/user-data {ci_tmp}/meta-data", shell=True, capture_output=True, text=True)
            if r.returncode != 0:
                return {"success": False, "error": f"genisoimage failed: {r.stderr}"}
            return {"success": True, "iso": ci_iso}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -- Phase 1: Guest Agent --

    def guest_agent_command(self, db, vm_id: int, command: str) -> dict:
        """Send a command to the QEMU Guest Agent."""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if not vm.agent_enabled:
            return {"success": False, "error": "Guest agent not enabled"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(vm.name)
            result = dom.agentCommand(command, 0, 0)
            return {"success": True, "result": result}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def guest_agent_info(self, db, vm_id: int) -> dict:
        """Get guest agent info (network, OS)."""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if not vm.agent_enabled:
            return {"success": False, "error": "Guest agent not enabled"}
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        info = {}
        try:
            dom = conn.lookupByName(vm.name)
            for cmd in ["guest-info", "guest-network-get-interfaces", "guest-get-osinfo"]:
                try:
                    result = dom.agentCommand(cmd, 0, 0)
                    if result:
                        info[cmd] = json.loads(result) if isinstance(result, str) else result
                except Exception:
                    pass
            return {"success": True, "info": info}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def guest_agent_fstrim(self, db, vm_id: int) -> dict:
        return self.guest_agent_command(db, vm_id, "guest-fstrim")

    def guest_agent_freeze(self, db, vm_id: int) -> dict:
        return self.guest_agent_command(db, vm_id, "guest-fsfreeze-freeze")

    def guest_agent_thaw(self, db, vm_id: int) -> dict:
        return self.guest_agent_command(db, vm_id, "guest-fsfreeze-thaw")

    def convert_to_template(self, db, vm_id: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if self._get_vm_status(vm.name) == "running":
            return {"success": False, "error": "VM must be stopped before converting to template"}
        vm.is_template = True
        db.commit()
        return {"success": True}


    # ── Internal helpers ──

    def _get_vm_status(self, name: str) -> str:
        conn = self._ensure_conn()
        if not conn:
            return "unknown"
        try:
            dom = conn.lookupByName(name)
            state, _ = dom.state()
            state_map = {
                libvirt.VIR_DOMAIN_RUNNING: "running",
                libvirt.VIR_DOMAIN_PAUSED: "paused",
                libvirt.VIR_DOMAIN_SHUTDOWN: "stopped",
                libvirt.VIR_DOMAIN_SHUTOFF: "stopped",
                libvirt.VIR_DOMAIN_CRASHED: "stopped",
            }
            return state_map.get(state, "unknown")
        except libvirt.libvirtError:
            return "stopped"

    def _generate_mac(self) -> str:
        mac = [0x52, 0x54, 0x00,
               int.from_bytes(os.urandom(1), 'big') | 0x80,
               int.from_bytes(os.urandom(1), 'big'), int.from_bytes(os.urandom(1), 'big')]
        return ":".join(f"{b:02x}" for b in mac)

    def _create_libvirt_vm(self, vm, config: dict) -> dict:
        conn = self._ensure_conn()
        if not conn:
            diag = self.get_diagnostics()
            error_msg = "libvirt is not available."
            if diag["issues"]:
                error_msg += " " + diag["issues"][0]
            return {"error": error_msg, "diagnostics": diag}

        mem_kb = vm.memory_mb * 1024
        disk_path = f"/var/lib/libvirt/images/{vm.name}.qcow2"

        if not os.path.exists(disk_path):
            cmd = f"qemu-img create -f qcow2 {disk_path} {vm.disk_gb}G"
            subprocess.run(cmd, shell=True, capture_output=True)

        bios_xml = ""
        if vm.bios_type == "ovmf":
            bios_xml = f"<os><type arch='x86_64' machine='pc-q35-8.2'>hvm</type><loader readonly='yes' type='pflash'>/usr/share/OVMF/OVMF_CODE.fd</loader><nvram>/var/lib/libvirt/qemu/nvram/{vm.name}_VARS.fd</nvram><boot dev='{vm.boot_order[0] if vm.boot_order else 'c'}'/></os>"
        else:
            bios_xml = f"<os><type arch='x86_64' machine='{vm.machine_type}'>hvm</type><boot dev='{vm.boot_order[0] if vm.boot_order else 'c'}'/></os>"

        serial_xml = "<serial type='pty'><target port='0'/></serial><console type='pty'><target type='serial' port='0'/></console>" if vm.serial_console else ""
        agent_xml = "<channel type='unix'><target type='virtio' name='org.qemu.guest_agent.0'/></channel>" if vm.agent_enabled else ""
        balloon_xml = "<memballoon model='virtio'/>" if vm.balloon else ""

        vm_xml = f"""<domain type='kvm'>
            <name>{vm.name}</name>
            <memory unit='KiB'>{mem_kb}</memory>
            <vcpu placement='static'>{vm.vcpu}</vcpu>
            <devices>
                <disk type='file' device='disk'>
                    <driver name='qemu' type='qcow2'/>
                    <source file='{disk_path}'/>
                    <target dev='vda' bus='{vm.disk_interface}'/>
                </disk>
                <interface type='bridge'>
                    <source bridge='vmbr0'/>
                    <mac address='{vm.mac_address}'/>
                    <model type='virtio'/>
                </interface>
                <graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'>
                    <listen type='address' address='0.0.0.0'/>
                </graphics>
                {serial_xml}{agent_xml}{balloon_xml}
            </devices>
            {bios_xml}
        </domain>"""

        try:
            conn.defineXML(vm_xml)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"error": str(e)}

    def _start_libvirt_vm(self, name: str) -> dict:
        conn = self._ensure_conn()
        if not conn:
            diag = self.get_diagnostics()
            hint = diag["issues"][0] if diag["issues"] else "Install libvirt"
            return {"success": False, "error": f"libvirt not available. {hint}"}
        try:
            dom = conn.lookupByName(name)
            dom.create()
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def _stop_libvirt_vm(self, name: str) -> dict:
        conn = self._ensure_conn()
        if not conn:
            return {"success": False, "error": "libvirt not available"}
        try:
            dom = conn.lookupByName(name)
            if dom.state()[0] == libvirt.VIR_DOMAIN_RUNNING:
                dom.destroy()
            else:
                dom.shutdown()
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def _undefine_libvirt_vm(self, name: str):
        conn = self._ensure_conn()
        if not conn:
            return
        try:
            dom = conn.lookupByName(name)
            dom.undefine()
        except libvirt.libvirtError:
            pass

    def _update_libvirt_config(self, vm):
        conn = self._ensure_conn()
        if not conn:
            return
        try:
            dom = conn.lookupByName(vm.name)
            if vm.hotplug_cpu:
                dom.setVcpus(vm.vcpu)
            if vm.hotplug_ram:
                dom.setMemory(vm.memory_mb * 1024)
        except libvirt.libvirtError:
            pass
