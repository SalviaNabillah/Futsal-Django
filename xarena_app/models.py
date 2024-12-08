from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta
from decimal import Decimal


# custom user model
class CustomUser(AbstractUser):
    nama_lengkap = models.CharField(max_length=100, blank=True, null=True)
    no_hp = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.username


# lapangan model
class Lapangan(models.Model):
    nama = models.CharField(max_length=100)
    deskripsi = models.TextField(max_length=500)
    harga_per_jam = models.DecimalField(max_digits=10, decimal_places=2)
    gambar = models.ImageField(upload_to='lapangan_images/', blank=True, null=True)
    is_available = models.BooleanField(default=True)

    def avg_rating(self):
        ratings = Ulasan.objects.filter(lapangan=self).values_list('rating', flat=True)
        if ratings:
            return sum(ratings) / len(ratings)
        return 0

    def __str__(self):
        return self.nama


# jadwal model
class Jadwal(models.Model):
    lapangan = models.ForeignKey(Lapangan, on_delete=models.CASCADE)
    tanggal = models.DateField()
    jam_mulai = models.TimeField()
    jam_selesai = models.TimeField()
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.lapangan.nama} - {self.tanggal} ({self.jam_mulai} - {self.jam_selesai})"


# ulasan model
class Ulasan(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ulasan_user',
        help_text="User yang memberikan ulasan"
    )
    lapangan = models.ForeignKey(Lapangan, on_delete=models.CASCADE, help_text="Lapangan yang diulas")
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    komentar = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ulasan {self.rating} oleh {self.user.username} untuk {self.lapangan.nama}"


# pemesanan model
class Pemesanan(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pemesanan_user',
        help_text="User yang melakukan pemesanan"
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='pemesanan_staff',
        help_text="Staff yang memproses pemesanan"
    )
    jadwal = models.ForeignKey(Jadwal, on_delete=models.CASCADE, help_text="Jadwal pemesanan")
    metode_pembayaran = models.CharField(max_length=20, choices=(
        ('transfer', 'Transfer Bank'),
        ('cash', 'Cash'),
    ), default='transfer')
    status = models.CharField(max_length=20, choices=(
        ('pending', 'Pending'),
        ('diterima', 'Diterima'),
        ('selesai', 'Selesai'),
        ('dibatalkan', 'Dibatalkan'),
    ), default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def hitung_harga(self):
        durasi = timedelta(
            hours=self.jadwal.jam_selesai.hour, minutes=self.jadwal.jam_selesai.minute
        ) - timedelta(
            hours=self.jadwal.jam_mulai.hour, minutes=self.jadwal.jam_mulai.minute
        )
        total_jam = Decimal(str(durasi.total_seconds() / 3600))
        return self.jadwal.lapangan.harga_per_jam * total_jam

    def __str__(self):
        return f"Pesanan oleh {self.user.username} - {self.status}"
