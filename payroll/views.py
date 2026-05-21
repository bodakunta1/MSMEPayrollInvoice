from io import BytesIO
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpResponse
from .exports import build_payroll_wage_register_workbook

from .models import PayrollLine, PayrollRun


# Create your views here.

@login_required
def payroll_run_list(request):
    """
    Shows all generated payroll runs.

    This is a normal application page, not Django admin.
    """

    payroll_runs = (
        PayrollRun.objects.select_related(
            "company",
            "po",
            "payroll_cycle",
        )
        .order_by("-payroll_cycle__period_start", "company__name", "po__po_number")
    )

    return render(
        request,
        "payroll/payroll_run_list.html",
        {
            "payroll_runs": payroll_runs,
        },
    )


@login_required
def payroll_run_detail(request, pk):
    """
    Shows one payroll run with labour-wise calculation.

    It reads calculated PayrollLine records.
    It does not recalculate payroll.
    """

    payroll_lines_qs = PayrollLine.objects.select_related(
        "labour_assignment",
        "muster_entry",
    ).prefetch_related(
        "components",
        "components__component",
    )

    payroll_run = get_object_or_404(
        PayrollRun.objects.select_related(
            "company",
            "po",
            "payroll_cycle",
            "calculated_by",
        ).prefetch_related(
            Prefetch("lines", queryset=payroll_lines_qs)
        ),
        pk=pk,
    )

    return render(
        request,
        "payroll/payroll_run_detail.html",
        {
            "payroll_run": payroll_run,
            "payroll_lines": payroll_run.lines.all(),
        },
    )


@login_required
def payroll_run_form_xix_bulk(request, pk):
    """
    Bulk Form XIX print page.

    Shows all labourers' payslips for one payroll run.
    Layout is designed for 4 slips per A4 page.
    """

    payroll_lines_qs = PayrollLine.objects.select_related(
        "labour_assignment",
        "labour_assignment__labourer",
        "muster_entry",
    ).order_by("labourer_name")

    payroll_run = get_object_or_404(
        PayrollRun.objects.select_related(
            "company",
            "po",
            "payroll_cycle",
        ).prefetch_related(
            Prefetch("lines", queryset=payroll_lines_qs)
        ),
        pk=pk,
    )

    return render(request, "payroll/form_xix_bulk.html",
        {
            "payroll_run": payroll_run,
            "payroll_lines": payroll_run.lines.all(),
        },
    )


@login_required
def payroll_line_form_xix_single(request, pk):
    """
    Single Form XIX print page for one labourer.
    """

    payroll_line = get_object_or_404(
        PayrollLine.objects.select_related(
            "payroll_run",
            "payroll_run__company",
            "payroll_run__po",
            "payroll_run__payroll_cycle",
            "labour_assignment",
            "labour_assignment__labourer",
            "muster_entry",
        ),
        pk=pk,
    )

    return render(
        request,
        "payroll/form_xix_single.html",
        {
            "payroll_run": payroll_line.payroll_run,
            "payroll_line": payroll_line,
        },
    )


@login_required
def payroll_run_wage_register_excel(request, pk):
    """
    Downloads Excel wage register for one payroll run.
    """

    payroll_run = get_object_or_404(
        PayrollRun.objects.select_related(
            "company",
            "po",
            "payroll_cycle",
        ).prefetch_related(
            "lines",
        ),
        pk=pk,
    )

    workbook = build_payroll_wage_register_workbook(payroll_run)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = f"wage_register_{payroll_run.run_number}.xlsx"

    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )

    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response