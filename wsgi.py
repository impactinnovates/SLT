"""wsgi.py - production entry point.  gunicorn -b 0.0.0.0:8502 wsgi:app"""
from app import app

if __name__ == "__main__":
    app.run()
