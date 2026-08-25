from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from ..database import SessionLocal
from ..models.firewall import FirewallRule, FirewallGroup
from ..services.firewall_service import FirewallService
from ..auth import get_current_user

router = APIRouter()
fw_service = FirewallService()


@router.get("/", response_class=HTMLResponse)
async def firewall_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        rules = db.query(FirewallRule).order_by(FirewallRule.position).all()
        groups = db.query(FirewallGroup).all()
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE — Firewall</title><script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0a0a0a] text-white min-h-screen flex">
    <nav class="w-64 bg-[#111] border-r border-[#222] p-4 min-h-screen">
        <h2 class="text-xl font-bold mb-8 text-orange-500">NexVE</h2>
        <ul class="space-y-2 text-sm">
            <li><a href="/" class="block px-4 py-2 rounded hover:bg-[#222]">Dashboard</a></li>
            <li><a href="/vms" class="block px-4 py-2 rounded hover:bg-[#222]">Virtual Machines</a></li>
            <li><a href="/containers" class="block px-4 py-2 rounded hover:bg-[#222]">Containers</a></li>
            <li><a href="/storage" class="block px-4 py-2 rounded hover:bg-[#222]">Storage</a></li>
            <li><a href="/network" class="block px-4 py-2 rounded hover:bg-[#222]">Network</a></li>
            <li><a href="/firewall" class="block px-4 py-2 rounded bg-orange-600/20 text-orange-400">Firewall</a></li>
            <li><a href="/backups" class="block px-4 py-2 rounded hover:bg-[#222]">Backups</a></li>
            <li><a href="/settings" class="block px-4 py-2 rounded hover:bg-[#222]">Settings</a></li>
        </ul>
    </nav>
    <main class="flex-1 p-8">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold">Firewall Rules</h1>
            <a href="/firewall/create" class="bg-orange-600 hover:bg-orange-700 px-4 py-2 rounded-lg font-semibold text-sm">+ Add Rule</a>
        </div>
        <div class="bg-[#111] border border-[#222] rounded-xl overflow-hidden">
            <table class="w-full text-sm">
                <thead class="bg-[#1a1a1a] text-gray-400">
                    <tr><th class="px-4 py-3 text-left">#</th><th class="px-4 py-3 text-left">Direction</th>
                    <th class="px-4 py-3 text-left">Action</th><th class="px-4 py-3 text-left">Protocol</th>
                    <th class="px-4 py-3 text-left">Source</th><th class="px-4 py-3 text-left">Destination</th>
                    <th class="px-4 py-3 text-left">Ports</th><th class="px-4 py-3 text-left">Target</th>
                    <th class="px-4 py-3 text-left">Status</th><th class="px-4 py-3 text-left">Actions</th></tr>
                </thead>
                <tbody class="divide-y divide-[#222]">
                    """ + "".join(f"""
                    <tr class="hover:bg-[#1a1a1a]">
                        <td class="px-4 py-3">{r.position}</td>
                        <td class="px-4 py-3">{r.direction.upper()}</td>
                        <td class="px-4 py-3"><span class="px-2 py-1 rounded text-xs {'bg-green-900 text-green-300' if r.action == 'accept' else 'bg-red-900 text-red-300'}">{r.action}</span></td>
                        <td class="px-4 py-3">{r.protocol}</td>
                        <td class="px-4 py-3 font-mono text-xs">{r.source or '*'}</td>
                        <td class="px-4 py-3 font-mono text-xs">{r.destination or '*'}</td>
                        <td class="px-4 py-3 font-mono text-xs">{r.sport or '*'}:{r.dport or '*'}</td>
                        <td class="px-4 py-3 text-xs">{r.target_type}:{r.target_id or 'all'}</td>
                        <td class="px-4 py-3">{'🟢' if r.enabled else '🔴'}</td>
                        <td class="px-4 py-3"><a href="/firewall/delete/{r.id}" class="text-red-400 hover:text-red-300 text-xs">Delete</a></td>
                    </tr>""" for r in rules) + """
                </tbody>
            </table>
        </div>
    </main>
</body></html>"""
    finally:
        db.close()


@router.get("/create", response_class=HTMLResponse)
async def create_rule_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE — Add Firewall Rule</title><script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0a0a0a] text-white min-h-screen p-8">
    <div class="max-w-lg mx-auto">
        <h1 class="text-2xl font-bold mb-6">Add Firewall Rule</h1>
        <form method="POST" action="/firewall/create" class="bg-[#111] border border-[#222] rounded-xl p-6 space-y-4">
            <div class="grid grid-cols-2 gap-4">
                <div><label class="text-gray-400 text-sm">Direction</label>
                    <select name="direction" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1">
                        <option value="in">Inbound</option><option value="out">Outbound</option></select></div>
                <div><label class="text-gray-400 text-sm">Action</label>
                    <select name="action" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1">
                        <option value="accept">Accept</option><option value="drop">Drop</option><option value="reject">Reject</option></select></div>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="text-gray-400 text-sm">Protocol</label>
                    <select name="protocol" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1">
                        <option value="tcp">TCP</option><option value="udp">UDP</option><option value="icmp">ICMP</option><option value="all">All</option></select></div>
                <div><label class="text-gray-400 text-sm">Position</label>
                    <input name="position" type="number" value="0" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1"></div>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="text-gray-400 text-sm">Source IP/CIDR</label>
                    <input name="source" placeholder="e.g. 192.168.1.0/24" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1"></div>
                <div><label class="text-gray-400 text-sm">Destination IP/CIDR</label>
                    <input name="destination" placeholder="e.g. 10.0.0.1" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1"></div>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="text-gray-400 text-sm">Source Port(s)</label>
                    <input name="sport" placeholder="e.g. 1024:65535" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1"></div>
                <div><label class="text-gray-400 text-sm">Dest Port(s)</label>
                    <input name="dport" placeholder="e.g. 80,443" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1"></div>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="text-gray-400 text-sm">Target</label>
                    <select name="target_type" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1">
                        <option value="host">Host</option><option value="vm">VM</option></select></div>
                <div><label class="text-gray-400 text-sm">Target ID (VM number, empty=all)</label>
                    <input name="target_id" placeholder="e.g. 100" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1"></div>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="text-gray-400 text-sm">Comment</label>
                    <input name="comment" class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1"></div>
                <div class="flex items-end gap-4">
                    <label class="flex items-center gap-2 text-sm"><input type="checkbox" name="enabled" checked class="rounded"> Enabled</label>
                    <label class="flex items-center gap-2 text-sm"><input type="checkbox" name="log" class="rounded"> Log</label>
                </div>
            </div>
            <div class="flex gap-4 pt-2">
                <button type="submit" class="bg-orange-600 hover:bg-orange-700 text-white px-6 py-2 rounded-lg font-semibold">Create Rule</button>
                <a href="/firewall" class="bg-[#222] hover:bg-[#333] px-6 py-2 rounded-lg">Cancel</a>
            </div>
        </form>
    </div>
</body></html>"""


@router.post("/create")
async def create_rule(request: Request, direction: str = Form(...), action: str = Form(...),
    protocol: str = Form("tcp"), source: str = Form(""), destination: str = Form(""),
    sport: str = Form(""), dport: str = Form(""), target_type: str = Form("host"),
    target_id: str = Form(""), comment: str = Form(""), position: int = Form(0),
    enabled: bool = Form(True), log: bool = Form(False)):

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        rule = FirewallRule(
            direction=direction, action=action, protocol=protocol,
            source=source, destination=destination, sport=sport, dport=dport,
            target_type=target_type, target_id=target_id, comment=comment,
            position=position, enabled=enabled, log=log
        )
        db.add(rule)
        db.commit()
        fw_service.apply_rules(db, target_type, target_id)
        return RedirectResponse(url="/firewall", status_code=302)
    finally:
        db.close()


@router.get("/delete/{rule_id}")
async def delete_rule(rule_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        rule = db.query(FirewallRule).filter(FirewallRule.id == rule_id).first()
        if rule:
            tt, ti = rule.target_type, rule.target_id
            db.delete(rule)
            db.commit()
            fw_service.apply_rules(db, tt, ti)
    finally:
        db.close()
    return RedirectResponse(url="/firewall", status_code=302)
