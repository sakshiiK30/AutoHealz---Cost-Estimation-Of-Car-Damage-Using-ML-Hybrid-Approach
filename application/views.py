# application/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.views import APIView
from rest_framework.response import Response

from datetime import datetime

from .models import enquiry_table, Appointment, UserProfile



import os
import re
import csv
import json
import hashlib
import uuid
import gc
import traceback

from PIL import Image

# ============================================================
# LAZY LOAD ML MODELS (Render memory fix)
# ============================================================

def get_detect_damage():
    from .ml_models.detect import detect_damage
    return detect_damage


def get_generate_caption():
    from .ml_models.blip_model import generate_caption
    return generate_caption


def get_predict_total_cost():
    from .ml_models.knn_model import predict_total_cost
    return predict_total_cost

GST_RATE    = 0.18
LABOUR_RATE = 0.12


# ============================================================
# STATIC PAGES
# ============================================================

def index(request):
    return render(request, 'index.html')


def contact(request):
    if request.method == 'POST':
        name    = request.POST.get('name')
        email   = request.POST.get('email')
        phone   = request.POST.get('phone')
        message = request.POST.get('message')

        if name and email and phone and message:
            enquiry_table.objects.create(
                name=name, email=email, phone=phone, message=message
            )
            messages.success(request, 'Enquiry submitted successfully.')
        else:
            messages.error(request, 'All fields are required.')

    return render(request, 'contact.html')


# ============================================================
# AUTH HELPERS
# ============================================================

def hash_password(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


# ============================================================
# SIGN UP
# ============================================================

EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')


def sign(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email',    '').strip()
        password = request.POST.get('password', '').strip()
        confirm  = request.POST.get('confirmPassword', '').strip()

        errors = {}

        # ── Username ──────────────────────────────────────────────
        if not username:
            errors['username'] = 'Username is required.'
        elif len(username) < 3:
            errors['username'] = 'Username must be at least 3 characters.'
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors['username'] = 'Only letters, numbers, and underscores are allowed.'
        elif UserProfile.objects.filter(username__iexact=username).exists():
            errors['username'] = 'This username is already taken.'

        # ── Email ─────────────────────────────────────────────────
        if not email:
            errors['email'] = 'Email is required.'
        elif not EMAIL_REGEX.match(email):
            errors['email'] = 'Please enter a valid email address (e.g. you@example.com).'
        elif UserProfile.objects.filter(email__iexact=email).exists():
            errors['email'] = 'An account with this email already exists.'

        # ── Password ──────────────────────────────────────────────
        if len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters.'
        elif password != confirm:
            errors['confirm'] = 'Passwords do not match.'

        if not errors:
            UserProfile.objects.create(
                username=username,
                email=email,
                password=hash_password(password),
            )
            messages.success(request, 'Account created successfully.')
            return redirect('login')

        return render(request, 'sign.html', {'errors': errors, 'old': request.POST})

    return render(request, 'sign.html')


# ============================================================
# AJAX — REAL-TIME FIELD UNIQUENESS CHECK
# GET /check-field/?field=username&value=...
# GET /check-field/?field=email&value=...
# Returns JSON: { "available": true/false, "message": "..." }
# ============================================================

def check_field(request):
    field = request.GET.get('field', '').strip()
    value = request.GET.get('value', '').strip()

    if field == 'username':
        if len(value) < 3:
            return JsonResponse({'available': False, 'message': 'Username must be at least 3 characters.'})
        if not re.match(r'^[a-zA-Z0-9_]+$', value):
            return JsonResponse({'available': False, 'message': 'Only letters, numbers, and underscores allowed.'})
        if UserProfile.objects.filter(username__iexact=value).exists():
            return JsonResponse({'available': False, 'message': 'This username is already taken.'})
        return JsonResponse({'available': True, 'message': 'Username is available.'})

    elif field == 'email':
        if not EMAIL_REGEX.match(value):
            return JsonResponse({'available': False, 'message': 'Please enter a valid email address.'})
        if UserProfile.objects.filter(email__iexact=value).exists():
            return JsonResponse({'available': False, 'message': 'An account with this email already exists.'})
        return JsonResponse({'available': True, 'message': 'Email is available.'})

    return JsonResponse({'available': True, 'message': ''})


# ============================================================
# LOGIN
# ============================================================

def login_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        next_url = (
            request.POST.get('next')
            or request.GET.get('next')
            or '/'
        )

        try:
            user = UserProfile.objects.get(username=username)

            if user.password == hash_password(password):
                request.session['user_id']  = user.id
                request.session['username'] = user.username
                request.session.set_expiry(0)

                messages.success(request, f'Welcome back, {user.username}!')
                return redirect(next_url)
            else:
                messages.error(request, 'Incorrect password.')

        except UserProfile.DoesNotExist:
            messages.error(request, 'No account found with that username.')

    next_url = request.GET.get('next', '')
    return render(request, 'Login.html', {'next': next_url})


# ============================================================
# LOGOUT
# ============================================================

def logout_user(request):
    request.session.flush()
    messages.success(request, 'Logged out successfully.')
    return redirect('/')


# ============================================================
# LOGIN CHECK (JSON endpoint)
# ============================================================

def login_required_json(request):
    if not request.session.get('user_id'):
        return JsonResponse({'logged_in': False})
    return JsonResponse({
        'logged_in': True,
        'username': request.session.get('username')
    })


# ============================================================
# GET BOOKED SLOTS FOR A DATE
# GET /get-booked-slots/?date=YYYY-MM-DD
# ============================================================

def get_booked_slots(request):
    date_str = request.GET.get('date', '').strip()
    if not date_str:
        return JsonResponse({'booked_slots': []})

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'booked_slots': []})

    booked = list(
        Appointment.objects.filter(date=date_obj).values_list('time_slot', flat=True)
    )
    return JsonResponse({'booked_slots': booked})


# ============================================================
# BOOK APPOINTMENT
# ============================================================

@csrf_exempt
def bookappointment(request):
    if request.method == "POST":
        try:
            content_type = request.content_type or ""

            if "multipart/form-data" in content_type:
                name        = request.POST.get('name',    '').strip()
                email       = request.POST.get('email',   '').strip()
                phone       = request.POST.get('phone',   '').strip()
                vehicle     = request.POST.get('vehicle', '').strip()
                service     = request.POST.get('service', '').strip()
                date        = request.POST.get('date',    '').strip()
                time_slot   = request.POST.get('time',    '').strip()
                notes       = request.POST.get('notes',   '').strip()
                report_file = request.FILES.get('report_file')
            else:
                data        = json.loads(request.body)
                name        = data.get('name',    '').strip()
                email       = data.get('email',   '').strip()
                phone       = data.get('phone',   '').strip()
                vehicle     = data.get('vehicle', '').strip()
                service     = data.get('service', '').strip()
                date        = data.get('date',    '').strip()
                time_slot   = data.get('time',    '').strip()
                notes       = data.get('notes',   '').strip()
                report_file = None

            if not all([name, email, phone, vehicle, service, date, time_slot]):
                return JsonResponse({
                    "status":  "error",
                    "message": "All required fields must be filled."
                })

            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({"status": "error", "message": "Invalid date format."})

            if Appointment.objects.filter(date=date_obj, time_slot=time_slot).exists():
                return JsonResponse({
                    "status":  "error",
                    "message": f"The slot {time_slot} on {date} is already booked. Please choose another slot."
                })

            appt = Appointment.objects.create(
                name=name,
                email=email,
                phone=phone,
                vehicle=vehicle,
                service=service,
                date=date_obj,
                time_slot=time_slot,
                notes=notes or None,
                report_file=report_file or None,
            )

            return JsonResponse({"status": "success", "id": appt.id})

        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON."})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return render(request, 'BookAppointment.html')


# ============================================================
# COST ESTIMATION HELPERS
# ============================================================

SUPPORTED_MODELS = [
    'Alto 800', 'Alto K10', 'Baleno', 'Brezza', 'Celerio',
    'Dzire', 'Eeco', 'Ertiga', 'Fronx', 'Grand Vitara',
    'Ignis', 'Invicto', 'Jimny', 'S-Presso', 'Super Carry',
    'Swift', 'WagonR', 'XL6',
]

PART_NAMES = {
    "front-bumper-dent":  "Front Bumper",
    "rear-bumper-dent":   "Rear Bumper",
    "doorouter-dent":     "Side Door",
    "bonnet-dent":        "Bonnet / Hood",
    "headlight-damage":   "Headlight",
    "taillight-damage":   "Taillight",
    "fender-dent":        "Side Door",
    "side-mirror-dent":   "Side Mirror",
    "door-dent":          "Side Door",
    "hood-dent":          "Bonnet / Hood",
    "bumper-dent":        "Front Bumper",
}


def load_part_availability():
    file_path = os.path.join(
        settings.BASE_DIR, "application", "ml_models", "part_availability.csv"
    )

    raw_map = {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                part         = row.get("part_name",    "").strip()
                model        = row.get("maruti_model", "").strip()
                availability = row.get("availability", "").strip()

                composite_key = f"{model}_{part}"
                if composite_key not in raw_map:
                    raw_map[composite_key] = {
                        "original":      None,
                        "alternative":   None,
                        "not_available": None,
                    }

                entry = {
                    "availability": availability,
                    "price_range":  row.get("price_range", "N/A").strip(),
                    "notes":        row.get("notes", "").strip(),
                }

                if availability == "Original":
                    raw_map[composite_key]["original"] = entry
                elif availability == "Alternative":
                    raw_map[composite_key]["alternative"] = entry
                elif availability == "Not Available":
                    raw_map[composite_key]["not_available"] = entry

    except Exception as e:
        print("CSV load error:", e)

    return raw_map


def _get_severity(bbox):
    if not bbox:
        return "Moderate"
    x1, y1, x2, y2 = bbox
    area = (x2 - x1) * (y2 - y1)
    if area < 8000:  return "Minor"
    if area < 25000: return "Moderate"
    return "Severe"


def _cost_breakdown(base_cost):
    labour   = round(base_cost * LABOUR_RATE, -1)
    subtotal = base_cost + int(labour)
    gst      = round(subtotal * GST_RATE, -1)
    grand    = subtotal + int(gst)
    return {
        "base":        base_cost,
        "labour":      int(labour),
        "gst":         int(gst),
        "grand_total": int(grand),
    }


def _get_overall_severity(detections):
    severities = [d.get('severity', '') for d in detections]
    if 'Severe'   in severities: return 'Severe'
    if 'Moderate' in severities: return 'Moderate'
    return 'Minor'


# ============================================================
# ESTIMATE PAGE
# ============================================================

def estimate(request):
    if not request.session.get('user_id'):
        return redirect('/login/?next=/estimate/')

    if request.method == 'POST' and request.FILES.get('image'):
        car_model = request.POST.get('car_model', 'Swift').strip()
        if car_model not in SUPPORTED_MODELS:
            car_model = 'Swift'

        img = request.FILES['image']

        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        filename = f"{uuid.uuid4()}.jpg"
        image_path = os.path.join(settings.MEDIA_ROOT, filename)

        with open(image_path, "wb+") as f:
             for chunk in img.chunks():
                 f.write(chunk)

        image_url = settings.MEDIA_URL + filename
        pil_image  = Image.open(image_path).convert("RGB")

        # ── All heavy ML processing wrapped so failures are logged
        # instead of surfacing as a bare, unexplained 500 ──────────
        try:
            detect_damage = get_detect_damage()
            raw_detections = detect_damage(image_path)

            # Free YOLO from memory before BLIP loads
            from .ml_models.detect import unload_model as unload_yolo
            unload_yolo()

            unique_parts = {}
            for det in raw_detections:
                cls = det['class']
                if cls not in unique_parts or det['conf'] > unique_parts[cls]['conf']:
                    unique_parts[cls] = det

            normalized       = list(unique_parts.values())
            availability_map = load_part_availability()

            generate_caption = get_generate_caption()

            for det in normalized:
                bbox      = det.get('bbox')
                severity  = _get_severity(bbox)
                part_name = PART_NAMES.get(det['class'], det['class'].replace('-', ' ').title())

                if bbox:
                    x1, y1, x2, y2 = bbox
                    crop = pil_image.crop((x1, y1, x2, y2))
                    caption = generate_caption(crop)
                else:
                    caption = generate_caption(pil_image)

                key = f"{car_model}_{part_name}"
                part_options = availability_map.get(key, {
                    "original":      None,
                    "alternative":   None,
                    "not_available": None,
                })

                det.update({
                    'severity':        severity,
                    'part_name':       part_name,
                    'caption':         caption,
                    'display_caption': f"{part_name} - {severity} damage.",
                    'part_options':    part_options,
                })

            # Free BLIP from memory before KNN/pandas step
            from .ml_models.blip_model import unload_blip
            unload_blip()
            gc.collect()

            detections  = normalized
            predict_total_cost = get_predict_total_cost()

            knn_output = predict_total_cost(car_model, detections)
            knn_results = knn_output["results"]

            total_base = total_labour = total_gst = grand_total = 0

            for det, knn_res in zip(detections, knn_results):
                det['knn'] = knn_res
                if 'estimated_cost' in knn_res:
                    det['breakdown'] = _cost_breakdown(knn_res['estimated_cost'])
                    total_base   += det['breakdown']['base']
                    total_labour += det['breakdown']['labour']
                    total_gst    += det['breakdown']['gst']
                    grand_total  += det['breakdown']['grand_total']

        except Exception:
            print("[ESTIMATE] ❌ PROCESSING ERROR:")
            traceback.print_exc()
            messages.error(request, "Something went wrong while analyzing the image. Please try again.")
            return redirect('estimate')

        request.session['estimation_results'] = {
            'car_model':        car_model,
            'image_url':        image_url,
            'detections':       detections,
            'total_base':       total_base,
            'total_labour':     total_labour,
            'total_gst':        total_gst,
            'grand_total':      grand_total,
            'overall_severity': _get_overall_severity(detections),
        }

        return redirect('results')

    return render(request, 'estimate.html', {
        'supported_models': SUPPORTED_MODELS,
        'car_model': 'Swift',
    })


# ============================================================
# RESULTS PAGE
# ============================================================

def results(request):
    if not request.session.get('user_id'):
        return redirect('/login/?next=/results/')

    data = request.session.get('estimation_results')
    if not data:
        messages.warning(request, 'Please upload an image first.')
        return redirect('estimate')

    return render(request, 'results.html', {
        'car_model':        data['car_model'],
        'image_url':        data['image_url'],
        'detections':       data['detections'],
        'total_base':       data['total_base'],
        'total_labour':     data['total_labour'],
        'total_gst':        data['total_gst'],
        'grand_total':      data['grand_total'],
        'overall_severity': data['overall_severity'],
    })


# ============================================================
# ALTERNATIVE PARTS
# ============================================================

inventory = {
    "Front Bumper": "Original",
    "Rear Door":    "Alternative",
    "Side Mirror":  "Not Available",
    "Bonnet":       "Original",
    "Headlight":    "Original",
    "Taillight":    "Alternative",
}


def alternative(request):
    return render(request, 'alternative.html', {'inventory': inventory})


# ============================================================
# DASHBOARD
# ============================================================

def dashboard(request):
    if not request.session.get('user_id'):
        return redirect('/login/?next=/dashboard/')

    total_enquiries    = enquiry_table.objects.count()
    total_appointments = Appointment.objects.count()
    total_users        = UserProfile.objects.count()

    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    monthly_data = (
        enquiry_table.objects
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    chart_labels = [
        item['month'].strftime('%b %Y') if item['month'] else ''
        for item in monthly_data
    ]
    chart_values = [item['count'] for item in monthly_data]

    return render(request, 'dashboard/index.html', {
        'username':           request.session.get('username'),
        'total_enquiries':    total_enquiries,
        'total_appointments': total_appointments,
        'total_users':        total_users,
        'chart_labels':       json.dumps(chart_labels),
        'chart_values':       json.dumps(chart_values),
    })


# ============================================================
# ENQUIRY DETAILS
# ============================================================

def enquiry_details(request):
    data = enquiry_table.objects.all()
    return render(request, 'dashboard/tables.html', {'abc': data})


def delete_record(request, id):
    if request.method == 'POST':
        enquiry_table.objects.filter(pk=id).delete()
    return HttpResponseRedirect('/enquiry-details/')


def edit_record(request, id):
    info = enquiry_table.objects.filter(pk=id)
    return render(request, 'dashboard/editrecord.html', {'abc': info})


def update_record(request, id):
    info            = enquiry_table.objects.get(pk=id)
    info.name       = request.POST.get('name')
    info.email      = request.POST.get('email')
    info.phone      = request.POST.get('phone')
    info.message    = request.POST.get('message')
    info.dropdown   = request.POST.get('dropdown')
    info.date_field = request.POST.get('date')
    info.save()
    return HttpResponseRedirect('/enquiry-details/')


# ============================================================
# APPOINTMENTS
# ============================================================

def appointments(request):
    data = Appointment.objects.all().order_by('-created_at')
    return render(request, 'dashboard/appointments.html', {'appointments': data})


def delete_appointment(request, id):
    if request.method == 'POST':
        Appointment.objects.filter(pk=id).delete()
    return HttpResponseRedirect('/appointments/')


@require_POST
def update_appointment_status(request, pk):
    """
    Handles Approve / Reject / Delivered actions from the appointments table.
    POST /appointments/<pk>/update-status/
    """
    appt   = get_object_or_404(Appointment, pk=pk)
    status = request.POST.get('status', '').strip()

    if status not in ['approved', 'rejected', 'delivered']:
        messages.error(request, "Invalid status value.")
        return redirect('appointment_list')

    if status == 'rejected':
        reason = request.POST.get('rejection_reason', '').strip()
        if not reason:
            messages.error(request, "Please provide a rejection reason.")
            return redirect('appointment_list')
        appt.rejection_reason = reason
    else:
        appt.rejection_reason = None   # clear old reason on re-approve / deliver

    appt.status = status
    appt.save()

    labels = {
        'approved':  'Appointment approved successfully.',
        'rejected':  'Appointment rejected.',
        'delivered': 'Appointment marked as delivered.',
    }
    messages.success(request, labels[status])
    return redirect('appointment_list')


# ============================================================
# USER PROFILES
# ============================================================

def userprofiles(request):
    data = UserProfile.objects.all().order_by('-created_at')
    return render(request, 'dashboard/userprofiles.html', {'profiles': data})


def delete_userprofile(request, id):
    if request.method == 'POST':
        UserProfile.objects.filter(pk=id).delete()
    return HttpResponseRedirect('/userprofiles/')


# ============================================================
# REPORTS
# ============================================================

def reports(request):
    context = {'appointments': Appointment.objects.none()}

    if request.method == 'POST':
        from_date_str = request.POST.get('fromdate', '').strip()
        to_date_str   = request.POST.get('todate',   '').strip()

        if from_date_str and to_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                to_date   = datetime.strptime(to_date_str,   '%Y-%m-%d').date()

                context['appointments'] = Appointment.objects.filter(
                    date__range=[from_date, to_date]
                ).order_by('date', 'time_slot')
                context['from_date'] = from_date_str
                context['to_date']   = to_date_str

            except ValueError:
                messages.error(request, 'Invalid date format. Please use the date picker.')
        else:
            messages.error(request, 'Please select both From and To dates.')

    return render(request, 'dashboard/reports.html', context)


def display(request):
    data = enquiry_table.objects.all()
    return render(request, 'dashboard/tables.html', {'abc': data})


# ============================================================
# CHANGE PASSWORD
# ============================================================

def change_password(request):
    if not request.session.get('user_id'):
        return redirect('/login/?next=/change-password/')

    if request.method == 'POST':
        current_password = request.POST.get('current_password', '').strip()
        new_password     = request.POST.get('new_password',     '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        user_id = request.session.get('user_id')

        try:
            user = UserProfile.objects.get(id=user_id)
        except UserProfile.DoesNotExist:
            request.session.flush()
            return redirect('/login/')

        if user.password != hash_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return render(request, 'dashboard/change_password.html')

        if not new_password:
            messages.error(request, "New password cannot be empty.")
            return render(request, 'dashboard/change_password.html')

        if len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return render(request, 'dashboard/change_password.html')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'dashboard/change_password.html')

        user.password = hash_password(new_password)
        user.save()

        messages.success(request, "Password updated successfully!")
        return render(request, 'dashboard/change_password.html')

    return render(request, 'dashboard/change_password.html')