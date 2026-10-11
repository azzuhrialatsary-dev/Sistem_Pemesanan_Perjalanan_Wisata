import math

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.utils.dateparse import parse_date

from .models import User, Paket, Jadwal, Booking, TripPost, TripJoinRequest
from .forms import RegisterForm, BookingForm, get_peserta_formset


# =========================================================
# HALAMAN UMUM (TIDAK BUTUH LOGIN)
# =========================================================

KATEGORI_BERANDA = [
    ('pantai', 'Pantai', 'waves'),
    ('gunung', 'Gunung', 'mountain'),
    ('budaya', 'Budaya', 'landmark'),
    ('kuliner', 'Kuliner', 'utensils-crossed'),
]


def home(request):
    paket_populer = Paket.objects.order_by('-rating', '-created_at')[:6]

    jumlah = dict(
        Paket.objects.order_by().values_list('kategori').annotate(n=Count('id'))
    )
    kategori_list = [
        {'kode': kode, 'label': label, 'ikon': ikon, 'jumlah': jumlah.get(kode, 0)}
        for kode, label, ikon in KATEGORI_BERANDA
    ]

    return render(request, 'customer/home.html', {
        'paket_populer': paket_populer,
        'kategori_list': kategori_list,
        'total_paket': Paket.objects.count(),
        'banner_paket': Paket.objects.exclude(foto='').exclude(foto__isnull=True)[:2],
    })


PAKET_PER_HALAMAN = 6

URUTAN_PAKET = {
    'populer': ('-rating', '-created_at'),
    'termurah': ('harga', '-rating'),
    'termahal': ('-harga', '-rating'),
    'durasi': ('durasi_hari', '-rating'),
}


def _ke_int(nilai, default):
    try:
        return int(nilai)
    except (TypeError, ValueError):
        return default


def _ke_tanggal(nilai):
    try:
        return parse_date(nilai or '')
    except ValueError:
        return None


def daftar_paket(request):
    semua = Paket.objects.all()

    # batas slider diambil dari data paket yang ada
    batas = semua.aggregate(durasi=Max('durasi_hari'), harga=Max('harga'))
    durasi_max_db = batas['durasi'] or 7
    harga_max_db = max(500000, math.ceil((batas['harga'] or 0) / 500000) * 500000)

    # ---- baca filter dari URL ----
    destinasi = request.GET.get('destinasi', '').strip()
    kategori_valid = dict(Paket.KATEGORI_CHOICES)
    kategori_dipilih = [k for k in request.GET.getlist('kategori') if k in kategori_valid]
    # 'tanggal' (satu tanggal) berasal dari search bar di beranda
    tanggal_dari = _ke_tanggal(request.GET.get('tanggal_dari') or request.GET.get('tanggal'))
    tanggal_sampai = _ke_tanggal(request.GET.get('tanggal_sampai'))
    durasi_maks = min(_ke_int(request.GET.get('durasi_maks'), durasi_max_db), durasi_max_db)
    harga_maks = min(_ke_int(request.GET.get('harga_maks'), harga_max_db), harga_max_db)
    urut = request.GET.get('urut', 'populer')
    if urut not in URUTAN_PAKET:
        urut = 'populer'

    # ---- terapkan filter ----
    paket_list = semua.filter(durasi_hari__lte=durasi_maks, harga__lte=harga_maks)
    if destinasi:
        paket_list = paket_list.filter(destinasi__icontains=destinasi)
    if kategori_dipilih:
        paket_list = paket_list.filter(kategori__in=kategori_dipilih)

    filter_jadwal = {}
    if tanggal_dari:
        filter_jadwal['jadwal__tanggal_berangkat__gte'] = tanggal_dari
    if tanggal_sampai:
        filter_jadwal['jadwal__tanggal_berangkat__lte'] = tanggal_sampai
    if filter_jadwal:
        # satu filter() supaya kedua batas berlaku pada jadwal yang sama
        paket_list = paket_list.filter(**filter_jadwal).distinct()

    paket_list = paket_list.order_by(*URUTAN_PAKET[urut])

    # ---- halaman ----
    paginator = Paginator(paket_list, PAKET_PER_HALAMAN)
    page_obj = paginator.get_page(request.GET.get('page'))

    # pilihan dropdown destinasi
    destinasi_list = list(
        semua.order_by('destinasi').values_list('destinasi', flat=True).distinct()
    )
    if destinasi and destinasi not in destinasi_list:
        destinasi_list.append(destinasi)

    # query string tanpa 'page', dipakai link nomor halaman
    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'customer/tours_list.html', {
        'page_obj': page_obj,
        'total': paginator.count,
        'query_string': params.urlencode(),
        'destinasi_list': destinasi_list,
        'destinasi_dicari': destinasi,
        'kategori_pilihan': Paket.KATEGORI_CHOICES,
        'kategori_dipilih': kategori_dipilih,
        'tanggal_dari': tanggal_dari.isoformat() if tanggal_dari else '',
        'tanggal_sampai': tanggal_sampai.isoformat() if tanggal_sampai else '',
        'durasi_maks': durasi_maks,
        'durasi_max_db': durasi_max_db,
        'harga_maks': harga_maks,
        'harga_max_db': harga_max_db,
        'harga_maks_label': f"{harga_maks:,}".replace(',', '.'),
        'urut': urut,
    })


def detail_paket(request, paket_id):
    paket = get_object_or_404(Paket, id=paket_id)
    itinerary_list = paket.itinerary.all()
    jadwal_list = paket.jadwal.all()

    return render(request, 'customer/tour_detail.html', {
        'paket': paket,
        'itinerary_list': itinerary_list,
        'jadwal_list': jadwal_list,
    })


# =========================================================
# AUTENTIKASI
# =========================================================

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Akun berhasil dibuat, selamat datang!")
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        identitas = request.POST.get('username', '').strip()
        password = request.POST.get('password')

        # boleh login pakai email ATAU username
        username = identitas
        if '@' in identitas:
            pengguna = User.objects.filter(email__iexact=identitas).first()
            if pengguna:
                username = pengguna.username

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            next_url = request.GET.get('next') or 'home'
            return redirect(next_url)
        else:
            messages.error(request, "Username atau password salah.")

    return render(request, 'accounts/login.html')


def logout_view(request):
    auth_logout(request)
    return redirect('home')


# =========================================================
# BOOKING, PEMBAYARAN, TIKET (BUTUH LOGIN)
# =========================================================

@login_required
def buat_booking(request, jadwal_id):
    """
    Tahap 1: pengguna pilih jadwal dari halaman detail paket,
    lalu masukkan jumlah peserta di sini.
    Kuota langsung dikurangi saat ini juga (supaya tidak dobel booking
    oleh orang lain), bukan menunggu sampai bayar.
    """
    jadwal = get_object_or_404(Jadwal, id=jadwal_id)

    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            jumlah = form.cleaned_data['jumlah_peserta']

            if jumlah > jadwal.kuota_tersisa:
                messages.error(request, f"Kuota tidak mencukupi. Sisa kuota: {jadwal.kuota_tersisa}")
            else:
                booking = Booking.objects.create(
                    user=request.user,
                    jadwal=jadwal,
                    jumlah_peserta=jumlah,
                )
                jadwal.kurangi_kuota(jumlah)
                return redirect('isi_peserta', booking_id=booking.id)
    else:
        form = BookingForm()

    return render(request, 'customer/booking.html', {
        'jadwal': jadwal,
        'form': form,
    })


@login_required
def isi_peserta(request, booking_id):
    """
    Tahap 2: isi nama dan identitas tiap peserta, jumlah formnya
    menyesuaikan booking.jumlah_peserta.
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    jumlah_kosong = max(booking.jumlah_peserta - booking.peserta.count(), 0)
    PesertaFormSet = get_peserta_formset(jumlah_kosong)

    if request.method == 'POST':
        formset = PesertaFormSet(request.POST, instance=booking)
        if formset.is_valid():
            formset.save()
            return redirect('payment', booking_id=booking.id)
    else:
        formset = PesertaFormSet(instance=booking)

    return render(request, 'customer/isi_peserta.html', {
        'booking': booking,
        'formset': formset,
    })


@login_required
def payment(request, booking_id):
    """
    Tahap 3: ringkasan dan tombol "Konfirmasi Pembayaran" (simulasi,
    tanpa payment gateway asli).
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == 'POST':
        booking.konfirmasi_pembayaran()
        messages.success(request, "Pembayaran berhasil dikonfirmasi!")
        return redirect('lihat_tiket', booking_id=booking.id)

    return render(request, 'customer/payment.html', {
        'booking': booking,
    })


@login_required
def lihat_tiket(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status != 'paid':
        messages.info(request, "Pesanan ini belum lunas.")
        return redirect('payment', booking_id=booking.id)

    return render(request, 'customer/ticket.html', {
        'booking': booking,
        'tiket': booking.tiket,
    })


@login_required
def riwayat_booking(request):
    booking_list = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'customer/riwayat.html', {
        'booking_list': booking_list,
    })


# =========================================================
# TRIP MATCHMAKER
# =========================================================

def daftar_trip_matchmaker(request):
    trip_list = list(TripPost.objects.all())

    if request.user.is_authenticated:
        status_map = {
            req.trip_post_id: req.status
            for req in TripJoinRequest.objects.filter(user=request.user)
        }
        for trip in trip_list:
            # ditempel sebagai atribut biasa, bukan disimpan ke database,
            # supaya template bisa pakai trip.status_pengajuan langsung
            trip.status_pengajuan = status_map.get(trip.id)
    else:
        for trip in trip_list:
            trip.status_pengajuan = None

    return render(request, 'customer/matchmaker.html', {
        'trip_list': trip_list,
    })


@login_required
def ajukan_gabung_trip(request, trip_id):
    trip = get_object_or_404(TripPost, id=trip_id)

    if trip.user == request.user:
        messages.error(request, "Tidak bisa mengajukan gabung ke trip buatan sendiri.")
        return redirect('daftar_trip_matchmaker')

    sudah_ada = TripJoinRequest.objects.filter(trip_post=trip, user=request.user).exists()
    if sudah_ada:
        messages.info(request, "Kamu sudah pernah mengajukan gabung ke trip ini.")
        return redirect('daftar_trip_matchmaker')

    if trip.sisa_kuota_teman() <= 0:
        messages.error(request, "Kuota trip ini sudah penuh.")
        return redirect('daftar_trip_matchmaker')

    TripJoinRequest.objects.create(trip_post=trip, user=request.user)
    messages.success(request, "Pengajuan gabung berhasil dikirim, menunggu persetujuan.")
    return redirect('daftar_trip_matchmaker')


# =========================================================
# PANEL ADMIN TRAVELHUB
# =========================================================

@login_required
def admin_jadwal(request):
    if not request.user.is_superuser:
        messages.error(request, "Anda tidak memiliki hak akses sebagai admin.")
        return redirect('home')

    if request.method == 'POST':
        paket_id = request.POST.get('paket_id')
        tanggal = request.POST.get('tanggal')
        kuota = request.POST.get('kuota')
        
        if paket_id and tanggal and kuota:
            paket_obj = get_object_or_404(Paket, id=paket_id)
            Jadwal.objects.create(
                paket=paket_obj,
                tanggal_berangkat=tanggal,
                kuota=int(kuota),
                kuota_tersisa=int(kuota)
            )
            messages.success(request, "Jadwal berhasil ditambahkan!")
            return redirect('admin_jadwal')

    # Ambil data semua jadwal dan hitung persentasenya dengan aman di Python
    jadwal_all = Jadwal.objects.select_related('paket').all()
    rows = []
    for j in jadwal_all:
        quota = j.kuota if j.kuota and j.kuota > 0 else 1
        booked = max(0, quota - j.kuota_tersisa)
        # Hitung persentase bilangan bulat di Python
        persen = int((booked / quota) * 100)
        
        rows.append({
            'tour': j.paket.nama if j.paket else 'Paket Dihapus',
            'date': j.tanggal_berangkat.strftime('%d %b %Y') if j.tanggal_berangkat else '-',
            'quota': j.kuota or 0,
            'booked': booked,
            'style_width': f"width: {persen}%;"
        })

    pakets = Paket.objects.all()

    return render(request, 'admin_panel/admin_jadwal.html', {
        'rows': rows,
        'pakets': pakets,
    })