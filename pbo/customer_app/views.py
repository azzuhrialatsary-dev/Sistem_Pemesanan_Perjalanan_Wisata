from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count

from .models import Paket, Jadwal, Booking, TripPost, TripJoinRequest
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


def daftar_paket(request):
    paket_list = Paket.objects.all()

    kategori = request.GET.get('kategori')
    if kategori:
        paket_list = paket_list.filter(kategori=kategori)

    destinasi = request.GET.get('destinasi')
    if destinasi:
        paket_list = paket_list.filter(destinasi__icontains=destinasi)

    return render(request, 'customer/tours_list.html', {
        'paket_list': paket_list,
        'kategori_dipilih': kategori or '',
        'destinasi_dicari': destinasi or '',
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
        username = request.POST.get('username')
        password = request.POST.get('password')
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
    booking_list = Booking.objects.filter(user=request.user).order_by('-dipesan_pada')
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
