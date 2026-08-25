import subprocess
import libvirt
import os
from typing import List, Optional
from ..models.vm import VM

class VMService:
    def __init__(self):
        try:
            self.conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError:
            self.conn = None
    
    def get_all_vms(self, db) -> List[dict]:
        """Get VMs from database + live status from libvirt"""
        db_vms = db.query(VM).all()
        result = []
        
        for vm in db_vms:
            live_status = self._get_vm_status(vm.name)
            result.append({
                "id": vm.id,
                "name": vm.name,
                "status": live_status,
                "vcpu": vm.vcpu,
                "memory_mb": vm.memory_mb,
                "disk_gb": vm.disk_gb,
                "ip_address": vm.ip_address,
                "created_at": vm.created_at.isoformat() if vm.created_at else None
            })
        
        return result

def create_vm_cloud_init(self, vm_id: int, hostname: str = "", ip: str = "",
    gateway: str = "", nameservers: str = "", username: str = "", password: str = "",
    ssh_keys: str = "") -> dict:
    """Generate cloud-init ISO for a VM."""

    ci_dir = f"/var/lib/nexve/cloud-init/{vm_id}"
    os.makedirs(ci_dir, exist_ok=True)

    # user-data
    userdata = f"""#cloud-config
hostname: {hostname or f'nexve-vm-{vm_id}'}
manage_etc_hosts: true
"""
    if username:
        userdata += f"""
users:
  - name: {username}
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
"""
        if password:
            userdata += f"    passwd: {password}\n"
        if ssh_keys:
            userdata += f"    ssh_authorized_keys:\n"
            for key in ssh_keys.strip().split("\n"):
                userdata += f"      - {key.strip()}\n"

    if ip and gateway:
        userdata += f"""
network:
  version: 2
  ethernets:
    ens18:
      addresses: [{ip}/24]
      gateway4: {gateway}
"""
        if nameservers:
            userdata += f"      nameservers:\n        addresses: [{nameservers}]\n"

    with open(os.path.join(ci_dir, "user-data"), "w") as f:
        f.write(userdata)

    # meta-data
    with open(os.path.join(ci_dir, "meta-data"), "w") as f:
        f.write(f"instance-id: nexve-vm-{vm_id}\nlocal-hostname: {hostname or f'nexve-vm-{vm_id}'}\n")

    # Generate ISO
    iso_path = f"/var/lib/nexve/iso/cloud-init-{vm_id}.iso"
    result = self.run_cmd(
        f"genisoimage -output {iso_path} -volid cidata -joliet -rock "
        f"{ci_dir}/user-data {ci_dir}/meta-data"
    )
    return result


    def attach_cloud_init(self, vm_id: int) -> dict:
        """Attach cloud-init ISO as secondary CD-ROM."""
        iso_path = f"/var/lib/nexve/iso/cloud-init-{vm_id}.iso"
        if not os.path.exists(iso_path):
            return {"success": False, "error": "Cloud-init ISO not found. Create it first."}
        return self.run_cmd(f"virsh attach-disk vm-{vm_id} {iso_path} vdb --type cdrom --mode readonly")

    
    def _get_vm_status(self, name: str) -> str:
        """Check live VM status from libvirt"""
        if not self.conn:
            return "unknown"
        try:
            dom = self.conn.lookupByName(name)
            if dom.isActive():
                return "running"
            else:
                return "stopped"
        except:
            return "stopped"
    
    def create_vm(self, db, name: str, vcpu: int, memory_mb: int, disk_gb: int) -> dict:
        """Create a new VM"""
        # Check if VM exists
        existing = db.query(VM).filter(VM.name == name).first()
        if existing:
            raise ValueError("VM already exists")
        
        # Create VM entry in database
        vm = VM(
            name=name,
            vcpu=vcpu,
            memory_mb=memory_mb,
            disk_gb=disk_gb,
            status="stopped"
        )
        db.add(vm)
        db.commit()
        db.refresh(vm)
        
        # Create actual VM with libvirt (XML template)
        xml = self._generate_vm_xml(name, vcpu, memory_mb, disk_gb)
        
        try:
            if self.conn:
                self.conn.defineXML(xml)
        except Exception as e:
            # If libvirt fails, still keep the DB entry for now
            pass
        
        return {"id": vm.id, "name": name, "status": "stopped"}
    
    def _generate_vm_xml(self, name: str, vcpu: int, memory_mb: int, disk_gb: int) -> str:
        """Generate libvirt XML for VM"""
        memory_kb = memory_mb * 1024
        return f"""
        <domain type='kvm'>
          <name>{name}</name>
          <memory unit='KiB'>{memory_kb}</memory>
          <vcpu placement='static'>{vcpu}</vcpu>
          <os>
            <type arch='x86_64' machine='pc-q35-8.2'>hvm</type>
            <boot dev='hd'/>
          </os>
          <devices>
            <disk type='file' device='disk'>
              <driver name='qemu' type='qcow2'/>
              <source file='/var/lib/libvirt/images/{name}.qcow2'/>
              <target dev='vda' bus='virtio'/>
            </disk>
            <interface type='bridge'>
              <source bridge='virbr0'/>
              <model type='virtio'/>
            </interface>
            <graphics type='vnc' port='-1' autoport='yes'/>
          </devices>
        </domain>
        """
    
    def start_vm(self, name: str) -> bool:
        """Start a VM"""
        if not self.conn:
            return False
        try:
            dom = self.conn.lookupByName(name)
            dom.create()
            return True
        except:
            return False
    
    def stop_vm(self, name: str) -> bool:
        """Stop a VM"""
        if not self.conn:
            return False
        try:
            dom = self.conn.lookupByName(name)
            dom.shutdown()
            return True
        except:
            return False
    
    def delete_vm(self, db, vm_id: int) -> bool:
        """Delete a VM"""
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return False
        
        # Try to undefine from libvirt
        if self.conn:
            try:
                dom = self.conn.lookupByName(vm.name)
                if dom.isActive():
                    dom.destroy()
                dom.undefine()
            except:
                pass
        
        # Delete disk file
        disk_path = f"/var/lib/libvirt/images/{vm.name}.qcow2"
        if os.path.exists(disk_path):
            os.remove(disk_path)
        
        db.delete(vm)
        db.commit()
        return True

vm_service = VMService()
