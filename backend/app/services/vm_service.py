import subprocess
import libvirt
import os
import json
import uuid
from typing import List, Optional
from datetime import datetime
from ..models.vm import VM


class VMService:
    def __init__(self):
        try:
            self.conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError:
            self.conn = None

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

        # Create actual libvirt VM
        result = self._create_libvirt_vm(vm, config)

        return {
            "success": True,
            "vm": {
                "id": vm.id,
                "name": vm.name,
                "status": "stopped",
                "mac_address": mac,
            },
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

        # Update libvirt config if running
        live_status = self._get_vm_status(vm.name)
        if live_status == "running":
            self._update_libvirt_config(vm)

        return {"success": True, "vm": self.get_vm(db, vm_id)}

    def delete_vm(self, db, vm_id: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}

        # Stop if running
        live_status = self._get_vm_status(vm.name)
        if live_status == "running":
            self._stop_libvirt_vm(vm.name)

        # Undefine from libvirt
        self._undefine_libvirt_vm(vm.name)

        # Delete disk file
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

        if linked:
            # Linked clone — backing file reference
            new_vm = VM(
                name=new_name,
                vcpu=vm.vcpu,
                cpu_type=vm.cpu_type,
                memory_mb=vm.memory_mb,
                disk_gb=vm.disk_gb,
                disk_interface=vm.disk_interface,
                os_type=vm.os_type,
                machine_type=vm.machine_type,
                bios_type=vm.bios_type,
                boot_order=vm.boot_order,
                notes=f"Linked clone of {vm.name}",
                serial_console=vm.serial_console,
                agent_enabled=vm.agent_enabled,
                balloon=vm.balloon,
                mac_address=self._generate_mac(),
                linked_from=vm.id,
            )
        else:
            # Full clone
            new_vm = VM(
                name=new_name,
                vcpu=vm.vcpu,
                cpu_type=vm.cpu_type,
                memory_mb=vm.memory_mb,
                disk_gb=vm.disk_gb,
                disk_interface=vm.disk_interface,
                os_type=vm.os_type,
                machine_type=vm.machine_type,
                bios_type=vm.bios_type,
                boot_order=vm.boot_order,
                notes=f"Full clone of {vm.name}",
                serial_console=vm.serial_console,
                agent_enabled=vm.agent_enabled,
                balloon=vm.balloon,
                mac_address=self._generate_mac(),
            )

        db.add(new_vm)
        db.commit()
        db.refresh(new_vm)

        # Clone disk
        src_disk = f"/var/lib/libvirt/images/{vm.name}.qcow2"
        dst_disk = f"/var/lib/libvirt/images/{new_name}.qcow2"
        if os.path.exists(src_disk):
            if linked:
                cmd = f"qemu-img create -f qcow2 -b {src_disk} -F qcow2 {dst_disk}"
            else:
                cmd = f"qemu-img create -f qcow2 -b {src_disk} -F qcow2 -F qcow2 {dst_disk}"
                cmd = f"cp {src_disk} {dst_disk}"
            subprocess.run(cmd, shell=True, capture_output=True)

        # Create libvirt domain
        self._create_libvirt_vm(new_vm, {"vcpu": new_vm.vcpu, "memory_mb": new_vm.memory_mb})

        return {"success": True, "vm": {"id": new_vm.id, "name": new_vm.name}}

    def resize_disk(self, db, vm_id: int, new_size_gb: int) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}

        disk_path = f"/var/lib/libvirt/images/{vm.name}.qcow2"
        if not os.path.exists(disk_path):
            return {"success": False, "error": "Disk file not found"}

        size_str = f"{new_size_gb}G"
        result = subprocess.run(
            f"qemu-img resize {disk_path} {size_str}",
            shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip()}

        vm.disk_gb = new_size_gb
        db.commit()
        return {"success": True}

    def get_vm_config(self, vm_name: str) -> dict:
        """Read actual libvirt XML config."""
        if not self.conn:
            return {"error": "No libvirt connection"}
        try:
            dom = self.conn.lookupByName(vm_name)
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

        if not self.conn:
            return {"success": False, "error": "No libvirt connection"}

        try:
            dom = self.conn.lookupByName(vm.name)
            flags = libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC
            xml = f"""
            <domainsnapshot>
                <description>Snapshot: {name}</description>
            </domainsnapshot>
            """
            dom.snapshotCreateXML(xml, flags)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def list_snapshots(self, vm_id: int, db) -> list:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm or not self.conn:
            return []
        try:
            dom = self.conn.lookupByName(vm.name)
            snapshots = dom.snapshotListFlags(0)
            result = []
            for snap in snapshots:
                info = snap.getInfo()
                result.append({
                    "name": snap.getName(),
                    "creation_time": datetime.fromtimestamp(info[3]).isoformat(),
                })
            return result
        except libvirt.libvirtError:
            return []

    def restore_snapshot(self, vm_id: int, snap_name: str, db) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if not self.conn:
            return {"success": False, "error": "No libvirt connection"}
        try:
            dom = self.conn.lookupByName(vm.name)
            snap = dom.snapshotLookupByName(snap_name, 0)
            flags = libvirt.VIR_DOMAIN_SNAPSHOT_REVERT_RUNNING
            dom.revertToSnapshot(snap, flags)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def delete_snapshot(self, vm_id: int, snap_name: str, db) -> dict:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return {"success": False, "error": "VM not found"}
        if not self.conn:
            return {"success": False, "error": "No libvirt connection"}
        try:
            dom = self.conn.lookupByName(vm.name)
            snap = dom.snapshotLookupByName(snap_name, 0)
            snap.delete(0)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    # ── Internal helpers ──

    def _get_vm_status(self, name: str) -> str:
        if not self.conn:
            return "unknown"
        try:
            dom = self.conn.lookupByName(name)
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
               int.from_bytes(os.urandom(1), 'big'),
               int.from_bytes(os.urandom(1), 'big')]
        return ":".join(f"{b:02x}" for b in mac)

    def _create_libvirt_vm(self, vm, config: dict) -> dict:
        if not self.conn:
            return {"error": "No libvirt connection"}

        mem_kb = vm.memory_mb * 1024
        disk_path = f"/var/lib/libvirt/images/{vm.name}.qcow2"

        # Create disk if it doesn't exist
        if not os.path.exists(disk_path):
            size = f"{vm.disk_gb}G"
            disk_fmt = "qcow2"
            cmd = f"qemu-img create -f {disk_fmt} {disk_path} {size}"
            subprocess.run(cmd, shell=True, capture_output=True)

        # Build XML
        bios_xml = ""
        if vm.bios_type == "ovmf":
            bios_xml = """
            <os>
                <type arch='x86_64' machine='pc-q35-8.2'>hvm</type>
                <loader readonly='yes' type='pflash'>/usr/share/OVMF/OVMF_CODE.fd</loader>
                <nvram>/var/lib/libvirt/qemu/nvram/{name}_VARS.fd</nvram>
                <boot dev='{boot}'/>
            </os>
            """.format(name=vm.name, boot=vm.boot_order[0] if vm.boot_order else "c")
        else:
            bios_xml = """
            <os>
                <type arch='x86_64' machine='{machine}'>hvm</type>
                <boot dev='{boot}'/>
            </os>
            """.format(machine=vm.machine_type, boot=vm.boot_order[0] if vm.boot_order else "c")

        serial_xml = ""
        if vm.serial_console:
            serial_xml = """
            <serial type='pty'>
                <target port='0'/>
            </serial>
            <console type='pty'>
                <target type='serial' port='0'/>
            </console>
            """

        agent_xml = ""
        if vm.agent_enabled:
            agent_xml = """
            <channel type='unix'>
                <target type='virtio' name='org.qemu.guest_agent.0'/>
            </channel>
            """

        balloon_xml = ""
        if vm.balloon:
            balloon_xml = "<memballoon model='virtio'/>"

        ifvm_xml = f"""
        <domain type='kvm'>
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
                {serial_xml}
                {agent_xml}
                {balloon_xml}
            </devices>
            {bios_xml}
        </domain>
        """

        try:
            self.conn.defineXML(ifvm_xml)
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"error": str(e)}

    def _start_libvirt_vm(self, name: str) -> dict:
        if not self.conn:
            return {"success": False, "error": "No libvirt connection"}
        try:
            dom = self.conn.lookupByName(name)
            dom.create()
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def _stop_libvirt_vm(self, name: str) -> dict:
        if not self.conn:
            return {"success": False, "error": "No libvirt connection"}
        try:
            dom = self.conn.lookupByName(name)
            if dom.state()[0] == libvirt.VIR_DOMAIN_RUNNING:
                dom.destroy()
            else:
                dom.shutdown()
            return {"success": True}
        except libvirt.libvirtError as e:
            return {"success": False, "error": str(e)}

    def _undefine_libvirt_vm(self, name: str):
        if not self.conn:
            return
        try:
            dom = self.conn.lookupByName(name)
            dom.undefine()
        except libvirt.libvirtError:
            pass

    def _update_libvirt_config(self, vm):
        """Update live VM config (CPU/RAM hotplug)."""
        if not self.conn:
            return
        try:
            dom = self.conn.lookupByName(vm.name)
            if vm.hotplug_cpu:
                dom.setVcpus(vm.vcpu)
            if vm.hotplug_ram:
                dom.setMemory(vm.memory_mb * 1024)
        except libvirt.libvirtError:
            pass
