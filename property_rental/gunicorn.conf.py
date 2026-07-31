"""Gunicorn runtime settings for the Django production process."""

import os


# Keep the default conservative; increase GUNICORN_WORKERS for larger instances.
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
accesslog = "-"
errorlog = "-"
capture_output = True
timeout = 60
graceful_timeout = 30
worker_tmp_dir = "/tmp"
