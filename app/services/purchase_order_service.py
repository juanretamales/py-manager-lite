from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.db.session import get_db_session
from app.repositories.purchase_order_repo import PurchaseOrderRepository
from app.repositories.client_repo import ClientRepository
from app.repositories.project_repo import ProjectRepository
from app.models.project import ProjectStatus


class PurchaseOrderService:
    def list_orders(
        self,
        client_id: Optional[int] = None,
        quote_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with get_db_session() as db:
            repo = PurchaseOrderRepository(db)
            orders = repo.list_orders(client_id=client_id, quote_id=quote_id, status=status)
            result = []
            for po in orders:
                result.append({
                    "id": po.id,
                    "number": po.number,
                    "client_id": po.client_id,
                    "client_name": po.client.name if po.client else "N/A",
                    "quote_id": po.quote_id,
                    "quote_number": po.quote.number if po.quote else "-",
                    "amount": po.amount,
                    "status": po.status,
                    "document_path": po.document_path or "",
                    "has_document": bool(po.document_path),
                    "notes": po.notes or "",
                    "issue_date": po.issue_date.strftime("%Y-%m-%d") if po.issue_date else "",
                    "has_project": len(po.projects) > 0,
                    "project_name": po.projects[0].name if po.projects else "-"
                })
            return result

    def get_order(self, po_id: int) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = PurchaseOrderRepository(db)
            po = repo.get_by_id(po_id)
            if not po:
                return None
            return {
                "id": po.id,
                "number": po.number,
                "client_id": po.client_id,
                "client_name": po.client.name if po.client else "N/A",
                "quote_id": po.quote_id,
                "quote_number": po.quote.number if po.quote else "-",
                "amount": po.amount,
                "status": po.status,
                "document_path": po.document_path or "",
                "has_document": bool(po.document_path),
                "notes": po.notes or "",
                "issue_date": po.issue_date.strftime("%Y-%m-%d") if po.issue_date else "",
                "has_project": len(po.projects) > 0
            }

    def create_order(
        self,
        client_id: int,
        number: str,
        amount: float,
        quote_id: Optional[int] = None,
        document_path: Optional[str] = None,
        notes: Optional[str] = None,
        status: str = "ACCEPTED",
        issue_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = PurchaseOrderRepository(db)
            client_repo = ClientRepository(db)

            po = repo.create(
                client_id=client_id,
                number=number,
                amount=amount,
                quote_id=quote_id,
                document_path=document_path,
                notes=notes,
                status=status,
                issue_date=issue_date or datetime.now(timezone.utc)
            )

            client_repo.add_event(
                client_id=client_id,
                event_type="PURCHASE_ORDER",
                description=f"Orden de Compra #{po.number} registrada por un monto de ${po.amount:,.0f}",
                purchase_order_id=po.id,
                quote_id=quote_id
            )

            return {"id": po.id, "number": po.number, "amount": po.amount, "status": po.status}

    def update_order(self, po_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = PurchaseOrderRepository(db)
            client_repo = ClientRepository(db)
            po = repo.update(po_id, **kwargs)
            if not po:
                return None

            client_repo.add_event(
                client_id=po.client_id,
                event_type="NOTE",
                description=f"Orden de Compra #{po.number} actualizada (Estado: {po.status}, Monto: ${po.amount:,.0f})",
                purchase_order_id=po.id
            )
            return {"id": po.id, "number": po.number, "amount": po.amount, "status": po.status}

    def delete_order(self, po_id: int) -> bool:
        with get_db_session() as db:
            repo = PurchaseOrderRepository(db)
            return repo.delete(po_id)

    def convert_to_project(self, po_id: int, project_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Directly starts a new project from an accepted purchase order."""
        with get_db_session() as db:
            repo = PurchaseOrderRepository(db)
            project_repo = ProjectRepository(db)
            client_repo = ClientRepository(db)

            po = repo.get_by_id(po_id)
            if not po:
                return None

            name = project_name or f"Proyecto OC #{po.number} - {po.client.name if po.client else ''}"
            project = project_repo.create(
                client_id=po.client_id,
                quote_id=po.quote_id,
                purchase_order_id=po.id,
                name=name,
                description=(
                    f"Generado a partir de Orden de Compra #{po.number}.\n"
                    f"Monto comprometido: ${po.amount:,.0f}"
                ),
                status=ProjectStatus.ACTIVE,
                progress=0
            )

            client_repo.add_event(
                client_id=po.client_id,
                event_type="PROJECT",
                description=f"Proyecto '{project.name}' iniciado a partir de Orden de Compra #{po.number}",
                project_id=project.id,
                purchase_order_id=po.id
            )

            return {"id": project.id, "name": project.name, "status": project.status}
