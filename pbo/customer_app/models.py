"""
customer_app/models.py

Struktur model ini sengaja ditulis untuk menunjukkan penerapan
4 Pilar OOP secara eksplisit, supaya mudah dijelaskan saat presentasi.

1. ABSTRACTION  -> BaseModel (class dasar, tidak pernah dipakai langsung)
2. INHERITANCE  -> Paket dan TripPost sama-sama mewarisi BaseModel
3. ENCAPSULATION -> logic terkait data disimpan sebagai method di dalam class,
                    bukan tersebar di views.py (misal kurangi_kuota())
4. POLYMORPHISM  -> method get_ringkasan() ada di beberapa class,
                    tapi hasilnya berbeda tergantung class-nya
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid


# =========================================================
# 1. ABSTRACTION
# Class dasar ini TIDAK membuat tabel sendiri di database.
# Dia cuma jadi "cetakan" field yang dipakai berulang.
# =========================================================
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # <- ini kunci dari abstraction di Django


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


# =========================================================
# 2. INHERITANCE
# Paket dan TripPost sama-sama "mewarisi" created_at & updated_at
# dari BaseModel, tidak perlu tulis ulang field itu di masing-masing.
# =========================================================
class Paket(BaseModel):
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

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.nama

    # ---------- 3. ENCAPSULATION ----------
    # Logic "bagaimana harga ditampilkan" disimpan di dalam class ini,
    # bukan ditulis ulang manual tiap kali di template/views.
    def harga_format_rupiah(self):
        return f"Rp {self.harga:,.0f}".replace(',', '.')

    def sisa_kursi(self):
        total = self.jadwal.filter(
            tanggal_berangkat__gte=timezone.localdate()
        ).aggregate(total=models.Sum('kuota_tersisa'))['total']
        return total or 0

    # ---------- 4. POLYMORPHISM ----------
    # Method dengan nama sama (get_ringkasan) ada juga di class TripPost
    # di bawah, tapi isinya beda. Inilah polymorphism.
    def get_ringkasan(self):
        return f"{self.nama} - {self.destinasi} ({self.durasi_hari} hari)"


class Itinerary(BaseModel):
    paket = models.ForeignKey(Paket, on_delete=models.CASCADE, related_name='itinerary')
    hari_ke = models.PositiveIntegerField()
    judul_kegiatan = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True)

    class Meta:
        ordering = ['hari_ke']

    def __str__(self):
        return f"Hari {self.hari_ke}: {self.judul_kegiatan}"


class Jadwal(BaseModel):
    paket = models.ForeignKey(Paket, on_delete=models.CASCADE, related_name='jadwal')
    tanggal_berangkat = models.DateField()
    kuota_total = models.PositiveIntegerField()
    kuota_tersisa = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.paket.nama} - {self.tanggal_berangkat}"

    # ---------- ENCAPSULATION ----------
    # Aturan "kuota tidak boleh minus" dijaga di dalam class ini sendiri,
    # bukan dicek manual tiap kali di views.py. Ini mencegah bug tersebar.
    @property
    def is_tersedia(self):
        return self.kuota_tersisa > 0

    def kurangi_kuota(self, jumlah):
        if jumlah > self.kuota_tersisa:
            raise ValueError("Kuota tidak mencukupi")
        self.kuota_tersisa -= jumlah
        self.save()

    def tambah_kuota(self, jumlah):
        self.kuota_tersisa = min(self.kuota_total, self.kuota_tersisa + jumlah)
        self.save()


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

    def save(self, *args, **kwargs):
        if not self.kode_booking:
            self.kode_booking = self._buat_kode()
        super().save(*args, **kwargs)

    def _buat_kode(self):
        # contoh hasil: TH-2611-0042 (tahun+bulan keberangkatan, lalu nomor urut)
        tgl = self.jadwal.tanggal_berangkat
        nomor = (Booking.objects.aggregate(m=models.Max('id'))['m'] or 0) + 1
        while True:
            kode = f"TH-{tgl:%y%m}-{nomor:04d}"
            if not Booking.objects.filter(kode_booking=kode).exists():
                return kode
            nomor += 1

    def __str__(self):
        return self.kode_booking

    # ---------- ENCAPSULATION ----------
    # Proses "konfirmasi bayar" jadi satu method, supaya view tinggal
    # panggil booking.konfirmasi_pembayaran(), tidak perlu tahu detailnya.
    def konfirmasi_pembayaran(self):
        self.status = 'paid'
        self.save()
        Tiket.objects.get_or_create(booking=self)

    def total_harga(self):
        return self.jadwal.paket.harga * self.jumlah_peserta

    def total_harga_rupiah(self):
        return f"Rp {self.total_harga():,.0f}".replace(',', '.')


class Peserta(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='peserta')
    nama_lengkap = models.CharField(max_length=100)
    no_identitas = models.CharField(max_length=30)
    umur = models.PositiveSmallIntegerField(null=True, blank=True)
    kota = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return self.nama_lengkap


class Tiket(models.Model):
    """
    Tiket diterbitkan otomatis begitu booking lunas. Verifikasi saat
    keberangkatan dilakukan admin secara manual lewat pencarian
    booking.kode_booking, tanpa QR Code.
    """
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='tiket')
    sudah_diverifikasi = models.BooleanField(default=False)
    diterbitkan_pada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tiket {self.booking.kode_booking}"

    def verifikasi(self):
        self.sudah_diverifikasi = True
        self.save()


# =========================================================
# TRIP MATCHMAKER (fitur unik)
# =========================================================
BULAN_SINGKAT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']


class TripPost(BaseModel):
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

    # ---------- POLYMORPHISM ----------
    # Nama method sama persis dengan milik Paket (get_ringkasan),
    # tapi isinya berbeda karena konteksnya beda (trip buatan user, bukan paket resmi).
    def get_ringkasan(self):
        return f"{self.judul} ke {self.destinasi} pada {self.tanggal_berangkat}"

    # ---------- helper tampilan kartu ----------
    def label_pembuat(self):
        # contoh hasil: "Dinda, 26 · Jakarta" (umur dan kota hanya tampil kalau diisi)
        u = self.user
        teks = u.first_name or u.username
        if u.umur:
            teks += f", {u.umur}"
        if u.kota:
            teks += f" · {u.kota}"
        return teks

    def rentang_tanggal(self):
        # contoh hasil: "5–9 Des 2026" atau "28 Nov – 2 Des 2026"
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

    # ---------- ENCAPSULATION ----------
    def terima(self):
        if self.trip_post.sisa_kuota_teman() <= 0:
            raise ValueError("Kuota trip sudah penuh")
        self.status = 'approved'
        self.save()

    def tolak(self):
        self.status = 'rejected'
        self.save()
