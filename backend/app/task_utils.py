"""Task logging utility — separated to avoid circular imports with main.py."""
from datetime import datetime
from .database import SessionLocal
from .models.user import Task
from .models.activity import ActivityLog


def log_task(user_id, username, action, target_type=None, target_name=None, status="running"):
    """Log a user action as a task record AND an activity log entry."""
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

        # Also write to ActivityLog so the logs page shows entries
        activity = ActivityLog(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_name=str(target_name) if target_name else None,
            details=f"Status: {status}" if status != "running" else None,
        )
        db.add(activity)

        db.commit()
        task_id = task.id
    finally:
        db.close()
    return task_id
