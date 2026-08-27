# NexVE Preview Server

## How to Run

```bash
cd /Volumes/Mac Storage/GitHub/NexVE
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Dependencies

All Python dependencies are already installed in the system Python (3.9.6):
- fastapi, uvicorn, sqlalchemy, bcrypt, psutil, jinja2, python-multipart
- aiofiles, itsdangerous, python-jose, pyotp, qrcode, pillow

## Notes

- The app needs to be run from the project root directory
- The backend.app.main module serves the FastAPI application
- Templates are in backend/app/templates/
- Static files are in static/
- The app creates a SQLite database at ~/.nexve/data/nexve.db on first run
