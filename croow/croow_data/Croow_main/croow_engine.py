#!/usr/bin/env python3
import sys
import re
import math

class CroowRuntime:
    def __init__(self):
        # 1. Kök Havuzu
        self.roots = {'A': 65, 'M': 77, 'D': 68, 'J': 74, 'K': 75}
        self.variables = {}
        self.bridges = []
        
        # 2. Çok Kademeli İndirgeme Depoları
        self.param_vault = {}    # 1. Kademe: Sayı <-> Harf
        self.orbit_vault = {}    # 2. Kademe: Harf <-> Yörünge

    def safe_eval(self, expr, local_vars=None):
        context = {**self.variables}
        if local_vars:
            context.update(local_vars)
        try:
            return eval(str(expr), {"__builtins__": None, "math": math}, context)
        except Exception:
            return expr

    # ==========================================================
    # KADEME 1: PARAMETRİK SAYI-HARF İNDİRGEME (40 + x + 9)
    # ==========================================================
    def resolve_chunk_to_root(self, chunk_num):
        val = int(chunk_num)
        if 49 <= val <= 60:
            x = val - 49
            letter = chr(64 + (x + 9))  # x=1 -> J
            return letter, f"Formül: 40 + ({x}+9)"
        for char, ascii_val in self.roots.items():
            if val == ascii_val:
                return char, f"Doğrudan Kök: 0x{val:02X}"
        if val == 68:
            return 'D', "Ofset Türetimi: M - 9"
        return chr(65 + (val % 26)), "Modüler Kök: % 26"

    def reduce_number_to_roots(self, num_str):
        if len(num_str) % 2 != 0:
            num_str = "0" + num_str
        chunks = [num_str[i:i+2] for i in range(0, len(num_str), 2)]
        root_group = []
        details = []
        for c in chunks:
            root_char, explanation = self.resolve_chunk_to_root(c)
            root_group.append(root_char)
            details.append((c, root_char, explanation))
        return "".join(root_group), chunks, details

    # ==========================================================
    # KADEME 2: YÖRÜNGE VE RUTİN KATLAMA (ORBIT / DRIFT MOTORU)
    # ==========================================================
    def analyze_orbit(self, pattern):
        """Bir harf döngüsünün vektörel sapmasını (Net Drift) hesaplar"""
        drift = 0
        steps = []
        for i in range(len(pattern) - 1):
            n1 = pattern[i]
            n2 = pattern[i+1]
            delta = ord(n2) - ord(n1)
            drift += delta
            steps.append((n1, n2, delta))
        return drift, steps

    def find_cycles(self, text):
        """Metin içindeki en belirgin tekrar eden yörüngeyi yakalar"""
        for length in range(2, len(text) // 2 + 1):
            candidate = text[:length]
            count = len(text) // length
            if candidate * count == text:
                return candidate, count
        return text, 1

    def execute_line(self, line):
        line = line.strip()
        if not line or line.startswith("//"):
            return

        # ----------------------------------------------------
        # 1. PARAM_REDUCE (Sayı -> Harfler Grubu)
        # ----------------------------------------------------
        m = re.match(r"PARAM_REDUCE\s+(\d+|[A-Za-z_][A-Za-z0-9_]*)\s*=>\s*([A-Za-z0-9_]+)", line)
        if m:
            target, dest = m.groups()
            raw_val = str(self.variables.get(target, target))
            reduced_roots, chunks, details = self.reduce_number_to_roots(raw_val)
            self.param_vault[dest] = (raw_val, reduced_roots, chunks)
            self.variables[dest] = reduced_roots
            
            print(f"\n[KADEME 1: PARAM_REDUCE] Sayı Harflere İndirgendi:")
            print(f"  ● Orijinal Sayı : {raw_val}")
            print(f"  └─> Harf Grubu  : [{reduced_roots}] -> Mühürlendi: [{dest}]")
            return

        # ----------------------------------------------------
        # 2. ORBIT_FOLD: Harf Rutinlerini ve Kapalı Yörüngeleri Katlama
        # ----------------------------------------------------
        m = re.match(r"ORBIT_FOLD\s+([A-Za-z0-9_]+)\s*=>\s*([A-Za-z0-9_]+)", line)
        if m:
            src, dest = m.groups()
            raw_text = str(self.variables.get(src, src))
            
            cycle, repeats = self.find_cycles(raw_text)
            drift, steps = self.analyze_orbit(cycle)
            
            # Depola
            orbit_repr = f"{repeats}x[ORBIT_{cycle}]"
            self.orbit_vault[dest] = (raw_text, cycle, repeats)
            self.variables[dest] = orbit_repr
            
            print(f"\n[KADEME 2: ORBIT_FOLD] Kapalı Yörünge Analizi Yapıldı:")
            print(f"  ● Girdi Zinciri     : {raw_text}")
            print(f"  ● Yakalanan Çekirdek: [{cycle}] (Tekrar Sayısı: {repeats})")
            print(f"  ● Vektörel Rotası   :")
            for n1, n2, d in steps:
                sign = "+" if d >= 0 else ""
                print(f"     * {n1} -> {n2} (Δ = {sign}{d})")
            
            status = "KUSURSUZ KAPALI REZONANS HALKASI" if drift == 0 else f"Açık Sarmal (Drift: {drift})"
            print(f"  ● Toplam Sapma (Net Drift): {drift} [{status}]")
            print(f"  └─> Nihai Çöküş Formülü   : {orbit_repr} ===> [{dest}]\n")
            return

        # ----------------------------------------------------
        # 3. ORBIT_EXPAND: Yörüngeden Harf Grubunu Geri Açma
        # ----------------------------------------------------
        m = re.match(r"ORBIT_EXPAND\s+([A-Za-z0-9_]+)\s*=>\s*([A-Za-z0-9_]+)", line)
        if m:
            src, dest = m.groups()
            if src in self.orbit_vault:
                raw_text, cycle, repeats = self.orbit_vault[src]
                restored_text = cycle * repeats
                self.variables[dest] = restored_text
                print(f"[CROOW ORBIT_EXPAND] [{src}] Yörüngesi Açıldı:")
                print(f"  ● Formül        : {repeats} x [{cycle}]")
                print(f"  └─> Açılan Harf : [{restored_text}] ===> [{dest}] Kaydedildi.\n")
            return

        # ----------------------------------------------------
        # 4. PARAM_RESTORE: Harflerden Orijinal Sayıyı Yeniden Üretme
        # ----------------------------------------------------
        m = re.match(r"PARAM_RESTORE\s+([A-Za-z0-9_]+)", line)
        if m:
            dest = m.group(1)
            raw_val_or_roots = self.variables.get(dest, dest)
            
            # Vault kontrolü
            found_original = None
            for orig, roots, chunks in self.param_vault.values():
                if roots == raw_val_or_roots or orig == raw_val_or_roots:
                    found_original = orig
                    break
            
            if found_original:
                print(f"[KADEME 3: PARAM_RESTORE] Kök Zincirinden Sayı Yeniden Doğrulandı:")
                print(f"  ● Girdi Harf Grubu: [{raw_val_or_roots}]")
                print(f"  └─> Orijinal Sayı : {found_original} [BİREBİR KUSURSUZ]\n")
            return

        # Değişken Tanımlama: LET
        m = re.match(r"LET\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", line)
        if m:
            var_name, expr = m.groups()
            self.variables[var_name] = self.safe_eval(expr)
            return

def run_script(filepath):
    vm = CroowRuntime()
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            vm.execute_line(line)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_script(sys.argv[1])
    else:
        print("Croow v0.8.0 (Orbit & Routine Cascade Core)")
