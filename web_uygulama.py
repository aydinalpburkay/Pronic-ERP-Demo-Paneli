from flask import Flask, g, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
from datetime import date
from functools import wraps
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

VERITABANI_ADI = "staj_erp.db"
GRAFIK_DOSYA_YOLU = os.path.join('static', 'images', 'profit_chart.png')
app = Flask(__name__)
app.secret_key = 'benim_cok_gizli_anahtarim_123'
UYUMLULUK_KURALLARI={"metal":["Metal İşleme","Bağlantı Elemanı","Makine Parçası","İnşaat Malzemesi","Ambalaj"],"mobilya":["Mobilya Aksesuar","Mobilya Sarf","Bağlantı Elemanı","Ambalaj"],"enerji":["Enerji Malzemesi","Polimer","İzolasyon","Enerji Depolama","Bağlantı Elemanı","Ambalaj"],"dayanıklı tüketim":["Metal İşleme","Polimer","Bağlantı Elemanı","Ambalaj"],"bilişim":["Yazılım","Bilişim","Enerji Depolama","Ambalaj"],"imalat":["Metal İşleme","Makine Parçası","Bağlantı Elemanı","Polimer","İnşaat Malzemesi","Ambalaj"],"yazılım":["Yazılım","Bilişim","Enerji Depolama","Ambalaj"],"elektronik":["Elektronik","Bağlantı Elemanı","Polimer","Ambalaj","Bilişim","Enerji Depolama","Yazılım"],None:["Ambalaj","Bağlantı Elemanı"]}
BILINEN_URUN_TURLERI = set(); [BILINEN_URUN_TURLERI.update(tur_listesi) for tur_listesi in UYUMLULUK_KURALLARI.values()]
SABIT_PAROLA = "pronic123"

# Sektör İkon Sözlüğü 
SEKTOR_IKONLARI = {
    "metal": "fas fa-industry",       
    "mobilya": "fas fa-chair",       
    "enerji": "fas fa-bolt",            
    "dayanıklı tüketim": "fas fa-box-open", 
    "bilişim": "fas fa-laptop-code",    
    "imalat": "fas fa-cogs",            
    "yazılım": "fas fa-code",           
    "elektronik": "fas fa-microchip",     
    "varsayilan": "fas fa-briefcase"    
}


@app.template_filter('tr_para')
def format_tr_para(value):
    try: s = f"{float(value):,.2f}"; return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError): return value

@app.template_filter('sektor_ikonu')
def get_sektor_ikonu(sektor_adi):
    if not sektor_adi: return SEKTOR_IKONLARI["varsayilan"]
    ikon = SEKTOR_IKONLARI.get(sektor_adi.lower(), SEKTOR_IKONLARI["varsayilan"])
    return ikon

def get_db():
    db = getattr(g, '_database', None)
    if db is None: db = g._database = sqlite3.connect(VERITABANI_ADI); db.row_factory = sqlite3.Row
    return db
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'giris_yapildi' not in session: flash("Bu sayfayı görüntülemek için lütfen giriş yapın.", "error"); return redirect(url_for('login_sayfasi_GET'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/login', methods=['GET'])
def login_sayfasi_GET():
    if 'giris_yapildi' in session: return redirect(url_for('ana_sayfa'))
    return render_template('login.html')
@app.route('/login-kontrol', methods=['POST'])
def login_kontrol_POST():
    if request.form['parola'] == SABIT_PAROLA: session['giris_yapildi'] = True; flash("Başarıyla giriş yaptınız!", "success"); return redirect(url_for('ana_sayfa'))
    else: flash("Hatalı parola girdiniz!", "error"); return redirect(url_for('login_sayfasi_GET'))
@app.route('/logout')
def logout(): session.pop('giris_yapildi', None); flash("Başarıyla çıkış yaptınız.", "success"); return redirect(url_for('login_sayfasi_GET'))

def generate_profit_chart():
    try:
        conn = sqlite3.connect(VERITABANI_ADI); conn.row_factory = sqlite3.Row; cur = conn.cursor()
        sql_sorgusu = "SELECT T_CARI.FirmaUnvani, SUM(T_SATIS.Tutar) - SUM(T_URUN.MaliyetFiyati * T_SATIS.SatisMiktari) AS ToplamKar FROM Satis_Hareketleri AS T_SATIS JOIN Cari_Kartlar AS T_CARI ON T_SATIS.MusteriKodu = T_CARI.MusteriKodu JOIN Urun_Kartlari AS T_URUN ON T_SATIS.UrunKodu = T_URUN.UrunKodu WHERE T_CARI.AktifMi = 1 GROUP BY T_CARI.FirmaUnvani HAVING ToplamKar > 0 ORDER BY ToplamKar DESC LIMIT 10"
        cur.execute(sql_sorgusu); data = cur.fetchall(); conn.close()
        if not data: print("Kâr grafiği için yeterli veri bulunamadı."); return
        fig, ax = plt.subplots(figsize=(10, 6)); musteriler = [row['FirmaUnvani'][:25] + '...' if len(row['FirmaUnvani']) > 25 else row['FirmaUnvani'] for row in reversed(data)]; karlar = [row['ToplamKar'] for row in reversed(data)]; bars = ax.barh(musteriler, karlar, color='#2ecc71'); ax.set_xlabel('Toplam Kâr (TL)'); ax.set_title('Müşteri Bazlı Toplam Kâr (Top 10)'); ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ','))); ax.grid(axis='x', linestyle='--', color='#cccccc', alpha=0.7); ax.set_facecolor('#f9f9f9'); fig.set_facecolor('#ffffff'); fig.subplots_adjust(left=0.3); max_kar = max(karlar); ax.set_xlim(right=max_kar * 1.18)
        for bar in bars: ax.text(bar.get_width() + (max_kar * 0.01), bar.get_y() + bar.get_height()/2., f"{int(bar.get_width()):,}", va='center', ha='left', fontsize=9)
        os.makedirs(os.path.dirname(GRAFIK_DOSYA_YOLU), exist_ok=True); fig.savefig(GRAFIK_DOSYA_YOLU); plt.close(fig)
        print(f"Kâr grafiği '{GRAFIK_DOSYA_YOLU}' olarak (iyileştirilmiş) kaydedildi.")
    except Exception as e: print(f"Kâr grafiği oluşturulurken hata oluştu: {e}")

@app.route('/')
@login_required
def ana_sayfa():
    cur = get_db().cursor()
    try:
        generate_profit_chart()
        cur.execute("SELECT COUNT(*) FROM Cari_Kartlar WHERE AktifMi = 1"); aktif_musteri_sayisi = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM Urun_Kartlari"); toplam_urun_sayisi = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM Satis_Hareketleri"); toplam_satis_sayisi = cur.fetchone()[0]
        bugunun_tarihi = date.today().strftime("%d.%m.%Y"); grafik_url = None
        if os.path.exists(GRAFIK_DOSYA_YOLU): timestamp = int(time.time()); grafik_url = f"{url_for('static', filename='images/profit_chart.png')}?t={timestamp}"
        dashboard_verileri = {'musteri_sayisi': aktif_musteri_sayisi,'urun_sayisi': toplam_urun_sayisi,'satis_sayisi': toplam_satis_sayisi,'tarih': bugunun_tarihi,'grafik_url': grafik_url}
        return render_template('ana_sayfa.html', dashboard=dashboard_verileri)
    except Exception as e: flash(f"Dashboard verileri alınırken veya grafik oluşturulurken hata oluştu: {e}", "error"); return render_template('ana_sayfa.html', dashboard={'tarih': date.today().strftime("%d.%m.%Y"), 'grafik_url': None})

@app.route('/musteriler')
@login_required
def musteri_listesi_sayfasi():
    cur = get_db().cursor()
    cur.execute("SELECT MusteriKodu, FirmaUnvani, Sehir, Sektor, AktifMi FROM Cari_Kartlar ORDER BY FirmaUnvani")
    musteri_listesi = cur.fetchall()
    return render_template('musteri_listesi.html', musteriler=musteri_listesi)

@app.route('/musteri-durum-degistir/<string:musteri_kodu>', methods=['GET'])
@login_required
def musteri_durum_degistir(musteri_kodu):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("SELECT AktifMi FROM Cari_Kartlar WHERE MusteriKodu = ?", (musteri_kodu,)); musteri = cur.fetchone()
        if not musteri: flash(f"Hata: Durumu değiştirilecek müşteri bulunamadı ({musteri_kodu}).", "error")
        else:
            yeni_durum = 0 if musteri['AktifMi'] == 1 else 1
            cur.execute("UPDATE Cari_Kartlar SET AktifMi = ? WHERE MusteriKodu = ?", (yeni_durum, musteri_kodu)); conn.commit()
            durum_metni = "Pasif" if yeni_durum == 0 else "Aktif"; flash(f"Başarılı: '{musteri_kodu}' kodlu müşterinin durumu '{durum_metni}' olarak güncellendi.", "success")
    except Exception as e: conn.rollback(); flash(f"Durum değiştirilirken hata oluştu: {e}", "error")
    return redirect(url_for('musteri_listesi_sayfasi'))

@app.route('/stok-raporu')
@login_required
def stok_raporu_sayfasi():
    cur = get_db().cursor()
    cur.execute("SELECT UrunKodu, UrunAdi, MevcutStok, KritikStok, (MevcutStok - KritikStok) AS Fark, MaliyetFiyati, BirimFiyati FROM Urun_Kartlari ORDER BY Fark ASC")
    stok_verileri = cur.fetchall()
    return render_template('stok_raporu.html', urunler=stok_verileri)

@app.route('/stok-giris', methods=['GET'])
@login_required
def stok_giris_sayfasi_GET():
    cur = get_db().cursor()
    cur.execute("SELECT UrunKodu, UrunAdi, MevcutStok FROM Urun_Kartlari ORDER BY UrunAdi")
    urun_listesi = cur.fetchall()
    return render_template('stok_giris.html', urunler=urun_listesi)

@app.route('/kaydet-stok-giris', methods=['POST'])
@login_required
def stok_giris_kaydet_POST():
    conn = get_db(); cur = conn.cursor()
    try:
        urun_kodu = request.form['urun_kodu']; miktar_str = request.form['miktar']
        if not urun_kodu or not miktar_str: flash("Hata: Ürün ve Miktar alanları zorunludur!", "error"); return redirect(url_for('stok_giris_sayfasi_GET'))
        try: miktar = float(miktar_str); assert miktar > 0
        except: flash(f"Hata: Geçersiz miktar girişi ({miktar_str})", "error"); return redirect(url_for('stok_giris_sayfasi_GET'))
        cur.execute("UPDATE Urun_Kartlari SET MevcutStok = MevcutStok + ? WHERE UrunKodu = ?", (miktar, urun_kodu)); etkilenen_satir = cur.rowcount
        if etkilenen_satir == 0: flash(f"Hata: Stok güncellenemedi (Geçersiz ürün kodu: {urun_kodu}?)", "error"); conn.rollback(); return redirect(url_for('stok_giris_sayfasi_GET'))
        else: conn.commit(); flash(f"Başarılı: '{urun_kodu}' kodlu ürünün stoğuna {miktar} adet eklendi.", "success"); return redirect(url_for('stok_raporu_sayfasi'))
    except Exception as e: conn.rollback(); flash(f"Stok Girişi Sırasında Hata Oluştu: {e}", "error"); return redirect(url_for('stok_giris_sayfasi_GET'))

@app.route('/kar-raporu')
@login_required
def kar_raporu_sayfasi():
    cur = get_db().cursor()
    sql_sorgusu = "SELECT T_CARI.MusteriKodu, T_CARI.FirmaUnvani, T_CARI.Sektor, SUM(T_SATIS.Tutar) AS ToplamCiro, SUM(T_URUN.MaliyetFiyati * T_SATIS.SatisMiktari) AS ToplamMaliyet, SUM(T_SATIS.Tutar) - SUM(T_URUN.MaliyetFiyati * T_SATIS.SatisMiktari) AS ToplamKar, CASE WHEN SUM(T_SATIS.Tutar) = 0 THEN 0 ELSE (SUM(T_SATIS.Tutar) - SUM(T_URUN.MaliyetFiyati * T_SATIS.SatisMiktari)) * 100.0 / SUM(T_SATIS.Tutar) END AS KarMarjiYuzde FROM Satis_Hareketleri AS T_SATIS JOIN Cari_Kartlar AS T_CARI ON T_SATIS.MusteriKodu = T_CARI.MusteriKodu JOIN Urun_Kartlari AS T_URUN ON T_SATIS.UrunKodu = T_URUN.UrunKodu GROUP BY T_CARI.MusteriKodu, T_CARI.FirmaUnvani, T_CARI.Sektor ORDER BY ToplamKar DESC"
    cur.execute(sql_sorgusu); sonuclar = cur.fetchall()
    return render_template('kar_raporu.html', musteri_verileri=sonuclar)

@app.route('/satis-gecmisi')
@login_required
def satis_gecmisi_sayfasi():
    cur = get_db().cursor()
    sql_sorgusu = "SELECT T_SATIS.SatisKodu, T_SATIS.Tarih, T_CARI.FirmaUnvani, T_URUN.UrunAdi, T_SATIS.SatisMiktari, T_URUN.BirimFiyati, T_SATIS.Tutar, T_SATIS.SatisKanali, T_SATIS.OdemeDurumu FROM Satis_Hareketleri AS T_SATIS JOIN Cari_Kartlar AS T_CARI ON T_SATIS.MusteriKodu = T_CARI.MusteriKodu JOIN Urun_Kartlari AS T_URUN ON T_SATIS.UrunKodu = T_URUN.UrunKodu ORDER BY T_SATIS.SatisKodu DESC"
    cur.execute(sql_sorgusu); satis_listesi = cur.fetchall()
    return render_template('satis_gecmisi.html', satislar=satis_listesi)

@app.route('/satis-ekle', methods=['GET'])
@login_required
def satis_ekle_sayfasi_GET():
    cur = get_db().cursor()
    cur.execute("SELECT MusteriKodu, FirmaUnvani, Sehir FROM Cari_Kartlar WHERE AktifMi = 1 ORDER BY FirmaUnvani")
    musteri_listesi = cur.fetchall()
    cur.execute("SELECT UrunKodu, UrunAdi, MevcutStok, BirimFiyati FROM Urun_Kartlari WHERE MevcutStok > 0 ORDER BY UrunAdi")
    urun_listesi = cur.fetchall()
    return render_template('satis_ekle.html', musteriler=musteri_listesi, urunler=urun_listesi)

@app.route('/onayla-satis', methods=['POST'])
@login_required
def satis_onayla_POST():
    conn = get_db(); cur = conn.cursor()
    try:
        musteri_kodu=request.form['musteri_kodu']; urun_kodu=request.form['urun_kodu']; satis_miktari_str=request.form['satis_miktari']; odeme_durumu=request.form['odeme_durumu']
        if not all([musteri_kodu, urun_kodu, satis_miktari_str]): flash("Hata: Müşteri, Ürün ve Miktar alanları zorunludur!", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))
        try: satis_miktari = float(satis_miktari_str); assert satis_miktari > 0
        except: flash(f"Hata: Geçersiz miktar girişi ({satis_miktari_str})", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))
        cur.execute("SELECT FirmaUnvani, Sektor, AktifMi FROM Cari_Kartlar WHERE MusteriKodu = ?", (musteri_kodu,)); musteri = cur.fetchone()
        cur.execute("SELECT UrunAdi, UrunTuru, BirimFiyati, MevcutStok FROM Urun_Kartlari WHERE UrunKodu = ?", (urun_kodu,)); urun = cur.fetchone()
        if not musteri or not urun: flash("Hata: Geçersiz Müşteri veya Ürün Kodu!", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))
        if musteri['AktifMi'] != 1: flash(f"Hata: '{musteri['FirmaUnvani']}' pasif durumdadır. Pasif müşteriye satış yapılamaz!", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))
        musteri_sektor = musteri['Sektor'].lower() if musteri['Sektor'] else None; urun_turu = urun['UrunTuru'] if urun['UrunTuru'] else None; is_known_type = urun_turu in BILINEN_URUN_TURLERI
        if is_known_type: izin_verilen_turler = UYUMLULUK_KURALLARI.get(musteri_sektor, UYUMLULUK_KURALLARI.get(None, []));
        if is_known_type and urun_turu not in izin_verilen_turler: flash(f"Hata: '{musteri['Sektor']}' sektörü ile '{urun['UrunTuru']}' ürün türü uyumlu değil!", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))
        if satis_miktari > urun['MevcutStok']: flash(f"Hata: Yetersiz stok! ({urun_kodu} için en fazla {urun['MevcutStok']} adet)", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))
        tutar = urun['BirimFiyati'] * satis_miktari; bugunun_tarihi = date.today().strftime("%d.%m.%Y")
        satis_ozeti = {'tarih': bugunun_tarihi,'musteri_kodu': musteri_kodu,'musteri_unvani': musteri['FirmaUnvani'],'urun_kodu': urun_kodu,'urun_adi': urun['UrunAdi'],'miktar': satis_miktari,'birim_fiyat': urun['BirimFiyati'],'odeme_durumu': odeme_durumu,'tutar': tutar}
        return render_template('onayla_satis.html', satis_ozeti=satis_ozeti)
    except Exception as e: flash(f"Onay sayfası hazırlanırken hata oluştu: {e}", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))

@app.route('/gerceklestir-satis', methods=['POST'])
@login_required
def satis_gerceklestir_POST():
    conn = get_db(); cur = conn.cursor()
    try:
        musteri_kodu=request.form['musteri_kodu']; urun_kodu=request.form['urun_kodu']; satis_miktari=float(request.form['satis_miktari']); odeme_durumu=request.form['odeme_durumu']
        cur.execute("SELECT BirimFiyati, MevcutStok FROM Urun_Kartlari WHERE UrunKodu = ?", (urun_kodu,)); urun = cur.fetchone()
        if not urun or satis_miktari > urun['MevcutStok']: flash(f"HATA: Kayıt sırasında stok yetersiz kaldı veya ürün bulunamadı! İşlem iptal edildi.", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))
        cur.execute("SELECT MAX(SatisKodu) FROM Satis_Hareketleri"); son_satis_kodu = cur.fetchone()[0]; son_id = int(son_satis_kodu.split('-')[1]) if son_satis_kodu else 1000; yeni_satis_kodu = f"SAT-{son_id + 1}"
        bugunun_tarihi = date.today().strftime("%d.%m.%Y"); tutar = urun['BirimFiyati'] * satis_miktari; satis_kanali = "Web"
        cur.execute("INSERT INTO Satis_Hareketleri (SatisKodu, Tarih, MusteriKodu, UrunKodu, SatisMiktari, SatisKanali, OdemeDurumu, Tutar) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (yeni_satis_kodu, bugunun_tarihi, musteri_kodu, urun_kodu, satis_miktari, satis_kanali, odeme_durumu, tutar))
        yeni_stok = urun['MevcutStok'] - satis_miktari
        cur.execute("UPDATE Urun_Kartlari SET MevcutStok = ? WHERE UrunKodu = ?", (yeni_stok, urun_kodu)); conn.commit()
        flash(f"Başarılı: {yeni_satis_kodu} kodlu satış kaydı oluşturuldu. Stok güncellendi.", "success"); return redirect(url_for('stok_raporu_sayfasi'))
    except Exception as e: conn.rollback(); flash(f"Kayıt Sırasında Hata Oluştu: {e}", "error"); return redirect(url_for('satis_ekle_sayfasi_GET'))

@app.route('/musteri-ekle', methods=['GET'])
@login_required
def musteri_ekle_sayfasi_GET(): return render_template('yeni_musteri.html')

@app.route('/kaydet-musteri', methods=['POST'])
@login_required
def musteri_kaydet_POST():
    conn = get_db(); cur = conn.cursor()
    try:
        musteri_kodu=request.form['musteri_kodu'].strip().upper(); firma_unvani=request.form['firma_unvani'].strip(); sehir=request.form['sehir'].strip().capitalize(); sektor=request.form['sektor'].strip().capitalize()
        if not musteri_kodu or not firma_unvani: flash("Hata: Müşteri Kodu ve Firma Ünvanı zorunludur!", "error"); return redirect(url_for('musteri_ekle_sayfasi_GET'))
        cur.execute("SELECT FirmaUnvani FROM Cari_Kartlar WHERE MusteriKodu = ?", (musteri_kodu,)); mevcut_musteri = cur.fetchone()
        if mevcut_musteri: flash(f"Hata: '{musteri_kodu}' kodlu müşteri zaten sistemde mevcut ({mevcut_musteri['FirmaUnvani']}). Lütfen farklı bir kod deneyin.", "error"); return redirect(url_for('musteri_ekle_sayfasi_GET'))
        cur.execute("INSERT INTO Cari_Kartlar (MusteriKodu, FirmaUnvani, Sehir, Sektor, AktifMi) VALUES (?, ?, ?, ?, 1)", (musteri_kodu, firma_unvani, sehir, sektor)); conn.commit()
        flash(f"Başarılı: '{firma_unvani}' ({musteri_kodu}) müşterisi başarıyla eklendi.", "success"); return redirect(url_for('musteri_ekle_sayfasi_GET'))
    except Exception as e: conn.rollback(); flash(f"Müşteri Kaydı Sırasında Hata Oluştu: {e}", "error"); return redirect(url_for('musteri_ekle_sayfasi_GET'))

@app.route('/urun-ekle', methods=['GET'])
@login_required
def urun_ekle_sayfasi_GET(): return render_template('yeni_urun.html')

@app.route('/kaydet-urun', methods=['POST'])
@login_required
def urun_kaydet_POST():
    conn = get_db(); cur = conn.cursor()
    try:
        urun_kodu=request.form['urun_kodu'].strip().upper(); urun_adi=request.form['urun_adi'].strip(); urun_turu=request.form['urun_turu'].strip().capitalize()
        maliyet_str=request.form['maliyet_fiyati']; birim_str=request.form['birim_fiyati']; stok_str=request.form['mevcut_stok']; kritik_str=request.form['kritik_stok']
        if not all([urun_kodu, urun_adi, maliyet_str, birim_str, stok_str, kritik_str]): flash("Hata: Tüm alanların doldurulması zorunludur!", "error"); return redirect(url_for('urun_ekle_sayfasi_GET'))
        try:
            maliyet=float(maliyet_str); birim=float(birim_str); stok=int(stok_str); kritik=int(kritik_str)
            if maliyet<0 or birim<0 or stok<0 or kritik<0: raise ValueError("Sayısal değerler negatif olamaz.")
            if maliyet>birim: flash("Uyarı: Maliyet fiyatı, birim (satış) fiyatından büyük!", "error"); return redirect(url_for('urun_ekle_sayfasi_GET'))
        except ValueError as e: flash(f"Hata: Geçersiz sayısal giriş ({e})", "error"); return redirect(url_for('urun_ekle_sayfasi_GET'))
        cur.execute("SELECT UrunAdi FROM Urun_Kartlari WHERE UrunKodu = ?", (urun_kodu,)); mevcut_urun = cur.fetchone()
        if mevcut_urun: flash(f"Hata: '{urun_kodu}' kodlu ürün zaten sistemde mevcut ({mevcut_urun['UrunAdi']}).", "error"); return redirect(url_for('urun_ekle_sayfasi_GET'))
        cur.execute("INSERT INTO Urun_Kartlari (UrunKodu, UrunAdi, UrunTuru, MaliyetFiyati, BirimFiyati, MevcutStok, KritikStok) VALUES (?, ?, ?, ?, ?, ?, ?)", (urun_kodu, urun_adi, urun_turu, maliyet, birim, stok, kritik)); conn.commit()
        flash(f"Başarılı: '{urun_adi}' ({urun_kodu}) ürünü başarıyla eklendi.", "success"); return redirect(url_for('urun_ekle_sayfasi_GET'))
    except Exception as e: conn.rollback(); flash(f"Ürün Kaydı Sırasında Hata Oluştu: {e}", "error"); return redirect(url_for('urun_ekle_sayfasi_GET'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)