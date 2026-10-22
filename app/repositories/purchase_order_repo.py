from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.project import PurchaseOrder


class PurchaseOrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_orders(
        self,
        client_id: Optional[int] = None,
        quote_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[PurchaseOrder]:
        query = self.db.query(PurchaseOrder)
        if client_id:
            query = query.filter(PurchaseOrder.client_id == client_id)
        if quote_id:
            query = query.filter(PurchaseOrder.quote_id == quote_id)
        if status and status != "ALL":
            query = query.filter(PurchaseOrder.status == status)
        return query.order_by(PurchaseOrder.issue_date.desc(), PurchaseOrder.id.desc()).all()

    def get_by_id(self, po_id: int) -> Optional[PurchaseOrder]:
        return self.db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

    def get_by_number(self, number: str) -> Optional[PurchaseOrder]:
        return self.db.query(PurchaseOrder).filter(PurchaseOrder.number == number).first()

    def create(self, **kwargs) -> PurchaseOrder:
        po = PurchaseOrder(**kwargs)
        self.db.add(po)
        self.db.commit()
        self.db.refresh(po)
        return po

    def update(self, po_id: int, **kwargs) -> Optional[PurchaseOrder]:
        po = self.get_by_id(po_id)
        if po:
            for k, v in kwargs.items():
                if hasattr(po, k):
                    setattr(po, k, v)
            self.db.commit()
            self.db.refresh(po)
        return po

    def delete(self, po_id: int) -> bool:
        po = self.get_by_id(po_id)
        if po:
            self.db.delete(po)
            self.db.commit()
            return True
        return False
