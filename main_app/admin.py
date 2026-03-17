from django.contrib import admin
from .models import *

for model in [
    CustomUser, Admin, Course, Book, Student, Library, IssuedBook, Staff, Subject,
    Attendance, AttendanceReport, LeaveReportStudent, LeaveReportStaff, FeedbackStudent,
    FeedbackStaff, NotificationStaff, NotificationStudent, StudentResult, Session,
    CollegeProfile, SyllabusDocument, Department, DepartmentNotice, Assignment,
    StudyMaterial, OnlineClassSession, FeeRecord, ExamSchedule, GeneratedCertificate,
    FaceAttendanceLog,
]:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
