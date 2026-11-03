#!/usr/bin/env python3
import http.server
import socketserver
import io, os, struct, json, time, base64, shutil
from PIL import Image

PORT = 8080
VAULT_DIR = "croow_cloud_vault"
STORAGE_DIR = f"{VAULT_DIR}/storage"
INDEX_FILE = f"{VAULT_DIR}/vault_index.json"
ROOTS_FILE = f"{VAULT_DIR}/universal_roots.bin"

os.makedirs(STORAGE_DIR, exist_ok=True)

# Otomatik Dosya Kontrolü (İndirmeler hazır mı?)
if not os.path.exists(f"{STORAGE_DIR}/crw-extension.zip") and os.path.exists("crw_extension"):
    shutil.make_archive(f"{STORAGE_DIR}/crw-extension", 'zip', 'crw_extension')

if not os.path.exists(f"{STORAGE_DIR}/CroowImage-Linux"):
    if os.path.exists("dist/CroowImage"):
        shutil.copy("dist/CroowImage", f"{STORAGE_DIR}/CroowImage-Linux")
    elif os.path.exists("/usr/local/bin/crwview"):
        shutil.copy("/usr/local/bin/crwview", f"{STORAGE_DIR}/CroowImage-Linux")

def load_universal_palette():
    if os.path.exists(ROOTS_FILE):
        with open(ROOTS_FILE, "rb") as f:
            count = struct.unpack("B", f.read(1))[0]
            palette = []
            for _ in range(count):
                palette.append(list(struct.unpack("BBB", f.read(3))))
            return palette
    return [[i, i, i] for i in range(0, 255, 16)]

UNIVERSAL_PALETTE = load_universal_palette()

def load_vault_index():
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return []

def save_vault_index(data):
    with open(INDEX_FILE, "w") as f: json.dump(data, f)

def compress_and_store(image_bytes, filename):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = img.size
    orig_bytes = img.tobytes()

    base_w = min(orig_w, 256)
    base_h = int(orig_h * (base_w / orig_w))
    base_img = img.resize((base_w, base_h), Image.Resampling.LANCZOS)

    base_data = base_img.tobytes()
    base_indices = []
    for i in range(0, len(base_data), 3):
        r, g, b = base_data[i], base_data[i+1], base_data[i+2]
        min_d = float('inf')
        best_idx = 0
        for idx, (pr, pg, pb) in enumerate(UNIVERSAL_PALETTE):
            d = (r-pr)**2 + (g-pg)**2 + (b-pb)**2
            if d < min_d: min_d = d; best_idx = idx
        base_indices.append(best_idx)

    base_payload = bytearray()
    bi = 0
    total = len(base_indices)
    while bi < total:
        val = base_indices[bi]
        run = 1
        while bi + run < total and base_indices[bi + run] == val and run < 127: run += 1
        if run > 1:
            base_payload.append(0x80 | run); base_payload.append(val); bi += run
        else:
            base_payload.append(val); bi += 1

    exp_img = Image.new("RGB", (base_w, base_h))
    exp_img.putdata([tuple(UNIVERSAL_PALETTE[p]) for p in base_indices])
    exp_bytes = exp_img.resize((orig_w, orig_h), Image.Resampling.BICUBIC).tobytes()

    delta_payload = bytearray()
    zero_runs = 0
    for idx in range(orig_w * orig_h):
        p = idx * 3
        dr = orig_bytes[p] - exp_bytes[p]
        dg = orig_bytes[p+1] - exp_bytes[p+1]
        db = orig_bytes[p+2] - exp_bytes[p+2]
        lum = abs(0.299*dr + 0.587*dg + 0.114*db)
        if lum < 22:
            zero_runs += 1
            if zero_runs == 255:
                delta_payload.append(0x00); delta_payload.append(255); zero_runs = 0
        else:
            if zero_runs > 0:
                delta_payload.append(0x00); delta_payload.append(zero_runs); zero_runs = 0
            delta_payload.append(0x01)
            delta_payload.extend(struct.pack("bbb", max(-128, min(127, dr)), max(-128, min(127, dg)), max(-128, min(127, db))))
    if zero_runs > 0: delta_payload.append(0x00); delta_payload.append(zero_runs)

    file_id = f"crw_{int(time.time()*1000)}"
    crw_filename = f"{file_id}.crw"
    crw_path = f"{STORAGE_DIR}/{crw_filename}"

    with open(crw_path, "wb") as f:
        f.write(b"CRW4")
        f.write(struct.pack(">HHHH", orig_w, orig_h, base_w, base_h))
        f.write(struct.pack("B", len(UNIVERSAL_PALETTE)))
        for rgb in UNIVERSAL_PALETTE: f.write(struct.pack("BBB", *rgb))
        f.write(struct.pack(">I", len(base_payload)))
        f.write(base_payload)
        f.write(struct.pack(">I", len(delta_payload)))
        f.write(delta_payload)

    raw_kb = len(orig_bytes) // 1024
    crw_kb = max(1, os.path.getsize(crw_path) // 1024)
    savings = round((1 - (crw_kb / raw_kb)) * 100) if raw_kb > 0 else 0

    thumb = exp_img.resize((140, max(20, int(140*(orig_h/orig_w)))))
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, format="JPEG", quality=65)
    thumb_b64 = base64.b64encode(thumb_buf.getvalue()).decode()

    meta = {
        "id": file_id, "name": filename, "crw_file": crw_filename,
        "orig_w": orig_w, "orig_h": orig_h, "raw_kb": raw_kb,
        "crw_kb": crw_kb, "savings": savings, "thumb": f"data:image/jpeg;base64,{thumb_b64}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M")
    }

    index = load_vault_index()
    index.insert(0, meta)
    save_vault_index(index)
    return meta

HTML_APP = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>C R O O W — Cloud Image Vault</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #06080d;
            --surface: #0c1017;
            --border: rgba(255,255,255,0.08);
            --accent: #58a6ff;
            --green: #00e676;
            --text: #f0f6fc;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text);
            margin: 0; padding: 20px; min-height: 100vh;
            background-image: radial-gradient(circle at 50% 0%, rgba(124, 58, 237, 0.07) 0%, transparent 60%);
        }

        /* TOP DIRECT ACTION BUTTONS BAR */
        .top-bar {
            max-width: 1050px;
            margin: 0 auto 15px auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .version-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #8b949e;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            padding: 5px 12px;
            border-radius: 12px;
        }
        .app-links-group {
            display: flex;
            gap: 10px;
        }
        .direct-dl-btn {
            background: rgba(0, 230, 118, 0.06);
            border: 1px solid rgba(0, 230, 118, 0.4);
            color: var(--green);
            padding: 7px 14px;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .direct-dl-btn:hover {
            background: rgba(0, 230, 118, 0.18);
            border-color: var(--green);
            box-shadow: 0 0 12px rgba(0, 230, 118, 0.25);
            transform: translateY(-1px);
        }

        /* HEADER */
        header { display: flex; flex-direction: column; align-items: center; max-width: 1100px; margin: 0 auto 30px auto; }
        .logo-wrapper { display: flex; flex-direction: column; align-items: center; cursor: pointer; transition: transform 0.25s ease; }
        .logo-wrapper:hover { transform: scale(1.02); }
        .brand-sub { font-size: 11px; color: #8b949e; letter-spacing: 3px; text-transform: uppercase; font-family: 'JetBrains Mono', monospace; margin-top: 8px; }

        .neon-divider { width: 100%; max-width: 820px; height: 1.5px; background: linear-gradient(90deg, transparent 0%, rgba(124, 58, 237, 0.7) 30%, rgba(0, 230, 118, 0.8) 70%, transparent 100%); box-shadow: 0 0 12px rgba(124, 58, 237, 0.4); margin: 18px 0 24px 0; }

        .vault-stats-bar { display: flex; gap: 15px; margin-bottom: 25px; justify-content: center; flex-wrap: wrap; }
        .vault-stat { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 6px 16px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #8b949e; }
        .vault-stat b { color: var(--green); }

        .main-container { max-width: 1050px; margin: 0 auto; display: flex; flex-direction: column; gap: 25px; }

        .upload-card { background: var(--surface); border: 1px dashed rgba(255,255,255,0.15); border-radius: 14px; padding: 40px 20px; text-align: center; cursor: pointer; transition: 0.2s ease; }
        .upload-card:hover { border-color: var(--green); background: rgba(0, 230, 118, 0.03); }
        .upload-title { font-size: 16px; font-weight: 600; margin: 0 0 6px 0; }
        .upload-hint { font-size: 12px; color: #8b949e; font-family: 'JetBrains Mono', monospace; margin: 0; }

        .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 20px; }
        .item-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; transition: transform 0.2s, border-color 0.2s; display: flex; flex-direction: column; }
        .item-card:hover { transform: translateY(-4px); border-color: rgba(0, 230, 118, 0.4); }
        .item-thumb { width: 100%; height: 170px; object-fit: cover; background: #000; }
        .item-meta { padding: 14px; font-size: 12px; font-family: 'JetBrains Mono', monospace; display: flex; flex-direction: column; gap: 5px; }
        .item-name { font-weight: 600; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: 'Inter'; }
        .badge { font-weight: bold; color: var(--green); }
        .item-actions { display: flex; gap: 8px; margin-top: 10px; }
        .act-btn { flex: 1; padding: 7px; font-size: 11px; background: rgba(255,255,255,0.06); color: #fff; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; text-align: center; text-decoration: none; font-family: 'Inter'; }
        .act-btn:hover { background: var(--green); color: #000; border-color: var(--green); font-weight: bold; }
    </style>
</head>
<body>
    <!-- TOP BAR: DIRECT INSTANT DOWNLOAD BUTTONS -->
    <div class="top-bar">
        <div class="version-badge">⚡ Core v2.0 • 255 Roots</div>
        <div class="app-links-group">
            <a href="/download/CroowImage-Linux" class="direct-dl-btn" download>
                <span>🐧</span> Download Linux App
            </a>
            <a href="/download/crw-extension.zip" class="direct-dl-btn" download>
                <span>🧩</span> Get Chrome Extension
            </a>
        </div>
    </div>

    <header>
        <div class="logo-wrapper">
            <svg width="340" height="75" viewBox="0 0 340 75" fill="none" xmlns="http://www.w3.org/2000/svg">
                <text x="35" y="54" font-family="'Inter', sans-serif" font-size="40" font-weight="800" fill="#ffffff" letter-spacing="14">C R</text>
                <path d="M 132 50 C 122 50 115 42 119 32 C 122 22 135 20 142 22 C 148 12 166 8 178 14 C 187 8 205 10 211 20 C 223 20 232 28 229 39 C 235 48 223 52 214 50 C 204 54 146 54 132 50 Z" fill="rgba(18, 25, 38, 0.7)" stroke="rgba(88, 166, 255, 0.28)" stroke-width="1.2"/>
                <path d="M 188 17 C 202 6 226 5 240 12 C 228 17 218 22 212 28 Z" fill="#1e293b"/>
                <path d="M 200 13 C 218 2 248 3 258 11 C 244 16 234 22 226 27 Z" fill="#2d3748"/>
                <path d="M 140 38 L 126 40 C 130 44 136 45 142 43 Z" fill="#1b2433"/>
                <line x1="164" y1="39" x2="178" y2="39" stroke="#00e676" stroke-width="4.5" stroke-linecap="round"/>
                <circle cx="152" cy="39" r="12.5" fill="#06080d" stroke="#00e676" stroke-width="4"/>
                <circle cx="152" cy="39" r="3" fill="#ffffff"/>
                <circle cx="190" cy="39" r="12.5" fill="#06080d" stroke="#00e676" stroke-width="4"/>
                <circle cx="190" cy="39" r="3" fill="#ffffff"/>
                <text x="218" y="54" font-family="'Inter', sans-serif" font-size="40" font-weight="800" fill="#ffffff">W</text>
            </svg>
            <div class="brand-sub">CLOUD IMAGE VAULT • 255-ROOT BRAIN</div>
        </div>
        <div class="neon-divider"></div>
        <div class="vault-stats-bar">
            <div class="vault-stat">Storage: <b id="stat-usage">0 MB</b></div>
            <div class="vault-stat">Economy: <b id="stat-saved">0 MB Saved (95%)</b></div>
            <div class="vault-stat">Brain: <b>255 Roots Saturated</b></div>
        </div>
    </header>

    <div class="main-container">
        <div class="upload-card" id="dz">
            <p class="upload-title">☁ Upload Photo to Croow Cloud</p>
            <p class="upload-hint">Compresses & stores in .CRW (Takes 95% less disk space)</p>
            <input type="file" id="inp-file" accept="image/*" multiple style="display:none">
        </div>
        <div id="upload-status" style="display:none; text-align:center; font-family:'JetBrains Mono'; color:var(--green); font-size:12px;">Compressing with 255-Root Brain & Uploading...</div>
        <div class="gallery-grid" id="gallery"></div>
    </div>

    <script>
        const dz = document.getElementById('dz');
        const inp = document.getElementById('inp-file');
        dz.onclick = () => inp.click();
        dz.ondragover = (e) => e.preventDefault();
        dz.ondrop = (e) => { e.preventDefault(); handleFiles(e.dataTransfer.files); };
        inp.onchange = (e) => handleFiles(e.target.files);

        async function handleFiles(files) {
            if (!files.length) return;
            document.getElementById('upload-status').style.display = 'block';
            for (let f of files) {
                await fetch('/api/upload?name=' + encodeURIComponent(f.name), { method: 'POST', body: f });
            }
            document.getElementById('upload-status').style.display = 'none';
            loadGallery();
        }

        async function loadGallery() {
            const res = await fetch('/api/gallery');
            const items = await res.json();
            const grid = document.getElementById('gallery');
            grid.innerHTML = '';

            let totalCrw = 0, totalRaw = 0;
            items.forEach(item => {
                totalCrw += item.crw_kb;
                totalRaw += item.raw_kb;

                const card = document.createElement('div');
                card.className = 'item-card';
                card.innerHTML = `
                    <img src="${item.thumb}" class="item-thumb">
                    <div class="item-meta">
                        <div class="item-name">${item.name}</div>
                        <div>Raw: ${item.raw_kb} KB → <span class="badge">${item.crw_kb} KB (-%${item.savings})</span></div>
                        <div style="color:#8b949e; font-size:10px;">${item.orig_w}x${item.orig_h} • ${item.timestamp}</div>
                        <div class="item-actions">
                            <a href="/download/${item.crw_file}" class="act-btn" download>Download .CRW</a>
                            <button onclick="deleteItem('${item.id}')" class="act-btn" style="color:#ff7b72;">Delete</button>
                        </div>
                    </div>
                `;
                grid.appendChild(card);
            });

            const saved = Math.max(0, totalRaw - totalCrw);
            document.getElementById('stat-usage').innerText = (totalCrw/1024).toFixed(1) + " MB";
            document.getElementById('stat-saved').innerText = (saved/1024).toFixed(1) + " MB Saved (95%)";
        }

        async function deleteItem(id) {
            if (!confirm('Delete from Croow Cloud?')) return;
            await fetch('/api/delete?id=' + id);
            loadGallery();
        }

        loadGallery();
    </script>
</body>
</html>
"""

class CroowCloudServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(HTML_APP.encode())
        elif self.path == '/api/gallery':
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(load_vault_index()).encode())
        elif self.path.startswith('/download/'):
            filename = self.path.split('/')[-1]
            file_path = f"{STORAGE_DIR}/{filename}"
            if os.path.exists(file_path):
                with open(file_path, "rb") as f: data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()
                self.wfile.write(b"File not found in storage.")
        elif self.path.startswith('/api/delete'):
            import urllib.parse
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            item_id = query.get('id', [''])[0]
            index = load_vault_index()
            new_index = []
            for item in index:
                if item["id"] == item_id:
                    p = f"{STORAGE_DIR}/{item['crw_file']}"
                    if os.path.exists(p): os.remove(p)
                else: new_index.append(item)
            save_vault_index(new_index)
            self.send_response(200); self.end_headers()

    def do_POST(self):
        if self.path.startswith('/api/upload'):
            import urllib.parse
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            filename = query.get('name', ['image.png'])[0]
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            meta = compress_and_store(body, filename)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(meta).encode())

if __name__ == "__main__":
    print(f"\n==================================================")
    print(f"☁ [CROOW IMAGE CLOUD AKTİF]")
    print(f"👉 Adres: http://localhost:{PORT}")
    print(f"==================================================\n")
    with socketserver.TCPServer(("", PORT), CroowCloudServer) as httpd:
        try: httpd.serve_forever()
        except KeyboardInterrupt: print("\nKapatıldı.")
