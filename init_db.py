"""
Run this ONCE to initialise flask-migrate and create the migrations folder.

    python init_db.py

After that, use the standard flask-migrate workflow:
    flask db migrate -m "description"
    flask db upgrade
"""
import subprocess
import sys
import os

os.environ.setdefault('FLASK_APP', 'run.py')

steps = [
    ['flask', 'db', 'init'],
    ['flask', 'db', 'migrate', '-m', 'initial schema'],
    ['flask', 'db', 'upgrade'],
]

for cmd in steps:
    print(f'\n>>> {" ".join(cmd)}')
    result = subprocess.run(cmd)
    if result.returncode != 0:
        # 'init' fails if migrations/ already exists — that's fine, keep going
        if cmd[1] == 'init':
            print('  (migrations/ already exists, skipping init)')
        else:
            print(f'  ERROR: command failed with code {result.returncode}')
            sys.exit(result.returncode)

print('\n✓ Database migrations initialised and applied.')
print('  Seed data: python seed.py')
