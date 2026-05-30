from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from .models import WhatsAppPayslipLog


def whatsapp_timestamp_to_datetime(timestamp_value):
    """
    WhatsApp webhook timestamp is usually Unix timestamp as string.
    Example: "1716980000"
    """

    if not timestamp_value:
        return timezone.now()

    try:
        unix_timestamp = int(timestamp_value)
        return datetime.fromtimestamp(unix_timestamp, tz=dt_timezone.utc)
    except (TypeError, ValueError):
        return timezone.now()


def extract_error_data(status_payload):
    errors = status_payload.get("errors") or []

    if not errors:
        return "", "", ""

    first_error = errors[0]

    code = str(first_error.get("code", ""))
    title = first_error.get("title", "") or first_error.get("message", "")
    details = first_error.get("details", "") or first_error.get("error_data", "")

    return code, str(title), str(details)


def update_payslip_log_from_status(status_payload, full_payload=None):
    """
    Updates WhatsAppPayslipLog using status webhook.

    Expected status payload example:
    {
        "id": "wamid....",
        "status": "delivered",
        "timestamp": "1716980000",
        "recipient_id": "919876543210",
        "conversation": {...},
        "errors": [...]
    }
    """

    message_id = status_payload.get("id")
    status = status_payload.get("status")
    timestamp_value = status_payload.get("timestamp")
    recipient_id = status_payload.get("recipient_id", "")

    if not message_id or not status:
        return None

    log = WhatsAppPayslipLog.objects.filter(
        whatsapp_message_id=message_id
    ).first()

    if not log:
        return None

    event_time = whatsapp_timestamp_to_datetime(timestamp_value)

    conversation = status_payload.get("conversation") or {}
    conversation_id = conversation.get("id", "")

    log.webhook_status_raw = status
    log.recipient_id = recipient_id or log.recipient_id
    log.conversation_id = conversation_id or log.conversation_id
    log.last_webhook_payload = full_payload or status_payload

    if status == "sent":
        log.status = WhatsAppPayslipLog.Status.SENT

    elif status == "delivered":
        log.status = WhatsAppPayslipLog.Status.DELIVERED
        log.delivered_at = event_time

    elif status == "read":
        log.status = WhatsAppPayslipLog.Status.READ
        log.read_at = event_time

    elif status == "failed":
        log.status = WhatsAppPayslipLog.Status.FAILED
        log.failed_at = event_time

        code, title, details = extract_error_data(status_payload)
        log.failure_code = code
        log.failure_title = title
        log.failure_details = details
        log.error_message = f"{code} {title} {details}".strip()

    else:
        # Unknown status. Keep existing main status but store raw status.
        pass

    log.save()

    return log


def process_whatsapp_webhook_payload(payload):
    """
    Processes WhatsApp webhook POST body.

    Returns number of status updates processed.
    """

    processed_count = 0

    entries = payload.get("entry", [])

    for entry in entries:
        changes = entry.get("changes", [])

        for change in changes:
            value = change.get("value", {})

            statuses = value.get("statuses", [])

            for status_payload in statuses:
                updated_log = update_payslip_log_from_status(
                    status_payload=status_payload,
                    full_payload=payload,
                )

                if updated_log:
                    processed_count += 1

    return processed_count
