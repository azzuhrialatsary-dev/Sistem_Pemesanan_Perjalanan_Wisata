from django import forms
from django.utils import timezone

from .models import Jadwal, Paket

INPUT = (
    "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm "
    "outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
)


class PaketAdminForm(forms.ModelForm):
    class Meta:
        model = Paket
        fields = ["nama", "destinasi", "kategori", "harga", "durasi_hari", "rating", "deskripsi", "foto"]
        labels = {
            "nama": "Nama paket",
            "destinasi": "Destinasi",
            "kategori": "Kategori",
            "harga": "Harga (Rp)",
            "durasi_hari": "Durasi (hari)",
            "rating": "Rating (0.0 - 5.0)",
            "deskripsi": "Deskripsi",
            "foto": "Foto",
        }
        widgets = {
            "nama": forms.TextInput(attrs={"class": INPUT}),
            "destinasi": forms.TextInput(attrs={"class": INPUT}),
            "kategori": forms.Select(attrs={"class": INPUT}),
            "harga": forms.NumberInput(attrs={"class": INPUT, "min": 1, "step": 50000}),
            "durasi_hari": forms.NumberInput(attrs={"class": INPUT, "min": 1}),
            "rating": forms.NumberInput(attrs={"class": INPUT, "min": 0, "max": 5, "step": "0.1"}),
            "deskripsi": forms.Textarea(attrs={"class": INPUT, "rows": 4}),
            "foto": forms.ClearableFileInput(attrs={"class": INPUT, "accept": "image/*"}),
        }

    def clean_harga(self):
        harga = self.cleaned_data["harga"]
        if harga < 1:
            raise forms.ValidationError("Harga harus lebih dari 0.")
        return harga

    def clean_durasi_hari(self):
        durasi = self.cleaned_data["durasi_hari"]
        if durasi < 1:
            raise forms.ValidationError("Durasi minimal 1 hari.")
        return durasi

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if rating < 0 or rating > 5:
            raise forms.ValidationError("Rating harus antara 0 dan 5.")
        return rating


class JadwalAdminForm(forms.ModelForm):
    """Form 'Tambah Jadwal'. kuota_tersisa otomatis diisi sama dengan kuota total."""

    class Meta:
        model = Jadwal
        fields = ["paket", "tanggal_berangkat", "kuota_total"]
        labels = {
            "paket": "Paket",
            "tanggal_berangkat": "Tanggal berangkat",
            "kuota_total": "Kuota",
        }
        widgets = {
            "paket": forms.Select(attrs={"class": INPUT}),
            "tanggal_berangkat": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "kuota_total": forms.NumberInput(attrs={"class": INPUT, "min": 1}),
        }

    def clean_tanggal_berangkat(self):
        tgl = self.cleaned_data["tanggal_berangkat"]
        if tgl < timezone.localdate():
            raise forms.ValidationError("Tanggal keberangkatan tidak boleh di masa lalu.")
        return tgl

    def clean_kuota_total(self):
        kuota = self.cleaned_data["kuota_total"]
        if kuota < 1:
            raise forms.ValidationError("Kuota minimal 1.")
        return kuota

    def clean(self):
        cleaned = super().clean()
        paket, tgl = cleaned.get("paket"), cleaned.get("tanggal_berangkat")
        if paket and tgl and Jadwal.objects.filter(paket=paket, tanggal_berangkat=tgl).exists():
            raise forms.ValidationError("Jadwal untuk paket dan tanggal ini sudah ada.")
        return cleaned

    def save(self, commit=True):
        jadwal = super().save(commit=False)
        jadwal.kuota_tersisa = jadwal.kuota_total
        if commit:
            jadwal.save()
        return jadwal


class VerifikasiForm(forms.Form):
    kode = forms.CharField(
        max_length=30,
        label="Kode booking / tiket",
        widget=forms.TextInput(attrs={"class": INPUT + " text-base py-3", "placeholder": "BK-3F9A21CD",
                                      "autofocus": True, "autocomplete": "off"}),
    )

    def clean_kode(self):
        return self.cleaned_data["kode"].strip().upper()


class LaporanForm(forms.Form):
    JENIS_CHOICES = [
        ("pendapatan", "Laporan Pendapatan"),
        ("pesanan", "Laporan Pesanan"),
        ("okupansi", "Laporan Okupansi Jadwal"),
    ]
    FORMAT_CHOICES = [("excel", "Excel (.xlsx)"), ("pdf", "PDF")]

    jenis = forms.ChoiceField(choices=JENIS_CHOICES, label="Jenis laporan",
                              widget=forms.Select(attrs={"class": INPUT}))
    tanggal_dari = forms.DateField(label="Dari tanggal",
                                   widget=forms.DateInput(attrs={"class": INPUT, "type": "date"}))
    tanggal_sampai = forms.DateField(label="Sampai tanggal",
                                     widget=forms.DateInput(attrs={"class": INPUT, "type": "date"}))
    format = forms.ChoiceField(choices=FORMAT_CHOICES, label="Format file",
                               widget=forms.Select(attrs={"class": INPUT}))

    def clean(self):
        cleaned = super().clean()
        d1, d2 = cleaned.get("tanggal_dari"), cleaned.get("tanggal_sampai")
        if d1 and d2 and d1 > d2:
            raise forms.ValidationError("Tanggal 'Dari' tidak boleh melebihi tanggal 'Sampai'.")
        return cleaned