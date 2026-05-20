from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch

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