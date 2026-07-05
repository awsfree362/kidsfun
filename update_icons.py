from app import create_app, db
from app.models import Sport

app = create_app()
with app.app_context():
    icons = {
        'soccer':       'fa-futbol',
        'boxing':       'fa-hand-rock',
        'wrestling':    'fa-people-arrows',
        'athletics':    'fa-running',
        'swimming':     'fa-swimmer',
        'martial-arts': 'fa-user-ninja',
        'chess':        'fa-chess',
        'school-sports':'fa-school',
    }
    for slug, icon in icons.items():
        s = Sport.query.filter_by(slug=slug).first()
        if s:
            s.icon = icon
            print(f"Updated {s.name} -> {icon}")
    db.session.commit()
    print("Done.")
