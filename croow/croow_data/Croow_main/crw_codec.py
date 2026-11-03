#!/usr/bin/env python3
import sys
import struct
import os

# Standart Croow Kökleri (Palet)
DEFAULT_PALETTE = [
    ('A', 10),  # Zemin (Siyah/Koyu)
    ('D', 40),  # Düşük ton
    ('J', 65),  # Orta ton
    ('M', 85),  # Yüksek ışık
    ('K', 99)   # Parlak çekirdek
]

SHADES = {
    'A': '  ',
    'D': '░░',
    'J': '▒▒',
    'M': '▓▓',
    'K': '██'
}

def quantize_pixel(val):
    """Piksel değerini en yakın kök harfe bağlar (Tolerans / Epsilon süzgeci)"""
    if val <= 25: return 0  # 'A'
    if val <= 50: return 1  # 'D'
    if val <= 75: return 2  # 'J'
    if val <= 90: return 3  # 'M'
    return 4                # 'K'

def encode_crw(image_grid, output_path):
    """Görüntü matrisini .crw formatında diske yazar"""
    height = len(image_grid)
    width = len(image_grid[0])
    
    # 1. Pikselleri Kök İndekslerine Dönüştür
    indices = []
    for row in image_grid:
        for p in row:
            indices.append(quantize_pixel(p))
            
    # 2. Yörüngesel Sıkıştırma (Run-Length / Orbit Encoding)
    # 1 Bayt ile hem harf hem de tekrar sayısı kodlanır!
    payload = bytearray()
    i = 0
    total_pixels = len(indices)
    
    while i < total_pixels:
        root_idx = indices[i]
        run_len = 1
        while i + 1 < total_pixels and indices[i+1] == root_idx and run_len < 63:
            run_len += 1
            i += 1
            
        if run_len > 1:
            # Tekrar baytı: En sol bit 1, sonraki 6 bit uzunluk, son bit kök
            # Format: 0xC0 | (run_len << 2) | root_idx
            payload.append(0x80 | run_len)
            payload.append(root_idx)
        else:
            payload.append(root_idx)
        i += 1

    # 3. İkili Dosyayı (Binary) Oluştur
    with open(output_path, "wb") as f:
        # Magic (4B) + Width (2B) + Height (2B)
        f.write(b"CRW1")
        f.write(struct.pack(">HH", width, height))
        
        # Palet (1B boyut + N*(1B harf, 1B değer))
        f.write(struct.pack("B", len(DEFAULT_PALETTE)))
        for char, val in DEFAULT_PALETTE:
            f.write(struct.pack("cB", char.encode('ascii'), val))
            
        # Gövde
        f.write(payload)

    raw_size = width * height
    crw_size = os.path.getsize(output_path)
    savings = round((1 - (crw_size / raw_size)) * 100, 1)

    print(f"\n==================================================")
    print(f"[CROOW KODLAYICI] Görüntü '.crw' Formatına Mühürlendi!")
    print(f"==================================================")
    print(f"  ● Çözünürlük         : {width}x{height} ({raw_size} Piksel)")
    print(f"  ● Ham Bitmap Boyutu  : {raw_size} Bayt")
    print(f"  ● .CRW Dosya Boyutu  : {crw_size} Bayt")
    print(f"  └─> Hacim Kazancı    : %{savings} KÜÇÜLTÜLDÜ (Minnacık Kaldı)")
    print(f"==================================================\n")

def decode_crw(input_path):
    """Diskteki .crw dosyasını okur, açar ve terminale çizer"""
    with open(input_path, "rb") as f:
        magic = f.read(4)
        if magic != b"CRW1":
            print("[HATA] Geçersiz .crw dosyası!")
            return
            
        width, height = struct.unpack(">HH", f.read(4))
        palette_len = struct.unpack("B", f.read(1))[0]
        
        palette = []
        for _ in range(palette_len):
            char, val = struct.unpack("cB", f.read(2))
            palette.append((char.decode('ascii'), val))
            
        payload = f.read()

    # Gövdeyi Çöz
    pixels = []
    i = 0
    while i < len(payload):
        b = payload[i]
        if b & 0x80:  # Tekrar Baytı
            run_len = b & 0x7F
            root_idx = payload[i+1]
            pixels.extend([palette[root_idx][0]] * run_len)
            i += 2
        else:
            pixels.append(palette[b][0])
            i += 1

    print(f">>> '.CRW' DOSYASINDAN EKRANA AÇILAN GÖRSEL ({width}x{height}):\n")
    for y in range(height):
        row_str = "".join([SHADES[c] for c in pixels[y*width : (y+1)*width]])
        print(f"  {row_str}")
    print()

if __name__ == "__main__":
    # Test Görseli: 12x12 Boyutunda Çekirdekli Bir Simge
    DEMO_IMAGE = [
        [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
        [10, 10, 40, 40, 40, 40, 40, 40, 40, 40, 10, 10],
        [10, 40, 65, 65, 65, 65, 65, 65, 65, 65, 40, 10],
        [10, 40, 65, 85, 85, 85, 85, 85, 85, 65, 40, 10],
        [10, 40, 65, 85, 99, 99, 99, 99, 85, 65, 40, 10],
        [10, 40, 65, 85, 99, 99, 99, 99, 85, 65, 40, 10],
        [10, 40, 65, 85, 99, 99, 99, 99, 85, 65, 40, 10],
        [10, 40, 65, 85, 99, 99, 99, 99, 85, 65, 40, 10],
        [10, 40, 65, 85, 85, 85, 85, 85, 85, 65, 40, 10],
        [10, 40, 65, 65, 65, 65, 65, 65, 65, 65, 40, 10],
        [10, 10, 40, 40, 40, 40, 40, 40, 40, 40, 10, 10],
        [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
    ]

    # 1. Kodla ve 'amblem.crw' olarak diske yaz
    encode_crw(DEMO_IMAGE, "amblem.crw")
    
    # 2. 'amblem.crw' dosyasını diskten oku ve ekrana çiz
    decode_crw("amblem.crw")
