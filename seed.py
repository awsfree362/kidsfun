from app import create_app, db
from app.models import User, SiteSettings, Sport, AgeGroup

app = create_app()

with app.app_context():
    db.create_all()

    # Seed admin
    if not User.query.filter_by(email='admin@admin.com').first():
        admin = User(email='admin@admin.com', first_name='Admin', last_name='User', role='admin', is_active=True)
        admin.set_password('Admin@1234')
        db.session.add(admin)

    # Seed default settings
    defaults = {
        'site_name': ('KidsComp', 'string', 'general'),
        'site_tagline': ('Find & Register Kids Competitions', 'string', 'general'),
        'primary_color': ('#6366f1', 'string', 'appearance'),
        'secondary_color': ('#f59e0b', 'string', 'appearance'),
        'hero_title': ('Find the Perfect Competition for Your Child', 'string', 'appearance'),
        'hero_subtitle': ('Browse hundreds of sports events for kids of all ages', 'string', 'appearance'),
        'footer_text': ('© 2024 KidsComp. All rights reserved.', 'string', 'general'),
        'currency': ('ZAR', 'string', 'payments'),
        'currency_symbol': ('R', 'string', 'payments'),
        'active_payment_gateway': ('paystack', 'string', 'payments'),
        'contact_email': ('info@kidscomp.com', 'string', 'contact'),
    }
    for key, (val, vtype, group) in defaults.items():
        if not SiteSettings.query.filter_by(key=key).first():
            SiteSettings.set(key, val, vtype, group=group)

    # Seed sports
    sports_data = [
        ('Soccer',       'soccer',       'fa-futbol'),
        ('Boxing',       'boxing',       'fa-hand-rock'),
        ('Wrestling',    'wrestling',    'fa-people-arrows'),
        ('Athletics',    'athletics',    'fa-running'),
        ('Swimming',     'swimming',     'fa-swimmer'),
        ('Martial Arts', 'martial-arts', 'fa-user-ninja'),
        ('Chess',        'chess',        'fa-chess'),
        ('School Sports','school-sports','fa-school'),
    ]
    for i, (name, slug, icon) in enumerate(sports_data):
        if not Sport.query.filter_by(slug=slug).first():
            db.session.add(Sport(name=name, slug=slug, icon=icon, is_active=True, sort_order=i))

    # Seed age groups
    age_groups = [
        ('U7', 0, 6), ('U9', 7, 8), ('U11', 9, 10),
        ('U13', 11, 12), ('U15', 13, 14), ('U17', 15, 16), ('U19', 17, 18),
    ]
    for i, (name, mn, mx) in enumerate(age_groups):
        if not AgeGroup.query.filter_by(name=name).first():
            db.session.add(AgeGroup(name=name, min_age=mn, max_age=mx, sort_order=i))

    db.session.commit()
    print("Database seeded. Admin: admin@admin.com / Admin@1234")
