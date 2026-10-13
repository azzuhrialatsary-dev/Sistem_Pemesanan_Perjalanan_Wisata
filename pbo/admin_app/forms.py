from django import forms
from django.forms import inlineformset_factory

from customer_app.models import Paket, Itinerary, Jadwal

# class CSS yang dipakai semua input supaya tampilannya seragam
INPUT = ("w-full bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 text-sm "
         "focus:ring-2 focus:ring-brand-500 outline-none")


class StyledFormMixin:
    """Beri class Tailwind ke semua field secara otomatis."""

    def _style(self):
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', INPUT)


class PaketForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Paket
        fields = ['nama', 'destinasi', 'kategori', 'harga', 'durasi_hari',
                  'rating', 'foto', 'deskripsi']
        widgets = {'deskripsi': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields['foto'].widget.attrs['class'] = INPUT + ' file:mr-3'

    def clean_rating(self):
        r = self.cleaned_data['rating']
        if r < 0 or r > 5:
            raise forms.ValidationError("Rating harus antara 0 sampai 5.")
        return r


class ItineraryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Itinerary
        fields = ['hari_ke', 'judul_kegiatan', 'deskripsi']
        widgets = {'deskripsi': forms.TextInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


ItineraryFormSet = inlineformset_factory(
    Paket, Itinerary, form=ItineraryForm, extra=2, can_delete=True,
)


class JadwalForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Jadwal
        fields = ['paket', 'tanggal_berangkat', 'kuota_total']
        widgets = {'tanggal_berangkat': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        # saat edit, jumlah kursi yang sudah terisi tidak boleh "hilang"
        self.terisi = 0
        if self.instance.pk:
            self.terisi = self.instance.kuota_total - self.instance.kuota_tersisa

    def clean_kuota_total(self):
        total = self.cleaned_data['kuota_total']
        if total < 1:
            raise forms.ValidationError("Kuota minimal 1.")
        if total < self.terisi:
            raise forms.ValidationError(
                f"Kuota tidak boleh di bawah jumlah kursi yang sudah terisi ({self.terisi})."
            )
        return total

    def save(self, commit=True):
        jadwal = super().save(commit=False)
        # kuota_tersisa = kuota baru dikurangi kursi yang sudah terisi
        jadwal.kuota_tersisa = jadwal.kuota_total - self.terisi
        if commit:
            jadwal.save()
        return jadwal
