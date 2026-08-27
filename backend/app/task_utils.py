"""Task logging utility — separated to avoid circular imports with main.py."""
from datetime import datetime
from .database import SessionLocal
from .models.user import Task


def log_task(user_id, username, action, target_type=None, target_name=None, status="running"):
    """Log a user action as a task record."""
    db = SessionLocal()
    try:
        task = Task(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_name=target_name,
            status=status,
            finished_at=datetime.utcnow() if status != "running" else None
        )
        db.add(task)
        db.commit()
        task_id = task.id
    finally:
        db.close()
    return task_id
