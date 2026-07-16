#!/bin/sh
set -e

echo "Applying migrations..."
python manage.py migrate --noinput

if [ "$DEBUG" = "True" ]; then
    echo "Checking whether the database needs seeding..."
    python manage.py shell -c "
from listings.models import Property
import sys
sys.exit(0 if Property.objects.exists() else 1)
" || python manage.py seed_data
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"