#!/bin/bash
# Run Celery worker with Xvfb virtual display (needed for headed Chrome)
exec xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    celery -A src.celery_app worker -c 1 --loglevel=info "$@"
