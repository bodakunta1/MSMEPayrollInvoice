from io import BytesIO
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpResponse
from django.urls import reverse
from .exports import build_payroll_wage_register_workbook
from .browser_pdf import render_url_to_pdf_bytes, render_many_urls_to_pdf_bytes
from zipfile import ZipFile, ZIP_DEFLATED
from django.utils.text import slugify


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


@login_required
def payroll_line_form_xix_pdf(request, pk):
    """
    Downloads single Form XIX PDF.

    This PDF is generated from the same HTML page:
    /payroll/lines/<id>/form-xix/
    """

    payroll_line = get_object_or_404(
        PayrollLine.objects.select_related(
            "payroll_run",
            "payroll_run__company",
            "payroll_run__po",
            "payroll_run__payroll_cycle",
        ),
        pk=pk,
    )

    html_url = request.build_absolute_uri(
        reverse("payroll:payroll_line_form_xix_single", args=[payroll_line.id])
    )

    pdf_bytes = render_url_to_pdf_bytes(html_url, request)

    filename = f"form_xix_{payroll_line.labour_code}_{payroll_line.labourer_name}.pdf"

    response = HttpResponse(
        pdf_bytes,
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@login_required
def payroll_run_form_xix_bulk_pdf(request, pk):
    """
    Downloads bulk Form XIX PDF.

    This PDF is generated from the same HTML page:
    /payroll/runs/<id>/form-xix/

    So the browser page and PDF remain visually same.
    """

    payroll_run = get_object_or_404(
        PayrollRun.objects.select_related(
            "company",
            "po",
            "payroll_cycle",
        ),
        pk=pk,
    )

    html_url = request.build_absolute_uri(
        reverse("payroll:payroll_run_form_xix_bulk", args=[payroll_run.id])
    )

    pdf_bytes = render_url_to_pdf_bytes(html_url, request)

    filename = f"bulk_form_xix_{payroll_run.payroll_cycle.name}.pdf"

    response = HttpResponse(
        pdf_bytes,
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@login_required
def payroll_run_individual_form_xix_zip(request, pk):
    """
    Downloads one ZIP file containing individual Form XIX PDFs
    for every labourer in a payroll run.

    This is useful for WhatsApp sending later.
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

    lines = payroll_run.lines.all().order_by("labourer_name")

    pdf_items = []

    for line in lines:
        safe_name = slugify(line.labourer_name) or f"labourer-{line.id}"
        safe_code = slugify(line.labour_code) or f"code-{line.id}"

        filename = f"{safe_code}_{safe_name}_form_xix.pdf"

        html_url = request.build_absolute_uri(
            reverse("payroll:payroll_line_form_xix_single", args=[line.id])
        )

        pdf_items.append((filename, html_url))

    rendered_pdfs = render_many_urls_to_pdf_bytes(pdf_items, request)

    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zip_file:
        for filename, pdf_bytes in rendered_pdfs:
            zip_file.writestr(filename, pdf_bytes)

    zip_buffer.seek(0)

    zip_filename = f"individual_form_xix_{payroll_run.payroll_cycle.name}.zip"

    response = HttpResponse(
        zip_buffer.getvalue(),
        content_type="application/zip",
    )
    response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'

    return response