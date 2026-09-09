"""Vercel's Python function entry point. Secrets are runtime environment variables."""
import os
os.environ.setdefault('APP_HOST','0.0.0.0')
os.environ.setdefault('DATA_DIR','/tmp/sheetwise')
os.environ.setdefault('STORAGE_MODE','blob')
os.environ.setdefault('COOKIE_SECURE','true')
from backend.main import create_app
app=create_app()
