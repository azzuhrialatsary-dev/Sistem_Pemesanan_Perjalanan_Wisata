from datetime import timedelta
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from customer_app.models import Paket, FotoPaket, Jadwal, Itinerary

# folder foto: pbo/customer_app/static/customer/img/
FOLDER_FOTO = Path(__file__).resolve().parents[2] / 'static' / 'customer' / 'img'
URUTAN_GALERI = ['hero.jpg', 'bali.jpg', 'bromo.jpg', 'komodo.jpg']

FASILITAS = "Hotel / homestay\nPemandu wisata\nMakan 3x sehari\nTransport lokal\nTiket masuk\nAsuransi perjalanan"

MEETING_POINT = {
    'Raja Ampat Island Hopping': 'Bandara Domine Eduard Osok, Sorong — 08.00 WIT',
    'Komodo Phinisi Sailing': 'Bandara Komodo, Labuan Bajo — 08.00 WITA',
    'Bali Ubud Cultural Escape': 'Bandara I Gusti Ngurah Rai, Denpasar — 09.00 WITA',
    'Ijen Blue Fire & Bromo': 'Bandara Juanda, Surabaya — 07.00 WIB',
    'Bromo Sunrise Adventure': 'Stasiun Probolinggo — 22.00 WIB',
    'Nusa Penida Day Trip': 'Pelabuhan Sanur, Denpasar — 07.00 WITA',
}

JUDUL_HARI = ['Kedatangan & Check-in', 'Eksplorasi Utama', 'Petualangan Alam',
            'Wisata Budaya & Kuliner', 'Kepulauan', 'Santai & Belanja Oleh-oleh']

# (nama, destinasi, kategori, harga, durasi, rating, ulasan, sisa kursi, file foto, deskripsi)
DATA_PAKET = [
    ('Raja Ampat Island Hopping', 'Papua Barat', 'pantai', 12500000, 5, 4.9, 128, 6, 'hero.jpg',
    'Snorkeling di surga bawah laut dunia, menginap di homestay atas air. Termasuk akomodasi, '
    'transportasi lokal, makan sesuai itinerary, dan pemandu berlisensi.'),
    ('Komodo Phinisi Sailing', 'NTT', 'pantai', 8900000, 4, 4.9, 96, 10, 'komodo.jpg',
    'Berlayar dengan kapal phinisi mengelilingi Pulau Komodo, Padar, dan Pink Beach.'),
    ('Bali Ubud Cultural Escape', 'Bali', 'budaya', 4750000, 4, 4.8, 112, 16, 'bali.jpg',
    'Menyelami budaya Bali: sawah terasering, pura, kelas tari, dan kuliner khas Ubud.'),
    ('Ijen Blue Fire & Bromo', 'Jawa Timur', 'gunung', 3450000, 4, 4.8, 74, 2, 'bromo.jpg',
    'Menyaksikan api biru Kawah Ijen dan sunrise Bromo dalam satu perjalanan.'),
    ('Bromo Sunrise Adventure', 'Jawa Timur', 'gunung', 2350000, 3, 4.7, 88, 4, 'bromo.jpg',
    'Mengejar matahari terbit di Penanjakan dan menyeberangi lautan pasir Bromo.'),
    ('Nusa Penida Day Trip', 'Bali', 'pantai', 1650000, 2, 4.6, 53, 28, 'bali.jpg',
    'Menjelajah Kelingking Beach, Angel Billabong, dan Crystal Bay dalam dua hari.'),
]


def _baca_foto(nama_file):
    path = FOLDER_FOTO / nama_file
    return ContentFile(path.read_bytes()) if path.exists() else None


class Command(BaseCommand):
    help = "Mengisi paket wisata contoh. Paket yang sudah ada hanya dilengkapi data barunya."

    def handle(self, *args, **options):
        hari_ini = timezone.localdate()
        dibuat = 0

        for i, (nama, destinasi, kategori, harga, durasi, rating, ulasan, sisa, file_foto, deskripsi) in enumerate(DATA_PAKET):
            paket = Paket.objects.filter(nama=nama).first()
            baru = paket is None
            if baru:
                paket = Paket.objects.create(
                    nama=nama, destinasi=destinasi, kategori=kategori, harga=harga,
                    durasi_hari=durasi, rating=rating, deskripsi=deskripsi,
                )
                Jadwal.objects.create(paket=paket, tanggal_berangkat=hari_ini + timedelta(days=14 + i * 7),
                                    kuota_total=20, kuota_tersisa=min(20, sisa))
                Jadwal.objects.create(paket=paket, tanggal_berangkat=hari_ini + timedelta(days=28 + i * 7),
                                    kuota_total=20, kuota_tersisa=11)
                dibuat += 1

            # ---- lengkapi data yang mungkin belum ada ----
            if not paket.fasilitas:
                paket.fasilitas = FASILITAS
            if not paket.jumlah_ulasan:
                paket.jumlah_ulasan = ulasan
            foto = _baca_foto(file_foto)
            if not paket.foto and foto:
                paket.foto.save(file_foto, foto, save=False)
            paket.save()

            if not paket.galeri.exists():
                tambahan = [f for f in URUTAN_GALERI if f != file_foto][:3]
                for urutan, nama_file in enumerate(tambahan):
                    isi = _baca_foto(nama_file)
                    if isi:
                        g = FotoPaket(paket=paket, urutan=urutan)
                        g.foto.save(nama_file, isi, save=True)

            if not paket.itinerary.exists():
                for hari in range(1, durasi + 1):
                    if hari == 1:
                        judul, ket = JUDUL_HARI[0], "Penjemputan di bandara, transfer ke penginapan, makan malam sambutan."
                    elif hari == durasi:
                        judul, ket = "Kepulangan", "Sarapan, check-out, dan diantar kembali ke bandara."
                    else:
                        judul, ket = JUDUL_HARI[min(hari - 1, len(JUDUL_HARI) - 1)], "Detail kegiatan bisa diubah lewat Django Admin."
                    Itinerary.objects.create(paket=paket, hari_ke=hari, judul_kegiatan=judul, deskripsi=ket)

        self.stdout.write(self.style.SUCCESS(f"Selesai. {dibuat} paket baru ditambahkan, data paket lainnya dilengkapi."))

        if not paket.meeting_point:
            paket.meeting_point = MEETING_POINT.get(nama, '')