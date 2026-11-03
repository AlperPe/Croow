#!/usr/bin/env python3
import sys
import os
import struct
from PIL import Image
import tkinter as tk

class CroowImageEngine:
    def __init__(self, max_roots=8):
        self.max_roots = max_roots

    def learn_and_encode(self, input_image_path, output_crw_path):
        """1. AŞAMA: Resmi tanı, kökleri öğren ve .crw olarak katla"""
        if not os.path.exists(input_image_path):
            print(f"[HATA] Dosya bulunamadı: {input_image_path}")
            return

        # Resmi aç ve RGB'ye çevir
        img = Image.open(input_image_path).convert("RGB")
        width, height = img.size

        # Boyut çok devasaysa işlenebilir bir boyuta ölçekle (Örn: max 128x128)
        max_dim = 128
        if width > max_dim or height > max_dim:
            img.thumbnail((max_dim, max_dim))
            width, height = img.size
            print(f"[CROOW ANALİZ] Resim optimize edildi: {width}x{height}")

        # 1. ÖĞRENME: Resimdeki en baskın N rengi (Kökleri) çıkar (Kuantalama)
        quantized = img.quantize(colors=self.max_roots, method=Image.Quantize.MEDIANCUT)
        palette_raw = quantized.getpalette()[:self.max_roots * 3]
        
        # Paleti (R, G, B) köklerine ayır
        learned_roots = []
        for i in range(0, len(palette_raw), 3):
            r, g, b = palette_raw[i], palette_raw[i+1], palette_raw[i+2]
            learned_roots.append((r, g, b))

        print(f"\n==================================================")
        print(f"[CROOW ÖĞRENME MOTORU] Resim Tandı ve Kökler Çıkarıldı:")
        for idx, (r, g, b) in enumerate(learned_roots):
            char_tag = chr(65 + idx) # A, B, C, D...
            print(f"  ● Kök [{char_tag}] -> RGB({r}, {g}, {b})")
        print(f"==================================================")

        # 2. PİKSELLERİ KÖK HARFLERİNE DÖK
        pixel_indices = list(quantized.getdata())

        # 3. YÖRÜNGESEL KATLAMA (Aynı kökleri tek bayta sıkıştır)
        payload = bytearray()
        i = 0
        total = len(pixel_indices)

        while i < total:
            root_idx = pixel_indices[i]
            run_len = 1
            while i + 1 < total and pixel_indices[i+1] == root_idx and run_len < 127:
                run_len += 1
                i += 1

            if run_len > 1:
                # Tekrar Baytı: En sol bit 1 (0x80 | tekrar), sonraki bayt kök
                payload.append(0x80 | run_len)
                payload.append(root_idx)
            else:
                payload.append(root_idx)
            i += 1

        # 4. .CRW DOSYASINI YAZ (Binary Format)
        with open(output_crw_path, "wb") as f:
            f.write(b"CRW2") # Sürüm 2 (Renkli Kökler)
            f.write(struct.pack(">HH", width, height))
            f.write(struct.pack("B", len(learned_roots)))
            for r, g, b in learned_roots:
                f.write(struct.pack("BBB", r, g, b))
            f.write(payload)

        raw_bytes = width * height * 3 # Ham RGB boyutu
        crw_bytes = os.path.getsize(output_crw_path)
        savings = round((1 - (crw_bytes / raw_bytes)) * 100, 1)

        print(f"\n[MÜHÜRLENDİ] '{output_crw_path}' Oluşturuldu!")
        print(f"  ● Ham RGB Boyutu : {raw_bytes} Bayt")
        print(f"  ● .CRW Boyutu    : {crw_bytes} Bayt")
        print(f"  └─> Sıkıştırma    : %{savings} KÜÇÜLTÜLDÜ (Bellek Boşaltıldı)\n")

    def decode_and_view(self, crw_path):
        """2. AŞAMA: .crw dosyasını doğrudan ekrana aç"""
        if not os.path.exists(crw_path):
            print(f"[HATA] Dosya bulunamadı: {crw_path}")
            return

        with open(crw_path, "rb") as f:
            magic = f.read(4)
            if magic != b"CRW2":
                print("[HATA] Bu geçerli bir CRW2 dosyası değil!")
                return

            width, height = struct.unpack(">HH", f.read(4))
            palette_len = struct.unpack("B", f.read(1))[0]
            
            roots = []
            for _ in range(palette_len):
                r, g, b = struct.unpack("BBB", f.read(3))
                roots.append((r, g, b))

            payload = f.read()

        # Pikselleri çöz
        pixels = []
        i = 0
        while i < len(payload):
            b = payload[i]
            if b & 0x80:
                run_len = b & 0x7F
                root_idx = payload[i+1]
                pixels.extend([root_idx] * run_len)
                i += 2
            else:
                pixels.append(b)
                i += 1

        # GUI Penceresinde Göster
        scale = max(1, min(10, 500 // max(width, height)))
        root_win = tk.Tk()
        root_win.title(f"Croow Engine - {os.path.basename(crw_path)} ({width}x{height})")
        
        canvas = tk.Canvas(root_win, width=width*scale, height=height*scale, bg="black")
        canvas.pack()

        for y in range(height):
            for x in range(width):
                idx = y * width + x
                if idx < len(pixels):
                    r, g, b = roots[pixels[idx]]
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    canvas.create_rectangle(
                        x*scale, y*scale, (x+1)*scale, (y+1)*scale,
                        fill=hex_color, outline=hex_color
                    )

        root_win.mainloop()

if __name__ == "__main__":
    engine = CroowImageEngine()

    if len(sys.argv) < 3:
        print("Kullanım Şekli:")
        print("  1. Resmi CRW'ye çevir:  python3 croow_studio.py encode <girdi.png> <cikti.crw>")
        print("  2. CRW dosyasını aç:    python3 croow_studio.py view <dosya.crw>")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "encode":
        engine.learn_and_encode(sys.argv[2], sys.argv[3])
    elif cmd == "view":
        engine.decode_and_view(sys.argv[2])
