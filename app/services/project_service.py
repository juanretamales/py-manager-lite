from typing import List, Dict, Any, Optional
from app.db.session import get_db_session
from app.repositories.project_repo import ProjectRepository
from app.repositories.client_repo import ClientRepository


class ProjectService:
    def list_projects(self, client_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db_session() as db:
            repo = ProjectRepository(db)
            projects = repo.list_projects(client_id=client_id, status=status)
            result = []
            for p in projects:
                result.append({
                    "id": p.id,
                    "name": p.name,
                    "client_id": p.client_id,
                    "client_name": p.client.name if p.client else "N/A",
                    "quote_id": p.quote_id,
                    "quote_number": p.quote.number if p.quote else "-",
                    "status": p.status,
                    "progress": p.progress,
                    "description": p.description or "",
                    "notes": p.notes or "",
                    "start_date": p.start_date.strftime("%Y-%m-%d") if p.start_date else "",
                    "estimated_end_date": p.estimated_end_date.strftime("%Y-%m-%d") if p.estimated_end_date else "-",
                    "actual_end_date": p.actual_end_date.strftime("%Y-%m-%d") if p.actual_end_date else "-"
                })
            return result

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        import os
        from app.repositories.finance_repo import FinanceRepository
        with get_db_session() as db:
            repo = ProjectRepository(db)
            fin_repo = FinanceRepository(db)
            p = repo.get_by_id(project_id)
            if not p:
                return None

            invoices_data = []
            for inv in p.invoices:
                summary = fin_repo.get_invoice_summary(inv)
                invoices_data.append({
                    "id": inv.id,
                    "type": inv.type,
                    "number": inv.number,
                    "category": inv.category or "General",
                    "total_amount": inv.total_amount,
                    "total_paid": summary["total_paid"],
                    "balance": summary["balance"],
                    "status": summary["status"],
                    "has_document": bool(inv.document_path and os.path.exists(inv.document_path)),
                    "document_path": inv.document_path or "",
                    "issue_date": inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "",
                    "notes": inv.notes or ""
                })

            return {
                "id": p.id,
                "name": p.name,
                "client_id": p.client_id,
                "client_name": p.client.name if p.client else "N/A",
                "quote_id": p.quote_id,
                "quote_number": p.quote.number if p.quote else "-",
                "status": p.status,
                "progress": p.progress,
                "description": p.description or "",
                "notes": p.notes or "",
                "start_date": p.start_date.strftime("%Y-%m-%d") if p.start_date else "",
                "estimated_end_date": p.estimated_end_date.strftime("%Y-%m-%d") if p.estimated_end_date else "",
                "invoices": invoices_data,
                "events": [
                    {
                        "id": ev.id,
                        "date": ev.date.strftime("%Y-%m-%d %H:%M") if ev.date else "",
                        "event_type": ev.event_type,
                        "description": ev.description
                    }
                    for ev in p.events
                ]
            }

    def create_project(self, **data) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = ProjectRepository(db)
            client_repo = ClientRepository(db)
            project = repo.create(**data)

            client_repo.add_event(
                client_id=project.client_id,
                event_type="PROJECT",
                description=f"Nuevo proyecto creado: '{project.name}'",
                project_id=project.id
            )
            return {"id": project.id, "name": project.name, "status": project.status}

    def update_project(self, project_id: int, **data) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = ProjectRepository(db)
            p = repo.update(project_id, **data)
            if p:
                return {"id": p.id, "name": p.name, "status": p.status, "progress": p.progress}
            return None

    def update_progress(self, project_id: int, progress: int, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = ProjectRepository(db)
            p = repo.update_progress(project_id, progress, notes)
            if p:
                return {"id": p.id, "progress": p.progress, "status": p.status}
            return None
