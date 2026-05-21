from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("runs/", views.payroll_run_list, name="payroll_run_list"),
    path("runs/<int:pk>/", views.payroll_run_detail, name="payroll_run_detail"),

    # Form XIX payslip pages
    path(
        "runs/<int:pk>/form-xix/",
        views.payroll_run_form_xix_bulk,
        name="payroll_run_form_xix_bulk",
    ),
    path(
        "lines/<int:pk>/form-xix/",
        views.payroll_line_form_xix_single,
        name="payroll_line_form_xix_single",
    ),

    path(
        "runs/<int:pk>/wage-register.xlsx",
        views.payroll_run_wage_register_excel,
        name="payroll_run_wage_register_excel",
    ),

    path(
        "runs/<int:pk>/form-xix.pdf",
        views.payroll_run_form_xix_bulk_pdf,
        name="payroll_run_form_xix_bulk_pdf",
    ),
    path(
        "lines/<int:pk>/form-xix.pdf",
        views.payroll_line_form_xix_pdf,
        name="payroll_line_form_xix_pdf",
    ),
    path(
        "runs/<int:pk>/individual-form-xix.zip",
        views.payroll_run_individual_form_xix_zip,
        name="payroll_run_individual_form_xix_zip",
    ),

]