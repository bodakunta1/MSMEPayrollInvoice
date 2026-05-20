from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("runs/", views.payroll_run_list, name="payroll_run_list"),
    path("runs/<int:pk>/", views.payroll_run_detail, name="payroll_run_detail"),
]