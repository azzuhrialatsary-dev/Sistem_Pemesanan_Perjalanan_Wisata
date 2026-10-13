from customer_app.models import Booking


def panel_badge(request):
    """Jumlah pesanan belum bayar untuk titik merah di ikon lonceng (hanya di /panel/)."""
    if request.path.startswith('/panel/') and request.user.is_authenticated:
        return {'badge_belum_bayar': Booking.objects.filter(status='unpaid').count()}
    return {}
