from datetime import datetime, timedelta
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import CreateView , DetailView, ListView, FormView
from django.http import HttpResponseNotAllowed, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from .models import CustomUser, Lapangan, Jadwal, Pemesanan, Ulasan
from .forms import CustomUserCreationForm, CustomAuthenticationForm


# tampilan register
class RegisterView(FormView):
    template_name = 'auth/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f'Akun berhasil dibuat untuk {user.username}. Silakan login.')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        for msg in form.error_messages:
            messages.error(self.request, f'{msg}: {form.error_messages[msg]}')
        return super().form_invalid(form)

# tampilan login
def login_view(request):
    if request.user.is_authenticated:
        return redirect('landing')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f'Selamat datang kembali, {username}.')
                
                # Redirect based on user type
                if user.is_superuser:
                    return redirect('dashboard_admin')
                elif user.is_staff:
                    return redirect('dashboard_staff')
                else:
                    return redirect('dashboard_user')
            else:
                messages.error(request, 'Username atau password tidak valid.')
                form.add_error(None, 'Username atau password tidak valid.')
        else:
            messages.error(request, 'Username atau password tidak valid.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'auth/login.html', {'form': form})
    
# tampilan logout
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'Anda telah keluar.')
        return redirect('landing')
    return render(request, 'auth/logout.html')


def landing(request):
    return render(request, "public/landing.html",)


def about(request):
    return render(request, "public/about.html",)


# -----USER-----
@login_required
def dashboard_user(request):
    if request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied
    
    pemesanan = Pemesanan.objects.filter(
        user=request.user
    ).select_related(
        'jadwal',
        'jadwal__lapangan'
    ).order_by('-created_at')
    
    # hitung total kecuali pemesanan yang dibatalkan
    pesanan = pemesanan.exclude(status='dibatalkan')
    total = sum(pesan.hitung_harga() for pesan in pesanan)
    
    context = {
        'pemesanan': pemesanan,
        'total': total,
        'pending_bookings': pemesanan.filter(status='pending').count(),
        'completed_bookings': pemesanan.filter(status='selesai').count()
    }
    
    return render(request, 'user/dashboard_user.html', context)

# detail pemesanan untuk user
@login_required
def detail_pemesanan_user(request, pemesanan_id):
    if request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied
    
    pemesanan = get_object_or_404(Pemesanan, id=pemesanan_id, user=request.user)
    return render(request, 'user/detail_pemesanan_user.html', {
        'pemesanan': pemesanan
    })

# list lapangan
class LapanganListView(ListView):
    model = Lapangan
    template_name = 'public/list_lapangan.html'
    context_object_name = 'lapangan'
    
    def get_queryset(self):
        return Lapangan.objects.all()
        # return Lapangan.objects.all().filter(is_available=True)

# detail lapangan
class DetailLapanganView(LoginRequiredMixin, DetailView):
    model = Lapangan
    template_name = 'user/detail_lapangan.html'
    pk_url_kwarg = 'lapangan_id'
    context_object_name = 'lapangan'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dates = []
        
        # Get all unique dates from Jadwal
        jadwal_dates = Jadwal.objects.filter(
            lapangan=self.object,
            # is_available=True
        ).dates('tanggal', 'day')

        for date in jadwal_dates:
            jadwal = Jadwal.objects.filter(
                lapangan=self.object,
                tanggal=date,
                # is_available=True
            )
            dates.append({
                'date': date,
                'slots': jadwal
            })
            
        context['dates'] = dates
        return context

# pesan lapangan
class PemesananCreateView(LoginRequiredMixin, CreateView):
    model = Pemesanan
    template_name = "user/konfirmasi_pemesanan.html"
    fields = ['metode_pembayaran']
    success_url = reverse_lazy('dashboard_user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        jadwal = get_object_or_404(Jadwal, id=self.kwargs['jadwal_id'])

        # buat temp pemesanan untuk hitung harga
        temp_pemesanan = Pemesanan(jadwal=jadwal)
        harga = temp_pemesanan.hitung_harga()

        context.update({
            'jadwal': jadwal,
            'lapangan': jadwal.lapangan,
            'harga': harga
        })
        return context
    
    def form_valid(self, form):
        jadwal = get_object_or_404(Jadwal, id=self.kwargs['jadwal_id'])
        if not jadwal.is_available:
            messages.error(self.request, 'Jadwal tidak tersedia.')
            return self.form_invalid(form)

        form.instance.user = self.request.user
        form.instance.jadwal = jadwal
        jadwal.is_available = False
        jadwal.save()
        
        messages.success(self.request, 'Pemesanan berhasil dibuat.')
        return super().form_valid(form)

# cancel pesanan
@login_required
def cancel_pemesanan(request, pemesanan_id):
    pemesanan = get_object_or_404(Pemesanan, id=pemesanan_id, user=request.user)
    
    # Only allow cancellation of pending orders
    if pemesanan.status != 'pending':
        messages.error(request, 'Hanya pemesanan dengan status pending yang dapat dibatalkan.')
        return redirect('dashboard_user')
        
    if request.method == 'POST':
        # Update pemesanan status
        pemesanan.status = 'dibatalkan'
        pemesanan.save()
        
        # Make jadwal available again
        jadwal = pemesanan.jadwal
        jadwal.is_available = True 
        jadwal.save()
        
        messages.success(request, 'Pemesanan berhasil dibatalkan.')
        return redirect('dashboard_user')
        
    return render(request, 'user/konfirmasi_cancel_pemesanan.html', {'pemesanan': pemesanan})

# add ulasan
@login_required
def add_ulasan(request, lapangan_id):
    if request.method == 'POST':
        lapangan = get_object_or_404(Lapangan, id=lapangan_id)
        
        # cek apakah user sudah pernah memberikan ulasan untuk lapangan ini
        if Ulasan.objects.filter(user=request.user, lapangan=lapangan).exists():
            messages.error(request, 'Anda sudah memberikan ulasan untuk lapangan ini.')
            return redirect('detail_lapangan', lapangan_id=lapangan_id)
        
        rating = request.POST.get('rating')
        komentar = request.POST.get('komentar')
        
        # validasi rating
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError('Rating harus diantara 1-5')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('detail_lapangan', lapangan_id=lapangan_id)
        
        ulasan = Ulasan.objects.create(
            user=request.user,
            lapangan=lapangan,
            rating=rating,
            komentar=komentar
        )

        messages.success(request, 'Terima kasih atas ulasan Anda.')
        return redirect('detail_lapangan', lapangan_id=lapangan_id)

    return HttpResponseNotAllowed(['POST'])

# -----STAFF-----
@staff_member_required
def dashboard_staff(request):
    # pemesanan
    pemesanan_list = Pemesanan.objects.all().order_by('-created_at')
    pemesanan_paginator = Paginator(pemesanan_list, 10)
    pemesanan_page = request.GET.get('pemesanan_page')
    pemesanan = pemesanan_paginator.get_page(pemesanan_page)

    # lapangan
    lapangan_list = Lapangan.objects.all()
    for field in lapangan_list:
        field.average_rating = field.avg_rating()
    lapangan_paginator = Paginator(lapangan_list, 10)
    lapangan_page = request.GET.get('lapangan_page')
    lapangan = lapangan_paginator.get_page(lapangan_page)
    
    # ulasan
    ulasan_list = Ulasan.objects.all().order_by('-created_at')
    ulasan_paginator = Paginator(ulasan_list, 10)
    ulasan_page = request.GET.get('ulasan_page')
    ulasan = ulasan_paginator.get_page(ulasan_page)

    # user
    users = CustomUser.objects.filter(is_staff=False, is_superuser=False).order_by('username')
    
    context = {
        'pemesanan': pemesanan,
        'users': users,
        'lapangan': lapangan,
        'ulasan': ulasan,
        'total_lapangan': lapangan_list.count(),
        'total_pemesanan': pemesanan_list.count(),
        'pending_pemesanan': pemesanan_list.filter(status='pending').count(),
        'diterima_pemesanan': pemesanan_list.filter(status='diterima').count(),
        'completed_pemesanan': pemesanan_list.filter(status='selesai').count(),
    }
    
    return render(request, 'staff/dashboard_staff.html', context)

# detail pemesanan untuk staff
@staff_member_required 
def detail_pemesanan_staff(request, pk):
    pemesanan = get_object_or_404(Pemesanan, pk=pk)
    return render(request, 'staff/detail_pemesanan_staff.html', {
        'pemesanan': pemesanan
    })

# update status pemesanan
@login_required
def update_pemesanan(request, pk):
    if not request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied
    
    if request.method == 'POST':
        pemesanan = get_object_or_404(Pemesanan, pk=pk)
        status = request.POST.get('status')
        
        if status in ['dibatalkan', 'pending', 'diterima', 'selesai']:
            pemesanan.status = status
            pemesanan.staff = request.user
            pemesanan.save()
            messages.success(request, f'Status pemesanan oleh {pemesanan.user.username} berhasil diubah menjadi {status}.')
        else:
            messages.error(request, 'Status tidak valid')
            
        return redirect('dashboard_staff')
        
    return HttpResponseNotAllowed(['POST'])

# ambil jadwal tersedia
@login_required
def get_available_jadwal(request):
    lapangan_id = request.GET.get('lapangan')
    tanggal = request.GET.get('tanggal')
    
    if not lapangan_id or not tanggal:
        return JsonResponse([], safe=False)
    
    jadwal = Jadwal.objects.filter(
        lapangan_id=lapangan_id,
        tanggal=tanggal,
        is_available=True
    ).values('id', 'jam_mulai', 'jam_selesai')
    
    return JsonResponse(list(jadwal), safe=False)

# add pemesanan
@login_required
def add_pemesanan(request):
    if not request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied
    
    if request.method == 'POST':
        user_id = request.POST.get('user')
        jadwal_id = request.POST.get('jadwal')
        metode_pembayaran = request.POST.get('metode_pembayaran')
        
        user = get_object_or_404(CustomUser, id=user_id, is_staff=False, is_superuser=False)
        jadwal = get_object_or_404(Jadwal, id=jadwal_id)
        
        if not jadwal.is_available:
            messages.error(request, 'Jadwal tidak tersedia.')
            return redirect('dashboard_staff')
        
        pemesanan = Pemesanan.objects.create(
            user=user,
            jadwal=jadwal,
            metode_pembayaran=metode_pembayaran,
            status='diterima',
            staff=request.user
        )
        
        jadwal.is_available = False
        jadwal.save()
        
        messages.success(request, f'Pemesanan oleh {user.username} berhasil dibuat.')
        return redirect('dashboard_staff')
    
    return HttpResponseNotAllowed(['POST'])
    
# hapus ulasan
@login_required
def delete_ulasan(request, pk): 
    if not request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied
    
    ulasan = get_object_or_404(Ulasan, pk=pk)
    ulasan.delete()
    messages.success(request, 'Ulasan berhasil dihapus.')

    if request.user.is_superuser:
        return redirect('manage_ulasan')
    return redirect('dashboard_staff')
    
    
# -----ADMIN-----
@login_required
def dashboard_admin(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    pemesanan_list = Pemesanan.objects.all().order_by('-created_at')
    paginator = Paginator(pemesanan_list, 10)
    
    page = request.GET.get('page')
    pemesanan = paginator.get_page(page)

    context = {
        'pemesanan': pemesanan,
        'total_users': CustomUser.objects.filter(is_staff=False, is_superuser=False).count(),
        'total_staff': CustomUser.objects.filter(is_staff=True, is_superuser=False).count(),
        'total_pemesanan': pemesanan_list.count(),
        'pending_pemesanan': pemesanan_list.filter(status='pending').count(),
    }
    
    return render(request, 'admin/dashboard_admin.html', context)

# manage lapangan
class ManageLapanganView(LoginRequiredMixin, ListView):
    model = Lapangan
    template_name = 'admin/manage_lapangan.html'
    context_object_name = 'lapangan'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
    
# add lapangan
@login_required
def add_lapangan(request):
    if not request.user.is_superuser:
        raise PermissionDenied
        
    if request.method == 'POST':
        nama = request.POST.get('nama')
        deskripsi = request.POST.get('deskripsi')
        harga_per_jam = request.POST.get('harga_per_jam')
        gambar = request.FILES.get('gambar')
        
        lapangan = Lapangan.objects.create(
            nama=nama,
            deskripsi=deskripsi,
            harga_per_jam=harga_per_jam,
            gambar=gambar
        )
        messages.success(request, 'Lapangan berhasil ditambahkan')
        return redirect('manage_lapangan')
        
    return HttpResponseNotAllowed(['POST'])

# edit lapangan
@login_required
def edit_lapangan(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
        
    lapangan = get_object_or_404(Lapangan, pk=pk)
    
    if request.method == 'POST':
        lapangan.nama = request.POST.get('nama')
        lapangan.deskripsi = request.POST.get('deskripsi')
        lapangan.harga_per_jam = request.POST.get('harga_per_jam')
        
        if 'gambar' in request.FILES:
            lapangan.gambar = request.FILES['gambar']
            
        lapangan.save()
        messages.success(request, 'Lapangan berhasil diupdate')
        return redirect('manage_lapangan')
        
    return HttpResponseNotAllowed(['POST'])

# delete lapangan
@login_required
def delete_lapangan(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
        
    lapangan = get_object_or_404(Lapangan, pk=pk)
    lapangan.delete()
    messages.success(request, 'Lapangan berhasil dihapus')
    return redirect('manage_lapangan')

# manage jadwal
def manage_jadwal(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    # filter
    lapangan_id = request.GET.get('lapangan')
    year = request.GET.get('year')
    month = request.GET.get('month')
    tanggal = request.GET.get('tanggal')

    jadwal_list = Jadwal.objects.all()
    
    if lapangan_id:
        jadwal_list = jadwal_list.filter(lapangan_id=lapangan_id)
        
    if tanggal:
        jadwal_list = jadwal_list.filter(tanggal=tanggal)
        # group jadwal by lapangan
        dates = {}
        lapangan_list = Lapangan.objects.all()
        for lapangan in lapangan_list:
            schedules = jadwal_list.filter(lapangan=lapangan).order_by('jam_mulai')
            if schedules.exists():
                dates[lapangan] = list(schedules)
    else:
        if month:
            jadwal_list = jadwal_list.filter(tanggal__month=month)
        if year:
            jadwal_list = jadwal_list.filter(tanggal__year=year)
        # group jadwal by date
        dates = {}
        for jadwal in jadwal_list.order_by('tanggal', 'jam_mulai'):
            if jadwal.tanggal not in dates:
                dates[jadwal.tanggal] = []
            dates[jadwal.tanggal].append(jadwal)
        
    # sort by date
    sorted_dates = sorted(dates.items(), key=lambda x: x[0].nama if isinstance(x[0], Lapangan) else x[0])
        
    years = Jadwal.objects.dates('tanggal', 'year').values_list('tanggal__year', flat=True)
    if not years:
        years = [datetime.now().year]
    
    # pagination
    paginator = Paginator(sorted_dates, 7)
    page = request.GET.get('page')
    dates_page = paginator.get_page(page)
    
    month_choices = [
        (1, 'Januari'),
        (2, 'Februari'), 
        (3, 'Maret'),
        (4, 'April'),
        (5, 'Mei'),
        (6, 'Juni'),
        (7, 'Juli'),
        (8, 'Agustus'),
        (9, 'September'),
        (10, 'Oktober'),
        (11, 'November'),
        (12, 'Desember')
    ]
    
    context = {
        'dates': dates_page,
        'lapangan': Lapangan.objects.all(),
        'selected_lapangan': lapangan_id,
        'selected_tanggal': tanggal,
        'selected_month': month,
        'selected_year': year,
        'months': month_choices,
        'years': years,
    }
    return render(request, 'admin/manage_jadwal.html', context)

# generate jadwal
@login_required 
def generate_jadwal(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        try:
            # Get form data
            lapangan_id = request.POST.get('lapangan')
            tanggal_mulai = request.POST.get('tanggal_mulai')
            tanggal_selesai = request.POST.get('tanggal_selesai')
            jam_mulai = request.POST.get('jam_mulai')
            jam_selesai = request.POST.get('jam_selesai')
            durasi = request.POST.get('durasi')

            # Validate durasi
            try:
                durasi = int(durasi)
                if durasi < 30 or durasi % 30 != 0:
                    raise ValueError("Durasi harus kelipatan 30 menit")
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('manage_jadwal')

            # Process data
            lapangan = Lapangan.objects.get(id=lapangan_id)
            start_date = datetime.strptime(tanggal_mulai, '%Y-%m-%d').date()
            end_date = datetime.strptime(tanggal_selesai, '%Y-%m-%d').date()
            start_time = datetime.strptime(jam_mulai, '%H:%M').time()
            end_time = datetime.strptime(jam_selesai, '%H:%M').time()
            
            current_date = start_date
            while current_date <= end_date:
                current_time = datetime.combine(current_date, start_time)
                end_datetime = datetime.combine(current_date, end_time)
                
                while current_time < end_datetime:
                    # Calculate end time for current slot
                    next_time = current_time + timedelta(minutes=durasi)
                    
                    if next_time.time() <= end_time:
                        # Create schedule
                        Jadwal.objects.create(
                            lapangan=lapangan,
                            tanggal=current_date,
                            jam_mulai=current_time.time(),
                            jam_selesai=next_time.time()
                        )
                        
                        # Add 30 min break
                        current_time = next_time + timedelta(minutes=30)
                    else:
                        break
                
                current_date += timedelta(days=1)
                
            messages.success(request, 'Jadwal berhasil dibuat')

        except ValueError as e:
            messages.error(request, f'Error format input: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            
        return redirect('manage_jadwal')
    
    return HttpResponseNotAllowed(['POST'])

# edit jadwal
@login_required
def edit_jadwal(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    jadwal = get_object_or_404(Jadwal, pk=pk)
    
    if request.method == 'POST':
        try:
            tanggal = request.POST.get('tanggal')
            jam_mulai = request.POST.get('jam_mulai') 
            jam_selesai = request.POST.get('jam_selesai')
            is_available = request.POST.get('is_available') == 'True'

            jadwal.tanggal = tanggal
            jadwal.jam_mulai = jam_mulai
            jadwal.jam_selesai = jam_selesai
            jadwal.is_available = is_available
            jadwal.save()
            
            messages.success(request, 'Jadwal berhasil diupdate')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            
        return redirect('manage_jadwal')
        
    return HttpResponseNotAllowed(['POST'])

# detail pemesanan untuk admin
@login_required
def detail_pemesanan_admin(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    pemesanan = get_object_or_404(Pemesanan.objects.select_related('user', 'jadwal', 'jadwal__lapangan'), pk=pk)
    
    context = {
        'pemesanan': pemesanan
    }
    return render(request, 'admin/detail_pemesanan_admin.html', context)

# hapus pemesanan
@login_required
def hapus_pemesanan(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    pemesanan = get_object_or_404(Pemesanan, pk=pk)
    
    if request.method == 'POST':
        jadwal = pemesanan.jadwal
        jadwal.is_available = True
        jadwal.save()
        
        pemesanan.delete()
        
        messages.success(request, 'Pemesanan berhasil dihapus.')
        return redirect('dashboard_admin')
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# manage users
@login_required
def manage_users(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    users = CustomUser.objects.filter(is_staff=False, is_superuser=False).order_by('username')
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        nama_lengkap = request.POST.get('nama_lengkap')
        no_hp = request.POST.get('no_hp')
        
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username sudah digunakan.')
        elif CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email sudah digunakan.')
        else:
            user = CustomUser.objects.create_user(username=username, email=email, password=password, nama_lengkap=nama_lengkap, no_hp=no_hp)
            messages.success(request, 'User berhasil ditambahkan.')
        
    return render(request, 'admin/manage_users.html', {'users': users})

# update users
@login_required
def update_users(request, id):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=id)
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        
        password = request.POST.get('password')
        if password:
            user.set_password(password)
            
        user.save()
        messages.success(request, 'User berhasil diupdate.')
        
    return redirect('manage_users')

# hapus users
@login_required
def hapus_users(request, id):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    user = get_object_or_404(CustomUser, id=id)
    user.delete()
    messages.success(request, 'User berhasil dihapus.')
    return redirect('manage_users')

# manage staff
@login_required
def manage_staff(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    staff = CustomUser.objects.filter(is_staff=True, is_superuser=False).order_by('username')
    return render(request, 'admin/manage_staff.html', {'staff': staff})

# add staff
@login_required
def add_staff(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        nama_lengkap = request.POST.get('nama_lengkap')
        no_hp = request.POST.get('no_hp')
        
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username sudah digunakan.')
        elif CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email sudah digunakan.')
        else:
            user = CustomUser.objects.create_user(username=username, email=email, password=password, nama_lengkap=nama_lengkap, no_hp=no_hp, is_staff=True)
            messages.success(request, 'Staff berhasil ditambahkan.')
            
    return redirect('manage_staff')

# update staff
def update_staff(request, id):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    if request.method == 'POST':
        staff = get_object_or_404(CustomUser, id=id)
        staff.username = request.POST.get('username')
        staff.email = request.POST.get('email')
        staff.nama_lengkap = request.POST.get('nama_lengkap')
        staff.no_hp = request.POST.get('no_hp')
        
        password = request.POST.get('password')
        if password:
            staff.set_password(password)
            
        staff.save()
        messages.success(request, 'Staff berhasil diupdate.')
        
    return redirect('manage_staff')

# hapus staff
def hapus_staff(request, id):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    if request.method == 'POST':
        staff = get_object_or_404(CustomUser, id=id)
        staff.delete()
        messages.success(request, 'Staff berhasil dihapus.')
        
    return redirect('manage_staff')

# manage ulasan
@login_required
def manage_ulasan(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    ulasan_list = Ulasan.objects.all().order_by('-created_at')

    search = request.GET.get('search', '')
    if search:
        ulasan_list = ulasan_list.filter(
            Q(user__username__icontains=search) |
            Q(lapangan__nama__icontains=search) |
            Q(komentar__icontains=search)
        )
    
    paginator = Paginator(ulasan_list, 10)
    page = request.GET.get('page')
    ulasan = paginator.get_page(page)
    
    context = {
        'ulasan': ulasan,
        'search': search
    }
    
    return render(request, 'admin/manage_ulasan.html', context)
