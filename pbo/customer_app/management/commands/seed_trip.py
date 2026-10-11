from datetime import timedelta
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from customer_app.models import User, TripPost

FOLDER_FOTO = Path(__file__).resolve().parents[2] / 'static' / 'customer' / 'img'
PASSWORD_DEMO = 'travelhub123'

# (username, nama, umur, kota)
DATA_USER = [
    ('dinda', 'Dinda', 26, 'Jakarta'),
    ('bima', 'Bima', 28, 'Bandung'),
    ('raka', 'Raka', 24, 'Surabaya'),
]

# (username, judul, destinasi, budget, mulai +hari, lama hari, slot, tags, deskripsi, foto)
DATA_TRIP = [
    ('dinda', 'Backpacker Labuan Bajo', 'Labuan Bajo, NTT', 3500000, 30, 4, 3,
    'Backpacker, Laut', 'Open trip santai keliling Pulau Padar dan Pink Beach.', 'komodo.jpg'),
    ('bima', 'Healing di Ubud', 'Ubud, Bali', 2800000, 40, 3, 2,
    'Santai, Budaya', 'Yoga pagi, kafe sawah, dan jalan-jalan pasar seni.', 'bali.jpg'),
    ('raka', 'Hiking Bromo Santai', 'Bromo, Jawa Timur', 1500000, 21, 2, 4,
    'Gunung, Foto', 'Mengejar sunrise di Penanjakan lalu turun ke lautan pasir.', 'bromo.jpg'),
    ('dinda', 'Diving Raja Ampat', 'Raja Ampat, Papua Barat', 9500000, 60, 5, 2,
    'Diving, Laut', 'Menyelam di Misool dan Dampier Strait. Wajib punya lisensi dasar.', 'hero.jpg'),
]


class Command(BaseCommand):
    help = "Mengisi akun dan trip contoh untuk Trip Matchmaker (aman dijalankan berulang)."

    def handle(self, *args, **options):
        hari_ini = timezone.localdate()
        akun = {}

        for username, nama, umur, kota in DATA_USER:
            user, baru = User.objects.get_or_create(
                username=username,
                defaults={'first_name': nama, 'email': f'{username}@travelhub.id', 'umur': umur, 'kota': kota},
            )
            if baru:
                user.set_password(PASSWORD_DEMO)
                user.save()
            akun[username] = user

        dibuat = 0
        for username, judul, destinasi, budget, mulai, lama, slot, tags, deskripsi, file_foto in DATA_TRIP:
            if TripPost.objects.filter(judul=judul).exists():
                continue
            trip = TripPost.objects.create(
                user=akun[username], judul=judul, destinasi=destinasi, budget=budget,
                tanggal_berangkat=hari_ini + timedelta(days=mulai),
                tanggal_selesai=hari_ini + timedelta(days=mulai + lama - 1),
                kuota_teman=slot, tags=tags, deskripsi=deskripsi,
            )
            path_foto = FOLDER_FOTO / file_foto
            if path_foto.exists():
                trip.foto.save(file_foto, ContentFile(path_foto.read_bytes()), save=True)
            dibuat += 1

        self.stdout.write(self.style.SUCCESS(f"Selesai. {dibuat} trip baru ditambahkan."))
        self.stdout.write(f"Akun contoh: dinda / bima / raka, password: {PASSWORD_DEMO}")