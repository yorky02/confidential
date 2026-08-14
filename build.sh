#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python styleleveling/manage.py collectstatic --no-input
python styleleveling/manage.py migrate
