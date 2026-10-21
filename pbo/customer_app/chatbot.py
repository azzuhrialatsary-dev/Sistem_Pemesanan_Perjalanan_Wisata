"""
Logika chatbot TravelHub.

- Jika environment variable GEMINI_API_KEY terisi -> jawaban dari Google Gemini (AI).
- Jika kosong / API gagal -> fallback sederhana berbasis data paket di database,
  jadi chatbot tetap bekerja.
"""
import os
import re
import google.generativeai as genai

from django.utils import timezone
from .models import Paket

MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')
WA_ADMIN = '+62 812 0000 0000'

GREETING = ("Halo! Selamat datang di TravelHub. Ada yang bisa saya bantu "
            "untuk rencana liburan Anda hari ini?")

SYSTEM_PROMPT = """# ROLE & IDENTITY
Kamu adalah AI customer service resmi untuk TravelHub. Tugasmu adalah menjawab
pertanyaan pengunjung website mengenai paket wisata, memberikan rekomendasi
destinasi, dan membantu proses pemesanan.

# ATURAN & GAYA BAHASA
1. Gunakan bahasa Indonesia yang sopan, ramah, dan komunikatif.
2. Jawab pertanyaan secara singkat, jelas, dan langsung ke inti masalah.
3. Fokus hanya pada topik seputar liburan, destinasi, harga, fasilitas, dan pemesanan di TravelHub.
4. Jika pertanyaan di luar topik pariwisata, alihkan kembali ke layanan TravelHub dengan sopan.
5. Jika ada permintaan paket custom atau komplain, minta kontak pengguna (Nama & No. WhatsApp) agar bisa dihubungi oleh tim CS/Sales.

# CARA MERESPONS
- Rekomendasi Paket: Tanyakan tujuan, jumlah peserta, durasi, atau anggaran jika pengguna masih bingung.
- Detail Paket: Sebutkan harga, durasi, fasilitas utama (termasuk/tidak termasuk), dan ringkasan destinasi.
- Pemesanan: Pandu pengguna untuk mengisi form pemesanan di website (buka halaman paket, pilih jadwal, lalu klik pesan) atau hubungi WhatsApp admin {wa}.

# ATURAN TAMBAHAN
- Hanya gunakan data paket di bawah ini. Jangan mengarang paket, harga, atau jadwal yang tidak ada.
- Jangan gunakan format markdown berat (tanpa tabel/heading); boleh daftar bernomor atau tanda "-" sederhana.

# DATA PAKET TRAVELHUB SAAT INI (tanggal {today})
{paket}
"""


def rupiah(n):
    return f"Rp {n:,.0f}".replace(',', '.')


def _paket_queryset():
    return Paket.objects.prefetch_related('jadwal').all()


def konteks_paket():
    hari_ini = timezone.localdate()
    baris = []
    for p in _paket_queryset():
        jadwal = [j for j in p.jadwal.all()
                  if j.tanggal_berangkat >= hari_ini and j.kuota_tersisa > 0]
        jadwal.sort(key=lambda j: j.tanggal_berangkat)
        jd = ', '.join(f"{j.tanggal_berangkat:%d-%m-%Y} (sisa {j.kuota_tersisa} kursi)"
                       for j in jadwal[:4]) or 'belum ada jadwal tersedia'
        fas = '; '.join(p.daftar_fasilitas()) or '-'
        baris.append(
            f"- {p.nama} | destinasi: {p.destinasi} | kategori: {p.get_kategori_display()} | "
            f"harga: {rupiah(p.harga)}/orang | durasi: {p.durasi_hari} hari | rating: {p.rating} | "
            f"fasilitas: {fas} | meeting point: {p.meeting_point or '-'} | "
            f"jadwal: {jd} | deskripsi: {p.deskripsi[:200]}"
        )
    return '\n'.join(baris) or '(belum ada paket)'


def _bersihkan_riwayat(riwayat):
    """Ambil maksimal 12 pesan terakhir, pastikan format & urutan valid untuk API."""
    hasil = []
    for m in (riwayat or [])[-12:]:
        role = m.get('role')
        teks = str(m.get('content', '')).strip()[:1000]
        if role in ('user', 'assistant') and teks:
            hasil.append({'role': role, 'content': teks})
    while hasil and hasil[0]['role'] != 'user':
        hasil.pop(0)
    # gabungkan pesan berurutan dengan role sama
    rapi = []
    for m in hasil:
        if rapi and rapi[-1]['role'] == m['role']:
            rapi[-1]['content'] += '\n' + m['content']
        else:
            rapi.append(m)
    return rapi


def jawab_ai(riwayat):
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    pesan = _bersihkan_riwayat(riwayat)
    if not api_key or not pesan or pesan[-1]['role'] != 'user':
        return None

    try:
        # Konfigurasi API key langsung menggunakan library resmi
        genai.configure(api_key=api_key)
        
        system_instruction = SYSTEM_PROMPT.format(
            wa=WA_ADMIN, today=timezone.localdate().strftime('%d-%m-%Y'), paket=konteks_paket()
        )
        
        # Inisialisasi model
        model = genai.GenerativeModel(
            model_name=MODEL,
            system_instruction=system_instruction,
            generation_config=genai.GenerationConfig(
                max_output_tokens=1024,
                temperature=0.7,
            )
        )
        
        # Format riwayat pesan untuk dikonsumsi oleh SDK
        formatted_contents = []
        for m in pesan:
            role = 'user' if m['role'] == 'user' else 'model' # SDK menggunakan 'user' dan 'model'
            formatted_contents.append({'role': role, 'parts': [m['content']]})
            
        # Eksekusi generasi konten
        response = model.generate_content(formatted_contents)
        return response.text.strip() or None
        
    except Exception as e:
        print(f"[chatbot] Gemini gagal memproses request: {e!r}")
        return None


# ---------------------------------------------------------
# Fallback sederhana (tanpa AI)
# ---------------------------------------------------------
def _ringkas(p):
    return f"{p.nama} ({p.destinasi}) - {p.durasi_hari} hari, {rupiah(p.harga)}/orang"


def jawab_fallback(teks):
    t = teks.lower()
    semua = list(_paket_queryset())

    if re.search(r'\b(halo|hai|hi|hello|selamat (pagi|siang|sore|malam))\b', t):
        return GREETING

    if re.search(r'custom|komplain|keluhan|refund|batal|kecewa|complain', t):
        return ("Baik, untuk permintaan paket custom atau komplain, tim CS/Sales kami akan membantu langsung. "
                f"Mohon kirimkan Nama dan No. WhatsApp Anda, atau hubungi admin di {WA_ADMIN}.")

    if re.search(r'pesan|booking|book|daftar|reservasi|bayar', t):
        return ("Untuk memesan: buka halaman Paket Wisata, pilih paket dan jadwal, lalu klik tombol pesan "
                f"dan isi form pemesanan. Atau hubungi WhatsApp admin di {WA_ADMIN}.")

    # cocokkan nama paket / destinasi / kategori
    cocok = [p for p in semua
             if p.nama.lower() in t or p.destinasi.lower() in t
             or any(k and k in t for k in re.split(r'[\s,/-]+', p.destinasi.lower()) if len(k) > 3)]
    if cocok and re.search(r'detail|fasilitas|include|termasuk|harga|biaya|berapa|durasi|jadwal|info|tentang', t):
        p = cocok[0]
        fas = ', '.join(p.daftar_fasilitas()[:6]) or 'hubungi admin untuk rincian'
        jadwal = [j for j in p.jadwal.all() if j.tanggal_berangkat >= timezone.localdate() and j.kuota_tersisa > 0]
        jadwal.sort(key=lambda j: j.tanggal_berangkat)
        jd = ', '.join(f"{j.tanggal_berangkat:%d-%m-%Y}" for j in jadwal[:3]) or 'belum ada jadwal'
        return (f"{p.nama} - {p.destinasi}. Harga {rupiah(p.harga)}/orang, durasi {p.durasi_hari} hari. "
                f"Fasilitas: {fas}. Jadwal terdekat: {jd}. Ingin saya bantu cara pemesanannya?")

    # filter kategori
    for kode, label in Paket.KATEGORI_CHOICES:
        if kode in t:
            hasil = [p for p in semua if p.kategori == kode][:4]
            if hasil:
                return f"Paket {label} yang tersedia:\n" + '\n'.join(f"- {_ringkas(p)}" for p in hasil)

    # anggaran
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(juta|jt|ribu|rb|k)\b', t)
    if m:
        angka = float(m.group(1).replace(',', '.'))
        mult = {'juta': 1_000_000, 'jt': 1_000_000, 'ribu': 1_000, 'rb': 1_000, 'k': 1_000}[m.group(2)]
        budget = angka * mult
        hasil = sorted([p for p in semua if p.harga <= budget], key=lambda p: -p.rating)[:4]
        if hasil:
            return (f"Paket dengan harga hingga {rupiah(budget)} per orang:\n"
                    + '\n'.join(f"- {_ringkas(p)}" for p in hasil))
        return "Mohon maaf, belum ada paket dalam anggaran tersebut. Boleh saya tahu anggaran lain atau tujuan yang diinginkan?"

    if re.search(r'rekomendasi|paket|wisata|liburan|destinasi|trip|tour|murah|populer|favorit', t):
        top = sorted(semua, key=lambda p: -p.rating)[:4]
        if top:
            return ("Beberapa paket populer kami:\n" + '\n'.join(f"- {_ringkas(p)}" for p in top)
                    + "\n\nBoleh tahu tujuan, jumlah peserta, durasi, atau anggaran Anda agar rekomendasinya lebih pas?")

    return ("Maaf, saya hanya bisa membantu seputar liburan, destinasi, harga, fasilitas, dan pemesanan di TravelHub. "
            "Ada rencana liburan yang ingin dibahas?")


def balas(riwayat):
    riwayat = riwayat or []
    teks_terakhir = next((m.get('content', '') for m in reversed(riwayat) if m.get('role') == 'user'), '')
    jawaban = jawab_ai(riwayat)
    return jawaban or jawab_fallback(str(teks_terakhir))