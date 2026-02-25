import sys
import os
import django

# Add current directory to sys.path explicitly
sys.path.insert(0, os.getcwd())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

try:
    from mdl.models import MdlServer
    print(f"MdlServer file: {sys.modules['mdl.models'].__file__}")
    print(f"Fields in MdlServer: {[f.name for f in MdlServer._meta.get_fields()]}")
except Exception as e:
    print(f"Error: {e}")
