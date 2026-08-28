# NexVE Preview Run Doc

## Reproduce uncommitted artifacts
No special env files needed. The app uses SQLite by default.

## Install dependencies
```bash
pip3 install -r requirements.txt
```

## Run the server
```bash
cd "/Volumes/Mac Storage/GitHub/NexVE"
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080
```

The server runs at http://localhost:8080. First boot redirects to /setup.
