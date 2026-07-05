from app import create_app
app = create_app()
rules = sorted([f"{r.methods} {r.rule}" for r in app.url_map.iter_rules()])
for r in rules:
    print(r)
print(f"\nTotal routes: {len(rules)}")
