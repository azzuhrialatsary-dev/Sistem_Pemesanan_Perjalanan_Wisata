from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='panel_dashboard'),

    path('paket/', views.paket_list, name='panel_paket'),
    path('paket/tambah/', views.paket_form, name='panel_paket_tambah'),
    path('paket/<int:paket_id>/edit/', views.paket_form, name='panel_paket_edit'),
    path('paket/<int:paket_id>/hapus/', views.paket_hapus, name='panel_paket_hapus'),

    path('jadwal/', views.jadwal_list, name='panel_jadwal'),
    path('jadwal/tambah/', views.jadwal_form, name='panel_jadwal_tambah'),
    path('jadwal/<int:jadwal_id>/edit/', views.jadwal_form, name='panel_jadwal_edit'),
    path('jadwal/<int:jadwal_id>/hapus/', views.jadwal_hapus, name='panel_jadwal_hapus'),

    path('pesanan/', views.pesanan_list, name='panel_pesanan'),
    path('pesanan/<int:booking_id>/', views.pesanan_detail, name='panel_pesanan_detail'),
    path('pesanan/<int:booking_id>/aksi/', views.pesanan_aksi, name='panel_pesanan_aksi'),

    path('verifikasi/', views.verifikasi, name='panel_verifikasi'),

    path('laporan/', views.laporan, name='panel_laporan'),
    path('laporan/ekspor/', views.laporan_ekspor, name='panel_laporan_ekspor'),
]
