#!/bin/sh
set -ue
python manage.py makemigrations
python manage.py migrate