from django.db import models
from django.utils import timezone


class enquiry_table(models.Model):
    name    = models.CharField(max_length=255)
    email   = models.EmailField(max_length=255)
    phone   = models.CharField(max_length=10)
    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    username   = models.CharField(max_length=100, unique=True)
    email      = models.EmailField(unique=True)
    password   = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.username} ({self.email})"


STATUS_CHOICES = [
    ('pending',   'Pending'),
    ('approved',  'Approved'),
    ('rejected',  'Rejected'),
    ('delivered', 'Delivered'),
]


class Appointment(models.Model):
    name        = models.CharField(max_length=100)
    email       = models.EmailField()
    phone       = models.CharField(max_length=10)
    vehicle     = models.CharField(max_length=20)
    service     = models.CharField(max_length=200)
    date        = models.DateField()
    time_slot   = models.CharField(max_length=20)
    notes       = models.TextField(blank=True, null=True)
    report_file = models.FileField(upload_to='reports/', blank=True, null=True)
    created_at  = models.DateTimeField(default=timezone.now)

    # ── NEW ──
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} — {self.service} on {self.date} at {self.time_slot} ({self.status})"