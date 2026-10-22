from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.client import Client, ClientEvent


class ClientRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_clients(self, search: Optional[str] = None, active_only: bool = False) -> List[Client]:
        query = self.db.query(Client)
        if active_only:
            query = query.filter(Client.active.is_(True))
        if search:
            s = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Client.name.ilike(s),
                    Client.legal_name.ilike(s),
                    Client.tax_id.ilike(s),
                    Client.email.ilike(s),
                    Client.contact_name.ilike(s),
                )
            )
        return query.order_by(Client.name.asc()).all()

    def get_by_id(self, client_id: int) -> Optional[Client]:
        return self.db.query(Client).filter(Client.id == client_id).first()

    def create(self, **kwargs) -> Client:
        client = Client(**kwargs)
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def update(self, client_id: int, **kwargs) -> Optional[Client]:
        client = self.get_by_id(client_id)
        if client:
            for k, v in kwargs.items():
                if hasattr(client, k):
                    setattr(client, k, v)
            self.db.commit()
            self.db.refresh(client)
        return client

    def set_active(self, client_id: int, active: bool) -> Optional[Client]:
        return self.update(client_id, active=active)

    def add_event(self, client_id: int, event_type: str, description: str, **kwargs) -> ClientEvent:
        event = ClientEvent(
            client_id=client_id,
            event_type=event_type,
            description=description,
            date=kwargs.get("date", datetime.now(timezone.utc)),
            quote_id=kwargs.get("quote_id"),
            purchase_order_id=kwargs.get("purchase_order_id"),
            project_id=kwargs.get("project_id"),
            invoice_id=kwargs.get("invoice_id")
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_events(self, client_id: int) -> List[ClientEvent]:
        return (
            self.db.query(ClientEvent)
            .filter(ClientEvent.client_id == client_id)
            .order_by(ClientEvent.date.desc())
            .all()
        )
