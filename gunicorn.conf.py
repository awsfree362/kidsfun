import os

# Workers: 2 * CPU cores + 1 is the standard formula
workers = int(os.getenv('WEB_CONCURRENCY', 3))
worker_class = 'sync'
threads = int(os.getenv('GUNICORN_THREADS', 2))

# Binding
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Timeouts
timeout = 120
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = '-'       # stdout
errorlog = '-'        # stderr
loglevel = os.getenv('LOG_LEVEL', 'info')

# Reload in development only
reload = os.getenv('FLASK_ENV') == 'development'

# Security: limit request line and header sizes
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Preload app to catch import errors before workers fork
preload_app = True
