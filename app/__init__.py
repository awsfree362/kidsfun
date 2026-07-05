import os
import json
from types import SimpleNamespace
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
import boto3
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # no global default; apply per-route
    storage_uri=os.getenv('REDIS_URL', 'memory://'),
)


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    db_url = os.getenv('DATABASE_URL', '')
    # Railway MySQL URLs sometimes come as mysql:// — SQLAlchemy needs mysql+pymysql://
    if db_url.startswith('mysql://') and 'pymysql' not in db_url:
        db_url = db_url.replace('mysql://', 'mysql+pymysql://', 1)
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it in your Railway service Variables tab."
        )
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
    }
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600
    app.config['WTF_CSRF_SSL_STRICT'] = False
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY')
    app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')
    app.config['S3_ENDPOINT_URL'] = os.getenv('S3_ENDPOINT_URL')
    app.config['S3_BUCKET_NAME'] = os.getenv('S3_BUCKET_NAME')
    app.config['S3_ACCESS_KEY_ID'] = os.getenv('S3_ACCESS_KEY_ID')
    app.config['S3_SECRET_ACCESS_KEY'] = os.getenv('S3_SECRET_ACCESS_KEY')
    app.config['S3_REGION'] = os.getenv('S3_REGION', 'auto')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
    app.config['RATELIMIT_STORAGE_URI'] = os.getenv('REDIS_URL', 'memory://')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME', 'noreply@kidscomp.com')
    app.config['APP_URL'] = os.getenv('APP_URL', 'http://localhost:5000')

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    CORS(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.events import events_bp
    from app.routes.user import user_bp
    from app.routes.api import api_bp
    from app.routes.payments import payments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(events_bp)
    app.register_blueprint(user_bp, url_prefix='/dashboard')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(payments_bp, url_prefix='/payments')

    # ── CSRF: exempt JSON-only blueprints (api) and payment webhooks ──────────
    csrf.exempt(api_bp)
    csrf.exempt('app.routes.payments.paystack_webhook')
    csrf.exempt('app.routes.payments.stripe_webhook')
    csrf.exempt('app.routes.payments.payfast_itn')

    # ── Admin AJAX endpoints send X-CSRFToken header — validate manually ──────
    # Flask-WTF validates form CSRF automatically; for JSON endpoints in admin
    # we rely on the X-CSRFToken header check built into Flask-WTF when
    # WTF_CSRF_CHECK_DEFAULT is True and the request has the header.

    from app.routes.events import get_cached_settings, get_nav
    from app.models import Sport, User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.template_filter('fromjson')
    def fromjson_filter(value):
        try:
            return json.loads(value or '[]')
        except Exception:
            return []

    @app.context_processor
    def inject_globals():
        raw = get_cached_settings()
        site = SimpleNamespace(**raw) if isinstance(raw, dict) else raw
        return {
            'site': site,
            'nav_items': get_nav(),
            'sports_list': Sport.query.filter_by(is_active=True).order_by(Sport.sort_order).all(),
        }

    # ── Security headers ──────────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        # Only set HSTS in production (when not running on localhost)
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # ── Rate limit error handler ──────────────────────────────────────────────
    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify(error='Too many requests. Please slow down.'), 429
        from flask import flash, redirect, url_for
        flash('Too many attempts. Please wait a moment and try again.', 'warning')
        return redirect(request.referrer or url_for('events.index'))

    # ── CSRF error handler ────────────────────────────────────────────────────
    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if request.is_json:
            return jsonify(error='CSRF token missing or invalid.'), 400
        from flask import flash, redirect
        flash('Session expired. Please try again.', 'warning')
        return redirect(request.referrer or '/')

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app


def get_redis():
    return redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)


def get_s3():
    return boto3.client(
        's3',
        endpoint_url=os.getenv('S3_ENDPOINT_URL'),
        region_name=os.getenv('S3_REGION', 'auto'),
        aws_access_key_id=os.getenv('S3_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('S3_SECRET_ACCESS_KEY'),
    )
