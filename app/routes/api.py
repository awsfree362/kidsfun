from flask import Blueprint, jsonify, request
from app.models import Event, Sport, SiteSettings
from app import get_redis
import json

api_bp = Blueprint('api', __name__)


def _redis_get(key):
    try:
        return get_redis().get(key)
    except Exception:
        return None


def _redis_set(key, timeout, value):
    try:
        get_redis().setex(key, timeout, value)
    except Exception:
        pass


@api_bp.route('/events')
def api_events():
    cache_key = f"api:events:{request.query_string.decode()}"
    cached = _redis_get(cache_key)
    if cached:
        return jsonify(json.loads(cached))

    sport_id = request.args.get('sport', 0, type=int)
    gender = request.args.get('gender', '')
    q = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    query = Event.query.filter_by(status='published')
    if sport_id:
        query = query.filter_by(sport_id=sport_id)
    if gender:
        query = query.filter(Event.gender_category.in_([gender, 'all']))
    if q:
        query = query.filter(Event.title.ilike(f'%{q}%'))

    events = query.order_by(Event.start_date).paginate(page=page, per_page=12)
    data = {
        'total': events.total,
        'pages': events.pages,
        'page': events.page,
        'items': [{
            'id': e.id,
            'title': e.title,
            'slug': e.slug,
            'sport': e.sport.name,
            'start_date': e.start_date.isoformat(),
            'venue': e.venue.full_address if e.venue else '',
            'cover_image': e.cover_image,
            'registration_open': e.registration_open,
            'participant_count': e.participant_count,
        } for e in events.items]
    }
    _redis_set(cache_key, 120, json.dumps(data))
    return jsonify(data)


@api_bp.route('/sports')
def api_sports():
    cached = _redis_get('api:sports')
    if cached:
        return jsonify(json.loads(cached))
    sports = Sport.query.filter_by(is_active=True).order_by(Sport.sort_order).all()
    data = [{'id': s.id, 'name': s.name, 'slug': s.slug, 'icon': s.icon} for s in sports]
    _redis_set('api:sports', 300, json.dumps(data))
    return jsonify(data)


@api_bp.route('/settings')
def api_settings():
    keys = request.args.getlist('keys') or ['site_name', 'primary_color', 'secondary_color',
                                              'currency_symbol', 'hero_title']
    return jsonify({k: SiteSettings.get(k, '') for k in keys})
