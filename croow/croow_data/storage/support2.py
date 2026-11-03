import socket

HOST = '0.0.0.0' 
PORT = 8088  # Kendi seçtiğiniz port

def croow_baslat():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    
    print(f"[CROOW ÇEKİRDEK] Aktif. Port: {PORT}")
    print("[CROOW BEKLENİYOR] Mobil uç nokta (Termux) bağlantısı bekleniyor...\n")

    conn, addr = server_socket.accept()
    print(f"[CROOW BAĞLANTI] Uç nokta bağlandı: {addr[0]}")
    print("[CROOW] Canlı tünel aktif! Çıkmak için istemcinin kapatmasını bekleyin veya Ctrl+C yapın.\n")

    try:
        while True:
            # Tabletten gelen veriyi bekle
            data = conn.recv(4096)
            if not data:
                print("[CROOW] Bağlantı uç nokta tarafından kapatıldı.")
                break
            
            mesaj = data.decode('utf-8')
            print(f"[GELEN]: {mesaj}")
            
            # Eğer çıkış komutu geldiyse döngüyü bitir
            if mesaj.strip().lower() == 'cikis':
                print("[CROOW] Oturum sonlandırılıyor...")
                break
            
            # Bilgisayardan tablete anlık yanıt yazabilme imkanı (İsteğe bağlı)
            cevap = input("[BİLGİSAYAR CEVAP]: ")
            conn.sendall(cevap.encode('utf-8'))
            
    except Exception as e:
        print(f"[HATA]: {e}")
    finally:
        conn.close()
        print("[CROOW TÜNEL] Kapatıldı.")

if __name__ == "__main__":
    croow_baslat()
