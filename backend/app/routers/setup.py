from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.user import User
import subprocess
import os

router = APIRouter()

SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE — Initial Setup</title>
    <link rel="icon" type="image/svg+xml" href="/static/img/favicon.svg">
    <link rel="stylesheet" href="/static/css/nexve.css">
    <link rel="manifest" href="/static/manifest.json">
    <meta name="theme-color" content="#00d4aa">
</head>
<body class="nx-login">
<div class="nx-wizard" style="max-width:640px;">

    <!-- Step indicators -->
    <div class="nx-wizard-steps" id="wizard-steps">
        <div class="nx-wizard-step active" data-step="1"><div class="nx-wizard-step-num">1</div><div class="nx-wizard-step-label">Admin</div></div>
        <div class="nx-wizard-step" data-step="2"><div class="nx-wizard-step-num">2</div><div class="nx-wizard-step-label">Server</div></div>
        <div class="nx-wizard-step" data-step="3"><div class="nx-wizard-step-num">3</div><div class="nx-wizard-step-label">Network</div></div>
        <div class="nx-wizard-step" data-step="4"><div class="nx-wizard-step-num">4</div><div class="nx-wizard-step-label">Confirm</div></div>
    </div>

    <div class="nx-wizard-body">
        <!-- Step 1: Admin Account -->
        <div class="wizard-page" id="page-1">
            <div style="text-align:center;margin-bottom:24px;">
                <img src="/static/img/logo.svg" alt="NexVE" style="width:64px;height:64px;margin-bottom:12px;">
                <h1 style="font-size:var(--text-2xl);font-weight:700;letter-spacing:-0.02em;">NexVE v3.0</h1>
                <p class="nx-text-muted" style="font-size:var(--text-sm);">Hypervisor Management Platform</p>
            </div>
            <h2 style="font-size:var(--text-xl);font-weight:700;margin-bottom:4px;">Create Admin Account</h2>
            <p class="nx-text-muted" style="font-size:var(--text-sm);margin-bottom:24px;">This will be the administrator for your NexVE system.</p>
            <div class="nx-flex nx-flex-col nx-gap-4">
                <div class="nx-input-group">
                    <label class="nx-label">Username</label>
                    <input type="text" name="username" class="nx-input" placeholder="admin" required value="admin">
                </div>
                <div class="nx-input-group">
                    <label class="nx-label">Email</label>
                    <input type="email" name="email" class="nx-input" placeholder="you@example.com" required>
                </div>
                <div class="nx-input-group">
                    <label class="nx-label">Password</label>
                    <input type="password" name="password" class="nx-input" placeholder="Min 8 characters" required minlength="8">
                </div>
                <div class="nx-input-group">
                    <label class="nx-label">Confirm Password</label>
                    <input type="password" name="password_confirm" class="nx-input" placeholder="Repeat password" required minlength="8">
                </div>
            </div>
        </div>

        <!-- Step 2: Server Settings -->
        <div class="wizard-page nx-hidden" id="page-2">
            <h2 style="font-size:var(--text-xl);font-weight:700;margin-bottom:4px;">Server Settings</h2>
            <p class="nx-text-muted" style="font-size:var(--text-sm);margin-bottom:24px;">Configure your server identity and locale.</p>
            <div class="nx-flex nx-flex-col nx-gap-4">
                <div class="nx-input-group">
                    <label class="nx-label">Hostname</label>
                    <input type="text" name="hostname" class="nx-input" placeholder="nexve" value="nexve">
                    <span class="nx-hint">The server's network name.</span>
                </div>
                <div class="nx-input-group">
                    <label class="nx-label">Timezone</label>
                    <select name="timezone" class="nx-select">
                        <option value="UTC">UTC</option>
                        <option value="America/New_York">Eastern Time (US)</option>
                        <option value="America/Chicago">Central Time (US)</option>
                        <option value="America/Denver">Mountain Time (US)</option>
                        <option value="America/Los_Angeles">Pacific Time (US)</option>
                        <option value="Europe/London">London</option>
                        <option value="Europe/Berlin">Berlin</option>
                        <option value="Europe/Paris">Paris</option>
                        <option value="Asia/Tokyo">Tokyo</option>
                        <option value="Asia/Shanghai">Shanghai</option>
                        <option value="Asia/Dubai">Dubai</option>
                        <option value="Asia/Kolkata">Kolkata</option>
                        <option value="Australia/Sydney">Sydney</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Step 3: Network -->
        <div class="wizard-page nx-hidden" id="page-3">
            <h2 style="font-size:var(--text-xl);font-weight:700;margin-bottom:4px;">Network Configuration</h2>
            <p class="nx-text-muted" style="font-size:var(--text-sm);margin-bottom:24px;">Configure network settings for your server.</p>
            <div class="nx-flex nx-flex-col nx-gap-4">
                <div class="nx-input-group">
                    <label class="nx-label">IP Address</label>
                    <input type="text" name="ip_address" class="nx-input" placeholder="e.g. 192.168.1.100">
                    <span class="nx-hint">Leave blank to use DHCP.</span>
                </div>
                <div class="nx-input-group">
                    <label class="nx-label">Gateway</label>
                    <input type="text" name="gateway" class="nx-input" placeholder="e.g. 192.168.1.1">
                </div>
                <div class="nx-input-group">
                    <label class="nx-label">DNS Servers</label>
                    <input type="text" name="dns" class="nx-input" placeholder="e.g. 1.1.1.1, 8.8.8.8" value="1.1.1.1, 8.8.8.8">
                </div>
            </div>
        </div>

        <!-- Step 4: Confirm -->
        <div class="wizard-page nx-hidden" id="page-4">
            <h2 style="font-size:var(--text-xl);font-weight:700;margin-bottom:4px;">Confirm & Initialize</h2>
            <p class="nx-text-muted" style="font-size:var(--text-sm);margin-bottom:24px;">Review your settings before initializing NexVE.</p>
            <div id="summary" style="background:var(--bg-elevated);border:1px solid var(--border-default);border-radius:var(--radius-lg);padding:20px;"></div>
            <div id="setup-error" style="margin-top:12px;"></div>
            <div id="setup-success" style="margin-top:12px;" class="nx-hidden">
                <div style="background:var(--success-dim);border:1px solid rgba(34,197,94,0.2);color:var(--success);padding:12px 16px;border-radius:var(--radius-lg);font-size:var(--text-sm);">
                    ✓ NexVE has been initialized successfully! Redirecting to login...
                </div>
            </div>
        </div>
    </div>

    <!-- Navigation -->
    <div class="nx-wizard-nav" id="wizard-nav">
        <button class="nx-btn nx-btn-secondary" id="btn-back" onclick="prevStep()" style="visibility:hidden;">← Back</button>
        <button class="nx-btn nx-btn-primary" id="btn-next" onclick="nextStep()">Next →</button>
    </div>

</div>

<script>
let currentStep = 1;
const totalSteps = 4;

function showStep(n) {
    document.querySelectorAll('.wizard-page').forEach(p => p.classList.add('nx-hidden'));
    document.getElementById('page-' + n).classList.remove('nx-hidden');

    document.querySelectorAll('.nx-wizard-step').forEach(s => {
        const sn = parseInt(s.dataset.step);
        s.classList.remove('active', 'done');
        if (sn === n) s.classList.add('active');
        if (sn < n) s.classList.add('done');
    });

    document.getElementById('btn-back').style.visibility = n === 1 ? 'hidden' : 'visible';
    document.getElementById('btn-next').textContent = n === totalSteps ? 'Initialize NexVE →' : 'Next →';

    if (n === 4) buildSummary();
}

function buildSummary() {
    const get = (name) => document.querySelector(`[name="${name}"]`)?.value || '-';
    document.getElementById('summary').innerHTML = `
        <div style="display:grid;grid-template-columns:120px 1fr;gap:8px 16px;font-size:var(--text-sm);">
            <span class="nx-text-muted">Admin</span><span>${get('username')} (${get('email')})</span>
            <span class="nx-text-muted">Hostname</span><span>${get('hostname') || 'nexve'}</span>
            <span class="nx-text-muted">Timezone</span><span>${get('timezone')}</span>
            <span class="nx-text-muted">IP</span><span>${get('ip_address') || 'DHCP'}</span>
            <span class="nx-text-muted">DNS</span><span>${get('dns') || '-'}</span>
        </div>`;
}

function nextStep() {
    if (currentStep === 1) {
        const pw = document.querySelector('[name="password"]').value;
        const pw2 = document.querySelector('[name="password_confirm"]').value;
        if (pw !== pw2) { showToast('Passwords do not match', 'error'); return; }
        if (pw.length < 8) { showToast('Password must be at least 8 characters', 'error'); return; }
    }
    if (currentStep < totalSteps) { currentStep++; showStep(currentStep); }
    else submitSetup();
}

function prevStep() { if (currentStep > 1) { currentStep--; showStep(currentStep); } }

async function submitSetup() {
    const btn = document.getElementById('btn-next');
    btn.disabled = true;
    btn.textContent = 'Initializing...';

    const formData = new FormData();
    formData.append('username', document.querySelector('[name="username"]').value);
    formData.append('email', document.querySelector('[name="email"]').value);
    formData.append('password', document.querySelector('[name="password"]').value);
    formData.append('password_confirm', document.querySelector('[name="password_confirm"]').value);
    formData.append('hostname', document.querySelector('[name="hostname"]').value || 'nexve');
    formData.append('timezone', document.querySelector('[name="timezone"]').value);
    formData.append('ip_address', document.querySelector('[name="ip_address"]').value);
    formData.append('gateway', document.querySelector('[name="gateway"]').value);
    formData.append('dns', document.querySelector('[name="dns"]').value);

    try {
        const r = await fetch('/setup/complete', { method: 'POST', body: formData });
        const text = await r.text();
        if (text.includes('error') || text.includes('Error')) {
            document.getElementById('setup-error').innerHTML = text;
            btn.disabled = false;
            btn.textContent = 'Initialize NexVE →';
        } else {
            document.getElementById('setup-success').classList.remove('nx-hidden');
            document.getElementById('wizard-nav').classList.add('nx-hidden');
            setTimeout(() => window.location.href = '/login', 2000);
        }
    } catch (e) {
        document.getElementById('setup-error').innerHTML = '<div style="color:var(--danger);">Network error. Please try again.</div>';
        btn.disabled = false;
        btn.textContent = 'Initialize NexVE →';
    }
}

showStep(1);
</script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def setup_page(request: Request):
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
    finally:
        db.close()
    # Always allow access to setup page - it checks user count internally
    return SETUP_HTML


@router.post("/complete")
async def complete_setup(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    hostname: str = Form("nexve"),
    timezone: str = Form("UTC"),
    ip_address: str = Form(""),
    gateway: str = Form(""),
    dns: str = Form("1.1.1.1, 8.8.8.8"),
):
    if password != password_confirm:
        return HTMLResponse('<div style="color:var(--danger);">Passwords do not match.</div>')
    if len(password) < 8:
        return HTMLResponse('<div style="color:var(--danger);">Password must be at least 8 characters.</div>')

    db = SessionLocal()
    try:
        # Delete existing users if re-running setup
        existing_count = db.query(User).count()
        if existing_count > 0:
            db.query(User).delete()
            db.commit()

        user = User(username=username, email=email, role="admin")
        user.set_password(password)
        db.add(user)
        db.commit()
    finally:
        db.close()

    # Apply server settings
    try:
        if hostname and hostname != "nexve":
            subprocess.run(["hostnamectl", "set-hostname", hostname],
                         capture_output=True, timeout=10)
            hosts = "/etc/hosts"
            try:
                with open(hosts) as f:
                    lines = f.readlines()
                new_lines = []
                for line in lines:
                    if line.strip().startswith("127.0.1.1"):
                        new_lines.append(f"127.0.1.1\t{hostname}\n")
                    else:
                        new_lines.append(line)
                with open(hosts, "w") as f:
                    f.writelines(new_lines)
            except Exception:
                pass

        if timezone and timezone != "UTC":
            subprocess.run(["timedatectl", "set-timezone", timezone],
                         capture_output=True, timeout=10)

        if dns:
            dns_servers = [s.strip() for s in dns.split(",") if s.strip()]
            if dns_servers:
                resolv = "# Generated by NexVE setup\n"
                for server in dns_servers:
                    resolv += f"nameserver {server}\n"
                with open("/etc/resolv.conf", "w") as f:
                    f.write(resolv)
    except Exception:
        pass

    return HTMLResponse(
        '<div style="color:var(--success);">Account created! Redirecting...</div>'
    )

@router.get("/reset")
async def reset_page(request: Request):
    """Show reset confirmation page."""
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE - Reset Setup</title>
    <link rel="icon" type="image/svg+xml" href="/static/img/favicon.svg">
    <link rel="stylesheet" href="/static/css/nexve.css">
</head><body class="nx-login">
<div class="nx-wizard" style="max-width:540px;">
    <div style="text-align:center;margin-bottom:24px;">
        <img src="/static/img/logo.svg" alt="NexVE" style="width:64px;height:64px;margin-bottom:12px;">
        <h1 style="font-size:var(--text-2xl);font-weight:700;">Reset NexVE Setup</h1>
        <p class="nx-text-muted" style="font-size:var(--text-sm);margin-top:8px;">This will delete all users and require re-running the initial setup wizard.</p>
    </div>
    <div style="background:var(--bg-elevated);border:1px solid rgba(239,68,68,0.3);border-radius:var(--radius-lg);padding:16px;margin-bottom:20px;">
        <p style="color:var(--danger);font-size:var(--text-sm);font-weight:600;margin-bottom:8px;">Warning:</p>
        <ul style="color:var(--text-secondary);font-size:var(--text-sm);list-style:disc;padding-left:20px;">
            <li>All admin accounts will be deleted</li>
            <li>2FA settings will be removed</li>
            <li>API tokens will be invalidated</li>
            <li>VMs, containers, and storage are NOT affected</li>
        </ul>
    </div>
    <div id="reset-error"></div>
    <div id="reset-success" class="nx-hidden">
        <div style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);color:var(--success);padding:12px;border-radius:var(--radius-lg);font-size:var(--text-sm);margin-bottom:16px;">
            Reset complete! Redirecting to setup wizard...
        </div>
    </div>
    <div style="display:flex;gap:12px;justify-content:center;">
        <a href="/settings" class="nx-btn nx-btn-secondary">Cancel</a>
        <button class="nx-btn" style="background:var(--danger);color:white;" onclick="doReset()">Reset Everything</button>
    </div>
</div>
<script>
async function doReset() {
    if (!confirm('Are you sure? This cannot be undone.')) return;
    try {
        const r = await fetch('/setup/reset', {method: 'POST'});
        const data = await r.json();
        if (data.success) {
            document.getElementById('reset-success').classList.remove('nx-hidden');
            setTimeout(() => window.location.href = '/setup/', 2000);
        } else {
            document.getElementById('reset-error').innerHTML = '<div style="color:var(--danger);padding:8px;">' + (data.error || 'Reset failed') + '</div>';
        }
    } catch(e) {
        document.getElementById('reset-error').innerHTML = '<div style="color:var(--danger);padding:8px;">Network error</div>';
    }
}
</script>
</body></html>""")


@router.post("/reset")
async def reset_setup(request: Request):
    """Reset all users and re-run setup."""
    db = SessionLocal()
    try:
        from ..models.user import User
        from ..models.vm import VM, Container
        db.query(User).delete()
        db.commit()
    finally:
        db.close()
    return JSONResponse({"success": True})


@router.post("/factory-reset")
async def factory_reset(request: Request):
    """Completely wipe everything: VMs, containers, storage configs, users, and database."""
    import subprocess
    import shutil
    import os
    import glob

    errors = []
    warnings = []

    def _run(cmd, timeout=15):
        """Run a command safely, return (success, stdout, stderr)."""
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Timeout"
        except Exception as e:
            return False, "", str(e)

    # 1. Stop and undefine all VMs via virsh
    has_virsh, _, _ = _run("which virsh 2>/dev/null")
    if has_virsh:
        ok, stdout, _ = _run("virsh list --name 2>/dev/null")
        if ok and stdout:
            for vm_name in stdout.splitlines():
                vm_name = vm_name.strip()
                if vm_name:
                    _run(f"virsh destroy {vm_name} 2>/dev/null")
                    _run(f"virsh undefine {vm_name} --remove-all-storage 2>/dev/null")
    else:
        warnings.append("virsh not found, skipping VM undefine")

    # 2. Stop and destroy all LXC containers
    has_lxc, _, _ = _run("which lxc-ls 2>/dev/null || which lxc-info 2>/dev/null")
    if has_lxc:
        ok, stdout, _ = _run("lxc-ls 2>/dev/null || true")
        if ok and stdout:
            for ct_name in stdout.splitlines():
                ct_name = ct_name.strip().strip("*").strip()
                if ct_name:
                    _run(f"lxc-stop -n {ct_name} -t 5 2>/dev/null")
                    _run(f"lxc-destroy -n {ct_name} --force 2>/dev/null")
    else:
        warnings.append("LXC tools not found, skipping container destroy")

    # 3. Remove all LXC rootfs directories (fallback if lxc-destroy failed)
    lxc_dir = "/var/lib/lxc"
    if os.path.isdir(lxc_dir):
        try:
            for item in os.listdir(lxc_dir):
                path = os.path.join(lxc_dir, item)
                if os.path.isdir(path) and (item.isdigit() or item == "rootfs"):
                    shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            errors.append(f"LXC directory cleanup: {e}")

    # 4. Destroy ZFS datasets for containers
    _run("zfs destroy -r lxc 2>/dev/null || true")

    # 5. Remove VM disk images
    vm_dirs = ["/var/lib/libvirt/images", "/var/lib/nexve/vms"]
    for vm_dir in vm_dirs:
        if os.path.isdir(vm_dir):
            try:
                for item in os.listdir(vm_dir):
                    item_path = os.path.join(vm_dir, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
            except Exception as e:
                errors.append(f"VM disk cleanup ({vm_dir}): {e}")

    # 6. Remove ISO images
    iso_dirs = ["/var/lib/nexve/iso", "/opt/nexve/data/isos"]
    for iso_dir in iso_dirs:
        if os.path.isdir(iso_dir):
            try:
                for f in os.listdir(iso_dir):
                    fpath = os.path.join(iso_dir, f)
                    if os.path.isfile(fpath):
                        os.remove(fpath)
            except Exception as e:
                errors.append(f"ISO cleanup: {e}")

    # 7. Remove backup files
    backup_dirs = ["/opt/nexve/data/backups", os.path.expanduser("~/.nexve/backups")]
    for backup_dir in backup_dirs:
        if os.path.isdir(backup_dir):
            try:
                shutil.rmtree(backup_dir, ignore_errors=True)
            except Exception as e:
                errors.append(f"Backup cleanup: {e}")

    # 8. Remove NexVE config/data directories
    config_dirs = ["/etc/nexve", "/opt/nexve/data", "/var/lib/nexve"]
    for d in config_dirs:
        if os.path.isdir(d):
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception as e:
                errors.append(f"Config cleanup ({d}): {e}")

    # 9. Wipe ALL database tables
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # Get all table names
        from sqlalchemy import inspect as sqla_inspect
        inspector = sqla_inspect(db.get_bind())
        tables = inspector.get_table_names()

        for table in tables:
            try:
                db.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass

        db.commit()
    except Exception as e:
        errors.append(f"Database cleanup: {e}")
    finally:
        db.close()

    # 10. Remove nftables rules
    _run("nft flush table inet nexve 2>/dev/null || true")
    _run("nft delete table inet nexve 2>/dev/null || true")

    # 11. Remove cron jobs
    _run("crontab -r 2>/dev/null || true")

    msg = "Factory reset complete. All VMs, containers, storage, users, and configurations have been removed."
    if warnings:
        msg += f" ({len(warnings)} warnings)"

    return JSONResponse({
        "success": True,
        "message": msg,
        "warnings": warnings if warnings else None,
        "errors": errors if errors else None,
    })


@router.get("/factory-reset")
async def factory_reset_page(request: Request):
    """Show factory reset confirmation page."""
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE - Factory Reset</title>
    <link rel="icon" type="image/svg+xml" href="/static/img/favicon.svg">
    <link rel="stylesheet" href="/static/css/nexve.css">
</head><body class="nx-login">
<div class="nx-wizard" style="max-width:540px;">
    <div style="text-align:center;margin-bottom:24px;">
        <img src="/static/img/logo.svg" alt="NexVE" style="width:64px;height:64px;margin-bottom:12px;">
        <h1 style="font-size:var(--text-2xl);font-weight:700;color:var(--danger);">Factory Reset</h1>
        <p class="nx-text-muted" style="font-size:var(--text-sm);margin-top:8px;">This will permanently destroy EVERYTHING and return NexVE to its original state.</p>
    </div>
    <div style="background:var(--bg-elevated);border:2px solid rgba(239,68,68,0.4);border-radius:var(--radius-lg);padding:16px;margin-bottom:20px;">
        <p style="color:var(--danger);font-size:var(--text-sm);font-weight:700;margin-bottom:8px;">⚠️ THIS ACTION IS IRREVERSIBLE</p>
        <ul style="color:var(--text-secondary);font-size:var(--text-sm);list-style:disc;padding-left:20px;line-height:1.8;">
            <li>All virtual machines will be <strong>stopped and permanently deleted</strong></li>
            <li>All containers will be <strong>stopped and permanently deleted</strong></li>
            <li>All ISO images will be removed</li>
            <li>All storage configurations (ZFS pools, LVM, NFS, CIFS) will be wiped</li>
            <li>All VM disk images and backups will be destroyed</li>
            <li>All user accounts, sessions, and API tokens will be deleted</li>
            <li>All firewall rules, network configs, SDN zones will be removed</li>
            <li>All cluster and HA configurations will be destroyed</li>
            <li>The system will return to the initial setup wizard</li>
        </ul>
    </div>
    <div id="reset-error"></div>
    <div id="reset-success" class="nx-hidden">
        <div style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);color:var(--success);padding:12px;border-radius:var(--radius-lg);font-size:var(--text-sm);margin-bottom:16px;">
            Factory reset complete! Redirecting to setup wizard...
        </div>
    </div>
    <div style="display:flex;gap:12px;justify-content:center;">
        <a href="/settings" class="nx-btn nx-btn-secondary">Cancel</a>
        <button class="nx-btn" style="background:var(--danger);color:white;padding:10px 24px;font-weight:700;" onclick="doFactoryReset()">⚠ Factory Reset</button>
    </div>
</div>
<script>
async function doFactoryReset() {
    if (!confirm('FINAL WARNING: This will permanently delete ALL data including VMs, containers, storage, and users. Type "RESET" in your mind and click OK to proceed.')) return;
    if (!confirm('Are you absolutely sure? There is NO undo.')) return;
    document.getElementById('reset-error').innerHTML = '<div style="color:var(--warning);padding:8px;">Performing factory reset... Please wait...</div>';
    try {
        const r = await fetch('/setup/factory-reset', {method: 'POST'});
        const data = await r.json();
        if (data.success) {
            document.getElementById('reset-success').classList.remove('nx-hidden');
            if (data.warnings && data.warnings.length > 0) {
                document.getElementById('reset-error').innerHTML = '<div style="color:var(--warning);padding:8px;font-size:var(--text-sm);">Warnings: ' + data.warnings.join('; ') + '</div>';
            }
            setTimeout(() => window.location.href = '/setup/', 3000);
        } else {
            document.getElementById('reset-error').innerHTML = '<div style="color:var(--danger);padding:8px;">' + (data.error || 'Reset failed') + '</div>';
        }
    } catch(e) {
        document.getElementById('reset-error').innerHTML = '<div style="color:var(--danger);padding:8px;">Network error: ' + e.message + '</div>';
    }
}
</script>
</body></html>""")

