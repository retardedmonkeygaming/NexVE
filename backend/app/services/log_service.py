from datetime import datetime
from ..database import SessionLocal
from ..models.vm import AuditLog, TaskLog, Notification


class LogService:
    def log_action(self, user_id, username, action, target_type=None, target_id=None, target_name=None, details=None, ip_address=None):
        db = SessionLocal()
        try:
            entry = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
                details=details,
                ip_address=ip_address,
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()

    def create_task(self, task_type, target_type=None, target_id=None, target_name=None, message=None) -> int:
        db = SessionLocal()
        try:
            task = TaskLog(
                type=task_type,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
                message=message,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task.id
        finally:
            db.close()

    def complete_task(self, task_id: int, status: str = "ok", message: str = None):
        db = SessionLocal()
        try:
            task = db.query(TaskLog).filter(TaskLog.id == task_id).first()
            if task:
                task.status = status
                task.message = message or task.message
                task.ended_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def get_tasks(self, limit: int = 50) -> list:
        db = SessionLocal()
        try:
            tasks = db.query(TaskLog).order_by(TaskLog.started_at.desc()).limit(limit).all()
            return [
                {
                    "id": t.id,
                    "type": t.type,
                    "status": t.status,
                    "target_type": t.target_type,
                    "target_name": t.target_name,
                    "message": t.message,
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "ended_at": t.ended_at.isoformat() if t.ended_at else None,
                }
                for t in tasks
            ]
        finally:
            db.close()

    def get_audit_log(self, limit: int = 100) -> list:
        db = SessionLocal()
        try:
            logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": l.id,
                    "username": l.username,
                    "action": l.action,
                    "target_type": l.target_type,
                    "target_name": l.target_name,
                    "details": l.details,
                    "ip_address": l.ip_address,
                    "created_at": l.created_at.isoformat() if l.created_at else None,
                }
                for l in logs
            ]
        finally:
            db.close()

    def notify(self, ntype: str, title: str, message: str):
        db = SessionLocal()
        try:
            notif = Notification(type=ntype, title=title, message=message)
            db.add(notif)
            db.commit()
        finally:
            db.close()

    def get_notifications(self, unread_only: bool = False) -> list:
        db = SessionLocal()
        try:
            q = db.query(Notification)
            if unread_only:
                q = q.filter(Notification.read == False)
            notifs = q.order_by(Notification.created_at.desc()).limit(50).all()
            return [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "read": n.read,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in notifs
            ]
        finally:
            db.close()

    def mark_read(self, notif_id: int):
        db = SessionLocal()
        try:
            n = db.query(Notification).filter(Notification.id == notif_id).first()
            if n:
                n.read = True
                db.commit()
        finally:
            db.close()

    def mark_all_read(self):
        db = SessionLocal()
        try:
            db.query(Notification).filter(Notification.read == False).update({"read": True})
            db.commit()
        finally:
            db.close()
