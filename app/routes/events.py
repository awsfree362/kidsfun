from flask import Blueprint, render_template, request, abort, Response, url_for
from app.models import Event, Sport, AgeGroup, SiteSettings, NavMenuItem, Page, EventAgeDivision
from app import get_redis
from datetime import datetime
import json

events_bp = Blueprint('events', __name__)


def get_cached_settings():
    try:
        r = get_redis()
        cached = r.get('settings:all')
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    keys = ['site_name', 'site_tagline', 'site_logo', 'primary_color', 'secondary_color',
            'hero_title', 'hero_subtitle', 'hero_image', 'footer_text',
            'contact_email', 'contact_phone', 'facebook_url', 'instagram_url',
            'twitter_url', 'currency_symbol', 'currency']
    data = {k: SiteSettings.get(k, '') for k in keys}
    try:
        r = get_redis()
        r.setex('settings:all', 300, json.dumps(data))
    except Exception:
        pass
    return data


def get_nav():
    try:
        r = get_redis()
        cached = r.get('nav:main')
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    items = NavMenuItem.query.filter_by(parent_id=None, is_active=True).order_by(NavMenuItem.sort_order).all()
    data = [{'label': i.label, 'url': i.url, 'open_in_new_tab': i.open_in_new_tab} for i in items]
    try:
        r = get_redis()
        r.setex('nav:main', 300, json.dumps(data))
    except Exception:
        pass
    return data


@events_bp.route('/')
def index():
    featured = Event.query.filter_by(status='published', featured=True).order_by(Event.start_date).limit(6).all()
    upcoming = Event.query.filter_by(status='published').order_by(Event.start_date).limit(12).all()
    sports = Sport.query.filter_by(is_active=True).order_by(Sport.sort_order).all()
    return render_template('events/index.html', featured=featured, upcoming=upcoming, sports=sports)


@events_bp.route('/events')
def event_list():
    page = request.args.get('page', 1, type=int)
    sport_id = request.args.get('sport', 0, type=int)
    gender = request.args.get('gender', '')
    location = request.args.get('location', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    age_group_id = request.args.get('age_group', 0, type=int)
    q = request.args.get('q', '')

    query = Event.query.filter_by(status='published')

    if q:
        query = query.filter(Event.title.ilike(f'%{q}%'))
    if sport_id:
        query = query.filter_by(sport_id=sport_id)
    if gender:
        query = query.filter(Event.gender_category.in_([gender, 'all']))
    if location:
        from app.models import Venue
        venue_ids = [v.id for v in Venue.query.filter(
            (Venue.city.ilike(f'%{location}%')) | (Venue.state.ilike(f'%{location}%'))
        ).all()]
        query = query.filter(Event.venue_id.in_(venue_ids))
    if date_from:
        try:
            query = query.filter(Event.start_date >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Event.start_date <= datetime.strptime(date_to, '%Y-%m-%d'))
        except ValueError:
            pass
    if age_group_id:
        # Filter events that have at least one division matching this age group
        ag = AgeGroup.query.get(age_group_id)
        if ag:
            matching_event_ids = (
                EventAgeDivision.query
                .filter(
                    EventAgeDivision.min_age <= ag.max_age,
                    EventAgeDivision.max_age >= ag.min_age,
                )
                .with_entities(EventAgeDivision.event_id)
                .distinct()
            )
            query = query.filter(Event.id.in_(matching_event_ids))

    events = query.order_by(Event.start_date).paginate(page=page, per_page=12)
    sports = Sport.query.filter_by(is_active=True).order_by(Sport.sort_order).all()
    age_groups = AgeGroup.query.order_by(AgeGroup.sort_order).all()

    filters = {
        'sport_id': sport_id, 'gender': gender, 'location': location,
        'date_from': date_from, 'date_to': date_to, 'q': q,
        'age_group_id': age_group_id,
    }
    return render_template('events/list.html', events=events, sports=sports,
                           age_groups=age_groups, filters=filters)


@events_bp.route('/events/<slug>')
def event_detail(slug):
    event = Event.query.filter_by(slug=slug, status='published').first_or_404()
    from app.models import Agreement
    agreements = Agreement.query.filter(
        (Agreement.is_global == True) | (Agreement.event_id == event.id)
    ).all()
    # OG meta data
    og = {
        'title': event.title,
        'description': event.short_description or (event.description or '')[:160],
        'image': event.cover_image or '',
        'url': url_for('events.event_detail', slug=event.slug, _external=True),
        'type': 'website',
    }
    return render_template('events/detail.html', event=event, agreements=agreements, og=og)


@events_bp.route('/sports/<slug>')
def sport_page(slug):
    sport = Sport.query.filter_by(slug=slug, is_active=True).first_or_404()
    page = request.args.get('page', 1, type=int)
    events = Event.query.filter_by(sport_id=sport.id, status='published').order_by(
        Event.start_date).paginate(page=page, per_page=12)
    return render_template('events/sport.html', sport=sport, events=events)


@events_bp.route('/page/<slug>')
def static_page(slug):
    page = Page.query.filter_by(slug=slug, is_published=True).first_or_404()
    return render_template('events/page.html', page=page)


# ── Sitemap ───────────────────────────────────────────────────────────────────

@events_bp.route('/sitemap.xml')
def sitemap():
    pages = []
    base = url_for('events.index', _external=True).rstrip('/')

    # Static routes
    for endpoint in ['events.index', 'events.event_list', 'auth.login', 'auth.register']:
        pages.append({'loc': url_for(endpoint, _external=True), 'priority': '0.8'})

    # Sport pages
    for sport in Sport.query.filter_by(is_active=True).all():
        pages.append({
            'loc': url_for('events.sport_page', slug=sport.slug, _external=True),
            'priority': '0.7',
        })

    # Event pages
    for event in Event.query.filter_by(status='published').all():
        pages.append({
            'loc': url_for('events.event_detail', slug=event.slug, _external=True),
            'lastmod': event.updated_at.strftime('%Y-%m-%d'),
            'priority': '0.9',
        })

    # Static CMS pages
    for p in Page.query.filter_by(is_published=True).all():
        pages.append({
            'loc': url_for('events.static_page', slug=p.slug, _external=True),
            'lastmod': p.updated_at.strftime('%Y-%m-%d'),
            'priority': '0.5',
        })

    xml = render_template('sitemap.xml', pages=pages)
    return Response(xml, mimetype='application/xml')


@events_bp.route('/robots.txt')
def robots():
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /dashboard/',
        f'Sitemap: {url_for("events.sitemap", _external=True)}',
    ]
    return Response('\n'.join(lines), mimetype='text/plain')
