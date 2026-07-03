#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Ensure the Django project package is on sys.path
sys.path.insert(0, str(ROOT / 'ota_platform'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ota_platform.settings')

from django.core.management import execute_from_command_line

if __name__ == '__main__':
    execute_from_command_line(sys.argv)
