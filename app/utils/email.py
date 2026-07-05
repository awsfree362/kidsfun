import os
import threading
from flask_mail import Message
from app import mail


def _send_async(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Email send error: {e}")


def send_email(to, subject, html_body):
    """Send email asynchronously via a daemon thread so it never blocks a request."""
    from flask import current_app
    msg = Message(
        subject=subject,
        recipients=[to],
        html=html_body,
        sender=os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME', 'noreply@kidscomp.com'))
    )
    app = current_app._get_current_object()
    t = threading.Thread(target=_send_async, args=(app, msg), daemon=True)
    t.start()
    return True


def send_verification_email(user, verify_url):
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#4f46e5;margin-bottom:8px">Verify Your Email Address</h2>
      <p style="color:#374151">Hi {user.first_name or 'there'},</p>
      <p style="color:#374151">Thanks for signing up! Click the button below to verify your
         email and activate your account.</p>
      <a href="{verify_url}"
         style="display:inline-block;background:#4f46e5;color:#fff;padding:13px 28px;
                border-radius:8px;text-decoration:none;font-weight:700;margin:20px 0;font-size:15px">
        Verify Email Address
      </a>
      <p style="color:#6b7280;font-size:13px">This link expires in 24 hours.</p>
      <p style="color:#9ca3af;font-size:12px">
        If you didn't create an account, you can safely ignore this email.<br/>
        Or copy this link: {verify_url}
      </p>
    </div>
    """
    send_email(user.email, 'Verify your email address', html)


def send_registration_confirmation(reg):
    division_row = (
        f'<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Division</td>'
        f'<td style="padding:8px;border-bottom:1px solid #eee">{reg.division.name}</td></tr>'
        if reg.division else ''
    )
    payment_note = (
        '<p style="background:#fef3c7;padding:12px;border-radius:8px">'
        '<strong>Payment Required:</strong> Please complete your payment to confirm your spot.</p>'
        if reg.payment_status == 'unpaid' else
        '<p style="background:#dcfce7;padding:12px;border-radius:8px">'
        'Payment received. Your registration is confirmed!</p>'
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#4f46e5">Registration Confirmed!</h2>
      <p>Hi {reg.user.first_name},</p>
      <p>Your registration for <strong>{reg.event.title}</strong> has been received.</p>
      <table style="width:100%;border-collapse:collapse;margin:20px 0">
        <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Athlete</td>
            <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold">{reg.child.full_name}</td></tr>
        <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Event</td>
            <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold">{reg.event.title}</td></tr>
        <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Date</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{reg.event.start_date.strftime('%A, %d %B %Y')}</td></tr>
        {division_row}
        <tr><td style="padding:8px;color:#666">Status</td>
            <td style="padding:8px;font-weight:bold;color:#16a34a">{reg.status.title()}</td></tr>
      </table>
      {payment_note}
      <p style="color:#6b7280;font-size:14px">If you have any questions, please contact us.</p>
    </div>
    """
    send_email(reg.user.email, f"Registration: {reg.event.title}", html)


def send_password_reset(user, reset_url):
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#4f46e5">Reset Your Password</h2>
      <p>Hi {user.first_name or user.email},</p>
      <p>Click the button below to reset your password. This link expires in 1 hour.</p>
      <a href="{reset_url}"
         style="display:inline-block;background:#4f46e5;color:#fff;padding:12px 24px;
                border-radius:8px;text-decoration:none;font-weight:700;margin:16px 0">
        Reset Password
      </a>
      <p style="color:#6b7280;font-size:13px">If you didn't request this, ignore this email.</p>
      <p style="color:#9ca3af;font-size:12px">Or copy this link: {reset_url}</p>
    </div>
    """
    send_email(user.email, "Password Reset Request", html)


def send_status_update(reg):
    colors = {
        'confirmed': '#16a34a', 'cancelled': '#dc2626',
        'waitlist': '#d97706', 'pending': '#2563eb',
    }
    color = colors.get(reg.status, '#6b7280')
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#4f46e5">Registration Update</h2>
      <p>Hi {reg.user.first_name},</p>
      <p>Your registration for <strong>{reg.event.title}</strong> has been updated.</p>
      <p style="font-size:18px">Status: <strong style="color:{color}">{reg.status.title()}</strong></p>
      <p style="color:#6b7280;font-size:14px">Log in to your dashboard to view details.</p>
    </div>
    """
    send_email(reg.user.email, f"Registration Update: {reg.event.title}", html)


def send_bulk_notification(users, subject, message):
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#4f46e5">{subject}</h2>
      <div style="color:#374151;line-height:1.6">{message}</div>
    </div>
    """
    for user in users:
        send_email(user.email, subject, html)
