#!/usr/bin/env python3
import sys, os, struct
from PIL import Image

def generate_crw4(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"[HATA] Dosya yok: {input_path}")
        return

    orig_img = Image.open(input_path).convert("RGB")
    orig_w, orig_h = orig_img.size

    # Devasa 12MP fotoğraflarda satır kaymasını önlemek için optimize taban
    base_w = min(orig_w, 256)
    base_h = int(orig_h * (base_w / orig_w))
    base_img = orig_img.resize((base_w, base_h), Image.Resampling.LANCZOS)

    # 16 Kök Rengi Çıkar
    quantized_base = base_img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    palette_raw = quantized_base.getpalette()[:48]
    base_indices = list(quantized_base.getdata())

    # Hatasız Taban Paketleme
    base_payload = bytearray()
    i = 0
    total = len(base_indices)
    while i < total:
        val = base_indices[i]
        run = 1
        while i + run < total and base_indices[i + run] == val and run < 127:
            run += 1
        if run > 1:
            base_payload.append(0x80 | run)
            base_payload.append(val)
            i += run
        else:
            base_payload.append(val)
            i += 1

    # Tohumu Orijinal Boyuta Genişlet
    expanded = quantized_base.convert("RGB").resize((orig_w, orig_h), Image.Resampling.BICUBIC)
    orig_bytes = orig_img.tobytes()
    exp_bytes = expanded.tobytes()

    # Yazı ve Kenar Deltalarını Kaydet (Faz Kayması Sıfırlandı)
    delta_payload = bytearray()
    total_pixels = orig_w * orig_h
    zero_runs = 0

    for idx in range(total_pixels):
        p = idx * 3
        dr = orig_bytes[p] - exp_bytes[p]
        dg = orig_bytes[p+1] - exp_bytes[p+1]
        db = orig_bytes[p+2] - exp_bytes[p+2]

        # Eşik kontrolü (Gürültüyü at, yazıları ve sert çizgileri tut)
        if abs(dr) < 20 and abs(dg) < 20 and abs(db) < 20:
            zero_runs += 1
            if zero_runs == 255:
                delta_payload.append(0x00)
                delta_payload.append(zero_runs)
                zero_runs = 0
        else:
            if zero_runs > 0:
                delta_payload.append(0x00)
                delta_payload.append(zero_runs)
                zero_runs = 0
            delta_payload.append(0x01)
            delta_payload.extend(struct.pack("bbb", max(-128, min(127, dr)), max(-128, min(127, dg)), max(-128, min(127, db))))

    if zero_runs > 0:
        delta_payload.append(0x00)
        delta_payload.append(zero_runs)

    # CRW4 Dosyasını Mühürle
    with open(output_path, "wb") as f:
        f.write(b"CRW4")
        f.write(struct.pack(">HHHH", orig_w, orig_h, base_w, base_h))
        f.write(struct.pack("B", len(palette_raw) // 3))
        f.write(bytes(palette_raw))
        f.write(struct.pack(">I", len(base_payload)))
        f.write(base_payload)
        f.write(struct.pack(">I", len(delta_payload)))
        f.write(delta_payload)

    raw_kb = len(orig_bytes) // 1024
    crw_kb = os.path.getsize(output_path) // 1024
    print(f"\n✓ MÜKEMMEL KODLANDI: {output_path}")
    print(f"  ● Ham Boyut: {raw_kb} KB → .CRW: {crw_kb} KB (Faz Kayması Yok)")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        generate_crw4(sys.argv[1], sys.argv[2])
    else:
        print("Kullanım: python3 crw_maker.py <resim.jpg/png> <hedef.crw>")
