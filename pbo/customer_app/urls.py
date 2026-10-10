from django.urls import path
from . import views

urlpatterns = [
    # Halaman umum
    path('', views.home, name='home'),
    path('paket/', views.daftar_paket, name='daftar_paket'),
    path('paket/<int:paket_id>/', views.detail_paket, name='detail_paket'),

    # Autentikasi
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Booking, pembayaran, tiket
    path('jadwal/<int:jadwal_id>/booking/', views.buat_booking, name='buat_booking'),
    path('booking/<int:booking_id>/peserta/', views.isi_peserta, name='isi_peserta'),
    path('booking/<int:booking_id>/bayar/', views.payment, name='payment'),
    path('booking/<int:booking_id>/tiket/', views.lihat_tiket, name='lihat_tiket'),
    path('riwayat/', views.riwayat_booking, name='riwayat_booking'),

    # Trip Matchmaker
    path('trip-matchmaker/', views.daftar_trip_matchmaker, name='daftar_trip_matchmaker'),
    path('trip-matchmaker/<int:trip_id>/gabung/', views.ajukan_gabung_trip, name='ajukan_gabung_trip'),
]
