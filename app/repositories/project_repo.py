from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.project import Project, ProjectStatus, ProjectEvent, PurchaseOrder


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_projects(self, client_id: Optional[int] = None, status: Optional[str] = None) -> List[Project]:
        query = self.db.query(Project)
        if client_id:
            query = query.filter(Project.client_id == client_id)
        if status:
            query = query.filter(Project.status == status)
        return query.order_by(Project.id.desc()).all()

    def get_by_id(self, project_id: int) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def create(self, **kwargs) -> Project:
        project = Project(**kwargs)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update(self, project_id: int, **kwargs) -> Optional[Project]:
        project = self.get_by_id(project_id)
        if project:
            for k, v in kwargs.items():
                if hasattr(project, k):
                    setattr(project, k, v)
            self.db.commit()
            self.db.refresh(project)
        return project

    def update_progress(self, project_id: int, progress: int, notes: Optional[str] = None) -> Optional[Project]:
        project = self.get_by_id(project_id)
        if project:
            project.progress = max(0, min(100, progress))
            if project.progress == 100 and project.status != ProjectStatus.COMPLETED:
                project.status = ProjectStatus.COMPLETED
                project.actual_end_date = datetime.now(timezone.utc)
            if notes:
                project_event = ProjectEvent(
                    project_id=project_id,
                    event_type="PROGRESS_UPDATE",
                    description=f"Progreso actualizado a {project.progress}%: {notes}"
                )
                self.db.add(project_event)
            self.db.commit()
            self.db.refresh(project)
        return project

    def add_event(self, project_id: int, event_type: str, description: str) -> ProjectEvent:
        event = ProjectEvent(
            project_id=project_id,
            event_type=event_type,
            description=description
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_purchase_orders(self, client_id: Optional[int] = None) -> List[PurchaseOrder]:
        query = self.db.query(PurchaseOrder)
        if client_id:
            query = query.filter(PurchaseOrder.client_id == client_id)
        return query.order_by(PurchaseOrder.id.desc()).all()

    def create_purchase_order(self, **kwargs) -> PurchaseOrder:
        po = PurchaseOrder(**kwargs)
        self.db.add(po)
        self.db.commit()
        self.db.refresh(po)
        return po
