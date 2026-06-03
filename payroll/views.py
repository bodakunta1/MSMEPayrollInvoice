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
from django.contrib import messages
from django.shortcuts import redirect

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


from .models import PayrollLine, PayrollRun
from .webhook_services import process_whatsapp_webhook_payload
from .whatsapp_services import send_bulk_payslips_whatsapp


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


@login_required
def payroll_line_send_whatsapp(request, pk):
    """
    Sends one labourer's Form XIX payslip by WhatsApp.
    """

    if request.method != "POST":
        return redirect("payroll:payroll_line_form_xix_single", pk=pk)

    payroll_line = get_object_or_404(
        PayrollLine.objects.select_related(
            "payroll_run",
            "payroll_run__company",
            "payroll_run__po",
            "payroll_run__payroll_cycle",
            "company",
            "payroll_cycle",
            "labour_assignment",
            "labour_assignment__labourer",
        ),
        pk=pk,
    )

    try:
        from .whatsapp_services import send_single_payslip_whatsapp

        log = send_single_payslip_whatsapp(
            payroll_line=payroll_line,
            request=request,
        )

        messages.success(
            request,
            f"WhatsApp payslip sent to {log.labourer_name} ({log.phone_number}).",
        )

    except Exception as error:
        messages.error(
            request,
            f"WhatsApp sending failed for {payroll_line.labourer_name}: {error}",
        )

    return redirect("payroll:payroll_run_detail", pk=payroll_line.payroll_run_id)

#Webhook to receive incoming messages from Meta servers (WhatsApp)

# @csrf_exempt
# def whatsapp_webhook(request):
#     if request.method == "GET":
#         mode = request.GET.get("hub.mode")
#         verify_token = request.GET.get("hub.verify_token")
#         challenge = request.GET.get("hub.challenge")

#         if mode == "subscribe" and verify_token == settings.WHATSAPP_VERIFY_TOKEN:
#             return HttpResponse(challenge, status=200)

#         return HttpResponse("Invalid verify token", status=403)

#     if request.method == "POST":
#         try:
#             payload = json.loads(request.body.decode("utf-8"))
#             logger.info("WhatsApp webhook payload: %s", payload)
#         except json.JSONDecodeError:
#             return JsonResponse({"error": "Invalid JSON"}, status=400)

#         return JsonResponse({"status": "received"}, status=200)

#     return HttpResponse("Method not allowed", status=405)


def verify_meta_signature(request):
    """
    Optional security check.

    Meta sends X-Hub-Signature-256 when app secret is configured.
    For local development, if META_APP_SECRET is empty, we skip this check.
    """

    app_secret = getattr(settings, "META_APP_SECRET", "")

    if not app_secret:
        return True

    received_signature = request.headers.get("X-Hub-Signature-256", "")

    if not received_signature.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=request.body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    expected_signature = f"sha256={expected_signature}"

    return hmac.compare_digest(received_signature, expected_signature)


@csrf_exempt
def whatsapp_webhook(request):
    """
    WhatsApp Cloud API webhook endpoint.

    GET  = Meta verification request.
    POST = delivery/read/failed status updates.
    """

    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        expected_token = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN

        if mode == "subscribe" and verify_token == expected_token and challenge:
            return HttpResponse(challenge, status=200)

        return HttpResponse("Webhook verification failed", status=403)

    if request.method == "POST":
        if not verify_meta_signature(request):
            return JsonResponse(
                {"ok": False, "error": "Invalid Meta signature"},
                status=403,
            )

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "error": "Invalid JSON"},
                status=400,
            )

        processed_count = process_whatsapp_webhook_payload(payload)

        return JsonResponse(
            {
                "ok": True,
                "processed_status_updates": processed_count,
            },
            status=200,
        )

    return HttpResponse("Method not allowed", status=405)

# The following views are for triggering bulk WhatsApp sending for payroll runs.

@login_required
def payroll_run_bulk_whatsapp(request, pk):
    """
    GET  = show confirmation page
    POST = send payslips by WhatsApp for the whole payroll run
    """

    payroll_run = get_object_or_404(
        PayrollRun.objects.select_related(
            "company",
            "po",
            "payroll_cycle",
        ).prefetch_related(
            "lines",
            "lines__labour_assignment",
            "lines__labour_assignment__labourer",
        ),
        pk=pk,
    )

    payroll_lines = payroll_run.lines.all().order_by("labourer_name")

    if request.method == "POST":

        resend_successful = request.POST.get("resend_successful") == "yes"

        results = send_bulk_payslips_whatsapp(
            payroll_run=payroll_run,
            request=request,
            skip_successful=not resend_successful,
        )

        # results = send_bulk_payslips_whatsapp(
        #     payroll_run=payroll_run,
        #     request=request,
        #     skip_successful=True,
        # )

        messages.success(
            request,
            (
                f"Bulk WhatsApp completed. "
                f"Sent: {results['sent']}, "
                f"Failed: {results['failed']}, "
                f"Skipped: {results['skipped']}."
            ),
        )

        return render(
            request,
            "payroll/bulk_whatsapp_result.html",
            {
                "payroll_run": payroll_run,
                "results": results,
            },
        )

    return render(
        request,
        "payroll/bulk_whatsapp_confirm.html",
        {
            "payroll_run": payroll_run,
            "payroll_lines": payroll_lines,
        },
    )