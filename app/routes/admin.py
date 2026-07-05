from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Event, Sport, Venue, AgeGroup, SiteSettings, User,
                         NavMenuItem, Page, Agreement, EventAgeDivision,
                         EventCustomField, EventImage, VenueImage, Notification, Registration)
from app.utils.helpers import admin_required, unique_slug, invalidate_cache
from app.utils.storage import upload_file, delete_file
from app.utils.forms import (EventForm, VenueForm, SportForm, AgeGroupForm,
                               SiteSettingsForm, PageForm, AgreementForm)
import json
from datetime import datetime

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
def require_admin():
    from flask_login import login_required
    from flask import redirect, url_for
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if not current_user.is_admin():
        from flask import abort
        abort(403)


@admin_bp.route('/')
def dashboard():
    from datetime import timedelta
    from sqlalchemy import func
    stats = {
        'events': Event.query.count(),
        'published': Event.query.filter_by(status='published').count(),
        'users': User.query.filter_by(role='parent').count(),
        'registrations': Registration.query.count(),
        'confirmed': Registration.query.filter_by(status='confirmed').count(),
        'pending': Registration.query.filter_by(status='pending').count(),
        'revenue': db.session.query(func.sum(Registration.amount_paid))
                     .filter_by(payment_status='paid').scalar() or 0,
        'sports': Sport.query.count(),
        'venues': Venue.query.count(),
    }
    recent_regs = (Registration.query
                   .order_by(Registration.registered_at.desc())
                   .limit(10).all())
    top_events = (db.session.query(Event, func.count(Registration.id).label('reg_count'))
                  .join(Registration, Registration.event_id == Event.id)
                  .group_by(Event.id)
                  .order_by(func.count(Registration.id).desc())
                  .limit(5).all())
    return render_template('admin/dashboard.html', stats=stats,
                           recent_regs=recent_regs, top_events=top_events)


# ─── Events ──────────────────────────────────────────────────────────────────

@admin_bp.route('/events')
def events():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '')
    query = Event.query
    if q:
        query = query.filter(Event.title.ilike(f'%{q}%'))
    events = query.order_by(Event.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/events.html', events=events, q=q)


@admin_bp.route('/events/new', methods=['GET', 'POST'])
def event_new():
    form = EventForm()
    form.sport_id.choices = [(s.id, s.name) for s in Sport.query.filter_by(is_active=True).all()]
    form.venue_id.choices = [(0, '-- Select Venue --')] + [(v.id, v.name) for v in Venue.query.all()]
    if form.validate_on_submit():
        event = Event(
            title=form.title.data,
            slug=unique_slug(Event, form.title.data),
            sport_id=form.sport_id.data,
            venue_id=form.venue_id.data or None,
            organizer_id=current_user.id,
            description=form.description.data,
            short_description=form.short_description.data,
            rules=form.rules.data,
            requirements=form.requirements.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            registration_deadline=form.registration_deadline.data,
            status=form.status.data,
            gender_category=form.gender_category.data,
            max_participants=form.max_participants.data,
            featured=form.featured.data,
        )
        if form.cover_image.data and form.cover_image.data.filename:
            event.cover_image = upload_file(form.cover_image.data, 'events')
        db.session.add(event)
        db.session.commit()
        invalidate_cache('events:*')
        flash('Event created.', 'success')
        return redirect(url_for('admin.event_edit', event_id=event.id))
    return render_template('admin/event_form.html', form=form, event=None)


@admin_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
def event_edit(event_id):
    event = Event.query.get_or_404(event_id)
    form = EventForm(obj=event)
    form.sport_id.choices = [(s.id, s.name) for s in Sport.query.filter_by(is_active=True).all()]
    form.venue_id.choices = [(0, '-- Select Venue --')] + [(v.id, v.name) for v in Venue.query.all()]
    if form.validate_on_submit():
        event.title = form.title.data
        event.sport_id = form.sport_id.data
        event.venue_id = form.venue_id.data or None
        event.description = form.description.data
        event.short_description = form.short_description.data
        event.rules = form.rules.data
        event.requirements = form.requirements.data
        event.start_date = form.start_date.data
        event.end_date = form.end_date.data
        event.registration_deadline = form.registration_deadline.data
        event.status = form.status.data
        event.gender_category = form.gender_category.data
        event.max_participants = form.max_participants.data
        event.featured = form.featured.data
        if form.cover_image.data and form.cover_image.data.filename:
            delete_file(event.cover_image)
            event.cover_image = upload_file(form.cover_image.data, 'events')
        db.session.commit()
        invalidate_cache('events:*')
        flash('Event updated.', 'success')
        return redirect(url_for('admin.event_edit', event_id=event.id))
    return render_template('admin/event_form.html', form=form, event=event)


@admin_bp.route('/events/<int:event_id>/delete', methods=['POST'])
def event_delete(event_id):
    event = Event.query.get_or_404(event_id)
    delete_file(event.cover_image)
    db.session.delete(event)
    db.session.commit()
    invalidate_cache('events:*')
    flash('Event deleted.', 'success')
    return redirect(url_for('admin.events'))


# ─── Age Divisions (AJAX) ────────────────────────────────────────────────────

@admin_bp.route('/events/<int:event_id>/divisions', methods=['GET', 'POST'])
def event_divisions(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        data = request.get_json()
        div = EventAgeDivision(
            event_id=event_id,
            name=data.get('name'),
            min_age=data.get('min_age'),
            max_age=data.get('max_age'),
            entry_fee=data.get('entry_fee', 0),
            max_spots=data.get('max_spots'),
            gender=data.get('gender', 'all'),
            weight_class=data.get('weight_class'),
        )
        db.session.add(div)
        db.session.commit()
        return jsonify({'id': div.id, 'name': div.name, 'entry_fee': str(div.entry_fee)})
    divs = [{'id': d.id, 'name': d.name, 'min_age': d.min_age, 'max_age': d.max_age,
              'entry_fee': str(d.entry_fee), 'max_spots': d.max_spots,
              'gender': d.gender, 'weight_class': d.weight_class} for d in event.age_divisions]
    return jsonify(divs)


@admin_bp.route('/events/divisions/<int:div_id>', methods=['PUT', 'DELETE'])
def division_detail(div_id):
    div = EventAgeDivision.query.get_or_404(div_id)
    if request.method == 'DELETE':
        db.session.delete(div)
        db.session.commit()
        return jsonify({'ok': True})
    data = request.get_json()
    for field in ('name', 'min_age', 'max_age', 'entry_fee', 'max_spots', 'gender', 'weight_class'):
        if field in data:
            setattr(div, field, data[field])
    db.session.commit()
    return jsonify({'ok': True})


# ─── Custom Fields (AJAX) ────────────────────────────────────────────────────

@admin_bp.route('/events/<int:event_id>/custom-fields', methods=['GET', 'POST'])
def event_custom_fields(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        data = request.get_json()
        cf = EventCustomField(
            event_id=event_id,
            field_name=data.get('field_name'),
            field_label=data.get('field_label'),
            field_type=data.get('field_type', 'text'),
            options=json.dumps(data.get('options', [])),
            required=data.get('required', False),
            sort_order=data.get('sort_order', 0),
        )
        db.session.add(cf)
        db.session.commit()
        return jsonify({'id': cf.id})
    fields = [{'id': f.id, 'field_name': f.field_name, 'field_label': f.field_label,
               'field_type': f.field_type, 'required': f.required} for f in event.custom_fields]
    return jsonify(fields)


@admin_bp.route('/events/custom-fields/<int:cf_id>', methods=['DELETE'])
def custom_field_delete(cf_id):
    cf = EventCustomField.query.get_or_404(cf_id)
    db.session.delete(cf)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Event Images (AJAX) ─────────────────────────────────────────────────────

@admin_bp.route('/events/<int:event_id>/images', methods=['POST'])
def event_images_upload(event_id):
    event = Event.query.get_or_404(event_id)
    files = request.files.getlist('images')
    uploaded = []
    for f in files:
        url = upload_file(f, 'events')
        if url:
            img = EventImage(event_id=event_id, image_url=url,
                             caption=request.form.get('caption', ''))
            db.session.add(img)
            uploaded.append(url)
    db.session.commit()
    return jsonify({'uploaded': uploaded})


@admin_bp.route('/events/images/<int:img_id>/delete', methods=['POST'])
def event_image_delete(img_id):
    img = EventImage.query.get_or_404(img_id)
    delete_file(img.image_url)
    db.session.delete(img)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Sports ──────────────────────────────────────────────────────────────────

@admin_bp.route('/sports')
def sports():
    sports = Sport.query.order_by(Sport.sort_order).all()
    return render_template('admin/sports.html', sports=sports)


@admin_bp.route('/sports/new', methods=['GET', 'POST'])
@admin_bp.route('/sports/<int:sport_id>/edit', methods=['GET', 'POST'])
def sport_form(sport_id=None):
    sport = Sport.query.get_or_404(sport_id) if sport_id else None
    form = SportForm(obj=sport)
    if form.validate_on_submit():
        if not sport:
            sport = Sport(slug=unique_slug(Sport, form.name.data))
            db.session.add(sport)
        sport.name = form.name.data
        sport.description = form.description.data
        sport.is_active = form.is_active.data
        sport.sort_order = form.sort_order.data or 0
        fa_icon = request.form.get('fa_icon', '').strip()
        if form.icon.data and form.icon.data.filename:
            delete_file(sport.icon)
            sport.icon = upload_file(form.icon.data, 'sports')
        elif fa_icon:
            sport.icon = fa_icon
        db.session.commit()
        invalidate_cache('sports:*')
        flash('Sport saved.', 'success')
        return redirect(url_for('admin.sports'))
    return render_template('admin/sport_form.html', form=form, sport=sport)


@admin_bp.route('/sports/<int:sport_id>/delete', methods=['POST'])
def sport_delete(sport_id):
    sport = Sport.query.get_or_404(sport_id)
    db.session.delete(sport)
    db.session.commit()
    flash('Sport deleted.', 'success')
    return redirect(url_for('admin.sports'))


# ─── Age Groups ──────────────────────────────────────────────────────────────

@admin_bp.route('/age-groups')
def age_groups():
    groups = AgeGroup.query.order_by(AgeGroup.sort_order).all()
    return render_template('admin/age_groups.html', groups=groups)


@admin_bp.route('/age-groups/new', methods=['GET', 'POST'])
@admin_bp.route('/age-groups/<int:group_id>/edit', methods=['GET', 'POST'])
def age_group_form(group_id=None):
    group = AgeGroup.query.get_or_404(group_id) if group_id else None
    form = AgeGroupForm(obj=group)
    if form.validate_on_submit():
        if not group:
            group = AgeGroup()
            db.session.add(group)
        form.populate_obj(group)
        db.session.commit()
        flash('Age group saved.', 'success')
        return redirect(url_for('admin.age_groups'))
    return render_template('admin/age_group_form.html', form=form, group=group)


@admin_bp.route('/age-groups/<int:group_id>/delete', methods=['POST'])
def age_group_delete(group_id):
    group = AgeGroup.query.get_or_404(group_id)
    db.session.delete(group)
    db.session.commit()
    flash('Age group deleted.', 'success')
    return redirect(url_for('admin.age_groups'))


# ─── Venues ──────────────────────────────────────────────────────────────────

@admin_bp.route('/venues')
def venues():
    venues = Venue.query.all()
    return render_template('admin/venues.html', venues=venues)


@admin_bp.route('/venues/new', methods=['GET', 'POST'])
@admin_bp.route('/venues/<int:venue_id>/edit', methods=['GET', 'POST'])
def venue_form(venue_id=None):
    venue = Venue.query.get_or_404(venue_id) if venue_id else None
    form = VenueForm(obj=venue)
    if form.validate_on_submit():
        if not venue:
            venue = Venue()
            db.session.add(venue)
        form.populate_obj(venue)
        db.session.commit()
        flash('Venue saved.', 'success')
        return redirect(url_for('admin.venues'))
    return render_template('admin/venue_form.html', form=form, venue=venue)


@admin_bp.route('/venues/<int:venue_id>/delete', methods=['POST'])
def venue_delete(venue_id):
    venue = Venue.query.get_or_404(venue_id)
    if venue.events:
        flash('Cannot delete venue with existing events.', 'danger')
        return redirect(url_for('admin.venues'))
    db.session.delete(venue)
    db.session.commit()
    flash('Venue deleted.', 'success')
    return redirect(url_for('admin.venues'))


@admin_bp.route('/venues/<int:venue_id>/images', methods=['POST'])
def venue_images_upload(venue_id):
    venue = Venue.query.get_or_404(venue_id)
    files = request.files.getlist('images')
    for f in files:
        url = upload_file(f, 'venues')
        if url:
            img = VenueImage(venue_id=venue_id, image_url=url)
            db.session.add(img)
    db.session.commit()
    return jsonify({'ok': True})


# ─── Registrations ───────────────────────────────────────────────────────────

@admin_bp.route('/registrations')
def registrations():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    event_id = request.args.get('event_id', 0, type=int)
    query = Registration.query
    if status:
        query = query.filter_by(status=status)
    if event_id:
        query = query.filter_by(event_id=event_id)
    regs = query.order_by(Registration.registered_at.desc()).paginate(page=page, per_page=25)
    events = Event.query.order_by(Event.title).all()
    return render_template('admin/registrations.html', regs=regs, events=events,
                           status=status, event_id=event_id)


@admin_bp.route('/registrations/<int:reg_id>/status', methods=['POST'])
def registration_status(reg_id):
    reg = Registration.query.get_or_404(reg_id)
    new_status = request.form.get('status')
    if new_status in ('pending', 'confirmed', 'cancelled', 'waitlist'):
        reg.status = new_status
        db.session.commit()
        try:
            from app.utils.email import send_status_update
            send_status_update(reg)
        except Exception:
            pass
        flash(f'Registration status updated to {new_status}.', 'success')
    return redirect(url_for('admin.registrations'))


@admin_bp.route('/registrations/<int:reg_id>')
def registration_detail(reg_id):
    reg = Registration.query.get_or_404(reg_id)
    return render_template('admin/registration_detail.html', reg=reg)


@admin_bp.route('/registrations/export')
def registrations_export():
    import csv
    import io
    from flask import Response
    status = request.args.get('status', '')
    event_id = request.args.get('event_id', 0, type=int)
    query = Registration.query
    if status:
        query = query.filter_by(status=status)
    if event_id:
        query = query.filter_by(event_id=event_id)
    regs = query.order_by(Registration.registered_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Parent', 'Email', 'Child', 'Child Age', 'Event', 'Division',
                     'Status', 'Payment', 'Amount', 'Registered At'])
    for r in regs:
        writer.writerow([
            r.id, r.user.full_name, r.user.email, r.child.full_name, r.child.age,
            r.event.title, r.division.name if r.division else '',
            r.status, r.payment_status, float(r.amount_paid or 0),
            r.registered_at.strftime('%Y-%m-%d %H:%M')
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=registrations.csv'}
    )


# ─── Users ───────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
def users():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '')
    role = request.args.get('role', '')
    query = User.query
    if q:
        query = query.filter(
            (User.email.ilike(f'%{q}%')) |
            (User.first_name.ilike(f'%{q}%')) |
            (User.last_name.ilike(f'%{q}%'))
        )
    if role:
        query = query.filter_by(role=role)
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=25)
    return render_template('admin/users.html', users=users, q=q)


@admin_bp.route('/users/export')
def users_export():
    import csv, io
    from flask import Response
    users = User.query.order_by(User.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Role',
                     'Active', 'Children', 'Registrations', 'Joined'])
    for u in users:
        writer.writerow([
            u.id, u.first_name, u.last_name, u.email, u.phone or '',
            u.role, u.is_active, len(u.children), len(u.registrations),
            u.created_at.strftime('%Y-%m-%d')
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=users.csv'}
    )


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
def user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    if new_role in ('parent', 'admin', 'organizer'):
        user.role = new_role
        db.session.commit()
        flash('User role updated.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash('User status updated.', 'success')
    return redirect(url_for('admin.users'))


# ─── Site Settings ───────────────────────────────────────────────────────────

@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    form = SiteSettingsForm()
    settings_map = {
        'site_name': ('string', 'general'),
        'site_tagline': ('string', 'general'),
        'primary_color': ('string', 'appearance'),
        'secondary_color': ('string', 'appearance'),
        'hero_title': ('string', 'appearance'),
        'hero_subtitle': ('string', 'appearance'),
        'footer_text': ('string', 'general'),
        'contact_email': ('string', 'contact'),
        'contact_phone': ('string', 'contact'),
        'facebook_url': ('string', 'social'),
        'instagram_url': ('string', 'social'),
        'twitter_url': ('string', 'social'),
        'active_payment_gateway': ('string', 'payments'),
        'currency': ('string', 'payments'),
        'currency_symbol': ('string', 'payments'),
    }
    if form.validate_on_submit():
        for key, (vtype, group) in settings_map.items():
            val = getattr(form, key).data
            if val is not None:
                SiteSettings.set(key, val, vtype, group=group)
        for file_key, folder in [('site_logo', 'branding'), ('site_favicon', 'branding'), ('hero_image', 'appearance')]:
            f = getattr(form, file_key).data
            if f and f.filename:
                old = SiteSettings.get(file_key)
                delete_file(old)
                url = upload_file(f, folder)
                if url:
                    SiteSettings.set(file_key, url, 'string', group='appearance')
        invalidate_cache('settings:*')
        flash('Settings saved.', 'success')
        return redirect(url_for('admin.settings'))
    # Pre-fill form
    for key in settings_map:
        field = getattr(form, key, None)
        if field:
            field.data = SiteSettings.get(key, '')
    return render_template('admin/settings.html', form=form)


# ─── Pages ───────────────────────────────────────────────────────────────────

@admin_bp.route('/pages')
def pages():
    pages = Page.query.order_by(Page.title).all()
    return render_template('admin/pages.html', pages=pages)


@admin_bp.route('/pages/new', methods=['GET', 'POST'])
@admin_bp.route('/pages/<int:page_id>/edit', methods=['GET', 'POST'])
def page_form(page_id=None):
    page = Page.query.get_or_404(page_id) if page_id else None
    form = PageForm(obj=page)
    if form.validate_on_submit():
        if not page:
            page = Page()
            db.session.add(page)
        form.populate_obj(page)
        db.session.commit()
        flash('Page saved.', 'success')
        return redirect(url_for('admin.pages'))
    return render_template('admin/page_form.html', form=form, page=page)


@admin_bp.route('/pages/<int:page_id>/delete', methods=['POST'])
def page_delete(page_id):
    page = Page.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    flash('Page deleted.', 'success')
    return redirect(url_for('admin.pages'))


# ─── Navigation ──────────────────────────────────────────────────────────────

@admin_bp.route('/navigation', methods=['GET', 'POST'])
def navigation():
    if request.method == 'POST':
        data = request.get_json()
        # Rebuild nav from submitted JSON array
        NavMenuItem.query.delete()
        db.session.commit()
        for item in data:
            nav = NavMenuItem(
                label=item['label'],
                url=item['url'],
                sort_order=item.get('sort_order', 0),
                is_active=item.get('is_active', True),
                open_in_new_tab=item.get('open_in_new_tab', False),
            )
            db.session.add(nav)
        db.session.commit()
        return jsonify({'ok': True})
    items = NavMenuItem.query.filter_by(parent_id=None).order_by(NavMenuItem.sort_order).all()
    return render_template('admin/navigation.html', items=items)


# ─── Notifications ──────────────────────────────────────────────────────────

@admin_bp.route('/notify', methods=['GET', 'POST'])
def send_notification():
    from app.models import Notification
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        target = request.form.get('target', 'all')  # all, confirmed
        send_email_flag = request.form.get('send_email') == '1'
        if not subject or not message:
            flash('Subject and message are required.', 'danger')
            return redirect(url_for('admin.send_notification'))
        if target == 'confirmed':
            user_ids = db.session.query(Registration.user_id).filter_by(status='confirmed').distinct()
            users = User.query.filter(User.id.in_(user_ids)).all()
        else:
            users = User.query.filter_by(is_active=True).all()
        for u in users:
            n = Notification(user_id=u.id, title=subject, message=message)
            db.session.add(n)
        db.session.commit()
        if send_email_flag:
            try:
                from app.utils.email import send_bulk_notification
                send_bulk_notification(users, subject, message)
            except Exception:
                pass
        flash(f'Notification sent to {len(users)} users.', 'success')
        return redirect(url_for('admin.send_notification'))
    return render_template('admin/notify.html')


# ─── Agreements ──────────────────────────────────────────────────────────────

@admin_bp.route('/agreements')
def agreements():
    agreements = Agreement.query.order_by(Agreement.created_at.desc()).all()
    return render_template('admin/agreements.html', agreements=agreements)


@admin_bp.route('/agreements/new', methods=['GET', 'POST'])
@admin_bp.route('/agreements/<int:ag_id>/edit', methods=['GET', 'POST'])
def agreement_form(ag_id=None):
    ag = Agreement.query.get_or_404(ag_id) if ag_id else None
    form = AgreementForm(obj=ag)
    form.event_id.choices = [(0, '-- Global (all events) --')] + [(e.id, e.title) for e in Event.query.all()]
    if form.validate_on_submit():
        if not ag:
            ag = Agreement()
            db.session.add(ag)
        ag.title = form.title.data
        ag.content = form.content.data
        ag.required = form.required.data
        ag.is_global = form.is_global.data
        ag.event_id = form.event_id.data or None
        db.session.commit()
        flash('Agreement saved.', 'success')
        return redirect(url_for('admin.agreements'))
    return render_template('admin/agreement_form.html', form=form, ag=ag)


@admin_bp.route('/agreements/<int:ag_id>/delete', methods=['POST'])
def agreement_delete(ag_id):
    ag = Agreement.query.get_or_404(ag_id)
    db.session.delete(ag)
    db.session.commit()
    flash('Agreement deleted.', 'success')
    return redirect(url_for('admin.agreements'))
