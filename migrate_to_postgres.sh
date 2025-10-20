#!/bin/bash

# Migration script from SQLite to PostgreSQL
# This script helps migrate existing SQLite data to PostgreSQL

set -e

echo "FURsvp SQLite to PostgreSQL Migration Script"
echo "============================================="

# Check if SQLite database exists
if [ ! -f "db.sqlite3" ]; then
    echo "Error: db.sqlite3 not found. Make sure you're in the project root directory."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it first."
    exit 1
fi

echo "Step 1: Creating database dump from SQLite..."
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission > datadump.json

echo "Step 2: Starting PostgreSQL container..."
docker-compose up -d db

echo "Step 3: Waiting for PostgreSQL to be ready..."
sleep 10

echo "Step 4: Running migrations..."
docker-compose exec web python manage.py migrate

echo "Step 5: Loading data into PostgreSQL..."
docker-compose exec web python manage.py loaddata datadump.json

echo "Step 6: Creating cache table..."
docker-compose exec web python manage.py createcachetable

echo "Step 7: Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput

echo "Migration completed successfully!"
echo ""
echo "Next steps:"
echo "1. Start the full application: docker-compose up"
echo "2. Create a superuser: docker-compose exec web python manage.py createsuperuser"
echo "3. Test the application at http://localhost:8000"
echo ""
echo "Note: The original SQLite database (db.sqlite3) has been preserved as a backup."
echo "You can remove it after verifying everything works correctly."