#!/usr/bin/env python3
import http.server
import socketserver
import io
import struct
import base64
import json
import zlib
from PIL import Image

PORT = 8080

def encode_image_to_crw5(image_bytes, max_colors=16):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = img.size

    # 1. Taban katman boyutu (maksimum 256px genişlik)
    base_w = min(orig_w, 256)
    base_h = max(1, round(orig_h * (base_w / orig_w)))

    # 2. Taban katmana indirgeme ve dinamik median-cut paletleme
    base_img = img.resize((base_w, base_h), Image.Resampling.BILINEAR)
    quantized = base_img.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
    
    palette_raw = quantized.getpalette()[:max_colors * 3]
    learned_palette = [
        (palette_raw[i], palette_raw[i+1], palette_raw[i+2])
        for i in range(0, len(palette_raw), 3)
    ]
    base_indices = list(quantized.getdata())

    # 3. Taban RLE paketleme
    base_payload = bytearray()
    bi = 0
    total_base = len(base_indices)
    while bi < total_base:
        val = base_indices[bi]
        run = 1
        while bi + run < total_base and base_indices[bi + run] == val and run < 127:
            run += 1
        if run > 1:
            base_payload.append(0x80 | run)
            base_payload.append(val)
            bi += run
        else:
            base_payload.append(val)
            bi += 1

    # 4. Tahmin edilen (genişletilmiş) taban görseli üret
    rec_base = Image.new("RGB", (base_w, base_h))
    rec_base.putdata([learned_palette[idx] for idx in base_indices])
    exp_img = rec_base.resize((orig_w, orig_h), Image.Resampling.BILINEAR)

    orig_pixels = list(img.getdata())
    exp_pixels = list(exp_img.getdata())

    # 5. Rezidüel Delta katmanı (Luminance eşikli)
    delta_payload = bytearray()
    zero_runs = 0

    for orig_p, exp_p in zip(orig_pixels, exp_pixels):
        dr = orig_p[0] - exp_p[0]
        dg = orig_p[1] - exp_p[1]
        db = orig_p[2] - exp_p[2]
        lum_diff = abs(0.299 * dr + 0.587 * dg + 0.114 * db)

        if lum_diff < 28:
            zero_runs += 1
            if zero_runs == 255:
                delta_payload.append(0x00)
                delta_payload.append(255)
                zero_runs = 0
        else:
            if zero_runs > 0:
                delta_payload.append(0x00)
                delta_payload.append(zero_runs)
                zero_runs = 0
            delta_payload.append(0x01)
            # -128..127 sınırla ve struct pack signed char (b)
            dr_clamped = max(-128, min(127, dr))
            dg_clamped = max(-128, min(127, dg))
            db_clamped = max(-128, min(127, db))
            delta_payload.extend(struct.pack("bbb", dr_clamped, dg_clamped, db_clamped))

    if zero_runs > 0:
        delta_payload.append(0x00)
        delta_payload.append(zero_runs)

    # 6. Ham Gövde = [base_len(4B)] + [base] + [delta_len(4B)] + [delta]
    raw_body = bytearray()
    raw_body.extend(struct.pack(">I", len(base_payload)))
    raw_body.extend(base_payload)
    raw_body.extend(struct.pack(">I", len(delta_payload)))
    raw_body.extend(delta_payload)

    # 7. Zlib Deflate Sıkıştırma
    compressed_body = zlib.compress(raw_body, level=9)

    # 8. CRW5 Header
    header = bytearray(b"CRW5")
    header.extend(struct.pack(">HHHHB", orig_w, orig_h, base_w, base_h, len(learned_palette)))
    for r, g, b in learned_palette:
        header.extend(struct.pack("BBB", r, g, b))

    crw5_bytes = bytes(header + compressed_body)

    preview_buf = io.BytesIO()
    exp_img.save(preview_buf, format="PNG")

    return {
        "width": orig_w,
        "height": orig_h,
        "raw_size": len(image_bytes),
        "crw_size": len(crw5_bytes),
        "savings": round((1 - (len(crw5_bytes) / len(image_bytes))) * 100, 1),
        "palette": learned_palette,
        "crw_base64": base64.b64encode(crw5_bytes).decode(),
        "preview_url": f"data:image/png;base64,{base64.b64encode(preview_buf.getvalue()).decode()}"
    }

def decode_crw5_bytes(crw_data):
    if len(crw_data) < 14 or crw_data[:4] != b"CRW5":
        return None

    orig_w, orig_h, base_w, base_h, pal_len = struct.unpack(">HHHHB", crw_data[4:13])
    off = 13
    palette = []
    for _ in range(pal_len):
        palette.append(struct.unpack("BBB", crw_data[off:off+3]))
        off += 3

    compressed_body = crw_data[off:]
    decompressed_body = zlib.decompress(compressed_body)

    base_len = struct.unpack(">I", decompressed_body[0:4])[0]
    body_off = 4
    base_payload = decompressed_body[body_off:body_off + base_len]
    body_off += base_len

    delta_len = struct.unpack(">I", decompressed_body[body_off:body_off + 4])[0]
    body_off += 4
    delta_payload = decompressed_body[body_off:body_off + delta_len]

    # Taban RLE Çöz
    base_pixels = []
    bi = 0
    total_base = base_w * base_h
    while bi < len(base_payload) and len(base_pixels) < total_base:
        b = base_payload[bi]
        bi += 1
        if b & 0x80:
            run = b & 0x7F
            val = base_payload[bi]
            bi += 1
            base_pixels.extend([val] * run)
        else:
            base_pixels.append(b)

    rec_base = Image.new("RGB", (base_w, base_h))
    rec_base.putdata([palette[p] for p in base_pixels])
    exp_img = rec_base.resize((orig_w, orig_h), Image.Resampling.BILINEAR)

    pixels = list(exp_img.getdata())
    di = 0
    pi = 0
    total_pixels = orig_w * orig_h

    # Delta katmanını uygula
    reconstructed_pixels = []
    while di < len(delta_payload) and pi < total_pixels:
        tag = delta_payload[di]
        di += 1
        if tag == 0x00:
            run = delta_payload[di]
            di += 1
            for _ in range(run):
                if pi < total_pixels:
                    reconstructed_pixels.append(pixels[pi])
                    pi += 1
        elif tag == 0x01:
            dr, dg, db = struct.unpack("bbb", delta_payload[di:di+3])
            di += 3
            orig_p = pixels[pi]
            reconstructed_pixels.append((
                max(0, min(255, orig_p[0] + dr)),
                max(0, min(255, orig_p[1] + dg)),
                max(0, min(255, orig_p[2] + db))
            ))
            pi += 1

    final_img = Image.new("RGB", (orig_w, orig_h))
    final_img.putdata(reconstructed_pixels)

    out_buf = io.BytesIO()
    final_img.save(out_buf, format="PNG")

    return {
        "width": orig_w,
        "height": orig_h,
        "size": len(crw_data),
        "preview_url": f"data:image/png;base64,{base64.b64encode(out_buf.getvalue()).decode()}"
    }

# ==========================================
# TEST WEBSİTESİ VE REST API
# ==========================================
class CroowServer(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # popup.html dosyasını doğrudan kök adreste sunar
        try:
            with open("popup.html", "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, "popup.html bulunamadi!")

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_len)

        if self.path == '/api/encode':
            res = encode_image_to_crw5(post_data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode())

        elif self.path == '/api/decode':
            res = decode_crw5_bytes(post_data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode())

if __name__ == "__main__":
    print(f"\n==================================================")
    print(f"🚀 [CROOW CRW5 MOTORU AKTİF]")
    print(f"👉 http://localhost:{PORT}")
    print(f"==================================================\n")
    with socketserver.TCPServer(("", PORT), CroowServer) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nSunucu kapatıldı.")
