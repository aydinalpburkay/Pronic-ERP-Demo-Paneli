import sqlite3
import os
from datetime import date 

# Veritabanı dosyasının adı
VERITABANI_ADI = "staj_erp.db"

def veritabanina_baglan():
    """Veritabanına bağlanır ve bağlantı (conn) ile cursor (cur) nesnelerini döndürür."""
    conn = sqlite3.connect(VERITABANI_ADI, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    cur = conn.cursor()
    return conn, cur

#  Yardımcı Fonksiyonlar

def yardimci_musteri_listele():
    """Yeni satış eklerken kullanıcıya yardımcı olmak için müşterileri listeler."""
    print("\n--- Sistemdeki Müşteriler ---")
    conn, cur = veritabanina_baglan()
    cur.execute("SELECT MusteriKodu, FirmaUnvani FROM Cari_Kartlar ORDER BY FirmaUnvani")
    musteriler = cur.fetchall()
    conn.close()
    for m in musteriler:
        print(f"  [{m['MusteriKodu']}] - {m['FirmaUnvani']}")
    print("-" * 30)

def yardimci_urun_listele():
    """Yeni satış eklerken kullanıcıya yardımcı olmak için ürünleri listeler."""
    print("\n--- Sistemdeki Ürünler ---")
    conn, cur = veritabanina_baglan()
    cur.execute("SELECT UrunKodu, UrunAdi, BirimFiyati FROM Urun_Kartlari ORDER BY UrunAdi")
    urunler = cur.fetchall()
    conn.close()
    for u in urunler:
        print(f"  [{u['UrunKodu']}] - {u['UrunAdi']} ({u['BirimFiyati']} TL)")
    print("-" * 30)

# Ana Fonksiyonlar

def rapor_musteri_bazli_kar():
    """Müşteri Bazlı Kârlılık Raporu (JOIN sorgusu)"""
    print("\n--- MÜŞTERİ BAZLI KÂRLILIK RAPORU ---")
    
    conn, cur = veritabanina_baglan()

    sql_sorgusu = """
    SELECT 
        T_CARI.FirmaUnvani,
        SUM(T_SATIS.Tutar) AS ToplamCiro,
        SUM(T_URUN.MaliyetFiyati * T_SATIS.SatisMiktari) AS ToplamMaliyet,
        SUM(T_SATIS.Tutar) - SUM(T_URUN.MaliyetFiyati * T_SATIS.SatisMiktari) AS ToplamKar,
        
        CASE 
            WHEN SUM(T_SATIS.Tutar) = 0 THEN 0
            ELSE (SUM(T_SATIS.Tutar) - SUM(T_URUN.MaliyetFiyati * T_SATIS.SatisMiktari)) * 100.0 / SUM(T_SATIS.Tutar)
        END AS KarMarjiYuzde
        
    FROM 
        Satis_Hareketleri AS T_SATIS
    JOIN 
        Cari_Kartlar AS T_CARI ON T_SATIS.MusteriKodu = T_CARI.MusteriKodu
    JOIN 
        Urun_Kartlari AS T_URUN ON T_SATIS.UrunKodu = T_URUN.UrunKodu
    GROUP BY 
        T_CARI.FirmaUnvani
    ORDER BY 
        ToplamKar DESC
    """
    
    cur.execute(sql_sorgusu)
    sonuclar = cur.fetchall()
    conn.close() 

    if not sonuclar:
        print("Gösterilecek satış kaydı bulunamadı.")
        return

    print(f"{'Firma Ünvanı':<35} | {'Toplam Ciro (TL)':<20} | {'Toplam Kâr (TL)':<20} | {'Kâr Marjı (%)':<15}")
    print("-" * 95)
    
    for satir in sonuclar:
        ciro_formatli = f"{round(satir['ToplamCiro'], 2):,.2f}"
        kar_formatli = f"{round(satir['ToplamKar'], 2):,.2f}"
        marj_formatli = f"{round(satir['KarMarjiYuzde'], 2):.2f}%"
        
        print(f"{satir['FirmaUnvani']:<35} | {ciro_formatli:<20} | {kar_formatli:<20} | {marj_formatli:<15}")
    
    print("-" * 95)
    print(f"Toplam {len(sonuclar)} adet müşteri listelendi.")


def rapor_stok_durumu():
    """Kritik Stok Durum Raporu"""
    print("\n--- KRİTİK STOK DURUM RAPORU ---")
    
    conn, cur = veritabanina_baglan()
    
    sql_sorgusu = """
    SELECT 
        UrunKodu,
        UrunAdi,
        MevcutStok,
        KritikStok,
        (MevcutStok - KritikStok) AS Fark
    FROM 
        Urun_Kartlari
    ORDER BY 
        Fark ASC
    """
    
    cur.execute(sql_sorgusu)
    sonuclar = cur.fetchall()
    conn.close()

    print(f"{'Durum':<7} | {'Ürün Kodu':<12} | {'Ürün Adı':<40} | {'Mevcut':<10} | {'Kritik':<10}")
    print("-" * 85)
    
    kritik_urun_sayisi = 0
    for satir in sonuclar:
        durum_isareti = ""
        if satir['Fark'] < 0:
            durum_isareti = "[!!!]" 
            kritik_urun_sayisi += 1
        elif satir['Fark'] < satir['KritikStok']:
            durum_isareti = "[ ! ]"
        else:
            durum_isareti = "[ OK ]"
            
        print(f"{durum_isareti:<7} | {satir['UrunKodu']:<12} | {satir['UrunAdi']:<40} | {satir['MevcutStok']:<10} | {satir['KritikStok']:<10}")

    print("-" * 85)
    print(f"Toplam {kritik_urun_sayisi} ürün kritik stok seviyesinin altındadır.")


# Veri Ekleme Fonksiyonları

def islem_yeni_satis_ekle():
    """Kullanıcıdan bilgi alarak yeni satış kaydı oluşturur (INSERT) ve stoğu günceller (UPDATE)."""
    print("\n--- YENİ SATİŞ KAYDI EKLEME ---")
    conn, cur = veritabanina_baglan()
    
    try:
        #  1- Müşteri bilgisini al ve doğrula kısmı
        yardimci_musteri_listele()
        musteri_kodu = input("Satış yapılacak Müşteri Kodu (örn: M-HAS01): ").strip().upper()
        
        cur.execute("SELECT FirmaUnvani FROM Cari_Kartlar WHERE MusteriKodu = ?", (musteri_kodu,))
        musteri = cur.fetchone()
        
        if not musteri:
            print(f"[HATA] '{musteri_kodu}' kodlu müşteri bulunamadı. İşlem iptal edildi.")
            conn.close()
            return
        
        print(f"Müşteri seçildi: {musteri['FirmaUnvani']}")

        #  2- Ürün bilgisini al ve doğrula kısmı
        yardimci_urun_listele()
        urun_kodu = input("Satılacak Ürün Kodu (örn: MBL-001): ").strip().upper()
        
        cur.execute("SELECT UrunAdi, BirimFiyati, MevcutStok FROM Urun_Kartlari WHERE UrunKodu = ?", (urun_kodu,))
        urun = cur.fetchone()
        
        if not urun:
            print(f"[HATA] '{urun_kodu}' kodlu ürün bulunamadı. İşlem iptal edildi.")
            conn.close()
            return
            
        print(f"Ürün seçildi: {urun['UrunAdi']} (Stok: {urun['MevcutStok']}, Fiyat: {urun['BirimFiyati']} TL)")

        #  3- Miktar bilgisini alma ve doğrulama kısmı
        while True:
            try:
                satis_miktari = float(input(f"Satış Miktarı (Adet/KG/Metre) (Mevcut Stok: {urun['MevcutStok']}): "))
                if satis_miktari <= 0:
                    print("[HATA] Miktar 0'dan büyük olmalıdır.")
                elif satis_miktari > urun['MevcutStok']:
                    print(f"[HATA] Yetersiz stok! En fazla {urun['MevcutStok']} adet satılabilir.")
                else:
                    break 
            except ValueError:
                print("[HATA] Lütfen sayısal bir değer girin.")

        #  4- Diğer bilgileri hazılrama kısmı
        cur.execute("SELECT MAX(SatisKodu) FROM Satis_Hareketleri")
        son_satis_kodu = cur.fetchone()[0] 
        son_id = int(son_satis_kodu.split('-')[1]) 
        yeni_satis_kodu = f"SAT-{son_id + 1}"
        
        bugunun_tarihi = date.today().strftime("%d.%m.%Y")
        tutar = urun['BirimFiyati'] * satis_miktari
        satis_kanali = "Konsol"
        odeme_durumu = "Ödendi"

        #  5- Onay kısmı
        print("\n--- SATIŞ ÖZETİ ---")
        print(f"  Tarih:         {bugunun_tarihi}")
        print(f"  Müşteri:       {musteri['FirmaUnvani']}")
        print(f"  Ürün:          {urun['UrunAdi']}")
        print(f"  Miktar:        {satis_miktari}")
        print(f"  TOPLAM TUTAR:  {tutar:,.2f} TL")
        print("-" * 20)
        
        onay = input(f"Satışı onaylıyor musunuz? (E/H): ").strip().upper()

        if onay == 'E':
            #  6- Veri tabanı işlemlerini yapma
            
            # 6a- Yeni satışı ekleme
            cur.execute("""
                INSERT INTO Satis_Hareketleri 
                (SatisKodu, Tarih, MusteriKodu, UrunKodu, SatisMiktari, SatisKanali, OdemeDurumu, Tutar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (yeni_satis_kodu, bugunun_tarihi, musteri_kodu, urun_kodu, satis_miktari, satis_kanali, odeme_durumu, tutar))
            
            # 6b- Stoğu güncelle
            yeni_stok = urun['MevcutStok'] - satis_miktari
            cur.execute("""
                UPDATE Urun_Kartlari 
                SET MevcutStok = ? 
                WHERE UrunKodu = ?
            """, (yeni_stok, urun_kodu))
            
            conn.commit()
            
            print(f"\n[BAŞARILI] {yeni_satis_kodu} kodlu satış kaydı oluşturuldu.")
            print(f"[BAŞARILI] {urun_kodu} kodlu ürünün stoğu {urun['MevcutStok']}'dan {yeni_stok}'a güncellendi.")
        
        else:
            print("\n[İPTAL] Satış işlemi iptal edildi.")

    except Exception as e:
        print(f"\n[HATA] Beklenmedik bir hata oluştu: {e}")
        conn.rollback() 
    finally:
        conn.close()

# Yeni eklenen fonksiyon kısmı
def islem_yeni_musteri_ekle():
    """Kullanıcıdan bilgi alarak 'Cari_Kartlar' tablosuna yeni müşteri ekler."""
    print("\n--- YENİ MÜŞTERİ KAYDI EKLEME ---")
    
    try:
        # Bilgileri al
        musteri_kodu = input("Yeni Müşteri Kodu (Benzersiz olmalı, örn: M-TEST01): ").strip().upper()
        if not musteri_kodu:
            print("[HATA] Müşteri Kodu boş bırakılamaz.")
            return

        firma_unvani = input("Firma Ünvanı: ").strip()
        if not firma_unvani:
            print("[HATA] Firma Ünvanı boş bırakılamaz.")
            return

        sehir = input("Şehir (örn: Ankara): ").strip().capitalize()
        sektor = input("Sektör (örn: Tekstil): ").strip().capitalize()

        conn, cur = veritabanina_baglan()

        #  DOĞRULAMA: Bu kod zaten var mı? sorgusu 
        cur.execute("SELECT FirmaUnvani FROM Cari_Kartlar WHERE MusteriKodu = ?", (musteri_kodu,))
        mevcut_musteri = cur.fetchone()
        
        if mevcut_musteri:
            print(f"\n[HATA] '{musteri_kodu}' kodlu müşteri zaten sistemde mevcut: ({mevcut_musteri['FirmaUnvani']})")
            print("İşlem iptal edildi.")
            conn.close()
            return

        # Kayıt işlemi
        cur.execute("""
            INSERT INTO Cari_Kartlar (MusteriKodu, FirmaUnvani, Sehir, Sektor)
            VALUES (?, ?, ?, ?)
        """, (musteri_kodu, firma_unvani, sehir, sektor))
        
        conn.commit() 
        conn.close()
        
        print(f"\n[BAŞARILI] Müşteri başarıyla eklendi:")
        print(f"  Kod:    {musteri_kodu}")
        print(f"  Ünvan:  {firma_unvani}")
        print(f"  Şehir:  {sehir}")
        print(f"  Sektör: {sektor}")

    except Exception as e:
        print(f"\n[HATA] Kayıt sırasında bir hata oluştu: {e}")
        conn.rollback()
        conn.close()


def ana_menu_goster():
    """Kullanıcıya ana menüyü gösterir ve seçimini alır."""
    
    print("\n" + "="*40)
    print("  PRONIC MİNİ-ERP KONSOL UYGULAMASI")
    print("="*40)
    print("\nLütfen yapmak istediğiniz işlemi seçin:\n")
    print("  [1] Müşteri Bazlı Kârlılık Raporu")
    print("  [2] Kritik Stok Durum Raporu")
    print("  [3] Yeni Satış Kaydı Ekle")
    print("  [4] Yeni Müşteri Ekle") 
    print("\n  [Q] Çıkış Yap")
    
    return input("\nSeçiminiz (1-4 veya Q): ").strip().upper()


# Ana uygulama döngüsü
def main():
    """
    Ana fonksiyon. Kullanıcı 'Q' tuşuna basana kadar
    sürekli olarak menüyü gösterir ve ilgili fonksiyonu çağırır.
    """
    # Uygulama başlarken veritabanı dosyasının varlığını kontrol etme
    if not os.path.exists(VERITABANI_ADI):
        print(f"[HATA] Veritabanı dosyası '{VERITABANI_ADI}' bulunamadı!")
        print("Lütfen önce 'python kurulum.py' script'ini çalıştırdığınızdan emin olun.")
        return 

    while True:
        secim = ana_menu_goster()
        
        if secim == '1':
            rapor_musteri_bazli_kar()
        
        elif secim == '2':
            rapor_stok_durumu()
            
        elif secim == '3':
            islem_yeni_satis_ekle()
            
        elif secim == '4':
            islem_yeni_musteri_ekle() # Yeni fonksiyonu buraya bağladım

        elif secim == 'Q':
            print("\nHoşçakalın! Pronic Mini-ERP kapatılıyor...")
            break 
            
        else:
            print(f"\n[HATA] Geçersiz seçim: '{secim}'. Lütfen menüden bir değer seçin.")
        
        input("\n--- Devam etmek için Enter'a basın ---")



if __name__ == "__main__":
    main()