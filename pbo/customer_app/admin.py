from django.contrib import admin
from .models import (
    User, Paket, Itinerary, Jadwal, Booking,
    Peserta, Tiket, TripPost, TripJoinRequest
)

admin.site.register(User)
admin.site.register(Paket)
admin.site.register(Itinerary)
admin.site.register(Jadwal)
admin.site.register(Booking)
admin.site.register(Peserta)
admin.site.register(Tiket)
admin.site.register(TripPost)
admin.site.register(TripJoinRequest)
