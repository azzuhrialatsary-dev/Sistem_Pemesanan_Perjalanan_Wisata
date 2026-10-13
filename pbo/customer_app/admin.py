from django.contrib import admin
from .models import (
    User, Paket, FotoPaket, Itinerary, Jadwal, Booking,
    Peserta, Tiket, TripPost, TripJoinRequest
)


class FotoPaketInline(admin.TabularInline):
    model = FotoPaket
    extra = 1


class ItineraryInline(admin.TabularInline):
    model = Itinerary
    extra = 1


class JadwalInline(admin.TabularInline):
    model = Jadwal
    extra = 1


@admin.register(Paket)
class PaketAdmin(admin.ModelAdmin):
    list_display = ('nama', 'destinasi', 'kategori', 'harga', 'rating')
    inlines = [FotoPaketInline, ItineraryInline, JadwalInline]


admin.site.register(User)
admin.site.register(Itinerary)
admin.site.register(Jadwal)
admin.site.register(Booking)
admin.site.register(Peserta)
admin.site.register(Tiket)
admin.site.register(TripPost)
admin.site.register(TripJoinRequest)