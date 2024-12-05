from django.contrib import admin
from .models import CustomUser, Lapangan, Jadwal, Ulasan, Pemesanan

admin.site.register(CustomUser)
admin.site.register(Lapangan)
admin.site.register(Jadwal)
admin.site.register(Ulasan)
admin.site.register(Pemesanan)
