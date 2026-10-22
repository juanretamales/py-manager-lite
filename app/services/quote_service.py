from typing import List, Dict, Any, Optional
from datetime import datetime
from app.db.session import get_db_session
from app.repositories.quote_repo import QuoteRepository
from app.repositories.client_repo import ClientRepository
from app.repositories.project_repo import ProjectRepository
from app.models.quote import QuoteStatus
from app.models.project import ProjectStatus


class QuoteService:
    def list_quotes(
        self,
        client_id: Optional[int] = None,
        client_name: Optional[str] = None,
        status: Optional[str] = None,
        issue_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with get_db_session() as db:
            repo = QuoteRepository(db)
            quotes = repo.list_quotes(
                client_id=client_id,
                client_name=client_name,
                status=status,
                issue_date=issue_date
            )
            result = []
            for q in quotes:
                result.append({
                    "id": q.id,
                    "number": q.number,
                    "client_id": q.client_id,
                    "client_name": q.client.name if q.client else "N/A",
                    "status": q.status,
                    "subtotal": q.subtotal,
                    "tax_amount": q.tax_amount,
                    "total_amount": q.total_amount,
                    "items_count": len(q.items),
                    "issue_date": q.issue_date.strftime("%Y-%m-%d") if q.issue_date else "",
                    "expiration_date": q.expiration_date.strftime("%Y-%m-%d") if q.expiration_date else "-",
                    "has_project": len(q.projects) > 0
                })
            return result

    def get_quote(self, quote_id: int) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = QuoteRepository(db)
            q = repo.get_by_id(quote_id)
            if not q:
                return None
            return {
                "id": q.id,
                "number": q.number,
                "client_id": q.client_id,
                "client_name": q.client.name if q.client else "N/A",
                "status": q.status,
                "subtotal": q.subtotal,
                "tax_amount": q.tax_amount,
                "total_amount": q.total_amount,
                "issue_date": q.issue_date.strftime("%Y-%m-%d") if q.issue_date else "",
                "expiration_date": q.expiration_date.strftime("%Y-%m-%d") if q.expiration_date else "",
                "notes": q.notes or "",
                "terms": q.terms or "",
                "items": [
                    {
                        "id": it.id,
                        "description": it.description,
                        "quantity": it.quantity,
                        "unit": it.unit,
                        "unit_price": it.unit_price,
                        "subtotal": it.subtotal,
                        "position": it.position
                    }
                    for it in q.items
                ]
            }

    def create_quote(
        self,
        client_id: int,
        items_data: List[Dict[str, Any]],
        expiration_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        terms: Optional[str] = None,
        tax_rate: float = 0.19
    ) -> Dict[str, Any]:
        with get_db_session() as db:
            quote_repo = QuoteRepository(db)
            client_repo = ClientRepository(db)

            quote = quote_repo.create(
                client_id=client_id,
                items_data=items_data,
                expiration_date=expiration_date,
                notes=notes,
                terms=terms,
                tax_rate=tax_rate
            )

            # Record event on client timeline
            client_repo.add_event(
                client_id=client_id,
                event_type="QUOTE_SENT",
                description=f"Cotización {quote.number} generada por un total de ${quote.total_amount:,.0f}",
                quote_id=quote.id
            )

            return {
                "id": quote.id,
                "number": quote.number,
                "total_amount": quote.total_amount,
                "status": quote.status
            }

    def change_status(self, quote_id: int, new_status: str) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            quote_repo = QuoteRepository(db)
            client_repo = ClientRepository(db)

            quote = quote_repo.update_status(quote_id, new_status)
            if quote:
                event_type = "QUOTE_ACCEPTED" if new_status == QuoteStatus.ACCEPTED else "NOTE"
                client_repo.add_event(
                    client_id=quote.client_id,
                    event_type=event_type,
                    description=f"Cotización {quote.number} cambió de estado a {new_status}",
                    quote_id=quote.id
                )
                return {"id": quote.id, "status": quote.status}
            return None

    def convert_to_project(self, quote_id: int, project_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Converts an accepted quote directly into a new project."""
        with get_db_session() as db:
            quote_repo = QuoteRepository(db)
            project_repo = ProjectRepository(db)
            client_repo = ClientRepository(db)

            quote = quote_repo.get_by_id(quote_id)
            if not quote:
                return None

            name = project_name or f"Proyecto {quote.number} - {quote.client.name if quote.client else ''}"
            project = project_repo.create(
                client_id=quote.client_id,
                quote_id=quote.id,
                name=name,
                description=(
                    f"Generado a partir de la cotización {quote.number}.\n"
                    f"Total acordado: ${quote.total_amount:,.0f}"
                ),
                status=ProjectStatus.ACTIVE,
                progress=0
            )

            client_repo.add_event(
                client_id=quote.client_id,
                event_type="PROJECT",
                description=f"Proyecto '{project.name}' iniciado a partir de cotización {quote.number}",
                quote_id=quote.id,
                project_id=project.id
            )

            return {"id": project.id, "name": project.name, "status": project.status}

    def update_quote(
        self,
        quote_id: int,
        client_id: Optional[int] = None,
        items_data: Optional[List[Dict[str, Any]]] = None,
        status: Optional[str] = None,
        expiration_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        terms: Optional[str] = None,
        tax_rate: float = 0.19
    ) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            quote_repo = QuoteRepository(db)
            client_repo = ClientRepository(db)

            quote = quote_repo.update(
                quote_id=quote_id,
                client_id=client_id,
                items_data=items_data,
                status=status,
                expiration_date=expiration_date,
                notes=notes,
                terms=terms,
                tax_rate=tax_rate
            )
            if not quote:
                return None

            client_repo.add_event(
                client_id=quote.client_id,
                event_type="QUOTE_UPDATED",
                description=(
                    f"Cotización {quote.number} modificada. "
                    f"Monto total: ${quote.total_amount:,.0f} (Estado: {quote.status})"
                ),
                quote_id=quote.id
            )
            return {
                "id": quote.id,
                "number": quote.number,
                "total_amount": quote.total_amount,
                "status": quote.status
            }

    def delete_quote(self, quote_id: int) -> bool:
        """Soft deletes quote: changes status to DELETED (oculta)."""
        with get_db_session() as db:
            quote_repo = QuoteRepository(db)
            client_repo = ClientRepository(db)
            quote = quote_repo.get_by_id(quote_id)
            if quote:
                client_repo.add_event(
                    client_id=quote.client_id,
                    event_type="NOTE",
                    description=f"Cotización {quote.number} enviada a papelera / eliminadas (oculta)",
                    quote_id=quote.id
                )
            return quote_repo.soft_delete(quote_id)

    def restore_quote(self, quote_id: int, restored_status: str = QuoteStatus.DRAFT) -> bool:
        """Restores a soft-deleted quote back to active status."""
        with get_db_session() as db:
            quote_repo = QuoteRepository(db)
            client_repo = ClientRepository(db)
            quote = quote_repo.update_status(quote_id, restored_status)
            if quote:
                client_repo.add_event(
                    client_id=quote.client_id,
                    event_type="NOTE",
                    description=f"Cotización {quote.number} restaurada al estado {restored_status}",
                    quote_id=quote.id
                )
                return True
            return False
