from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()
with app.app_context():
    insp = inspect(db.engine)
    user_cols = [c['name'] for c in insp.get_columns('users')]
    print("Current users columns:", user_cols)

    with db.engine.begin() as conn:
        if 'reset_token' not in user_cols:
            conn.execute(text('ALTER TABLE users ADD COLUMN reset_token VARCHAR(100)'))
            print("Added reset_token")
        else:
            print("reset_token already exists")

        if 'reset_token_expires' not in user_cols:
            conn.execute(text('ALTER TABLE users ADD COLUMN reset_token_expires DATETIME'))
            print("Added reset_token_expires")
        else:
            print("reset_token_expires already exists")

    # Verify
    insp2 = inspect(db.engine)
    final_cols = [c['name'] for c in insp2.get_columns('users')]
    print("Final users columns:", final_cols)
    print("Migration complete.")
