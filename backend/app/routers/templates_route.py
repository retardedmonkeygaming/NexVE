from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from ..services.iso_service import ISOService
from ..auth import get_current_user
import os

router = APIRouter()
iso_svc = ISOService()


@router.get("/", response_class=HTMLResponse)
async def templates_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    isos = iso_svc.list_local()
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE — ISO Templates</title><script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0a0a0a] text-white min-h-screen p-8">
    <div class="max-w-4xl mx-auto">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold">ISO Templates</h1>
            <a href="/templates/upload" class="bg-orange-600 hover:bg-orange-700 px-4 py-2 rounded-lg font-semibold text-sm">+ Upload ISO</a>
        </div>
        <div class="bg-[#111] border border-[#222] rounded-xl p-4 mb-6">
            <h2 class="text-sm text-gray-400 mb-3">Download from URL</h2>
            <form method="POST" action="/templates/download" class="flex gap-3">
                <input name="url" type="url" placeholder="https://example.com/debian-12.iso" required
                    class="flex-1 bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2">
                <button type="submit" class="bg-orange-600 hover:bg-orange-700 px-4 py-2 rounded-lg font-semibold text-sm whitespace-nowrap">Download</button>
            </form>
        </div>
        <div class="bg-[#111] border border-[#222] rounded-xl overflow-hidden">
            <table class="w-full text-sm">
                <thead class="bg-[#1a1a1a] text-gray-400">
                    <tr><th class="px-4 py-3 text-left">Name</th><th class="px-4 py-3 text-left">Size</th>
                    <th class="px-4 py-3 text-left">Actions</th></tr>
                </thead>
                <tbody class="divide-y divide-[#222]">
                    """ + ("".join(f"""
                    <tr class="hover:bg-[#1a1a1a]">
                        <td class="px-4 py-3 font-mono">{i['name']}</td>
                        <td class="px-4 py-3">{i['size_gb']} GB</td>
                        <td class="px-4 py-3"><a href="/templates/delete/{i['filename']}" class="text-red-400 hover:text-red-300 text-xs">Delete</a></td>
                    </tr>""" for i in isos) if isos else '<tr><td colspan="3" class="px-4 py-8 text-center text-gray-500">No ISO images found</td></tr>') + """
                </tbody>
            </table>
        </div>
        <a href="/" class="inline-block mt-4 text-gray-400 hover:text-white text-sm">← Back to Dashboard</a>
    </div>
</body></html>"""


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE — Upload ISO</title><script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0a0a0a] text-white min-h-screen p-8">
    <div class="max-w-lg mx-auto">
        <h1 class="text-2xl font-bold mb-6">Upload ISO Image</h1>
        <form method="POST" action="/templates/upload" enctype="multipart/form-data"
            class="bg-[#111] border border-[#222] rounded-xl p-6 space-y-4">
            <div><label class="text-gray-400 text-sm">Select ISO File</label>
                <input name="file" type="file" accept=".iso,.img" required
                    class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-2 mt-1 text-sm file:mr-4 file:py-1 file:px-3 file:rounded file:border-0 file:bg-orange-600 file:text-white"></div>
            <div class="flex gap-4">
                <button type="submit" class="bg-orange-600 hover:bg-orange-700 px-6 py-2 rounded-lg font-semibold">Upload</button>
                <a href="/templates" class="bg-[#222] hover:bg-[#333] px-6 py-2 rounded-lg">Cancel</a>
            </div>
        </form>
    </div>
</body></html>"""


@router.post("/upload")
async def upload_iso(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    dest = os.path.join(iso_svc.ISO_DIR, file.filename)
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return RedirectResponse(url="/templates", status_code=302)


@router.post("/download")
async def download_iso(request: Request, url: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    iso_svc.download(url)
    return RedirectResponse(url="/templates", status_code=302)


@router.get("/delete/{filename}")
async def delete_iso(filename: str, request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    iso_svc.delete(filename)
    return RedirectResponse(url="/templates", status_code=302)
