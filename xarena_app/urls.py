from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('about/', views.about, name='about'),
    
    # auth
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # user
    path('dashboard/', views.dashboard_user, name='dashboard_user'),
    path('lapangan/', views.LapanganListView.as_view(), name='list_lapangan'),
    path('lapangan/<int:lapangan_id>/', views.DetailLapanganView.as_view(), name='detail_lapangan'),
    path('lapangan/<int:lapangan_id>/ulasan/', views.add_ulasan, name='add_ulasan'),
    
    path('pesan/<int:jadwal_id>/', views.PemesananCreateView.as_view(), name='pesan_lapangan'),
    path('konfirmasi-pemesanan/<int:jadwal_id>/', views.PemesananCreateView.as_view(), name='konfirmasi_pemesanan'),
    path('pemesanan/cancel/<int:pemesanan_id>/', views.cancel_pemesanan, name='cancel_pemesanan'),
    path('pemesanan/<int:pemesanan_id>/', views.detail_pemesanan_user, name='detail_pemesanan_user'),
    
    # staff
    path('staff/dashboard/', views.dashboard_staff, name='dashboard_staff'),
    path('staff/pemesanan/<int:pk>/', views.detail_pemesanan_staff, name='detail_pemesanan_staff'),
    path('staff/pemesanan/<int:pk>/update/', views.update_pemesanan, name='update_pemesanan'),
    
    path('pemesanan/add/', views.add_pemesanan, name='add_pemesanan'),
    path('staff/ulasan/<int:pk>/delete/', views.delete_ulasan, name='delete_ulasan'),

    # admin
    path('adm/dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('adm/lapangan/', views.ManageLapanganView.as_view(), name='manage_lapangan'),
    path('adm/lapangan/add/', views.add_lapangan, name='add_lapangan'),
    path('adm/lapangan/<int:pk>/edit/', views.edit_lapangan, name='edit_lapangan'),
    path('adm/lapangan/<int:pk>/delete/', views.delete_lapangan, name='delete_lapangan'),
    
    path('adm/jadwal/', views.manage_jadwal, name='manage_jadwal'),
    path('adm/jadwal/generate/', views.generate_jadwal, name='generate_jadwal'),
    path('adm/jadwal/<int:pk>/edit/', views.edit_jadwal, name='edit_jadwal'),
    
    path('adm/pemesanan/<int:pk>/', views.detail_pemesanan_admin, name='detail_pemesanan_admin'),
    path('adm/pemesanan/<int:pk>/hapus/', views.hapus_pemesanan, name='hapus_pemesanan_admin'),

    path('adm/users/', views.manage_users, name='manage_users'),
    path('adm/users/<int:id>/update/', views.update_users, name='update_users'),
    path('adm/users/<int:id>/hapus/', views.hapus_users, name='hapus_users'),
    
    path('adm/staff/', views.manage_staff, name='manage_staff'),
    path('adm/staff/add/', views.add_staff, name='add_staff'),
    path('adm/staff/<int:id>/update/', views.update_staff, name='update_staff'),
    path('adm/staff/<int:id>/hapus/', views.hapus_staff, name='hapus_staff'),
    
    path('adm/reports/', views.admin_reports, name='admin_reports'),

    # api
    path('api/jadwal/', views.get_available_jadwal, name='get_jadwal'),
]