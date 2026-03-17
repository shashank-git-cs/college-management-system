from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    Assignment, AttendanceReport, Course, CustomUser, Department, DepartmentNotice,
    ExamSchedule, FaceAttendanceLog, FeeRecord, GeneratedCertificate,
    NotificationStudent, NotificationStaff, OnlineClassSession, Staff, Student,
    StudyMaterial, Subject
)


def _get_staff(request):
    return get_object_or_404(Staff, admin=request.user)


def _get_student(request):
    return get_object_or_404(Student, admin=request.user)


def _is_hod(staff):
    return bool(staff and staff.is_hod)


def _department_scoped_students(staff):
    if not staff:
        return Student.objects.none()
    return Student.objects.select_related('admin', 'course').filter(course=staff.course)


def _department_scoped_staff(staff):
    if not staff:
        return Staff.objects.none()
    return Staff.objects.select_related('admin', 'course').filter(course=staff.course)


@login_required
def admin_advanced_dashboard(request):
    context = {
        'page_title': 'Advanced Admin Dashboard',
        'page_subtitle': 'Overview of departments, fees, exams, certificates, notices, and automation modules.',
        'departments': Department.objects.select_related('hod__admin').all(),
        'pending_students': Student.objects.filter(approval_status='pending').count(),
        'pending_staff': Staff.objects.filter(approval_status='pending').count(),
        'fees_due': FeeRecord.objects.exclude(status='paid').count(),
        'total_fee_amount': FeeRecord.objects.aggregate(total=Sum('amount'))['total'],
        'exam_count': ExamSchedule.objects.count(),
        'certificate_count': GeneratedCertificate.objects.count(),
        'notice_count': DepartmentNotice.objects.count(),
        'face_logs': FaceAttendanceLog.objects.all()[:10],
    }
    return render(request, 'advanced/admin_advanced_dashboard.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def admin_department_management(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        hod_id = request.POST.get('hod') or None
        if name and code:
            department, created = Department.objects.get_or_create(code=code, defaults={'name': name, 'description': description})
            if not created:
                department.name = name
                department.description = description
            if hod_id:
                department.hod = Staff.objects.filter(id=hod_id).first()
            department.save()
            messages.success(request, 'Department saved successfully.')
        else:
            messages.error(request, 'Department name and code are required.')
        return redirect('admin_department_management')
    context = {
        'page_title': 'Department Management',
        'departments': Department.objects.select_related('hod__admin').all(),
        'staff_list': Staff.objects.select_related('admin', 'course').all().order_by('course__name', 'admin__first_name'),
    }
    return render(request, 'advanced/admin_department_management.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def admin_fee_management(request):
    if request.method == 'POST':
        student = Student.objects.filter(id=request.POST.get('student')).first()
        if student:
            FeeRecord.objects.create(
                student=student,
                title=request.POST.get('title', 'College Fee'),
                amount=request.POST.get('amount') or 0,
                due_date=request.POST.get('due_date') or None,
                status=request.POST.get('status') or 'pending',
                receipt_number=request.POST.get('receipt_number', ''),
                remarks=request.POST.get('remarks', ''),
            )
            messages.success(request, 'Fee record added.')
        else:
            messages.error(request, 'Select a valid student.')
        return redirect('admin_fee_management')
    context = {
        'page_title': 'Fee Management',
        'fee_records': FeeRecord.objects.select_related('student__admin').all(),
        'students': Student.objects.select_related('admin').all(),
    }
    return render(request, 'advanced/admin_fee_management.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def admin_exam_management(request):
    if request.method == 'POST':
        subject = Subject.objects.filter(id=request.POST.get('subject')).first()
        if subject:
            ExamSchedule.objects.create(
                course=subject.course,
                subject=subject,
                exam_title=request.POST.get('exam_title', 'Internal Exam'),
                exam_date=request.POST.get('exam_date'),
                start_time=request.POST.get('start_time') or None,
                end_time=request.POST.get('end_time') or None,
                room=request.POST.get('room', ''),
            )
            messages.success(request, 'Exam scheduled.')
        else:
            messages.error(request, 'Select a valid subject.')
        return redirect('admin_exam_management')
    context = {
        'page_title': 'Exam & Result Management',
        'subjects': Subject.objects.select_related('course').all(),
        'exams': ExamSchedule.objects.select_related('course', 'subject').all(),
    }
    return render(request, 'advanced/admin_exam_management.html', context)


@login_required
def admin_reports_certificates(request):
    certificate_type = request.GET.get('type', '')
    query = GeneratedCertificate.objects.select_related('student__admin').all()
    if certificate_type:
        query = query.filter(certificate_type=certificate_type)
    context = {
        'page_title': 'Reports & Certificates',
        'certificates': query,
        'fee_summary': FeeRecord.objects.values('status').annotate(total=Count('id')).order_by('status'),
        'attendance_summary': FaceAttendanceLog.objects.values('mode').annotate(total=Count('id')).order_by('mode'),
        'students': Student.objects.select_related('admin').all()[:10],
    }
    return render(request, 'advanced/admin_reports_certificates.html', context)


@login_required
def unified_search(request):
    q = request.GET.get('q', '').strip()
    scope = request.GET.get('scope', 'all')
    results = {}
    if q:
        if scope in ('all', 'students'):
            results['students'] = Student.objects.select_related('admin', 'course').filter(
                Q(admin__first_name__icontains=q) | Q(admin__last_name__icontains=q) | Q(registration_number__icontains=q)
            )[:20]
        if scope in ('all', 'staff'):
            results['staff'] = Staff.objects.select_related('admin', 'course').filter(
                Q(admin__first_name__icontains=q) | Q(admin__last_name__icontains=q) | Q(employee_id__icontains=q)
            )[:20]
        if scope in ('all', 'fees'):
            results['fees'] = FeeRecord.objects.select_related('student__admin').filter(
                Q(title__icontains=q) | Q(student__admin__first_name__icontains=q) | Q(receipt_number__icontains=q)
            )[:20]
        if scope in ('all', 'attendance'):
            results['attendance'] = FaceAttendanceLog.objects.select_related('user', 'subject').filter(
                Q(user__first_name__icontains=q) | Q(status__icontains=q) | Q(subject__name__icontains=q)
            )[:20]
        if scope in ('all', 'documents'):
            results['documents'] = StudyMaterial.objects.select_related('subject').filter(
                Q(title__icontains=q) | Q(description__icontains=q) | Q(subject__name__icontains=q)
            )[:20]
        if scope in ('all', 'notices'):
            results['notices'] = DepartmentNotice.objects.select_related('department').filter(
                Q(title__icontains=q) | Q(message__icontains=q) | Q(department__name__icontains=q)
            )[:20]
        if scope in ('all', 'results'):
            from .models import StudentResult
            results['results'] = StudentResult.objects.select_related('student__admin', 'subject').filter(
                Q(student__admin__first_name__icontains=q) | Q(subject__name__icontains=q)
            )[:20]
    context = {'page_title': 'Smart Search', 'q': q, 'scope': scope, 'results': results}
    return render(request, 'advanced/unified_search.html', context)


@login_required
def hod_dashboard(request):
    staff = _get_staff(request)
    if not _is_hod(staff):
        messages.error(request, 'Only assigned HOD accounts can access this page.')
        return redirect('staff_home')
    departments = Department.objects.filter(hod=staff)
    scoped_students = _department_scoped_students(staff)
    scoped_staff = _department_scoped_staff(staff)
    scoped_subjects = Subject.objects.filter(course=staff.course)
    scoped_notices = DepartmentNotice.objects.filter(department__in=departments).order_by('-created_at')
    scoped_online_sessions = OnlineClassSession.objects.filter(subject__course=staff.course).select_related('subject').order_by('-scheduled_for')
    recent_subjects = list(scoped_subjects.values_list('name', flat=True)[:6])
    recent_subject_attendance = []
    for subject_name in recent_subjects:
        recent_subject_attendance.append(AttendanceReport.objects.filter(attendance__subject__name=subject_name, attendance__subject__course=staff.course).count())
    context = {
        'page_title': 'HOD Dashboard',
        'page_subtitle': f'Department command center for {staff.department_name}',
        'department_name': staff.department_name,
        'departments': departments,
        'pending_students': scoped_students.filter(approval_status='pending').count(),
        'pending_staff': scoped_staff.filter(approval_status='pending').exclude(id=staff.id).count(),
        'notice_count': scoped_notices.count(),
        'online_class_count': scoped_online_sessions.count(),
        'department_notices': scoped_notices[:10],
        'subject_count': scoped_subjects.count(),
        'student_count': scoped_students.count(),
        'staff_count': scoped_staff.count(),
        'students': scoped_students[:12],
        'staff_members': scoped_staff[:12],
        'online_sessions': scoped_online_sessions[:8],
        'subject_labels': recent_subjects,
        'subject_attendance_counts': recent_subject_attendance,
    }
    return render(request, 'advanced/hod_dashboard.html', context)


@login_required
def hod_department_data(request):
    staff = _get_staff(request)
    if not _is_hod(staff):
        messages.error(request, 'Only HOD accounts can access department data.')
        return redirect('staff_home')
    scoped_students = _department_scoped_students(staff)
    scoped_staff = _department_scoped_staff(staff)
    scoped_subjects = Subject.objects.filter(course=staff.course).select_related('staff__admin', 'course')
    context = {
        'page_title': 'HOD Department Data',
        'students': scoped_students,
        'staff_members': scoped_staff,
        'subjects': scoped_subjects,
        'department': Department.objects.filter(hod=staff).first(),
    }
    return render(request, 'advanced/hod_department_data.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def hod_approvals(request):
    staff = _get_staff(request)
    if not _is_hod(staff):
        messages.error(request, 'Only assigned HOD accounts can approve department accounts.')
        return redirect('staff_home')
    scoped_students = _department_scoped_students(staff)
    scoped_staff = _department_scoped_staff(staff)
    if request.method == 'POST':
        entity = request.POST.get('entity')
        obj_id = request.POST.get('id')
        status = request.POST.get('status')
        if entity == 'student':
            obj = scoped_students.filter(id=obj_id).first()
        else:
            obj = scoped_staff.filter(id=obj_id).first()
        if obj and status in ('approved', 'rejected', 'pending'):
            obj.approval_status = status
            obj.save()
            messages.success(request, f'{entity.title()} account updated.')
        return redirect('hod_approvals')
    context = {
        'page_title': 'Authorize Accounts',
        'students': scoped_students,
        'staff_members': scoped_staff.exclude(id=staff.id),
        'course_name': staff.course.name if staff.course else 'Department',
    }
    return render(request, 'advanced/hod_approvals.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def hod_notice_board(request):
    staff = _get_staff(request)
    if not _is_hod(staff):
        messages.error(request, 'Only assigned HOD accounts can publish department notices.')
        return redirect('staff_home')
    departments = Department.objects.filter(hod=staff)
    if request.method == 'POST':
        department = departments.filter(id=request.POST.get('department')).first()
        if department:
            DepartmentNotice.objects.create(
                department=department,
                title=request.POST.get('title', '').strip(),
                message=request.POST.get('message', '').strip(),
                target_role=request.POST.get('target_role') or 'all',
                attachment=request.FILES.get('attachment'),
                created_by=request.user,
            )
            messages.success(request, 'Department notice published.')
        else:
            messages.error(request, 'Select a valid department.')
        return redirect('hod_notice_board')
    context = {
        'page_title': 'Department Notice Board',
        'departments': departments,
        'notices': DepartmentNotice.objects.filter(department__in=departments).order_by('-created_at'),
    }
    return render(request, 'advanced/hod_notice_board.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def staff_assignments(request):
    staff = _get_staff(request)
    subjects = Subject.objects.filter(staff=staff).select_related('course').order_by('name')
    if request.method == 'POST':
        subject = subjects.filter(id=request.POST.get('subject')).first()
        if subject:
            Assignment.objects.create(
                subject=subject,
                staff=staff,
                title=request.POST.get('title', ''),
                description=request.POST.get('description', ''),
                due_date=request.POST.get('due_date') or None,
                attachment=request.FILES.get('attachment')
            )
            messages.success(request, 'Assignment created.')
        return redirect('staff_assignments')
    context = {'page_title': 'Assignments', 'subjects': subjects, 'assignments': Assignment.objects.filter(staff=staff)}
    return render(request, 'advanced/staff_assignments.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def staff_notes(request):
    staff = _get_staff(request)
    subjects = Subject.objects.filter(staff=staff).select_related('course').order_by('name')
    if request.method == 'POST':
        subject = subjects.filter(id=request.POST.get('subject')).first()
        if subject:
            StudyMaterial.objects.create(
                subject=subject,
                staff=staff,
                title=request.POST.get('title', ''),
                description=request.POST.get('description', ''),
                file=request.FILES.get('file'),
                external_link=request.POST.get('external_link', ''),
            )
            messages.success(request, 'Study material uploaded.')
        return redirect('staff_notes')
    context = {'page_title': 'Notes & Materials', 'subjects': subjects, 'materials': StudyMaterial.objects.filter(staff=staff)}
    return render(request, 'advanced/staff_notes.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def staff_online_classes(request):
    staff = _get_staff(request)
    subjects = Subject.objects.filter(staff=staff).select_related('course').order_by('name')
    if request.method == 'POST':
        subject = subjects.filter(id=request.POST.get('subject')).first()
        if subject:
            OnlineClassSession.objects.create(
                subject=subject,
                staff=staff,
                title=request.POST.get('title', ''),
                scheduled_for=request.POST.get('scheduled_for'),
                meet_link=request.POST.get('meet_link', ''),
                agenda=request.POST.get('agenda', ''),
                air_canvas_enabled=bool(request.POST.get('air_canvas_enabled')),
            )
            messages.success(request, 'Online class scheduled.')
        return redirect('staff_online_classes')
    context = {'page_title': 'Subject-wise Lecture Panel', 'subjects': subjects, 'sessions': OnlineClassSession.objects.filter(staff=staff).select_related('subject').order_by('-scheduled_for')}
    return render(request, 'advanced/staff_online_classes.html', context)


@login_required
def staff_air_canvas(request):
    staff = Staff.objects.filter(admin=request.user).first()
    classes = OnlineClassSession.objects.none()
    if staff:
        classes = OnlineClassSession.objects.filter(staff=staff).select_related('subject').order_by('-scheduled_for')[:12]
    context = {'page_title': 'Air Canvas Virtual Board', 'online_sessions': classes}
    return render(request, 'advanced/staff_air_canvas.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def face_attendance_center(request):
    selected_user = request.user
    selected_scope = 'self'
    subjects = Subject.objects.none()
    students = Student.objects.none()
    staff_members = Staff.objects.none()
    allowed_user_ids = set()

    if request.user.user_type == '1':
        students = Student.objects.select_related('admin', 'course').all()
        staff_members = Staff.objects.select_related('admin', 'course').all()
        subjects = Subject.objects.select_related('course', 'staff__admin').all()
        selected_scope = 'admin'
    elif request.user.user_type == '2':
        staff = _get_staff(request)
        if _is_hod(staff):
            students = _department_scoped_students(staff)
            staff_members = _department_scoped_staff(staff)
            subjects = Subject.objects.filter(course=staff.course).select_related('course', 'staff__admin')
            selected_scope = 'hod'
        else:
            subjects = Subject.objects.filter(staff=staff).select_related('course').order_by('name').select_related('course', 'staff__admin')
            staff_members = Staff.objects.filter(id=staff.id).select_related('admin', 'course')
            selected_scope = 'staff'
    else:
        student = _get_student(request)
        subjects = Subject.objects.filter(course=student.course).select_related('course', 'staff__admin')
        students = Student.objects.filter(id=student.id).select_related('admin', 'course')

    allowed_user_ids.update(students.values_list('admin_id', flat=True))
    allowed_user_ids.update(staff_members.values_list('admin_id', flat=True))
    allowed_user_ids.add(request.user.id)

    if request.method == 'POST':
        mode = request.POST.get('mode', 'manual')
        target_user_id = (request.POST.get('target_user_id') or '').strip()
        identifier = (request.POST.get('identifier') or '').strip()
        role = request.POST.get('role') or ('staff' if request.user.user_type == '2' else 'student')

        if target_user_id.isdigit() and int(target_user_id) in allowed_user_ids:
            selected_user = CustomUser.objects.filter(id=int(target_user_id)).first() or request.user
        elif identifier:
            matched_student = students.filter(
                Q(registration_number__iexact=identifier) |
                Q(admin__email__iexact=identifier) |
                Q(admin__first_name__iexact=identifier) |
                Q(admin__last_name__iexact=identifier)
            ).first()
            matched_staff = staff_members.filter(
                Q(employee_id__iexact=identifier) |
                Q(admin__email__iexact=identifier) |
                Q(admin__first_name__iexact=identifier) |
                Q(admin__last_name__iexact=identifier)
            ).first()
            if matched_student:
                selected_user = matched_student.admin
                role = 'student'
            elif matched_staff:
                selected_user = matched_staff.admin
                role = 'staff'

        subject = None
        subject_id = (request.POST.get('subject') or '').strip()
        if subject_id.isdigit():
            subject = subjects.filter(id=int(subject_id)).first()

        confidence_raw = (request.POST.get('confidence') or '').strip()
        try:
            confidence = float(confidence_raw) if confidence_raw else 0
        except ValueError:
            confidence = 0

        note_parts = []
        if identifier:
            note_parts.append(f"Lookup: {identifier}")
        extra_notes = request.POST.get('notes', '').strip()
        if extra_notes:
            note_parts.append(extra_notes)

        FaceAttendanceLog.objects.create(
            user=selected_user,
            role=role,
            mode=mode,
            subject=subject,
            status=request.POST.get('status', 'marked'),
            confidence=confidence,
            notes=' | '.join(note_parts),
        )
        messages.success(request, f'Attendance saved for {selected_user.first_name} {selected_user.last_name}.')
        return redirect('face_attendance_center')

    logs = FaceAttendanceLog.objects.filter(user=request.user)
    if request.user.user_type == '1':
        logs = FaceAttendanceLog.objects.select_related('user', 'subject').all()[:50]
    elif request.user.user_type == '2' and selected_scope == 'hod':
        staff = _get_staff(request)
        logs = FaceAttendanceLog.objects.select_related('user', 'subject').filter(
            Q(user__student__course=staff.course) | Q(user__staff__course=staff.course)
        )[:50]
    else:
        logs = logs.select_related('user', 'subject')[:20]

    context = {
        'page_title': 'Face Recognition Attendance',
        'subjects': subjects,
        'logs': logs,
        'students': students,
        'staff_members': staff_members,
        'selected_scope': selected_scope,
        'identifier_help': 'Use student register number, staff employee ID, email, or name to mark attendance quickly.',
    }
    return render(request, 'advanced/face_attendance_center.html', context)


@login_required
def student_services(request):
    student = _get_student(request)
    notices = DepartmentNotice.objects.all()
    context = {
        'page_title': 'Student Services Hub',
        'fees': FeeRecord.objects.filter(student=student),
        'assignments': Assignment.objects.filter(subject__course=student.course),
        'materials': StudyMaterial.objects.filter(subject__course=student.course),
        'sessions': OnlineClassSession.objects.filter(subject__course=student.course, scheduled_for__gte=timezone.now() - timezone.timedelta(days=30)).select_related('subject', 'staff__admin'),
        'notices': notices[:15],
        'certificates': GeneratedCertificate.objects.filter(student=student),
        'attendance_logs': FaceAttendanceLog.objects.filter(user=request.user)[:10],
    }
    return render(request, 'advanced/student_services.html', context)
