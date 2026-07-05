import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import Registration, Event, SiteSettings
from app.utils.payments import (paystack_verify, paystack_verify_webhook,
                                  stripe_verify_webhook, payfast_verify_itn,
                                  yoco_create_charge, initiate_payment)

payments_bp = Blueprint('payments', __name__)


def get_gateway():
    return SiteSettings.get('active_payment_gateway') or os.getenv('ACTIVE_PAYMENT_GATEWAY', 'paystack')


def get_currency():
    return SiteSettings.get('currency') or os.getenv('CURRENCY', 'ZAR')


@payments_bp.route('/checkout/<int:reg_id>')
@login_required
def checkout(reg_id):
    reg = Registration.query.filter_by(id=reg_id, user_id=current_user.id).first_or_404()
    if reg.payment_status == 'paid':
        return redirect(url_for('user.registration_detail', reg_id=reg.id))

    gateway = get_gateway()
    currency = get_currency()
    amount_cents = int(float(reg.amount_paid or reg.division.entry_fee or 0) * 100)
    reference = f"REG-{reg.id}-{uuid.uuid4().hex[:8].upper()}"
    description = f"Registration: {reg.event.title}"
    callback_url = url_for('payments.verify', reg_id=reg.id, _external=True)
    success_url = url_for('payments.success', reg_id=reg.id, _external=True)
    cancel_url = url_for('payments.cancel', reg_id=reg.id, _external=True)
    notify_url = url_for('payments.payfast_itn', _external=True)

    try:
        result = initiate_payment(
            gateway=gateway,
            amount_cents=amount_cents,
            email=current_user.email,
            reference=reference,
            callback_url=callback_url,
            description=description,
            metadata={'reg_id': reg.id, 'user_id': current_user.id},
            currency=currency,
            success_url=success_url,
            cancel_url=cancel_url,
            notify_url=notify_url,
        )
    except Exception as e:
        flash(f'Payment initiation failed: {e}', 'danger')
        return redirect(url_for('user.registration_detail', reg_id=reg.id))

    reg.payment_intent_id = reference
    db.session.commit()

    # Redirect gateways
    if 'redirect_url' in result:
        return redirect(result['redirect_url'])

    # PayFast form POST
    if 'form_action' in result:
        return render_template('payments/payfast_redirect.html',
                               form_action=result['form_action'],
                               form_data=result['form_data'])

    # Yoco JS SDK
    if 'yoco_public_key' in result:
        return render_template('payments/yoco_checkout.html',
                               reg=reg, result=result,
                               amount_cents=amount_cents, currency=currency,
                               description=description)

    flash('Unknown payment gateway response.', 'danger')
    return redirect(url_for('user.registration_detail', reg_id=reg.id))


@payments_bp.route('/verify/<int:reg_id>')
@login_required
def verify(reg_id):
    reg = Registration.query.filter_by(id=reg_id, user_id=current_user.id).first_or_404()
    gateway = get_gateway()
    reference = request.args.get('reference') or request.args.get('trxref') or reg.payment_intent_id

    if gateway == 'paystack':
        data = paystack_verify(reference)
        if data and data.get('status') == 'success':
            reg.payment_status = 'paid'
            reg.status = 'confirmed'
            reg.amount_paid = data['amount'] / 100
            db.session.commit()
            try:
                from app.utils.email import send_registration_confirmation
                send_registration_confirmation(reg)
            except Exception:
                pass
            flash('Payment successful! Registration confirmed.', 'success')
            return redirect(url_for('user.registration_detail', reg_id=reg.id))

    elif gateway == 'stripe':
        session_id = request.args.get('session_id')
        if session_id:
            import stripe
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                reg.payment_status = 'paid'
                reg.status = 'confirmed'
                reg.amount_paid = session.amount_total / 100
                db.session.commit()
                try:
                    from app.utils.email import send_registration_confirmation
                    send_registration_confirmation(reg)
                except Exception:
                    pass
                flash('Payment successful! Registration confirmed.', 'success')
                return redirect(url_for('user.registration_detail', reg_id=reg.id))

    flash('Payment could not be verified. Please contact support.', 'warning')
    return redirect(url_for('user.registration_detail', reg_id=reg.id))


@payments_bp.route('/success/<int:reg_id>')
@login_required
def success(reg_id):
    reg = Registration.query.filter_by(id=reg_id, user_id=current_user.id).first_or_404()
    return redirect(url_for('payments.verify', reg_id=reg_id,
                            session_id=request.args.get('session_id', '')))


@payments_bp.route('/cancel/<int:reg_id>')
@login_required
def cancel(reg_id):
    flash('Payment was cancelled.', 'warning')
    return redirect(url_for('user.registration_detail', reg_id=reg_id))


# ─── Webhooks ────────────────────────────────────────────────────────────────

@payments_bp.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    payload = request.get_data()
    sig = request.headers.get('x-paystack-signature', '')
    if not paystack_verify_webhook(payload, sig):
        abort(400)
    import json
    event = json.loads(payload)
    if event.get('event') == 'charge.success':
        ref = event['data']['reference']
        reg = Registration.query.filter_by(payment_intent_id=ref).first()
        if reg:
            reg.payment_status = 'paid'
            reg.status = 'confirmed'
            reg.amount_paid = event['data']['amount'] / 100
            db.session.commit()
    return jsonify({'ok': True})


@payments_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    event = stripe_verify_webhook(payload, sig)
    if not event:
        abort(400)
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        reg_id = session.get('metadata', {}).get('reg_id')
        if reg_id:
            reg = Registration.query.get(int(reg_id))
            if reg:
                reg.payment_status = 'paid'
                reg.status = 'confirmed'
                reg.amount_paid = session['amount_total'] / 100
                db.session.commit()
    return jsonify({'ok': True})


@payments_bp.route('/webhook/payfast', methods=['POST'])
def payfast_itn():
    if not payfast_verify_itn(request.form.to_dict()):
        abort(400)
    m_payment_id = request.form.get('m_payment_id', '')
    payment_status = request.form.get('payment_status', '')
    if payment_status == 'COMPLETE' and m_payment_id.startswith('REG-'):
        try:
            reg_id = int(m_payment_id.split('-')[1])
            reg = Registration.query.get(reg_id)
            if reg:
                reg.payment_status = 'paid'
                reg.status = 'confirmed'
                reg.amount_paid = float(request.form.get('amount_gross', 0))
                db.session.commit()
        except Exception:
            pass
    return '', 200


@payments_bp.route('/yoco/charge', methods=['POST'])
@login_required
def yoco_charge():
    data = request.get_json()
    reg_id = data.get('reg_id')
    token = data.get('token')
    reg = Registration.query.filter_by(id=reg_id, user_id=current_user.id).first_or_404()
    amount_cents = int(float(reg.division.entry_fee or 0) * 100)
    currency = get_currency()
    try:
        result = yoco_create_charge(amount_cents, currency, token,
                                    f"Registration: {reg.event.title}")
        reg.payment_status = 'paid'
        reg.status = 'confirmed'
        reg.amount_paid = amount_cents / 100
        db.session.commit()
        return jsonify({'success': True, 'redirect': url_for('user.registration_detail', reg_id=reg.id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
