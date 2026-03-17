from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import datetime, timedelta


class CustomUserManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email(email)
        user = CustomUser(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        assert extra_fields["is_staff"]
        assert extra_fields["is_superuser"]
        return self._create_user(email, password, **extra_fields)


class Session(models.Model):
    start_year = models.DateField()
    end_year = models.DateField()

    def __str__(self):
        return "From " + str(self.start_year) + " to " + str(self.end_year)


class CustomUser(AbstractUser):
    USER_TYPE = ((1, "HOD"), (2, "Staff"), (3, "Student"))
    GENDER = [("M", "Male"), ("F", "Female")]

    username = None
    email = models.EmailField(unique=True)
    user_type = models.CharField(default=1, choices=USER_TYPE, max_length=1)
    gender = models.CharField(max_length=1, choices=GENDER)
    profile_pic = models.ImageField()
    address = models.TextField()
    fcm_token = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __str__(self):
        return self.first_name + " " + self.last_name


class Admin(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)


class Course(models.Model):
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    name = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    isbn = models.PositiveIntegerField()
    category = models.CharField(max_length=50)

    def __str__(self):
        return str(self.name) + " [" + str(self.isbn) + ']'


class Student(models.Model):
    APPROVAL_STATUS = (("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"))
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.DO_NOTHING, null=True, blank=False)
    session = models.ForeignKey(Session, on_delete=models.DO_NOTHING, null=True)
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default="approved")
    registration_number = models.CharField(max_length=50, blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.admin.last_name + ", " + self.admin.first_name


class Library(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=False)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, null=True, blank=False)

    def __str__(self):
        return str(self.student)


def expiry():
    return datetime.today() + timedelta(days=14)


class IssuedBook(models.Model):
    student_id = models.CharField(max_length=100, blank=True)
    isbn = models.CharField(max_length=13)
    issued_date = models.DateField(auto_now=True)
    expiry_date = models.DateField(default=expiry)


class Staff(models.Model):
    APPROVAL_STATUS = (("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"))
    course = models.ForeignKey(Course, on_delete=models.DO_NOTHING, null=True, blank=False)
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default="approved")
    employee_id = models.CharField(max_length=50, blank=True)
    designation = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.admin.first_name + " " + self.admin.last_name

    @property
    def is_hod(self):
        return self.managed_departments.exists()

    @property
    def department_name(self):
        department = self.managed_departments.first()
        return department.name if department else (self.course.name if self.course else "Department")


class Subject(models.Model):
    name = models.CharField(max_length=120)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Attendance(models.Model):
    session = models.ForeignKey(Session, on_delete=models.DO_NOTHING)
    subject = models.ForeignKey(Subject, on_delete=models.DO_NOTHING)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AttendanceReport(models.Model):
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING)
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LeaveReportStudent(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.CharField(max_length=60)
    message = models.TextField()
    status = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LeaveReportStaff(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    date = models.CharField(max_length=60)
    message = models.TextField()
    status = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeedbackStudent(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    feedback = models.TextField()
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeedbackStaff(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    feedback = models.TextField()
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationStaff(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationStudent(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StudentResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    test = models.FloatField(default=0)
    exam = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CollegeProfile(models.Model):
    college_name = models.CharField(max_length=200, default="My College")
    vision = models.TextField()
    mission = models.TextField()
    about = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.college_name


class SyllabusDocument(models.Model):
    title = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    semester = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="syllabus/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.course:
            return f"{self.title} - {self.course.name}"
        return self.title


class Department(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    hod = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_departments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class DepartmentNotice(models.Model):
    TARGET_ROLE = (("all", "All"), ("staff", "Staff"), ("students", "Students"))
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='notices')
    title = models.CharField(max_length=200)
    message = models.TextField()
    target_role = models.CharField(max_length=20, choices=TARGET_ROLE, default='all')
    attachment = models.FileField(upload_to='notices/', blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Assignment(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField(null=True, blank=True)
    attachment = models.FileField(upload_to='assignments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class StudyMaterial(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='notes/', blank=True, null=True)
    external_link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class OnlineClassSession(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    scheduled_for = models.DateTimeField()
    meet_link = models.URLField(blank=True)
    agenda = models.TextField(blank=True)
    air_canvas_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_for']

    def __str__(self):
        return self.title


class FeeRecord(models.Model):
    STATUS = (("pending", "Pending"), ("partial", "Partial"), ("paid", "Paid"), ("overdue", "Overdue"))
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    receipt_number = models.CharField(max_length=50, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} - {self.title}"


class ExamSchedule(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_title = models.CharField(max_length=150)
    exam_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    room = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['exam_date', 'start_time']

    def __str__(self):
        return f"{self.exam_title} - {self.subject.name}"


class GeneratedCertificate(models.Model):
    CERTIFICATE_TYPES = (("id_card", "ID Card"), ("bonafide", "Bonafide"), ("fee_receipt", "Fee Receipt"), ("marksheet", "Marksheet"), ("attendance_report", "Attendance Report"))
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    certificate_type = models.CharField(max_length=30, choices=CERTIFICATE_TYPES)
    reference_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.student} - {self.certificate_type}"


class FaceAttendanceLog(models.Model):
    ROLE = (("student", "Student"), ("staff", "Staff"))
    MODE = (("face", "Face Recognition"), ("manual", "Manual Backup"))
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE)
    mode = models.CharField(max_length=20, choices=MODE, default='face')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, default='marked')
    captured_at = models.DateTimeField(auto_now_add=True)
    confidence = models.FloatField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-captured_at']

    def __str__(self):
        return f"{self.user} - {self.role} - {self.mode}"


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.user_type == '1' or instance.user_type == 1:
            Admin.objects.create(admin=instance)
        if instance.user_type == '2' or instance.user_type == 2:
            Staff.objects.create(admin=instance)
        if instance.user_type == '3' or instance.user_type == 3:
            Student.objects.create(admin=instance)


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    try:
        if instance.user_type == '1' or instance.user_type == 1:
            instance.admin.save()
        if instance.user_type == '2' or instance.user_type == 2:
            instance.staff.save()
        if instance.user_type == '3' or instance.user_type == 3:
            instance.student.save()
    except Exception:
        pass
