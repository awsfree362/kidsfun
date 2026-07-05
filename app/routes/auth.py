from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter
from app.models import User
from app.utils.forms import LoginForm, RegisterForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('20 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('events.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if user.is_admin():
                return redirect(next_page or url_for('admin.dashboard'))
            return redirect(next_page or url_for('user.dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('events.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html', form=form)
        user = User(
            email=form.email.data.lower().strip(),
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            role='parent',
            is_verified=False,
        )
        user.set_password(form.password.data)
        token = user.generate_verify_token()
        db.session.add(user)
        db.session.commit()
        verify_url = url_for('auth.verify_email', token=token, _external=True)
        try:
            from app.utils.email import send_verification_email
            send_verification_email(user, verify_url)
        except Exception:
            pass
        login_user(user)
        flash('Account created! Please check your email to verify your address.', 'info')
        return redirect(url_for('user.dashboard'))
    return render_template('auth/register.html', form=form)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(verify_token=token).first()
    if not user:
        flash('Invalid or expired verification link.', 'danger')
        return redirect(url_for('events.index'))
    if user.confirm_verify_token(token):
        db.session.commit()
        flash('Email verified! Your account is fully activated.', 'success')
    else:
        flash('Verification link has expired. Please request a new one.', 'warning')
    return redirect(url_for('user.dashboard'))


@auth_bp.route('/resend-verification')
@login_required
@limiter.limit('3 per hour')
def resend_verification():
    if current_user.is_verified:
        flash('Your email is already verified.', 'info')
        return redirect(url_for('user.dashboard'))
    token = current_user.generate_verify_token()
    db.session.commit()
    verify_url = url_for('auth.verify_email', token=token, _external=True)
    try:
        from app.utils.email import send_verification_email
        send_verification_email(current_user, verify_url)
    except Exception:
        pass
    flash('Verification email resent. Please check your inbox.', 'info')
    return redirect(url_for('user.dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('events.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per hour')
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('events.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                from app.utils.email import send_password_reset
                send_password_reset(user, reset_url)
            except Exception:
                pass
        flash('If that email exists, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Password reset successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)
