import math
from datetime import timedelta
from django.db import transaction

from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.utils.dateparse import parse_date

from .models import User, Paket, Jadwal, Booking, TripPost, TripJoinRequest
from .forms import RegisterForm, BookingForm, TripPostForm, PesertaFormSet, get_peserta_formset
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

    # hanya jadwal yang belum lewat; yang pertama masih tersedia dipilih otomatis
    jadwal_list = paket.jadwal.filter(
        tanggal_berangkat__gte=timezone.localdate()
    ).order_by('tanggal_berangkat')
    jadwal_default = next((j for j in jadwal_list if j.is_tersedia), None)

    return render(request, 'customer/tour_detail.html', {
        'paket': paket,
        'foto_list': paket.daftar_foto()[:5],
        'fasilitas_list': paket.daftar_fasilitas(),
        'itinerary_list': paket.itinerary.all(),
        'jadwal_list': jadwal_list,
        'jadwal_default': jadwal_default,
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
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            next_url = request.GET.get('next') or (
                'panel_dashboard' if (user.is_superuser or user.role == 'admin') else 'home')
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

MAKS_PESERTA = 10


@login_required
def buat_booking(request, jadwal_id):
    """
    Form Pemesanan: jumlah peserta + data tiap peserta dalam satu halaman.
    Kuota langsung dikurangi saat pesanan dibuat (supaya tidak dobel booking
    oleh orang lain), dan dikembalikan kalau pesanan dibatalkan.
    """
    jadwal = get_object_or_404(Jadwal.objects.select_related('paket'), id=jadwal_id)
    paket = jadwal.paket

    if jadwal.tanggal_berangkat < timezone.localdate() or not jadwal.is_tersedia:
        messages.error(request, "Jadwal ini sudah tidak tersedia. Silakan pilih jadwal lain.")
        return redirect('detail_paket', paket_id=paket.id)

    if request.method == 'POST':
        formset = PesertaFormSet(request.POST, prefix='peserta')
        if formset.is_valid():
            jumlah = len(formset.forms)
            with transaction.atomic():
                jadwal = Jadwal.objects.select_for_update().get(id=jadwal_id)
                if jumlah > jadwal.kuota_tersisa:
                    messages.error(request, f"Kuota tidak mencukupi. Sisa kuota: {jadwal.kuota_tersisa}")
                else:
                    booking = Booking.objects.create(
                        user=request.user, jadwal=jadwal, jumlah_peserta=jumlah,
                    )
                    for form in formset:
                        peserta = form.save(commit=False)
                        peserta.booking = booking
                        peserta.save()
                    jadwal.kurangi_kuota(jumlah)
                    return redirect('payment', booking_id=booking.id)
    else:
        formset = PesertaFormSet(prefix='peserta')

    return render(request, 'customer/booking.html', {
        'jadwal': jadwal,
        'paket': paket,
        'formset': formset,
        'maks_peserta': min(MAKS_PESERTA, jadwal.kuota_tersisa),
        'biaya_layanan': Booking.BIAYA_LAYANAN,
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


# (kode, label, nama ikon lucide)
METODE_BAYAR = [
    ('va', 'Virtual Account (BCA, BNI, Mandiri)', 'landmark'),
    ('qris', 'QRIS', 'qr-code'),
    ('ewallet', 'E-Wallet (GoPay, OVO, DANA)', 'wallet'),
    ('kartu', 'Kartu Kredit / Debit', 'credit-card'),
]


@login_required
def payment(request, booking_id):
    """
    Pembayaran: pilih metode lalu konfirmasi (simulasi, tanpa payment gateway asli).
    Pesanan dibatalkan otomatis kalau tidak dibayar dalam 24 jam.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('jadwal', 'jadwal__paket'),
        id=booking_id, user=request.user,
    )

    if booking.status == 'paid':
        return redirect('lihat_tiket', booking_id=booking.id)

    if booking.status != 'unpaid':
        messages.info(request, "Pesanan ini sudah tidak aktif.")
        return redirect('riwayat_booking')

    if booking.sudah_kedaluwarsa():
        booking.batalkan()
        messages.error(request, "Waktu pembayaran habis, pesanan dibatalkan.")
        return redirect(f"{reverse('riwayat_booking')}?tab=dibatalkan")

    if request.method == 'POST':
        metode = request.POST.get('metode')
        if metode not in dict((kode, label) for kode, label, _ in METODE_BAYAR):
            metode = 'va'
        booking.konfirmasi_pembayaran(metode)
        messages.success(request, "Pembayaran berhasil dikonfirmasi!")
        return redirect('lihat_tiket', booking_id=booking.id)

    return render(request, 'customer/payment.html', {
        'booking': booking,
        'paket': booking.jadwal.paket,
        'metode_list': METODE_BAYAR,
        'sisa_detik': booking.sisa_detik_bayar(),
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


TAB_RIWAYAT = ('aktif', 'selesai', 'dibatalkan')


@login_required
def riwayat_booking(request):
    tab = request.GET.get('tab', 'aktif')
    if tab not in TAB_RIWAYAT:
        tab = 'aktif'

    # pesanan yang lewat batas waktu bayar dibatalkan otomatis (kuota dikembalikan)
    batas = timezone.now() - timedelta(hours=Booking.BATAS_BAYAR_JAM)
    for kedaluwarsa in Booking.objects.filter(user=request.user, status='unpaid', created_at__lt=batas):
        kedaluwarsa.batalkan()

    hari_ini = timezone.localdate()
    semua = (Booking.objects
            .filter(user=request.user)
            .select_related('jadwal', 'jadwal__paket'))

    if tab == 'aktif':
        # belum dibayar, atau sudah lunas tapi belum berangkat
        booking_list = semua.filter(
            Q(status='unpaid') | Q(status='paid', jadwal__tanggal_berangkat__gte=hari_ini)
        ).order_by('jadwal__tanggal_berangkat')
    elif tab == 'selesai':
        # ditandai selesai, atau sudah lunas dan tanggal berangkatnya sudah lewat
        booking_list = semua.filter(
            Q(status='completed') | Q(status='paid', jadwal__tanggal_berangkat__lt=hari_ini)
        ).order_by('-jadwal__tanggal_berangkat')
    else:
        booking_list = semua.filter(status='cancelled').order_by('-jadwal__tanggal_berangkat')

    return render(request, 'customer/riwayat.html', {
        'tab': tab,
        'booking_list': booking_list,
    })


# =========================================================
# TRIP MATCHMAKER
# =========================================================

TAB_TRIP = ('jelajah', 'posting', 'permintaan')


def _url_tab(tab):
    return f"{reverse('daftar_trip_matchmaker')}?tab={tab}"


def _trip_untuk_dijelajahi(request):
    """Trip yang muncul sebagai kartu swipe: belum lewat, masih ada slot,
    bukan milik sendiri, belum pernah diajukan, dan belum di-swipe kiri."""
    dilewati = request.session.get('trip_dilewati', [])
    qs = (TripPost.objects
        .filter(tanggal_berangkat__gte=timezone.localdate())
        .exclude(id__in=dilewati)
        .select_related('user'))
    if request.user.is_authenticated:
        sudah = list(TripJoinRequest.objects.filter(user=request.user)
                    .values_list('trip_post_id', flat=True))
        qs = qs.exclude(user=request.user).exclude(id__in=sudah)
    return [trip for trip in qs.order_by('-created_at') if trip.sisa_kuota_teman() > 0]


def daftar_trip_matchmaker(request):
    tab = request.GET.get('tab', 'jelajah')
    if tab not in TAB_TRIP:
        tab = 'jelajah'

    # tab Posting Trip dan Permintaan Saya butuh login
    if tab != 'jelajah' and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    konteks = {'tab': tab}

    if tab == 'jelajah':
        konteks['trip_list'] = _trip_untuk_dijelajahi(request)

    elif tab == 'posting':
        if request.method == 'POST':
            form = TripPostForm(request.POST, request.FILES)
            if form.is_valid():
                trip = form.save(commit=False)
                trip.user = request.user
                trip.save()
                messages.success(request, "Trip berhasil diposting. Tunggu teman yang tertarik bergabung!")
                return redirect(_url_tab('permintaan'))
        else:
            form = TripPostForm()
        konteks['form'] = form

    else:  # permintaan
        konteks['masuk'] = (TripJoinRequest.objects
                            .filter(trip_post__user=request.user)
                            .select_related('user', 'trip_post')
                            .order_by('-created_at'))
        konteks['keluar'] = (TripJoinRequest.objects
                            .filter(user=request.user)
                            .select_related('trip_post', 'trip_post__user')
                            .order_by('-created_at'))

    return render(request, 'customer/matchmaker.html', konteks)


def _proses_gabung(trip, user):
    """Aturan pengajuan gabung. Mengembalikan (berhasil, pesan)."""
    if trip.user == user:
        return False, "Tidak bisa mengajukan gabung ke trip buatan sendiri."
    if TripJoinRequest.objects.filter(trip_post=trip, user=user).exists():
        return False, "Kamu sudah pernah mengajukan gabung ke trip ini."
    if trip.sisa_kuota_teman() <= 0:
        return False, "Kuota trip ini sudah penuh."
    TripJoinRequest.objects.create(trip_post=trip, user=user)
    return True, "Pengajuan gabung berhasil dikirim, menunggu persetujuan."


@login_required
def ajukan_gabung_trip(request, trip_id):
    trip = get_object_or_404(TripPost, id=trip_id)
    berhasil, pesan = _proses_gabung(trip, request.user)
    (messages.success if berhasil else messages.error)(request, pesan)
    return redirect('daftar_trip_matchmaker')


@require_POST
def swipe_trip(request, trip_id):
    """Dipanggil lewat JavaScript saat kartu di-swipe (atau tombol X / hati ditekan)."""
    trip = get_object_or_404(TripPost, id=trip_id)
    arah = request.POST.get('arah')

    if arah == 'kiri':
        dilewati = request.session.get('trip_dilewati', [])
        if trip.id not in dilewati:
            dilewati.append(trip.id)
            request.session['trip_dilewati'] = dilewati
        return JsonResponse({'ok': True})

    if arah == 'kanan':
        if not request.user.is_authenticated:
            login_url = f"{reverse('login')}?next={_url_tab('jelajah')}"
            return JsonResponse({'ok': False, 'login': login_url}, status=401)
        berhasil, pesan = _proses_gabung(trip, request.user)
        return JsonResponse({'ok': berhasil, 'pesan': pesan})

    return JsonResponse({'ok': False, 'pesan': 'Arah swipe tidak valid.'}, status=400)


@login_required
@require_POST
def respon_permintaan_trip(request, req_id, aksi):
    # hanya pembuat trip yang boleh menerima/menolak
    permintaan = get_object_or_404(TripJoinRequest, id=req_id, trip_post__user=request.user)
    nama = permintaan.user.first_name or permintaan.user.username

    if permintaan.status != 'pending':
        messages.info(request, "Permintaan ini sudah diproses.")
    elif aksi == 'terima':
        try:
            permintaan.terima()
            messages.success(request, f"{nama} diterima di trip \"{permintaan.trip_post.judul}\".")
        except ValueError as e:
            messages.error(request, str(e))
    else:
        permintaan.tolak()
        messages.success(request, f"Permintaan dari {nama} ditolak.")

    return redirect(_url_tab('permintaan'))


# =========================================================
# CHATBOT
# =========================================================
import json as _json
from . import chatbot as _chatbot


@require_POST
def chatbot_api(request):
    try:
        data = _json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'reply': 'Permintaan tidak valid.'}, status=400)
    riwayat = data.get('messages', [])
    if not isinstance(riwayat, list) or not riwayat:
        return JsonResponse({'reply': 'Pesan kosong.'}, status=400)
    return JsonResponse({'reply': _chatbot.balas(riwayat)})
