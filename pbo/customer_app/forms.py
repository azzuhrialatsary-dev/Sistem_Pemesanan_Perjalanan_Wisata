from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory
from .models import User, Booking, Peserta


class RegisterForm(UserCreationForm):
    """
    Form daftar sesuai desain: Nama lengkap, Email, No. HP, Password, Konfirmasi.
    Username tidak ditampilkan, dibuat otomatis dari email.
    """
    nama_lengkap = forms.CharField(max_length=150, label="Nama lengkap")
    email = forms.EmailField(label="Email")
    no_hp = forms.CharField(max_length=20, label="No. HP")

    class Meta:
        model = User
        fields = ['email', 'no_hp']

    field_order = ['nama_lengkap', 'email', 'no_hp', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = "Password"
        self.fields['password1'].help_text = ""
        self.fields['password2'].label = "Konfirmasi password"
        self.fields['password2'].help_text = ""
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full bg-white border border-slate-200 rounded-2xl px-4 py-2.5 '
                         'shadow-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20'
            })

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email ini sudah terdaftar.")
        return email

    def _buat_username(self):
        # username dibuat dari bagian depan email, ditambah angka kalau sudah dipakai
        dasar = self.cleaned_data['email'].split('@')[0][:140] or 'user'
        username, n = dasar, 1
        while User.objects.filter(username__iexact=username).exists():
            n += 1
            username = f"{dasar}{n}"
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['nama_lengkap']
        user.email = self.cleaned_data['email']
        user.no_hp = self.cleaned_data['no_hp']
        user.username = self._buat_username()
        if commit:
            user.save()
        return user


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
