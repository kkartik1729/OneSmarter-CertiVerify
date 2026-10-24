#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    # Keep the local API server aligned with the Vite proxy target.
    if (
        len(sys.argv) >= 2
        and sys.argv[1] == 'runserver'
        and (len(sys.argv) == 2 or sys.argv[2].startswith('-'))
    ):
        sys.argv.insert(2, os.getenv('DJANGO_RUNSERVER_PORT', '8000'))
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
