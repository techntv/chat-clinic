#!/bin/sh
# Container entrypoint for the web service.
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
# gthread workers: the webhook hands work to a thread pool inside each worker process.
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --worker-class gthread \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 60 \
  --access-logfile -
