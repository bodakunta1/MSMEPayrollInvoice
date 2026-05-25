import re

import requests
from django.conf import settings
from django.core.exceptions import ValidationError


def normalize_indian_whatsapp_number(raw_number):
    """
    Converts Indian mobile numbers to WhatsApp Cloud API format.

    Examples:
    9876543210     -> 919876543210
    +919876543210  -> 919876543210
    0919876543210  -> 919876543210
    """

    if not raw_number:
        return ""

    digits = re.sub(r"\D", "", str(raw_number))

    if len(digits) == 10:
        return f"91{digits}"

    if len(digits) == 12 and digits.startswith("91"):
        return digits

    if len(digits) == 13 and digits.startswith("091"):
        return digits[1:]

    return digits


def get_whatsapp_api_base_url():
    if not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise ValidationError("WHATSAPP_PHONE_NUMBER_ID is not configured.")

    return (
        f"https://graph.facebook.com/"
        f"{settings.WHATSAPP_GRAPH_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}"
    )


def get_auth_headers():
    if not settings.WHATSAPP_ACCESS_TOKEN:
        raise ValidationError("WHATSAPP_ACCESS_TOKEN is not configured.")

    return {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }


def ensure_whatsapp_enabled():
    if not settings.WHATSAPP_CLOUD_API_ENABLED:
        raise ValidationError(
            "WhatsApp sending is disabled. Set WHATSAPP_CLOUD_API_ENABLED=True."
        )


def upload_pdf_to_whatsapp(pdf_bytes, filename):
    """
    Upload PDF to WhatsApp Cloud API media endpoint.
    Returns WhatsApp media ID.
    """

    ensure_whatsapp_enabled()

    url = f"{get_whatsapp_api_base_url()}/media"

    files = {
        "file": (filename, pdf_bytes, "application/pdf"),
    }

    data = {
        "messaging_product": "whatsapp",
        "type": "application/pdf",
    }

    response = requests.post(
        url,
        headers=get_auth_headers(),
        data=data,
        files=files,
        timeout=60,
    )

    if response.status_code >= 400:
        raise ValidationError(
            f"WhatsApp media upload failed: {response.status_code} {response.text}"
        )

    payload = response.json()
    media_id = payload.get("id")

    if not media_id:
        raise ValidationError(f"WhatsApp media upload did not return media ID: {payload}")

    return media_id


def send_whatsapp_document(to_phone, media_id, filename, caption):
    """
    Send already-uploaded PDF document to WhatsApp number.
    """

    ensure_whatsapp_enabled()

    if not to_phone:
        raise ValidationError("Recipient WhatsApp number is empty.")

    url = f"{get_whatsapp_api_base_url()}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename,
            "caption": caption,
        },
    }

    headers = {
        **get_auth_headers(),
        "Content-Type": "application/json",
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    if response.status_code >= 400:
        raise ValidationError(
            f"WhatsApp document send failed: {response.status_code} {response.text}"
        )

    payload = response.json()

    messages = payload.get("messages", [])
    if not messages:
        raise ValidationError(f"WhatsApp send response missing message ID: {payload}")

    return messages[0].get("id", "")