from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from ..database import SessionLocal
from ..models.vm import Container
from ..auth import get_current_user
import subprocess

router = APIRouter()


def _run(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception:
        return "stopped"


def _lxc_status(name: str) -> str:
    output = _run(f"pct status {name} 2>/dev/null || lxc-info -n {name} --state 2>/dev/null || echo stopped")
    if "running" in output.lower():
        return "running"
    return "stopped"


def _render_container_list(containers) -> str:
    if not containers:
        return '<div class="text-gray-500 py-8 text-center bg-[#111] border border-gray-800 rounded-xl">No containers yet. Click "Create Container" to get started.</div>'

    rows = ""
    for c in containers:
        live_status = _lxc_status(c.name)
        status_color = "text-green-400" if live_status == "running" else "text-gray-500"
        status_dot = "bg-green-400" if live_status == "running" else "bg-gray-500"

        stop_btn = ""
        start_btn = ""
        if live_status == "running":
            stop_btn = f'<button hx-post="/api/containers/{c.name}/stop" hx-swap="none" hx-confirm="Stop this container?" class="text-gray-400 hover:text-yellow-400 p-2 transition" title="Stop"><svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1"/></svg></button>'
        else:
            start_btn = f'<button hx-post="/api/containers/{c.name}/start" hx-swap="none" class="text-gray-400 hover:text-green-400 p-2 transition" title="Start"><svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></button>'

        rows += f"""
        <div class="flex items-center justify-between bg-[#111] border border-gray-800 rounded-xl px-5 py-4">
            <div class="flex items-center gap-4">
                <div class="w-2 h-2 rounded-full {status_dot}"></div>
                <div>
                    <div class="font-semibold">{c.name}</div>
                    <div class="text-sm text-gray-500">{c.template} &middot; {c.vcpu} vCPU &middot; {c.memory_mb}MB RAM &middot; {c.disk_gb}GB</div>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-sm {status_color} capitalize">{live_status}</span>
                {start_btn}
                {stop_btn}
                <button hx-delete="/api/containers/{c.name}" hx-swap="none" hx-confirm="Delete this container?" class="text-gray-400 hover:text-red-400 p-2 transition" title="Delete">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                </button>
            </div>
        </div>"""

    return rows


@router.get("/", response_class=HTMLResponse)
async def containers_page(request: Request):
    user = get_current_user(request)
    if not user:
        return HTMLResponse(status_code=303, headers={"Location": "/login"})

    db = SessionLocal()
    try:
        containers = db.query(Container).all()
        list_html = _render_container_list(containers)
    finally:
        db.close()

    return f"""<div class="space-y-6">
        <div class="flex items-center justify-between">
            <h2 class="text-2xl font-bold">Containers</h2>
            <button onclick="document.getElementById('create-container-modal').classList.remove('hidden')"
                class="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-semibold transition">
                + Create Container
            </button>
        </div>

        <div id="container-list" class="space-y-2">
            {list_html}
        </div>
    </div>

    <!-- Create Modal -->
    <div id="create-container-modal" class="hidden fixed inset-0 bg-black/70 flex items-center justify-center z-50" onclick="document.getElementById('create-container-modal').classList.add('hidden')">
        <div class="bg-[#111] border border-gray-800 rounded-xl p-6 w-full max-w-lg" onclick="event.stopPropagation()">
            <h3 class="text-xl font-semibold mb-4">Create Container</h3>
            <form hx-post="/api/containers/create" hx-swap="innerHTML" hx-target="#container-list"
                  hx-after-request="document.getElementById('create-container-modal').classList.add('hidden')">
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm text-gray-400 mb-1">Name</label>
                        <input type="text" name="name" required
                            class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-orange-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-sm text-gray-400 mb-1">Template</label>
                        <select name="template"
                            class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-orange-500 focus:outline-none">
                            <option value="debian-12-standard">Debian 12</option>
                            <option value="ubuntu-24.04-standard">Ubuntu 24.04</option>
                            <option value="alpine-3.19-standard">Alpine 3.19</option>
                            <option value="centos-9-stream-standard">CentOS 9 Stream</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm text-gray-400 mb-1">CPU Cores</label>
                        <input type="number" name="vcpu" value="1" min="1" max="32"
                            class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-orange-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-sm text-gray-400 mb-1">Memory (MB)</label>
                        <input type="number" name="memory_mb" value="512" min="64"
                            class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-orange-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-sm text-gray-400 mb-1">Disk (GB)</label>
                        <input type="number" name="disk_gb" value="8" min="1"
                            class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-orange-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-sm text-gray-400 mb-1">Bridge</label>
                        <select name="bridge"
                            class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-orange-500 focus:outline-none">
                            <option value="vmbr0">vmbr0</option>
                        </select>
                    </div>
                </div>
                <div id="create-error"></div>
                <div class="flex justify-end gap-3">
                    <button type="button" onclick="document.getElementById('create-container-modal').classList.add('hidden')"
                        class="px-4 py-2 text-gray-400 hover:text-white transition">Cancel</button>
                    <button type="submit"
                        class="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2 rounded-lg font-semibold transition">Create</button>
                </div>
            </form>
        </div>
    </div>"""


@router.get("/list", response_class=HTMLResponse)
async def container_list(request: Request):
    user = get_current_user(request)
    if not user:
        return HTMLResponse(status_code=303, headers={"Location": "/login"})

    db = SessionLocal()
    try:
        containers = db.query(Container).all()
        return _render_container_list(containers)
    finally:
        db.close()


@router.post("/create", response_class=HTMLResponse)
async def create_container(
    request: Request,
    name: str = Form(...),
    template: str = Form("debian-12-standard"),
    vcpu: int = Form(1),
    memory_mb: int = Form(512),
    disk_gb: int = Form(8),
    bridge: str = Form("vmbr0"),
):
    user = get_current_user(request)
    if not user:
        return HTMLResponse(status_code=303, headers={"Location": "/login"})

    db = SessionLocal()
    try:
        existing = db.query(Container).filter(Container.name == name).first()
        if existing:
            return HTMLResponse(
                '<div class="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-2 rounded-lg mb-4">Container name already exists.</div>'
            )

        container = Container(
            name=name, template=template, vcpu=vcpu,
            memory_mb=memory_mb, disk_gb=disk_gb, bridge=bridge,
        )
        db.add(container)
        db.commit()

        containers = db.query(Container).all()
        return _render_container_list(containers)
    finally:
        db.close()


@router.post("/{name}/start")
async def start_container(name: str, request: Request):
    user = get_current_user(request)
    if not user:
        return HTMLResponse(status_code=303, headers={"Location": "/login"})
    # subprocess.run(["pct", "start", name])
    return HTMLResponse("OK", headers={"HX-Trigger": "refresh"})


@router.post("/{name}/stop")
async def stop_container(name: str, request: Request):
    user = get_current_user(request)
    if not user:
        return HTMLResponse(status_code=303, headers={"Location": "/login"})
    # subprocess.run(["pct", "stop", name])
    return HTMLResponse("OK", headers={"HX-Trigger": "refresh"})


@router.delete("/{name}")
async def delete_container(name: str, request: Request):
    user = get_current_user(request)
    if not user:
        return HTMLResponse(status_code=303, headers={"Location": "/login"})

    db = SessionLocal()
    try:
        db.query(Container).filter(Container.name == name).delete()
        db.commit()
        containers = db.query(Container).all()
        return _render_container_list(containers)
    finally:
        db.close()
