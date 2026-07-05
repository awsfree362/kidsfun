"""
Payment gateway abstraction.
Supports: Stripe, Paystack, PayFast, Yoco
Active gateway is set via ACTIVE_PAYMENT_GATEWAY env var.
"""
import os
import hmac
import hashlib
import requests
from urllib.parse import urlencode


GATEWAY = os.getenv('ACTIVE_PAYMENT_GATEWAY', 'paystack')


# ─── Paystack ────────────────────────────────────────────────────────────────

def paystack_initialize(amount_cents, email, reference, callback_url, metadata=None):
    """Returns (authorization_url, reference) or raises."""
    url = "https://api.paystack.co/transaction/initialize"
    headers = {"Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}"}
    payload = {
        "email": email,
        "amount": int(amount_cents),   # kobo / cents
        "reference": reference,
        "callback_url": callback_url,
        "metadata": metadata or {},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    data = r.json()
    if not data.get('status'):
        raise ValueError(data.get('message', 'Paystack init failed'))
    return data['data']['authorization_url'], data['data']['reference']


def paystack_verify(reference):
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}"}
    r = requests.get(url, headers=headers, timeout=15)
    data = r.json()
    if not data.get('status'):
        return None
    return data['data']  # dict with status, amount, etc.


def paystack_verify_webhook(payload_bytes, signature):
    secret = os.getenv('PAYSTACK_WEBHOOK_SECRET', '').encode()
    computed = hmac.new(secret, payload_bytes, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature or '')


# ─── Stripe ──────────────────────────────────────────────────────────────────

def stripe_create_session(amount_cents, currency, description, success_url, cancel_url, metadata=None):
    import stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': currency,
                'product_data': {'name': description},
                'unit_amount': int(amount_cents),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata or {},
    )
    return session.url, session.id


def stripe_verify_webhook(payload_bytes, sig_header):
    import stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    try:
        event = stripe.Webhook.construct_event(
            payload_bytes, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
        return event
    except Exception:
        return None


# ─── PayFast ─────────────────────────────────────────────────────────────────

def payfast_build_form(amount, item_name, return_url, cancel_url, notify_url, m_payment_id):
    sandbox = os.getenv('PAYFAST_SANDBOX', 'True') == 'True'
    base = "https://sandbox.payfast.co.za/eng/process" if sandbox else "https://www.payfast.co.za/eng/process"
    data = {
        'merchant_id': os.getenv('PAYFAST_MERCHANT_ID'),
        'merchant_key': os.getenv('PAYFAST_MERCHANT_KEY'),
        'return_url': return_url,
        'cancel_url': cancel_url,
        'notify_url': notify_url,
        'm_payment_id': m_payment_id,
        'amount': f"{float(amount):.2f}",
        'item_name': item_name,
    }
    passphrase = os.getenv('PAYFAST_PASSPHRASE', '')
    param_string = urlencode({k: v for k, v in data.items() if v})
    if passphrase:
        param_string += f"&passphrase={passphrase}"
    signature = hashlib.md5(param_string.encode()).hexdigest()
    data['signature'] = signature
    return base, data


def payfast_verify_itn(post_data: dict):
    """Verify PayFast ITN (Instant Transaction Notification)."""
    passphrase = os.getenv('PAYFAST_PASSPHRASE', '')
    params = {k: v for k, v in post_data.items() if k != 'signature'}
    param_string = urlencode(params)
    if passphrase:
        param_string += f"&passphrase={passphrase}"
    computed = hashlib.md5(param_string.encode()).hexdigest()
    return computed == post_data.get('signature', '')


# ─── Yoco ─────────────────────────────────────────────────────────────────────

def yoco_create_charge(amount_cents, currency, token, description):
    url = "https://online.yoco.com/v1/charges/"
    headers = {"X-Auth-Secret-Key": os.getenv('YOCO_SECRET_KEY')}
    payload = {
        "token": token,
        "amountInCents": int(amount_cents),
        "currency": currency,
        "description": description,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    data = r.json()
    if data.get('status') == 'successful':
        return data
    raise ValueError(data.get('displayMessage', 'Yoco charge failed'))


# ─── Unified gateway entry points ────────────────────────────────────────────

def initiate_payment(gateway, amount_cents, email, reference, callback_url,
                     description='Tournament Registration', metadata=None,
                     currency='ZAR', **kwargs):
    """Returns dict with keys: redirect_url, session_id, form_action, form_data"""
    if gateway == 'paystack':
        url, ref = paystack_initialize(amount_cents, email, reference, callback_url, metadata)
        return {'redirect_url': url, 'reference': ref}

    elif gateway == 'stripe':
        url, sid = stripe_create_session(
            amount_cents, currency, description,
            kwargs.get('success_url', callback_url),
            kwargs.get('cancel_url', callback_url),
            metadata
        )
        return {'redirect_url': url, 'session_id': sid}

    elif gateway == 'payfast':
        action, form_data = payfast_build_form(
            amount_cents / 100, description,
            kwargs.get('return_url', callback_url),
            kwargs.get('cancel_url', callback_url),
            kwargs.get('notify_url', callback_url),
            reference
        )
        return {'form_action': action, 'form_data': form_data}

    elif gateway == 'yoco':
        # Yoco needs a frontend token first; return public key for JS SDK
        return {'yoco_public_key': os.getenv('YOCO_PUBLIC_KEY'), 'reference': reference}

    raise ValueError(f"Unknown gateway: {gateway}")
