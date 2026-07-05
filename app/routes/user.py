from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Child, ChildDocument, Event, Registration, EventAgeDivision,
                         Agreement, EventCustomField, RegistrationDocument,
                         SiteSettings, Notification)
from app.utils.storage import upload_file, delete_file
from app.utils.forms import ChildForm
import json
from datetime import datetime

user_bp = Blueprint('user', __name__)


# ── Fix: before_request + login_required don't chain via decorator.
#    Use a plain before_request that calls login_required's underlying check.
@user_bp.before_request
def require_login():
    from flask_login import current_user
    from flask import redirect, url_for, request as req
    if not current_user.is_authenticated:
        from flask_login import login_manager
        return login_manager.unauthorized()


@user_bp.route('/')
def dashboard():
    children = Child.query.filter_by(parent_id=current_user.id).all()
    registrations = (Registration.query
                     .filter_by(user_id=current_user.id)
                     .order_by(Registration.registered_at.desc())
                     .limit(10).all())
    notifications = (Notification.query
                     .filter_by(user_id=current_user.id, is_read=False)
                     .order_by(Notification.created_at.desc())
                     .limit(5).all())
    return render_template('user/dashboard.html', children=children,
                           registrations=registrations, notifications=notifications)


# ─── Children ────────────────────────────────────────────────────────────────

@user_bp.route('/children')
def children():
    children = Child.query.filter_by(parent_id=current_user.id).all()
    return render_template('user/children.html', children=children)


@user_bp.route('/children/new', methods=['GET', 'POST'])
@user_bp.route('/children/<int:child_id>/edit', methods=['GET', 'POST'])
def child_form(child_id=None):
    child = None
    if child_id:
        child = Child.query.filter_by(id=child_id, parent_id=current_user.id).first_or_404()
    form = ChildForm(obj=child)
    if form.validate_on_submit():
        if not child:
            child = Child(parent_id=current_user.id)
            db.session.add(child)
        child.first_name = form.first_name.data
        child.last_name = form.last_name.data
        child.date_of_birth = form.date_of_birth.data
        child.gender = form.gender.data
        child.medical_notes = form.medical_notes.data
        if form.profile_image.data and form.profile_image.data.filename:
            delete_file(child.profile_image)
            child.profile_image = upload_file(form.profile_image.data, 'children')
        db.session.commit()
        flash('Child profile saved.', 'success')
        return redirect(url_for('user.children'))
    return render_template('user/child_form.html', form=form, child=child)


@user_bp.route('/children/<int:child_id>/documents', methods=['POST'])
def child_document_upload(child_id):
    child = Child.query.filter_by(id=child_id, parent_id=current_user.id).first_or_404()
    f = request.files.get('document')
    doc_type = request.form.get('doc_type', 'other')
    if f:
        url = upload_file(f, 'documents')
        if url:
            doc = ChildDocument(child_id=child.id, doc_type=doc_type,
                                file_url=url, file_name=f.filename)
            db.session.add(doc)
            db.session.commit()
            return jsonify({'id': doc.id, 'url': url, 'file_name': f.filename})
    return jsonify({'error': 'Upload failed'}), 400


@user_bp.route('/children/documents/<int:doc_id>/delete', methods=['POST'])
def child_document_delete(doc_id):
    doc = ChildDocument.query.join(Child).filter(
        ChildDocument.id == doc_id, Child.parent_id == current_user.id
    ).first_or_404()
    delete_file(doc.file_url)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Registration ─────────────────────────────────────────────────────────────

@user_bp.route('/register/<int:event_id>', methods=['GET', 'POST'])
def register_event(event_id):
    event = Event.query.filter_by(id=event_id, status='published').first_or_404()
    if not event.registration_open:
        flash('Registration is closed for this event.', 'warning')
        return redirect(url_for('events.event_detail', slug=event.slug))

    children = Child.query.filter_by(parent_id=current_user.id).all()
    if not children:
        flash('Please add a child profile before registering.', 'info')
        return redirect(url_for('user.child_form'))

    agreements = Agreement.query.filter(
        (Agreement.is_global == True) | (Agreement.event_id == event.id)
    ).all()
    custom_fields = EventCustomField.query.filter_by(event_id=event.id).order_by(
        EventCustomField.sort_order).all()

    if request.method == 'POST':
        child_id = request.form.get('child_id', type=int)
        division_id = request.form.get('division_id', type=int)
        child = Child.query.filter_by(id=child_id, parent_id=current_user.id).first()
        if not child:
            flash('Invalid child selection.', 'danger')
            return redirect(request.url)

        # ── Duplicate registration guard ──────────────────────────────────────
        existing = Registration.query.filter(
            Registration.child_id == child.id,
            Registration.event_id == event.id,
            Registration.status.in_(['pending', 'confirmed', 'waitlist'])
        ).first()
        if existing:
            flash(f'{child.first_name} is already registered for this event.', 'warning')
            return redirect(url_for('events.event_detail', slug=event.slug))

        # ── Age validation against selected division ──────────────────────────
        division = EventAgeDivision.query.get(division_id) if division_id else None
        if division:
            child_age = child.age
            if division.min_age is not None and child_age < division.min_age:
                flash(
                    f'{child.first_name} is {child_age} years old and does not meet the '
                    f'minimum age of {division.min_age} for the {division.name} division.',
                    'danger'
                )
                return redirect(request.url)
            if division.max_age is not None and child_age > division.max_age:
                flash(
                    f'{child.first_name} is {child_age} years old and exceeds the '
                    f'maximum age of {division.max_age} for the {division.name} division.',
                    'danger'
                )
                return redirect(request.url)

        # ── Agreements ────────────────────────────────────────────────────────
        signed_ids = request.form.getlist('agreements')
        required_ids = [str(a.id) for a in agreements if a.required]
        if not all(rid in signed_ids for rid in required_ids):
            flash('You must agree to all required agreements.', 'danger')
            return redirect(request.url)

        # ── Custom fields ─────────────────────────────────────────────────────
        cf_values = {}
        for cf in custom_fields:
            val = request.form.get(f'cf_{cf.field_name}', '')
            if cf.required and not val:
                flash(f'{cf.field_label or cf.field_name} is required.', 'danger')
                return redirect(request.url)
            cf_values[cf.field_name] = val

        amount = float(division.entry_fee) if division else 0

        reg = Registration(
            user_id=current_user.id,
            event_id=event.id,
            child_id=child.id,
            division_id=division_id,
            status='pending',
            payment_status='unpaid' if amount > 0 else 'paid',
            amount_paid=0,
            custom_field_values=json.dumps(cf_values),
            agreements_signed=json.dumps(signed_ids),
        )
        db.session.add(reg)
        db.session.commit()

        # Handle document uploads
        for key in request.files:
            f = request.files[key]
            if f and f.filename:
                url = upload_file(f, 'registrations')
                if url:
                    rdoc = RegistrationDocument(
                        registration_id=reg.id,
                        doc_type=key,
                        file_url=url,
                        file_name=f.filename
                    )
                    db.session.add(rdoc)
        db.session.commit()

        if amount > 0:
            return redirect(url_for('payments.checkout', reg_id=reg.id))

        reg.status = 'confirmed'
        db.session.commit()
        try:
            from app.utils.email import send_registration_confirmation
            send_registration_confirmation(reg)
        except Exception:
            pass
        flash('Registration confirmed!', 'success')
        return redirect(url_for('user.registration_detail', reg_id=reg.id))

    return render_template('user/register_event.html', event=event, children=children,
                           agreements=agreements, custom_fields=custom_fields)


@user_bp.route('/registrations')
def registrations():
    regs = (Registration.query
            .filter_by(user_id=current_user.id)
            .order_by(Registration.registered_at.desc())
            .all())
    return render_template('user/registrations.html', registrations=regs)


@user_bp.route('/registrations/<int:reg_id>')
def registration_detail(reg_id):
    reg = Registration.query.filter_by(id=reg_id, user_id=current_user.id).first_or_404()
    return render_template('user/registration_detail.html', reg=reg)


@user_bp.route('/registrations/<int:reg_id>/cancel', methods=['POST'])
def cancel_registration(reg_id):
    reg = Registration.query.filter_by(id=reg_id, user_id=current_user.id).first_or_404()
    if reg.status in ('pending', 'confirmed'):
        reg.status = 'cancelled'
        db.session.commit()
        # ── Waitlist auto-promotion ───────────────────────────────────────────
        _promote_waitlist(reg.event_id, reg.division_id)
        flash('Registration cancelled.', 'info')
    return redirect(url_for('user.registrations'))


def _promote_waitlist(event_id, division_id):
    """Promote the oldest waitlisted registration when a spot opens up."""
    next_up = (Registration.query
               .filter_by(event_id=event_id, division_id=division_id, status='waitlist')
               .order_by(Registration.registered_at.asc())
               .first())
    if not next_up:
        return
    next_up.status = 'confirmed'
    db.session.commit()
    try:
        from app.utils.email import send_status_update
        send_status_update(next_up)
    except Exception:
        pass


# ─── Profile ─────────────────────────────────────────────────────────────────

@user_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', current_user.first_name)
        current_user.last_name = request.form.get('last_name', current_user.last_name)
        current_user.phone = request.form.get('phone', current_user.phone)
        f = request.files.get('profile_image')
        if f and f.filename:
            delete_file(current_user.profile_image)
            current_user.profile_image = upload_file(f, 'profiles')
        new_pw = request.form.get('new_password')
        if new_pw:
            if not current_user.check_password(request.form.get('current_password', '')):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('user.profile'))
            current_user.set_password(new_pw)
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('user.profile'))
    return render_template('user/profile.html')


# ─── Notifications ───────────────────────────────────────────────────────────

@user_bp.route('/notifications/read/<int:notif_id>', methods=['POST'])
def mark_notification_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({'ok': True})
