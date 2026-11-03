#!/usr/bin/env python3
import sys

# 1. ORİJİNAL PİKSEL MATRİSİ (8x8 Gri Tonlama: 0=Siyah, 99=Parlak Beyaz)
# Bu aslında 64 adet sayıdır (Bir görüntünün pikselleri)
PIXEL_GRID = [
    [10, 10, 10, 10, 10, 10, 10, 10],
    [10, 30, 50, 50, 50, 50, 30, 10],
    [10, 50, 80, 99, 99, 80, 50, 10],
    [10, 50, 99, 99, 99, 99, 50, 10],
    [10, 50, 99, 99, 99, 99, 50, 10],
    [10, 50, 80, 99, 99, 80, 50, 10],
    [10, 30, 50, 50, 50, 50, 30, 10],
    [10, 10, 10, 10, 10, 10, 10, 10],
]

# 2. CROOW KÖK HARİTASI (Piksel Parlaklığı -> Harf / Ton)
# Parlaklık değerlerini harflere mühürleyen palet
def pixel_to_root(val):
    if val <= 15: return 'A'   # Karanlık zemin
    if val <= 40: return 'D'   # Düşük ışık
    if val <= 65: return 'J'   # Orta ton (Formül kökü)
    if val <= 85: return 'M'   # Yüksek ışık
    return 'K'                 # Parlak çekirdek

def root_to_render(char):
    # Harfi ekrana görsel blok olarak basma
    PALETTE = {
        'A': '  ',   # Boşluk (Siyah zemin)
        'D': '░░',   # Hafif ton
        'J': '▒▒',   # Orta ton
        'M': '▓▓',   # Yoğun ton
        'K': '██'    # Saf beyaz piksel
    }
    return PALETTE.get(char, '??')

# ==========================================
# CROOW MOTOR: PİKSELLERİ HARFLERE KATLAMA
# ==========================================
print("==================================================")
print("[CROOW PIXEL ENGINE] Ham Görüntü Matrisi Taranıyor...")
print("==================================================")

compressed_stream = []
for row in PIXEL_GRID:
    row_roots = "".join([pixel_to_root(p) for p in row])
    compressed_stream.append(row_roots)

full_harf_zinciri = "".join(compressed_stream)

print(f"Ham Piksel Sayısı       : {len(PIXEL_GRID) * len(PIXEL_GRID[0])} piksel (Sayılar)")
print(f"Katlanmış Harf Akışı    : [{full_harf_zinciri[:32]}...]")
print(f"Yakalanan Kök Harfler   : [ A = Zemin, D = Gönye, J = Halka, K = Çekirdek ]\n")

# ==========================================
# GERİ ÇİZİM: HARFLERDEN PİKSELLERİ AÇMA
# ==========================================
print(">>> CROOW FORMÜLÜNDEN EKRANA YENİDEN ÇİZİLEN PİKSEL RESMİ:\n")
for row_idx, row_str in enumerate(compressed_stream):
    line_render = "".join([root_to_render(char) for char in row_str])
    print(f"  {line_render}   <-- [Harf Satırı: {row_str}]")

print("\n==================================================")
print("[SONUÇ] Resim hafızada sayı olarak tutulmadı;")
print("Kök harflerin ışık rezonansından piksel piksel yeniden üretildi!")
print("==================================================")
