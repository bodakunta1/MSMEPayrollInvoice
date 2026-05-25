from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .browser_pdf import render_url_to_pdf_bytes
from .models import WhatsAppPayslipLog
from .whatsapp import (
    normalize_indian_whatsapp_number,
    send_whatsapp_document,
    upload_pdf_to_whatsapp,
)


def get_labourer_whatsapp_number(payroll_line):
    labourer = payroll_line.labour_assignment.labourer

    return (
        labourer.whatsapp_number
        or labourer.mobile_number
        or ""
    )


def build_payslip_pdf_filename(payroll_line):
    safe_code = slugify(payroll_line.labour_code) or f"code-{payroll_line.id}"
    safe_name = slugify(payroll_line.labourer_name) or f"labourer-{payroll_line.id}"

    return f"{safe_code}_{safe_name}_form_xix.pdf"


def send_single_payslip_whatsapp(payroll_line, request):
    """
    Generates one Form XIX PDF and sends it to labourer's WhatsApp.
    """

    raw_phone = get_labourer_whatsapp_number(payroll_line)
    phone_number = normalize_indian_whatsapp_number(raw_phone)

    filename = build_payslip_pdf_filename(payroll_line)

    log, _ = WhatsAppPayslipLog.objects.update_or_create(
        payroll_line=payroll_line,
        defaults={
            "payroll_run": payroll_line.payroll_run,
            "company": payroll_line.company,
            "labour_code": payroll_line.labour_code,
            "labourer_name": payroll_line.labourer_name,
            "phone_number": phone_number,
            "pdf_filename": filename,
            "status": WhatsAppPayslipLog.Status.PENDING,
            "error_message": "",
        },
    )

    if not phone_number:
        log.status = WhatsAppPayslipLog.Status.SKIPPED
        log.error_message = "No WhatsApp/mobile number found for labourer."
        log.save(update_fields=["status", "error_message", "updated_at"])
        raise ValidationError(log.error_message)

    try:
        html_url = request.build_absolute_uri(
            reverse("payroll:payroll_line_form_xix_single", args=[payroll_line.id])
        )

        pdf_bytes = render_url_to_pdf_bytes(html_url, request)

        media_id = upload_pdf_to_whatsapp(
            pdf_bytes=pdf_bytes,
            filename=filename,
        )

        caption = (
            f"Form XIX payslip for {payroll_line.labourer_name} - "
            f"{payroll_line.payroll_cycle.name}"
        )

        message_id = send_whatsapp_document(
            to_phone=phone_number,
            media_id=media_id,
            filename=filename,
            caption=caption,
        )

        log.status = WhatsAppPayslipLog.Status.SENT
        log.whatsapp_media_id = media_id
        log.whatsapp_message_id = message_id
        log.error_message = ""
        log.sent_at = timezone.now()
        log.save()

        return log

    except Exception as error:
        log.status = WhatsAppPayslipLog.Status.FAILED
        log.error_message = str(error)
        log.save(update_fields=["status", "error_message", "updated_at"])
        raise