#!/usr/bin/env python3
import sys, os, struct, io
import tkinter as tk
from PIL import Image

def view_crw(filepath):
    if not os.path.exists(filepath):
        print(f"[HATA] Dosya yok: {filepath}")
        return

    with open(filepath, "rb") as f:
        magic = f.read(4)
        if magic != b"CRW4":
            print("[HATA] Bu dosya yeni CRW4 formatında değil!")
            return

        orig_w, orig_h, base_w, base_h = struct.unpack(">HHHH", f.read(8))
        pal_len = struct.unpack("B", f.read(1))[0]
        palette = [struct.unpack("BBB", f.read(3)) for _ in range(pal_len)]

        base_len = struct.unpack(">I", f.read(4))[0]
        base_payload = f.read(base_len)
        delta_len = struct.unpack(">I", f.read(4))[0]
        delta_payload = f.read(delta_len)

    # 1. Taban Pikselleri Hatasız Aç (Tam Eşitleme)
    base_pixels = []
    i = 0
    total_base_pixels = base_w * base_h
    while i < len(base_payload) and len(base_pixels) < total_base_pixels:
        b = base_payload[i]
        if b & 0x80:
            run_len = b & 0x7F
            val = base_payload[i+1]
            base_pixels.extend([val] * run_len)
            i += 2
        else:
            base_pixels.append(b)
            i += 1

    # Eksik piksel kaldıysa doldur (Kaymayı önler)
    if len(base_pixels) < total_base_pixels:
        base_pixels.extend([0] * (total_base_pixels - len(base_pixels)))

    base_img = Image.new("RGB", (base_w, base_h))
    base_img.putdata([palette[p] if p < len(palette) else (0,0,0) for p in base_pixels[:total_base_pixels]])
    
    # 2. Yumuşak Büyütme (BICUBIC)
    smooth_img = base_img.resize((orig_w, orig_h), Image.Resampling.BICUBIC)
    smooth_bytes = bytearray(smooth_img.tobytes())

    # 3. Deltaları Kayma Olmadan Üzerine Mühürle
    di = 0
    pi = 0
    total_bytes = len(smooth_bytes)
    while di < len(delta_payload) and pi < total_bytes:
        tag = delta_payload[di]; di += 1
        if tag == 0x00: # Sıfır fark atlama
            run = delta_payload[di]; di += 1
            pi += run * 3
        elif tag == 0x01: # Renk düzeltme
            dr, dg, db = struct.unpack("bbb", delta_payload[di:di+3])
            di += 3
            if pi + 2 < total_bytes:
                smooth_bytes[pi]   = max(0, min(255, smooth_bytes[pi] + dr))
                smooth_bytes[pi+1] = max(0, min(255, smooth_bytes[pi+1] + dg))
                smooth_bytes[pi+2] = max(0, min(255, smooth_bytes[pi+2] + db))
            pi += 3

    final_img = Image.frombytes("RGB", (orig_w, orig_h), bytes(smooth_bytes))

    # Ekrana Şık ve Orantılı Bas
    win = tk.Tk()
    win.title(f"C R W Reconstructed — {os.path.basename(filepath)} ({orig_w}x{orig_h})")
    win.configure(bg="#07090e")

    # Ekrana taşmaması için 800px genişliğe optimize et
    scale = min(1.0, 800 / orig_w)
    disp_w = int(orig_w * scale)
    disp_h = int(orig_h * scale)
    disp_img = final_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    disp_img.save(buf, format="PPM")
    tk_img = tk.PhotoImage(data=buf.getvalue())

    lbl = tk.Label(win, image=tk_img, bg="#07090e")
    lbl.pack(padx=10, pady=10)

    lbl_info = tk.Label(
        win,
        text=f"Orijinal: {orig_w}x{orig_h} | Faz Kayması Düzeltildi | Net Görüntü",
        font=("Courier", 10), fg="#3fb950", bg="#07090e"
    )
    lbl_info.pack(pady=5)
    win.mainloop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        view_crw(sys.argv[1])
    else:
        print("Kullanım: crwview <dosya.crw>")
