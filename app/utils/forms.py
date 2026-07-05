from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, PasswordField, BooleanField, TextAreaField,
                     SelectField, IntegerField, DecimalField, DateTimeLocalField,
                     DateField, HiddenField, SubmitField, MultipleFileField)
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo, NumberRange


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')


class RegisterForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(2, 100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(2, 100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    password = PasswordField('Password', validators=[DataRequired(), Length(8, 128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])


class ChildForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(2, 100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(2, 100)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    medical_notes = TextAreaField('Medical Notes', validators=[Optional()])
    profile_image = FileField('Profile Photo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'])])


class EventForm(FlaskForm):
    title = StringField('Event Title', validators=[DataRequired(), Length(3, 300)])
    sport_id = SelectField('Sport', coerce=int, validators=[DataRequired()])
    venue_id = SelectField('Venue', coerce=int, validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional()])
    short_description = StringField('Short Description', validators=[Optional(), Length(max=500)])
    rules = TextAreaField('Rules & Regulations', validators=[Optional()])
    requirements = TextAreaField('Requirements', validators=[Optional()])
    start_date = DateTimeLocalField('Start Date & Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_date = DateTimeLocalField('End Date & Time', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    registration_deadline = DateTimeLocalField('Registration Deadline', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    status = SelectField('Status', choices=[('draft', 'Draft'), ('published', 'Published'), ('cancelled', 'Cancelled'), ('completed', 'Completed')])
    gender_category = SelectField('Gender Category', choices=[('all', 'All'), ('male', 'Male Only'), ('female', 'Female Only')])
    max_participants = IntegerField('Max Participants', validators=[Optional(), NumberRange(min=1)])
    featured = BooleanField('Featured Event')
    cover_image = FileField('Cover Image', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'gif'])])


class VenueForm(FlaskForm):
    name = StringField('Venue Name', validators=[DataRequired(), Length(2, 200)])
    address = StringField('Address', validators=[Optional()])
    city = StringField('City', validators=[Optional()])
    state = StringField('State / Province', validators=[Optional()])
    zip_code = StringField('ZIP / Postal Code', validators=[Optional()])
    country = StringField('Country', validators=[Optional()])
    capacity = IntegerField('Capacity', validators=[Optional()])
    facilities = TextAreaField('Facilities', validators=[Optional()])


class SportForm(FlaskForm):
    name = StringField('Sport Name', validators=[DataRequired(), Length(2, 100)])
    description = TextAreaField('Description', validators=[Optional()])
    icon = FileField('Icon / Image', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'svg', 'gif'])])
    is_active = BooleanField('Active', default=True)
    sort_order = IntegerField('Sort Order', default=0, validators=[Optional()])


class AgeGroupForm(FlaskForm):
    name = StringField('Name (e.g. U9)', validators=[DataRequired(), Length(1, 50)])
    min_age = IntegerField('Min Age', validators=[Optional()])
    max_age = IntegerField('Max Age', validators=[Optional()])
    description = StringField('Description', validators=[Optional()])
    sort_order = IntegerField('Sort Order', default=0, validators=[Optional()])


class SiteSettingsForm(FlaskForm):
    site_name = StringField('Site Name', validators=[DataRequired()])
    site_tagline = StringField('Tagline', validators=[Optional()])
    site_logo = FileField('Logo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'svg'])])
    site_favicon = FileField('Favicon', validators=[Optional(), FileAllowed(['ico', 'png'])])
    primary_color = StringField('Primary Color (hex)', validators=[Optional()])
    secondary_color = StringField('Secondary Color (hex)', validators=[Optional()])
    hero_title = StringField('Hero Title', validators=[Optional()])
    hero_subtitle = StringField('Hero Subtitle', validators=[Optional()])
    hero_image = FileField('Hero Image', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'])])
    footer_text = TextAreaField('Footer Text', validators=[Optional()])
    contact_email = StringField('Contact Email', validators=[Optional(), Email()])
    contact_phone = StringField('Contact Phone', validators=[Optional()])
    facebook_url = StringField('Facebook URL', validators=[Optional()])
    instagram_url = StringField('Instagram URL', validators=[Optional()])
    twitter_url = StringField('Twitter URL', validators=[Optional()])
    active_payment_gateway = SelectField('Payment Gateway',
        choices=[('paystack', 'Paystack'), ('stripe', 'Stripe'), ('payfast', 'PayFast'), ('yoco', 'Yoco')])
    currency = StringField('Currency Code (e.g. ZAR, USD)', validators=[Optional()])
    currency_symbol = StringField('Currency Symbol (e.g. R, $)', validators=[Optional()])


class PageForm(FlaskForm):
    title = StringField('Page Title', validators=[DataRequired()])
    slug = StringField('URL Slug', validators=[DataRequired()])
    content = TextAreaField('Content (HTML)', validators=[Optional()])
    meta_title = StringField('Meta Title', validators=[Optional()])
    meta_description = TextAreaField('Meta Description', validators=[Optional()])
    is_published = BooleanField('Published', default=True)


class AgreementForm(FlaskForm):
    title = StringField('Agreement Title', validators=[DataRequired()])
    content = TextAreaField('Agreement Content', validators=[DataRequired()])
    required = BooleanField('Required', default=True)
    is_global = BooleanField('Apply to All Events', default=False)
    event_id = SelectField('Event (leave blank for global)', coerce=int, validators=[Optional()])
