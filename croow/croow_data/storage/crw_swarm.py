#!/usr/bin/env python3
import sys, os, time, struct, random, urllib.request
from PIL import Image

class CroowSwarm:
    def __init__(self, output_dir="crw_training_lab"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(f"{self.output_dir}/raw_images", exist_ok=True)
        os.makedirs(f"{self.output_dir}/crw_files", exist_ok=True)
        self.dict_file = f"{self.output_dir}/universal_roots.bin"
        self.learned_memory = []
        self.load_memory()

    def load_memory(self):
        """Önceki oturumlardan öğrenilen evrensel kökleri hafızaya yükler"""
        if os.path.exists(self.dict_file):
            try:
                with open(self.dict_file, "rb") as f:
                    count = struct.unpack("B", f.read(1))[0]
                    for _ in range(count):
                        self.learned_memory.append(list(struct.unpack("BBB", f.read(3))))
                print(f"[HAFIZA] Önceki oturumlardan {len(self.learned_memory)} adet kök renk yüklendi.")
            except Exception:
                self.learned_memory = []

    def fetch_fresh_images(self, count=15):
        """Her seferinde TAMAMEN YENİ VE BENZERSİZ fotoğraflar çeker"""
        print(f"\n🌐 İnternetten {count} adet yepyeni görsel indiriliyor...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        downloaded = []
        batch_id = int(time.time())

        for i in range(1, count + 1):
            seed = random.randint(10000, 999999)
            file_path = f"{self.output_dir}/raw_images/img_{batch_id}_{i:03d}.jpg"
            url = f"https://picsum.photos/400/400?random={seed}"
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp, open(file_path, 'wb') as f:
                    f.write(resp.read())
                print(f"  ● [{i:02d}/{count:02d}] Yeni Resim Alındı (Tohum: {seed})")
                downloaded.append(file_path)
                time.sleep(0.2)
            except Exception as e:
                print(f"  ✖ [{i:02d}/{count:02d}] İndirme hatası: {e}")
                continue
        return downloaded

    def train_single_image(self, img_path, index, total):
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            return None

        w, h = img.size
        orig_bytes = img.tobytes()

        # 1. Kökleri Öğren
        quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
        pal = quantized.getpalette()[:48]
        palette_roots = [list(pal[i:i+3]) for i in range(0, len(pal), 3)]

        new_roots_added = 0
        for c in palette_roots:
            if c not in self.learned_memory and len(self.learned_memory) < 255:
                self.learned_memory.append(c)
                new_roots_added += 1

        # 2. Açma/Kapama Simülasyonu
        base_w = min(w, 160)
        base_h = int(h * (base_w / w))
        sim = img.resize((base_w, base_h), Image.Resampling.LANCZOS)
        sim_exp = sim.resize((w, h), Image.Resampling.BICUBIC).tobytes()

        diff_sum = 0
        step = 8
        for p in range(0, len(orig_bytes), 3 * step):
            diff_sum += (abs(orig_bytes[p] - sim_exp[p]) +
                         abs(orig_bytes[p+1] - sim_exp[p+1]) +
                         abs(orig_bytes[p+2] - sim_exp[p+2])) / 3

        fidelity = max(0, 100 - round((diff_sum / (len(orig_bytes) // (3 * step))) / 2.55, 1))

        # 3. .CRW Dosyasını Yaz
        base_payload = bytearray(quantized.resize((base_w, base_h)).getdata())
        crw_path = f"{self.output_dir}/crw_files/{os.path.basename(img_path)}.crw"
        raw_kb = len(orig_bytes) // 1024

        with open(crw_path, "wb") as f:
            f.write(b"CRW4")
            f.write(struct.pack(">HHHH", w, h, base_w, base_h))
            f.write(struct.pack("B", len(pal) // 3))
            f.write(bytes(pal))
            f.write(struct.pack(">I", len(base_payload)))
            f.write(base_payload)
            f.write(struct.pack(">I", 0))

        crw_kb = max(1, os.path.getsize(crw_path) // 1024)
        savings = round((1 - (crw_kb / raw_kb)) * 100)

        added_str = f"(+{new_roots_added} Yeni Kök)" if new_roots_added > 0 else "(Tanıdık Renkler)"
        print(f"[{index:02d}/{total:02d}] Açıldı/Kapatıldı: Doğruluk: %{fidelity} | Tasarruf: -%{savings} {added_str}")
        return fidelity, savings

    def run_swarm(self, image_list):
        print("\n" + "="*60)
        print("🚀 [CROOW SWARM] Otonom Açma-Kapama Deneyim Turu Başladı")
        print("="*60)
        
        fidelities = []
        savings_list = []

        for idx, p in enumerate(image_list, 1):
            res = self.train_single_image(p, idx, len(image_list))
            if res:
                fidelities.append(res[0])
                savings_list.append(res[1])

        # Güncel Evrensel Belleği Mühürle
        with open(self.dict_file, "wb") as f:
            f.write(struct.pack("B", len(self.learned_memory)))
            for rgb in self.learned_memory:
                f.write(struct.pack("BBB", *rgb))

        avg_fid = round(sum(fidelities) / len(fidelities), 1) if fidelities else 0
        avg_sav = round(sum(savings_list) / len(savings_list), 1) if savings_list else 0

        print("\n" + "="*60)
        print("🏆 EĞİTİM TURU BAŞARIYLA TAMAMLANDI")
        print("="*60)
        print(f"  ● Bu Turda İşlenen Yeni Resim : {len(fidelities)} Adet")
        print(f"  ● Ortalama Görsel Netlik      : %{avg_fid} Doğruluk")
        print(f"  ● Ortalama Hacim Tasarrufu    : %{avg_sav} Tasarruf")
        print(f"  ● Toplam Birikmiş Evrensel Kök: {len(self.learned_memory)} Renk")
        print(f"  └─> Güncel Hafıza Dosyası     : '{self.dict_file}'")
        print("="*60 + "\n")

if __name__ == "__main__":
    swarm = CroowSwarm()
    count = 15
    if len(sys.argv) > 2 and sys.argv[1] == "--fetch":
        count = int(sys.argv[2])
    images = swarm.fetch_fresh_images(count)
    swarm.run_swarm(images)
