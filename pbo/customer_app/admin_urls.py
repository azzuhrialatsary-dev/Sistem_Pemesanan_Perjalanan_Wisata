from django.urls import path

from . import admin_views as v

urlpatterns = [
    path("", v.admin_dashboard, name="admin_dashboard"),

    path("paket/", v.paket_list, name="admin_paket"),
    path("paket/tambah/", v.paket_tambah, name="admin_paket_tambah"),
    path("paket/<int:pk>/edit/", v.paket_edit, name="admin_paket_edit"),
    path("paket/<int:pk>/hapus/", v.paket_hapus, name="admin_paket_hapus"),

    path("jadwal/", v.jadwal_list, name="admin_jadwal"),
    path("pesanan/", v.pesanan_list, name="admin_pesanan"),
    path("verifikasi/", v.verifikasi, name="admin_verifikasi"),
    path("laporan/", v.laporan, name="admin_laporan"),

    path("keluar/", v.admin_keluar, name="admin_keluar"),
]