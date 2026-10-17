from abc import ABCMeta, abstractmethod
from datetime import timedelta
from django.db import models
from django.db.models.base import ModelBase
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid


# =========================================================
# 1. ABSTRACTION
# BaseModel adalah class dasar yang tidak pernah membuat tabel
# sendiri (class Meta: abstract = True), cuma jadi "cetakan" field
# created_at/updated_at yang dipakai berulang oleh class turunannya.
# =========================================================
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # <- ini kunci dari abstraction di Django


# =========================================================
# 1. ABSTRACTION (abstract class + abstract method sungguhan)
# Django punya metaclass sendiri (ModelBase) untuk mengurus ORM,
# sedangkan Python juga punya metaclass sendiri untuk abstract class
# (ABCMeta). AbstractModelMeta di bawah ini menggabungkan keduanya,
# supaya Ringkasan bisa jadi abstract class versi Python (bukan cuma
# abstract versi Django) DAN tetap berupa Django model biasa.
#
# @abstractmethod pada get_ringkasan() membuat Python benar-benar
# MELARANG membuat objek dari class apa pun yang mewarisi Ringkasan
# tapi lupa meng-override get_ringkasan()-nya. Ini beda dari sekadar
# NotImplementedError manual: pelanggarannya ketahuan lebih awal,
# begitu objeknya mau dibuat, bukan baru ketahuan saat method-nya
# dipanggil.
# =========================================================
class AbstractModelMeta(ModelBase, ABCMeta):
    pass


class Ringkasan(models.Model, metaclass=AbstractModelMeta):
    class Meta:
        abstract = True

    @abstractmethod
    def get_ringkasan(self):
        """Wajib di-override oleh class yang mewarisi Ringkasan."""
        ...


# =========================================================
# USER & ROLE
# =========================================================
class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    no_hp = models.CharField(max_length=20, blank=True)
    umur = models.PositiveSmallIntegerField(null=True, blank=True)
    kota = models.CharField(max_length=80, blank=True)

    def is_admin_role(self):
        return self.role == 'admin'


def rupiah(angka):
    """12500000 -> 'Rp 12.500.000'"""
    return f"Rp {angka:,.0f}".replace(',', '.')


# =========================================================
# 2. INHERITANCE
# Paket mewarisi BaseModel (dapat created_at/updated_at gratis)
# SEKALIGUS mewarisi Ringkasan (terikat kontrak get_ringkasan()).
# Satu class mewarisi dua abstract class berbeda sekaligus -> ini
# juga contoh multiple inheritance yang valid di Python.
# =========================================================
class Paket(BaseModel, Ringkasan):
    KATEGORI_CHOICES = (
        ('pantai', 'Pantai'),
        ('gunung', 'Gunung'),
        ('budaya', 'Budaya'),
        ('kuliner', 'Kuliner'),
    )

    nama = models.CharField(max_length=100)
    destinasi = models.CharField(max_length=100)
    kategori = models.CharField(max_length=20, choices=KATEGORI_CHOICES)
    harga = models.PositiveIntegerField()
    durasi_hari = models.PositiveIntegerField()
    deskripsi = models.TextField()
    foto = models.ImageField(upload_to='paket/', blank=True, null=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    jumlah_ulasan = models.PositiveIntegerField(default=0)
    fasilitas = models.TextField(blank=True)
    meeting_point = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.nama

    def daftar_fasilitas(self):
        return [baris.strip() for baris in self.fasilitas.splitlines() if baris.strip()]

    def daftar_foto(self):
        urls = [self.foto.url] if self.foto else []
        urls += [g.foto.url for g in self.galeri.all() if g.foto]
        return urls

    def harga_format_rupiah(self):
        return f"Rp {self.harga:,.0f}".replace(',', '.')

    def sisa_kursi(self):
        total = self.jadwal.filter(
            tanggal_berangkat__gte=timezone.localdate()
        ).aggregate(total=models.Sum('kuota_tersisa'))['total']
        return total or 0

    # ---------------------------------------------------
    # 3. POLYMORPHISM
    # Ini implementasi Paket atas kontrak abstract method
    # get_ringkasan() dari Ringkasan. TripPost di bawah juga
    # mewarisi kontrak yang sama tapi isinya beda -> kode
    # pemanggil bisa memperlakukan Paket & TripPost secara
    # seragam lewat get_ringkasan() tanpa peduli class aslinya.
    # ---------------------------------------------------
    def get_ringkasan(self):
        return f"{self.nama} - {self.destinasi} ({self.durasi_hari} hari)"


class FotoPaket(models.Model):
    """Foto tambahan (galeri) untuk satu paket wisata."""
    paket = models.ForeignKey(Paket, on_delete=models.CASCADE, related_name='galeri')
    foto = models.ImageField(upload_to='paket/galeri/')
    urutan = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['urutan', 'id']

    def __str__(self):
        return f"Foto {self.paket.nama} #{self.urutan}"


class Itinerary(BaseModel):
    paket = models.ForeignKey(Paket, on_delete=models.CASCADE, related_name='itinerary')
    hari_ke = models.PositiveIntegerField()
    judul_kegiatan = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True)

    class Meta:
        ordering = ['hari_ke']

    def __str__(self):
        return f"Hari {self.hari_ke}: {self.judul_kegiatan}"


# =========================================================
# 4. ENCAPSULATION
# Diterapkan 3 level akses sekaligus di class ini:
#   PUBLIC     kurangi_kuota(), tambah_kuota(), is_tersedia, dst
#              -> boleh dipanggil dari views.py/admin_app.
#   PROTECTED  _catat_log_kuota() (satu garis bawah)
#              -> boleh dipakai class turunan, tapi tidak
#              dimaksudkan dipanggil langsung dari views.py.
#   PRIVATE    __validasi_kuota() (dua garis bawah)
#              -> murni dipakai di dalam class ini sendiri.
#              Python melakukan name mangling pada nama ini,
#              jadi tidak bisa dipanggil dari luar class dengan
#              nama aslinya.
# Field kuota_tersisa sendiri tetap public karena Django ORM,
# Admin, dan Form memang butuh akses langsung ke field supaya
# bisa bekerja. Yang "dijaga" di sini adalah ATURAN BISNISNYA
# (lewat method), bukan field mentahnya.
# =========================================================
class Jadwal(BaseModel):
    paket = models.ForeignKey(Paket, on_delete=models.CASCADE, related_name='jadwal')
    tanggal_berangkat = models.DateField()
    kuota_total = models.PositiveIntegerField()
    kuota_tersisa = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.paket.nama} - {self.tanggal_berangkat}"

    @property
    def is_tersedia(self):
        return self.kuota_tersisa > 0

    @property
    def kuota_terisi(self):
        return max(0, self.kuota_total - self.kuota_tersisa)

    @property
    def persen_terisi(self):
        return round(self.kuota_terisi * 100 / self.kuota_total) if self.kuota_total else 0

    def kurangi_kuota(self, jumlah):
        self.__validasi_kuota(jumlah)
        self.kuota_tersisa -= jumlah
        self.save()
        self._catat_log_kuota(-jumlah)

    def tambah_kuota(self, jumlah):
        self.kuota_tersisa = min(self.kuota_total, self.kuota_tersisa + jumlah)
        self.save()
        self._catat_log_kuota(+jumlah)

    def _catat_log_kuota(self, perubahan):
        tanda = '+' if perubahan > 0 else ''
        print(f"[LOG KUOTA] {self.paket.nama} ({self.tanggal_berangkat}): {tanda}{perubahan}")

    def __validasi_kuota(self, jumlah):
        if jumlah <= 0:
            raise ValueError("Jumlah yang dikurangi harus lebih dari 0")
        if jumlah > self.kuota_tersisa:
            raise ValueError("Kuota tidak mencukupi")


class Booking(BaseModel):
    STATUS_CHOICES = (
        ('unpaid', 'Belum Bayar'),
        ('paid', 'Lunas'),
        ('cancelled', 'Dibatalkan'),
        ('completed', 'Selesai'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    jadwal = models.ForeignKey(Jadwal, on_delete=models.CASCADE, related_name='bookings')
    jumlah_peserta = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    kode_booking = models.CharField(max_length=20, unique=True, blank=True)
    metode_pembayaran = models.CharField(max_length=10, blank=True)

    BIAYA_LAYANAN = 15000
    BATAS_BAYAR_JAM = 24

    def save(self, *args, **kwargs):
        if not self.kode_booking:
            self.kode_booking = self._buat_kode()
        super().save(*args, **kwargs)

    # ---------------------------------------------------
    # ENCAPSULATION (protected)
    # _buat_kode() dipakai save() sendiri, tidak dimaksudkan
    # dipanggil langsung dari views.py.
    # ---------------------------------------------------
    def _buat_kode(self):
        tgl = self.jadwal.tanggal_berangkat
        nomor = (Booking.objects.aggregate(m=models.Max('id'))['m'] or 0) + 1
        while True:
            kode = f"TH-{tgl:%y%m}-{nomor:04d}"
            if not Booking.objects.filter(kode_booking=kode).exists():
                return kode
            nomor += 1

    def __str__(self):
        return self.kode_booking

    def konfirmasi_pembayaran(self, metode=''):
        self.status = 'paid'
        if metode:
            self.metode_pembayaran = metode
        self.save()
        Tiket.objects.get_or_create(booking=self)

    def total_harga(self):
        return self.__hitung_subtotal()

    def total_harga_rupiah(self):
        return rupiah(self.total_harga())

    def total_bayar(self):
        return self.total_harga() + self.BIAYA_LAYANAN

    def total_bayar_rupiah(self):
        return rupiah(self.total_bayar())

    def biaya_layanan_rupiah(self):
        return rupiah(self.BIAYA_LAYANAN)

    @property
    def batas_bayar(self):
        return self.created_at + timedelta(hours=self.BATAS_BAYAR_JAM)

    def sisa_detik_bayar(self):
        return max(0, int((self.batas_bayar - timezone.now()).total_seconds()))

    def sudah_kedaluwarsa(self):
        return self.status == 'unpaid' and self.sisa_detik_bayar() == 0

    def batalkan(self):
        """Membatalkan pesanan yang belum dibayar dan mengembalikan kuota."""
        if self.status == 'unpaid':
            self.status = 'cancelled'
            self.save()
            self.jadwal.tambah_kuota(self.jumlah_peserta)

    # ---------------------------------------------------
    # ENCAPSULATION (private)
    # Perhitungan mentah, murni dipakai di dalam class ini.
    # ---------------------------------------------------
    def __hitung_subtotal(self):
        return self.jadwal.paket.harga * self.jumlah_peserta


class Peserta(models.Model):
    JENIS_KELAMIN = (
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    )

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='peserta')
    nama_lengkap = models.CharField(max_length=100)
    no_identitas = models.CharField(max_length=30)          
    tanggal_lahir = models.DateField(null=True, blank=True)
    jenis_kelamin = models.CharField(max_length=1, choices=JENIS_KELAMIN, blank=True)
    kontak_darurat_nama = models.CharField(max_length=100, blank=True)
    kontak_darurat_hp = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.nama_lengkap

    def identitas_tersamar(self):
        n = self.no_identitas
        if len(n) <= 8:
            return n
        return n[:4] + 'x' * (len(n) - 8) + n[-4:]


class Tiket(models.Model):
    """
    Tiket diterbitkan otomatis begitu booking lunas. Verifikasi saat
    keberangkatan dilakukan admin lewat input kode booking manual
    atau scan QR Code (isinya kode_booking).
    """
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='tiket')
    sudah_diverifikasi = models.BooleanField(default=False)
    diterbitkan_pada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tiket {self.booking.kode_booking}"

    def verifikasi(self):
        self.sudah_diverifikasi = True
        self.save()

        # ---------- QR Code untuk e-tiket ----------
    def qr_data_uri(self):
        """
        QR Code berisi kode booking, dalam bentuk data URI supaya bisa langsung
        dipasang di <img>. Kosong kalau library 'qrcode' belum terpasang.
        """
        try:
            import base64
            from io import BytesIO
            import qrcode
        except ImportError:
            return ''
        gambar = qrcode.make(self.booking.kode_booking, box_size=10, border=2)
        buf = BytesIO()
        gambar.save(buf)
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


# =========================================================
# TRIP MATCHMAKER (fitur unik)
# =========================================================
BULAN_SINGKAT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']


# =========================================================
# INHERITANCE + POLYMORPHISM
# TripPost mewarisi BaseModel dan Ringkasan, sama seperti Paket.
# get_ringkasan() WAJIB di-override (kontrak abstract method dari
# Ringkasan), isinya beda dari milik Paket karena konteksnya memang
# beda (trip buatan user, bukan paket resmi).
# =========================================================
class TripPost(BaseModel, Ringkasan):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trip_posts')
    judul = models.CharField(max_length=150)
    destinasi = models.CharField(max_length=100)
    tanggal_berangkat = models.DateField()           # "Tanggal mulai"
    tanggal_selesai = models.DateField(null=True, blank=True)
    budget = models.PositiveIntegerField(default=0)  # budget per orang
    tags = models.CharField(max_length=150, blank=True)  # contoh: "Backpacker, Laut, Foto"
    foto = models.ImageField(upload_to='trip/', blank=True, null=True)
    deskripsi = models.TextField()
    kuota_teman = models.PositiveIntegerField()      # "Jumlah slot"

    def __str__(self):
        return self.judul

    def get_ringkasan(self):
        return f"{self.judul} ke {self.destinasi} pada {self.tanggal_berangkat}"

    def label_pembuat(self):
        u = self.user
        teks = u.first_name or u.username
        if u.umur:
            teks += f", {u.umur}"
        if u.kota:
            teks += f" · {u.kota}"
        return teks

    def rentang_tanggal(self):
        a, b = self.tanggal_berangkat, self.tanggal_selesai
        bln_a, bln_b = BULAN_SINGKAT[a.month - 1], (BULAN_SINGKAT[b.month - 1] if b else '')
        if not b or b == a:
            return f"{a.day} {bln_a} {a.year}"
        if (a.year, a.month) == (b.year, b.month):
            return f"{a.day}–{b.day} {bln_b} {b.year}"
        if a.year == b.year:
            return f"{a.day} {bln_a} – {b.day} {bln_b} {b.year}"
        return f"{a.day} {bln_a} {a.year} – {b.day} {bln_b} {b.year}"

    def budget_format_rupiah(self):
        return f"Rp {self.budget:,.0f}".replace(',', '.')

    def daftar_tags(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def sisa_kuota_teman(self):
        jumlah_diterima = self.join_requests.filter(status='approved').count()
        return max(0, self.kuota_teman - jumlah_diterima)


class TripJoinRequest(BaseModel):
    STATUS_CHOICES = (
        ('pending', 'Menunggu'),
        ('approved', 'Diterima'),
        ('rejected', 'Ditolak'),
    )

    trip_post = models.ForeignKey(TripPost, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='join_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        unique_together = ('trip_post', 'user')

    def __str__(self):
        return f"{self.user} -> {self.trip_post} ({self.status})"

    def terima(self):
        if not self._boleh_diterima():
            raise ValueError("Kuota trip sudah penuh")
        self.status = 'approved'
        self.save()

    def tolak(self):
        self.status = 'rejected'
        self.save()

    # ---------------------------------------------------
    # ENCAPSULATION (protected)
    # Pengecekan "boleh diterima atau tidak" dipisah ke sini,
    # supaya kalau ada aturan tambahan nanti, cukup diubah di
    # satu tempat ini tanpa menyentuh terima()/tolak().
    # ---------------------------------------------------
    def _boleh_diterima(self):
        return self.trip_post.sisa_kuota_teman() > 0
