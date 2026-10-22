from typing import List, Dict, Any, Optional
from app.db.session import get_db_session
from app.repositories.client_repo import ClientRepository


class ClientService:
    def list_clients(self, search: Optional[str] = None, active_only: bool = False) -> List[Dict[str, Any]]:
        with get_db_session() as db:
            repo = ClientRepository(db)
            clients = repo.list_clients(search=search, active_only=active_only)
            result = []
            for c in clients:
                result.append({
                    "id": c.id,
                    "name": c.name,
                    "legal_name": c.legal_name or "",
                    "tax_id": c.tax_id or "",
                    "business_activity": c.business_activity or "",
                    "address": c.address or "",
                    "contact_name": c.contact_name or "",
                    "email": c.email or "",
                    "phone": c.phone or "",
                    "notes": c.notes or "",
                    "active": c.active,
                    "quotes_count": len(c.quotes),
                    "projects_count": len(c.projects),
                    "created_at": c.created_at.strftime("%Y-%m-%d") if c.created_at else ""
                })
            return result

    def get_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = ClientRepository(db)
            c = repo.get_by_id(client_id)
            if not c:
                return None
            events = repo.get_events(client_id)
            return {
                "id": c.id,
                "name": c.name,
                "legal_name": c.legal_name or "",
                "tax_id": c.tax_id or "",
                "business_activity": c.business_activity or "",
                "address": c.address or "",
                "contact_name": c.contact_name or "",
                "email": c.email or "",
                "phone": c.phone or "",
                "notes": c.notes or "",
                "active": c.active,
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
                "events": [
                    {
                        "id": e.id,
                        "date": e.date.strftime("%Y-%m-%d %H:%M") if e.date else "",
                        "event_type": e.event_type,
                        "description": e.description
                    }
                    for e in events
                ]
            }

    def create_client(self, **data) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = ClientRepository(db)
            c = repo.create(**data)
            # Add initial creation event
            repo.add_event(c.id, "NOTE", f"Cliente creado en el sistema: {c.name}")
            return {"id": c.id, "name": c.name, "active": c.active}

    def update_client(self, client_id: int, **data) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = ClientRepository(db)
            c = repo.update(client_id, **data)
            if c:
                return {"id": c.id, "name": c.name, "active": c.active}
            return None

    def toggle_active(self, client_id: int) -> Optional[bool]:
        with get_db_session() as db:
            repo = ClientRepository(db)
            client = repo.get_by_id(client_id)
            if client:
                new_status = not client.active
                repo.set_active(client_id, new_status)
                status_text = "activado" if new_status else "desactivado"
                repo.add_event(client_id, "NOTE", f"Estado del cliente cambiado a {status_text}")
                return new_status
            return None

    def add_event(self, client_id: int, event_type: str, description: str) -> None:
        with get_db_session() as db:
            repo = ClientRepository(db)
            repo.add_event(client_id, event_type, description)
