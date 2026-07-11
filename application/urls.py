"""
URL configuration for Autohealz project.
"""

from django.urls import path
from application import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    

    # ── Public pages ──────────────────────────────────────────────
    path('', views.index, name='home'),
    path('contact/', views.contact, name='contact'),

    # ── Auth ──────────────────────────────────────────────────────
    path('login/', views.login_user, name='login'),
    path('sign/', views.sign, name='sign'),
    path('logout/', views.logout_user, name='logout'),
    path('change_password/', views.change_password, name='change_password'),

    # ── Booking ───────────────────────────────────────────────────
    path('book-appointment/', views.bookappointment, name='BookAppointment'),
    path('get-booked-slots/', views.get_booked_slots, name='get_booked_slots'),

    # ── Estimation ────────────────────────────────────────────────
    path('estimate/', views.estimate, name='estimate'),
    path('results/', views.results, name='results'),
    path('alternative/', views.alternative, name='alternative'),

    # ── Dashboard ─────────────────────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── Enquiries ─────────────────────────────────────────────────
    path('display/', views.display, name='display'),
    path('enquiry-details/', views.enquiry_details, name='enquiry_details'),
    path('delete/<int:id>/', views.delete_record, name='delete_record'),
    path('edit/<int:id>/', views.edit_record, name='edit_record'),
    path('update/<int:id>/', views.update_record, name='update_record'),

    # ── Appointments ──────────────────────────────────────────────
    path('appointments/', views.appointments, name='appointment_list'),
    path('appointments/delete/<int:id>/', views.delete_appointment, name='delete_appointment'),

    # NEW: Approve / Reject / Delivered action
    path('appointments/<int:pk>/update-status/', views.update_appointment_status, name='update_appointment_status'),

    # ── User Profiles ─────────────────────────────────────────────
    path('userprofiles/', views.userprofiles, name='userprofile_list'),
    path('userprofiles/delete/<int:id>/', views.delete_userprofile, name='delete_userprofile'),

    # ── Reports ───────────────────────────────────────────────────
    path('reports/', views.reports, name='reports'),

    # NEW: AJAX real-time username/email uniqueness check for signup
    path('check-field/', views.check_field, name='check_field'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)