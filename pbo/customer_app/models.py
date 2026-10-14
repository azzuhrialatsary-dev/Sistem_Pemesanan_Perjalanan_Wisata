"""
customer_app/models.py

1. ABSTRACTION   -> BaseModel (abstract = True, tanpa tabel sendiri) + kontrak
                    get_ringkasan() lewat NotImplementedError
2. INHERITANCE   -> Paket, Itinerary, Jadwal, Booking, TripPost, dan
                    TripJoinRequest mewarisi BaseModel (created_at & updated_at)
3. ENCAPSULATION -> logic terkait data disimpan sebagai method di dalam class,
                    bukan tersebar di views.py.
                    public    : kurangi_kuota(), terima(), konfirmasi_pembayaran(), dst.
                    protected : _buat_kode(), _BIAYA_LAYANAN, _BATAS_BAYAR_JAM
                    private   : __cukup() di Jadwal, __kuota_penuh() di TripJoinRequest
4. POLYMORPHISM  -> get_ringkasan() di-override di 6 class (method overriding),
                    dipanggil seragam tanpa peduli class-nya (duck typing).
                    __str__() juga di-override di hampir semua class.

Catatan: di Python, "_" dan "__" adalah konvensi penamaan, bukan larangan mutlak.
"""
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid


# =========================================================
# 1. ABSTRACTION
# Class dasar ini TIDAK membuat tabel sendiri di database.
# Dia jadi "cetakan" field yang dipakai berulang, sekaligus
# menetapkan KONTRAK method yang wajib dimiliki semua turunan.
# =========================================================
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # <- ini kunci dari abstraction di Django

    def get_ringkasan(self):
        """
        Kontrak: setiap turunan WAJIB meng-override method ini.
        (Django punya metaclass sendiri sehingga ABC/@abstractmethod
        menyebabkan metaclass conflict; NotImplementedError adalah
        padanannya.)
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} harus mengimplementasikan get_ringkasan()"
        )


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
# Paket, Itinerary, Jadwal, Booking, TripPost, dan TripJoinRequest
# sama-sama "mewarisi" created_at & updated_at dari BaseModel,
# tidak perlu tulis ulang field itu di masing-masing.
# =========================================================
def rupiah(angka):
    """12500000 -> 'Rp 12.500.000'"""
    return f"Rp {angka:,.0f}".replace(',', '.')


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

    # ---------- 3. ENCAPSULATION ----------
    # Logic "bagaimana harga ditampilkan" disimpan di dalam class ini,
    # bukan ditulis ulang manual tiap kali di template/views.
    def harga_format_rupiah(self):
        return rupiah(self.harga)

    def sisa_kursi(self):
        total = self.jadwal.filter(
            tanggal_berangkat__gte=timezone.localdate()
        ).aggregate(total=models.Sum('kuota_tersisa'))['total']
        return total or 0

    # ---------- 4. POLYMORPHISM (method overriding) ----------
    # Meng-override get_ringkasan() milik BaseModel.
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

    # ---------- POLYMORPHISM ----------
    def get_ringkasan(self):
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

    @property
    def kuota_terisi(self):
        return max(0, self.kuota_total - self.kuota_tersisa)

    @property
    def persen_terisi(self):
        return round(self.kuota_terisi * 100 / self.kuota_total) if self.kuota_total else 0

    # private: pengecekan kuota hanya urusan internal class ini
    def __cukup(self, jumlah):
        return jumlah <= self.kuota_tersisa

    # public: antarmuka yang dipanggil dari views
    def kurangi_kuota(self, jumlah):
        if not self.__cukup(jumlah):
            raise ValueError("Kuota tidak mencukupi")
        self.kuota_tersisa -= jumlah
        self.save()

    def tambah_kuota(self, jumlah):
        self.kuota_tersisa = min(self.kuota_total, self.kuota_tersisa + jumlah)
        self.save()

    # ---------- POLYMORPHISM ----------
    def get_ringkasan(self):
        return f"{self.paket.nama} berangkat {self.tanggal_berangkat} (sisa {self.kuota_tersisa})"


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

    # protected: konstanta internal, tidak untuk diubah dari luar class
    _BIAYA_LAYANAN = 15000
    _BATAS_BAYAR_JAM = 24

    def save(self, *args, **kwargs):
        if not self.kode_booking:
            self.kode_booking = self._buat_kode()
        super().save(*args, **kwargs)

    # protected: hanya dipakai di dalam class lewat save()
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
    def konfirmasi_pembayaran(self, metode=''):
        self.status = 'paid'
        if metode:
            self.metode_pembayaran = metode
        self.save()
        Tiket.objects.get_or_create(booking=self)

    def total_harga(self):
        return self.jadwal.paket.harga * self.jumlah_peserta

    def total_harga_rupiah(self):
        return rupiah(self.total_harga())

    def total_bayar(self):
        return self.total_harga() + self._BIAYA_LAYANAN

    def total_bayar_rupiah(self):
        return rupiah(self.total_bayar())

    def biaya_layanan_rupiah(self):
        return rupiah(self._BIAYA_LAYANAN)

    # ---------- batas waktu pembayaran ----------
    @property
    def batas_bayar(self):
        return self.created_at + timedelta(hours=self._BATAS_BAYAR_JAM)

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

    # ---------- POLYMORPHISM ----------
    def get_ringkasan(self):
        return f"{self.kode_booking}: {self.jumlah_peserta} peserta ({self.get_status_display()})"


class Peserta(models.Model):
    JENIS_KELAMIN = (
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    )

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='peserta')
    nama_lengkap = models.CharField(max_length=100)
    no_identitas = models.CharField(max_length=30)          # NIK / No. Paspor
    tanggal_lahir = models.DateField(null=True, blank=True)
    jenis_kelamin = models.CharField(max_length=1, choices=JENIS_KELAMIN, blank=True)
    kontak_darurat_nama = models.CharField(max_length=100, blank=True)
    kontak_darurat_hp = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.nama_lengkap

    def identitas_tersamar(self):
        # contoh: 3201123456780001 -> 3201xxxxxxxx0001 (untuk e-tiket)
        n = self.no_identitas
        if len(n) <= 8:
            return n
        return n[:4] + 'x' * (len(n) - 8) + n[-4:]


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

    # ---------- POLYMORPHISM (method overriding) ----------
    # Nama method sama dengan milik BaseModel dan Paket, tapi isinya berbeda
    # karena konteksnya beda (trip buatan user, bukan paket resmi).
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
        return rupiah(self.budget)

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
    # private: pengecekan kuota disembunyikan di dalam class
    def __kuota_penuh(self):
        return self.trip_post.sisa_kuota_teman() <= 0

    # public: antarmuka yang dipanggil dari views
    def terima(self):
        if self.__kuota_penuh():
            raise ValueError("Kuota trip sudah penuh")
        self.status = 'approved'
        self.save()

    def tolak(self):
        self.status = 'rejected'
        self.save()

    # ---------- POLYMORPHISM ----------
    def get_ringkasan(self):
        return f"{self.user} minta gabung ke {self.trip_post.judul} ({self.get_status_display()})"
