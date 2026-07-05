from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import secrets


class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')  # string, json, bool, int
    label = db.Column(db.String(200))
    group = db.Column(db.String(100), default='general')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=None):
        s = SiteSettings.query.filter_by(key=key).first()
        if not s:
            return default
        if s.value_type == 'json':
            try:
                return json.loads(s.value)
            except Exception:
                return default
        if s.value_type == 'bool':
            return s.value.lower() in ('true', '1', 'yes')
        if s.value_type == 'int':
            try:
                return int(s.value)
            except Exception:
                return default
        return s.value

    @staticmethod
    def set(key, value, value_type='string', label=None, group='general'):
        s = SiteSettings.query.filter_by(key=key).first()
        if not s:
            s = SiteSettings(key=key, value_type=value_type, label=label, group=group)
            db.session.add(s)
        if value_type == 'json':
            s.value = json.dumps(value)
        else:
            s.value = str(value)
        s.value_type = value_type
        if label:
            s.label = label
        if group:
            s.group = group
        db.session.commit()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    role = db.Column(db.String(20), default='parent')  # parent, admin, organizer
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(500))
    reset_token = db.Column(db.String(100))
    reset_token_expires = db.Column(db.DateTime)
    verify_token = db.Column(db.String(100))
    verify_token_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    children = db.relationship('Child', backref='parent', lazy=True, cascade='all, delete-orphan')
    registrations = db.relationship('Registration', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def is_admin(self):
        return self.role == 'admin'

    def is_organizer(self):
        return self.role in ('admin', 'organizer')

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    def verify_reset_token(self, token):
        if not self.reset_token or self.reset_token != token:
            return False
        if self.reset_token_expires and datetime.utcnow() > self.reset_token_expires:
            return False
        return True

    def generate_verify_token(self):
        self.verify_token = secrets.token_urlsafe(32)
        self.verify_token_expires = datetime.utcnow() + timedelta(hours=24)
        return self.verify_token

    def confirm_verify_token(self, token):
        if not self.verify_token or self.verify_token != token:
            return False
        if self.verify_token_expires and datetime.utcnow() > self.verify_token_expires:
            return False
        self.is_verified = True
        self.verify_token = None
        self.verify_token_expires = None
        return True


class Child(db.Model):
    __tablename__ = 'children'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(20))
    medical_notes = db.Column(db.Text)
    profile_image = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    documents = db.relationship('ChildDocument', backref='child', lazy=True, cascade='all, delete-orphan')
    registrations = db.relationship('Registration', backref='child', lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        today = datetime.today().date()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class ChildDocument(db.Model):
    __tablename__ = 'child_documents'
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id'), nullable=False)
    doc_type = db.Column(db.String(100))  # birth_certificate, medical, id, etc.
    file_url = db.Column(db.String(500))
    file_name = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Sport(db.Model):
    __tablename__ = 'sports'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(500))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    events = db.relationship('Event', backref='sport', lazy=True)


class AgeGroup(db.Model):
    __tablename__ = 'age_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # U7, U9, U11, etc.
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    description = db.Column(db.String(200))
    sort_order = db.Column(db.Integer, default=0)


class Venue(db.Model):
    __tablename__ = 'venues'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(100), default='USA')
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    capacity = db.Column(db.Integer)
    facilities = db.Column(db.Text)
    images = db.relationship('VenueImage', backref='venue', lazy=True, cascade='all, delete-orphan')
    events = db.relationship('Event', backref='venue', lazy=True)

    @property
    def full_address(self):
        parts = [self.address, self.city, self.state, self.zip_code]
        return ', '.join(p for p in parts if p)


class VenueImage(db.Model):
    __tablename__ = 'venue_images'
    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venues.id'), nullable=False)
    image_url = db.Column(db.String(500))
    caption = db.Column(db.String(200))
    is_primary = db.Column(db.Boolean, default=False)


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False)
    sport_id = db.Column(db.Integer, db.ForeignKey('sports.id'), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey('venues.id'))
    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    description = db.Column(db.Text)
    short_description = db.Column(db.String(500))
    rules = db.Column(db.Text)
    requirements = db.Column(db.Text)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    registration_deadline = db.Column(db.DateTime)
    status = db.Column(db.String(30), default='draft')  # draft, published, cancelled, completed
    gender_category = db.Column(db.String(20), default='all')  # all, male, female
    max_participants = db.Column(db.Integer)
    featured = db.Column(db.Boolean, default=False)
    cover_image = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    images = db.relationship('EventImage', backref='event', lazy=True, cascade='all, delete-orphan')
    age_divisions = db.relationship('EventAgeDivision', backref='event', lazy=True, cascade='all, delete-orphan')
    registrations = db.relationship('Registration', backref='event', lazy=True)
    custom_fields = db.relationship('EventCustomField', backref='event', lazy=True, cascade='all, delete-orphan')
    organizer = db.relationship('User', foreign_keys=[organizer_id])

    @property
    def registration_open(self):
        if self.status != 'published':
            return False
        if self.registration_deadline and datetime.utcnow() > self.registration_deadline:
            return False
        if self.max_participants:
            count = Registration.query.filter_by(event_id=self.id, status='confirmed').count()
            if count >= self.max_participants:
                return False
        return True

    @property
    def participant_count(self):
        return Registration.query.filter_by(event_id=self.id, status='confirmed').count()


class EventImage(db.Model):
    __tablename__ = 'event_images'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    image_url = db.Column(db.String(500))
    caption = db.Column(db.String(200))
    is_primary = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)


class EventAgeDivision(db.Model):
    __tablename__ = 'event_age_divisions'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    age_group_id = db.Column(db.Integer, db.ForeignKey('age_groups.id'))
    name = db.Column(db.String(100))
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    entry_fee = db.Column(db.Numeric(10, 2), default=0)
    max_spots = db.Column(db.Integer)
    gender = db.Column(db.String(20), default='all')
    weight_class = db.Column(db.String(100))
    age_group = db.relationship('AgeGroup')

    @property
    def spots_remaining(self):
        if not self.max_spots:
            return None
        taken = Registration.query.filter_by(division_id=self.id, status='confirmed').count()
        return max(0, self.max_spots - taken)


class EventCustomField(db.Model):
    __tablename__ = 'event_custom_fields'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    field_label = db.Column(db.String(200))
    field_type = db.Column(db.String(50), default='text')  # text, select, checkbox, file
    options = db.Column(db.Text)  # JSON for select options
    required = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)


class Agreement(db.Model):
    __tablename__ = 'agreements'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)  # null = global
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    required = db.Column(db.Boolean, default=True)
    is_global = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Registration(db.Model):
    __tablename__ = 'registrations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id'), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey('event_age_divisions.id'))
    status = db.Column(db.String(30), default='pending')  # pending, confirmed, cancelled, waitlist
    payment_status = db.Column(db.String(30), default='unpaid')  # unpaid, paid, refunded
    payment_intent_id = db.Column(db.String(200))
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    custom_field_values = db.Column(db.Text)  # JSON
    agreements_signed = db.Column(db.Text)  # JSON list of agreement IDs
    notes = db.Column(db.Text)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    documents = db.relationship('RegistrationDocument', backref='registration', lazy=True, cascade='all, delete-orphan')
    division = db.relationship('EventAgeDivision')

    @property
    def custom_fields_dict(self):
        try:
            return json.loads(self.custom_field_values or '{}')
        except Exception:
            return {}

    @property
    def agreements_list(self):
        try:
            return json.loads(self.agreements_signed or '[]')
        except Exception:
            return []


class RegistrationDocument(db.Model):
    __tablename__ = 'registration_documents'
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey('registrations.id'), nullable=False)
    doc_type = db.Column(db.String(100))
    file_url = db.Column(db.String(500))
    file_name = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class NavMenuItem(db.Model):
    __tablename__ = 'nav_menu_items'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(300))
    parent_id = db.Column(db.Integer, db.ForeignKey('nav_menu_items.id'), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    open_in_new_tab = db.Column(db.Boolean, default=False)
    children = db.relationship('NavMenuItem', backref=db.backref('parent', remote_side=[id]), lazy=True)


class Page(db.Model):
    __tablename__ = 'pages'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False)
    content = db.Column(db.Text)
    meta_title = db.Column(db.String(300))
    meta_description = db.Column(db.String(500))
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
