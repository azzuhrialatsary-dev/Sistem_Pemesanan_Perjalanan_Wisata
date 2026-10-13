from django.utils import timezone
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import BaseFormSet, formset_factory, inlineformset_factory
from .models import User, Booking, Peserta, TripPost

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

GAYA_INPUT = ('w-full bg-white border border-slate-200 rounded-xl px-3.5 py-2 text-sm '
            'outline-none focus:border-primary focus:ring-2 focus:ring-primary/20')


class TripPostForm(forms.ModelForm):
    class Meta:
        model = TripPost
        fields = ['judul', 'destinasi', 'budget', 'tanggal_berangkat', 'tanggal_selesai',
                'kuota_teman', 'tags', 'deskripsi', 'foto']
        labels = {
            'judul': 'Judul trip',
            'destinasi': 'Destinasi',
            'budget': 'Budget per orang',
            'tanggal_berangkat': 'Tanggal mulai',
            'tanggal_selesai': 'Tanggal selesai',
            'kuota_teman': 'Jumlah slot',
            'tags': 'Gaya trip / tags',
            'deskripsi': 'Deskripsi',
            'foto': 'Foto',
        }
        widgets = {
            'judul': forms.TextInput(attrs={'placeholder': 'cth. Backpacker Labuan Bajo'}),
            'destinasi': forms.TextInput(attrs={'placeholder': 'Labuan Bajo, NTT'}),
            'budget': forms.NumberInput(attrs={'placeholder': '3500000', 'min': 0}),
            'tanggal_berangkat': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'kuota_teman': forms.NumberInput(attrs={'placeholder': '3', 'min': 1}),
            'tags': forms.TextInput(attrs={'placeholder': 'Backpacker, Laut, Foto'}),
            'deskripsi': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ceritakan rencana perjalananmu...'}),
            'foto': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tanggal_selesai'].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = GAYA_INPUT

    def clean(self):
        data = super().clean()
        mulai, selesai = data.get('tanggal_berangkat'), data.get('tanggal_selesai')
        if mulai and mulai < timezone.localdate():
            self.add_error('tanggal_berangkat', "Tanggal mulai tidak boleh sudah lewat.")
        if mulai and selesai and selesai < mulai:
            self.add_error('tanggal_selesai', "Tanggal selesai harus sama atau setelah tanggal mulai.")
        if data.get('kuota_teman') is not None and data['kuota_teman'] < 1:
            self.add_error('kuota_teman', "Minimal 1 slot.")
        return data

GAYA_INPUT_BOOKING = ('w-full bg-white border border-slate-200 rounded-2xl px-4 py-2 text-sm '
                      'outline-none focus:border-primary focus:ring-2 focus:ring-primary/20')


class PesertaForm(forms.ModelForm):
    jenis_kelamin = forms.ChoiceField(choices=Peserta.JENIS_KELAMIN, label="Jenis kelamin")

    class Meta:
        model = Peserta
        fields = ['nama_lengkap', 'no_identitas', 'tanggal_lahir', 'jenis_kelamin',
                  'kontak_darurat_nama', 'kontak_darurat_hp']
        labels = {
            'nama_lengkap': 'Nama lengkap',
            'no_identitas': 'NIK / No. Paspor',
            'tanggal_lahir': 'Tanggal lahir',
            'kontak_darurat_nama': 'Kontak darurat (nama)',
            'kontak_darurat_hp': 'No. HP kontak darurat',
        }
        widgets = {
            'tanggal_lahir': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nama in ('tanggal_lahir', 'kontak_darurat_nama', 'kontak_darurat_hp'):
            self.fields[nama].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = GAYA_INPUT_BOOKING
            if field.required:
                field.widget.attrs['required'] = True

    def clean_tanggal_lahir(self):
        tanggal = self.cleaned_data['tanggal_lahir']
        if tanggal and tanggal > timezone.localdate():
            raise forms.ValidationError("Tanggal lahir tidak boleh di masa depan.")
        return tanggal


class BasePesertaFormSet(BaseFormSet):
    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        # semua kartu peserta wajib diisi (tidak boleh dibiarkan kosong)
        form.empty_permitted = False
        return form


PesertaFormSet = formset_factory(
    PesertaForm, formset=BasePesertaFormSet,
    extra=0, min_num=1, validate_min=True, max_num=10, validate_max=True,
)

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
