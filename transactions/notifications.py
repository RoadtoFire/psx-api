import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)


def _normalize_pakistani_number(raw_number: str):
    """
    Normalize common Pakistani local phone number formats to E.164.

    Accepts formats like '03001234567' or '0300-1234567' (with spaces or
    dashes), and converts a leading '0' + 10 digits to '+92' + 10 digits.
    If the number already starts with '+', it is passed through as-is
    (assumed already E.164). Returns None if the number can't be
    confidently normalized.
    """
    if not raw_number:
        return None

    cleaned = re.sub(r'[\s-]', '', raw_number)

    if cleaned.startswith('+'):
        return cleaned

    if re.fullmatch(r'0\d{10}', cleaned):
        return '+92' + cleaned[1:]

    return None


def send_whatsapp_message(to_number: str, body: str) -> bool:
    """
    Send a WhatsApp message via Twilio's WhatsApp Business API.

    Returns True if the message was sent successfully, False otherwise
    (including when Twilio isn't configured, or the number can't be
    normalized, or the send fails for any reason). Never raises.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_WHATSAPP_FROM:
        logger.warning(
            'WhatsApp notification skipped: Twilio is not configured '
            '(TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_WHATSAPP_FROM missing).'
        )
        return False

    normalized_number = _normalize_pakistani_number(to_number)
    if not normalized_number:
        logger.warning('WhatsApp notification skipped: could not normalize phone number %r', to_number)
        return False

    from twilio.rest import Client

    from_number = settings.TWILIO_WHATSAPP_FROM
    if not from_number.startswith('whatsapp:'):
        from_number = f'whatsapp:{from_number}'

    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=from_number,
            to=f'whatsapp:{normalized_number}',
            body=body,
        )
        return True
    except Exception as exc:
        logger.error('Failed to send WhatsApp message to %r: %s', normalized_number, exc)
        return False
