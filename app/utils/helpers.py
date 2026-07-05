import json
from functools import wraps
from flask import abort
from flask_login import current_user
from app import get_redis


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def organizer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_organizer():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def cached(key_prefix, timeout=300):
    """Redis cache decorator. key_prefix can contain {kwargs}."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                r = get_redis()
                key = key_prefix.format(**kwargs)
                cached_val = r.get(key)
                if cached_val:
                    return json.loads(cached_val)
                result = f(*args, **kwargs)
                r.setex(key, timeout, json.dumps(result, default=str))
                return result
            except Exception:
                return f(*args, **kwargs)
        return decorated
    return decorator


def invalidate_cache(pattern):
    try:
        r = get_redis()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


def slugify(text):
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


def unique_slug(model, title, exclude_id=None):
    from app import db
    base = slugify(title)
    slug = base
    counter = 1
    while True:
        q = model.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{counter}"
        counter += 1
