from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory
from .models import User, Booking, Peserta


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full border border-slate-200 rounded-lg px-3 py-2'
            })


class BookingForm(forms.Form):
    jumlah_peserta = forms.IntegerField(
        min_value=1,
        label="Jumlah Peserta",
        widget=forms.NumberInput(attrs={
            'class': 'w-full border border-slate-200 rounded-lg px-3 py-2'
        })
    )


def get_peserta_formset(jumlah_form_kosong):
    """
    Dibuat sebagai fungsi (bukan formset siap pakai), supaya jumlah form
    kosong bisa ditentukan sesuai booking.jumlah_peserta tiap kali dipanggil,
    tanpa mengubah pengaturan global yang dipakai bersama semua request.
    """
    return inlineformset_factory(
        Booking,
        Peserta,
        fields=['nama_lengkap', 'no_identitas'],
        extra=jumlah_form_kosong,
        can_delete=False,
        widgets={
            'nama_lengkap': forms.TextInput(attrs={
                'class': 'w-full border border-slate-200 rounded-lg px-3 py-2',
                'placeholder': 'Nama lengkap sesuai KTP'
            }),
            'no_identitas': forms.TextInput(attrs={
                'class': 'w-full border border-slate-200 rounded-lg px-3 py-2',
                'placeholder': 'NIK / No. KTP'
            }),
        }
    )
