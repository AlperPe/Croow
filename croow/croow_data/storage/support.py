#!/usr/bin/env python3
import sys
from PIL import Image

def resize_for_chrome_store(input_path, output_path="icon_128.png"):
    try:
        # Görseli aç
        img = Image.open(input_path)
        
        # Chrome Mağaza kuralları gereği şeffaflığı (RGBA -> RGB) düzelt
        # Arka planda şeffaflık varsa beyaz veya krem renk ile doldurur
        if img.mode in ('RGBA', 'LA'):
            background = Image.new("RGB", img.size, (253, 243, 219)) # Sıcak krem-altın tonu
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert("RGB")
            
        # Keskinliği koruyarak tam 128x128 piksele yeniden boyutlandır
        img_resized = img.resize((128, 128), Image.Resampling.LANCZOS)
        
        # 24-bit PNG olarak kaydet (Mağazanın kabul ettiği format)
        img_resized.save(output_path, "PNG", optimize=True)
        print(f"[BAŞARILI] Görsel tam 128x128 piksele dönüştürüldü ve '{output_path}' olarak kaydedildi.")
        
    except Exception as e:
        print(f"[HATA] Dönüştürme sırasında sorun oluştu: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        resize_for_chrome_store(sys.argv[1])
    else:
        print("Kullanım: python resize_icon.py <resim_dosyasi.png>")
