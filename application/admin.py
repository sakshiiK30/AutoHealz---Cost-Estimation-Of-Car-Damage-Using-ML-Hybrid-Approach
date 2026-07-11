
# from django.contrib import admin
# from .models import Appointment, enquiry_table

# admin.site.register(enquiry_table)

# admin.site.register(Appointment)

from django.contrib import admin
from .models import Appointment, enquiry_table,UserProfile


@admin.register(enquiry_table)
class EnquiryAdmin(admin.ModelAdmin):
    list_display  = ('name', 'email', 'phone')
    search_fields = ('name', 'email', 'phone')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display   = ('username', 'email', 'created_at')
    search_fields  = ('username', 'email')
    ordering       = ('-created_at',)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display   = ('name', 'phone', 'service', 'date', 'time_slot', 'vehicle', 'created_at')
    list_filter    = ('service', 'date')
    search_fields  = ('name', 'email', 'phone', 'vehicle')
    ordering       = ('-created_at',)