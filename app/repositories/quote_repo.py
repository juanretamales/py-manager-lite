from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.quote import Quote, QuoteItem, QuoteStatus


class QuoteRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_next_quote_number(self) -> str:
        current_year = datetime.now().year
        prefix = f"COT-{current_year}-"
        last_quote = (
            self.db.query(Quote)
            .filter(Quote.number.like(f"{prefix}%"))
            .order_by(Quote.id.desc())
            .first()
        )
        if last_quote:
            try:
                seq = int(last_quote.number.split("-")[-1]) + 1
            except ValueError:
                seq = self.db.query(Quote).count() + 1
        else:
            seq = 1
        return f"{prefix}{seq:03d}"

    def list_quotes(
        self,
        client_id: Optional[int] = None,
        client_name: Optional[str] = None,
        status: Optional[str] = None,
        issue_date: Optional[str] = None
    ) -> List[Quote]:
        from app.models.client import Client
        query = self.db.query(Quote)
        if client_name and client_name != "ALL":
            query = query.join(Quote.client).filter(Client.name == client_name)
        elif client_id:
            query = query.filter(Quote.client_id == client_id)

        if status and status != "ALL":
            query = query.filter(Quote.status == status)
        elif status is None or status == "ALL":
            # Por defecto, ocultar cotizaciones eliminadas
            query = query.filter(Quote.status != QuoteStatus.DELETED)
        if issue_date:
            query = query.filter(func.date(Quote.issue_date) == issue_date)
        return query.order_by(Quote.id.desc()).all()

    def get_by_id(self, quote_id: int) -> Optional[Quote]:
        return self.db.query(Quote).filter(Quote.id == quote_id).first()

    def create(
        self,
        client_id: int,
        items_data: List[Dict[str, Any]],
        number: Optional[str] = None,
        expiration_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        terms: Optional[str] = None,
        status: str = QuoteStatus.DRAFT,
        tax_rate: float = 0.19
    ) -> Quote:
        if not number:
            number = self.get_next_quote_number()

        subtotal = 0.0
        quote_items = []
        for idx, item in enumerate(items_data, start=1):
            qty = float(item.get("quantity", 1.0))
            price = float(item.get("unit_price", 0.0))
            item_subtotal = round(qty * price, 2)
            subtotal += item_subtotal
            quote_items.append(
                QuoteItem(
                    description=item.get("description", ""),
                    quantity=qty,
                    unit=item.get("unit", "un"),
                    unit_price=price,
                    subtotal=item_subtotal,
                    position=idx
                )
            )

        subtotal = round(subtotal, 2)
        tax_amount = round(subtotal * tax_rate, 2)
        total_amount = round(subtotal + tax_amount, 2)

        quote = Quote(
            number=number,
            client_id=client_id,
            status=status,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            expiration_date=expiration_date,
            notes=notes,
            terms=terms,
            items=quote_items
        )
        self.db.add(quote)
        self.db.commit()
        self.db.refresh(quote)
        return quote

    def update_status(self, quote_id: int, status: str) -> Optional[Quote]:
        quote = self.get_by_id(quote_id)
        if quote:
            quote.status = status
            self.db.commit()
            self.db.refresh(quote)
        return quote

    def update(
        self,
        quote_id: int,
        client_id: Optional[int] = None,
        items_data: Optional[List[Dict[str, Any]]] = None,
        expiration_date: Optional[datetime] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        terms: Optional[str] = None,
        tax_rate: float = 0.19
    ) -> Optional[Quote]:
        quote = self.get_by_id(quote_id)
        if not quote:
            return None

        if client_id is not None:
            quote.client_id = client_id
        if expiration_date is not None:
            quote.expiration_date = expiration_date
        if status is not None:
            quote.status = status
        if notes is not None:
            quote.notes = notes
        if terms is not None:
            quote.terms = terms

        if items_data is not None:
            quote.items.clear()
            subtotal = 0.0
            for idx, item in enumerate(items_data, start=1):
                qty = float(item.get("quantity", 1.0))
                price = float(item.get("unit_price", 0.0))
                item_subtotal = round(qty * price, 2)
                subtotal += item_subtotal
                quote.items.append(
                    QuoteItem(
                        description=item.get("description", ""),
                        quantity=qty,
                        unit=item.get("unit", "un"),
                        unit_price=price,
                        subtotal=item_subtotal,
                        position=idx
                    )
                )
            quote.subtotal = round(subtotal, 2)
            quote.tax_amount = round(subtotal * tax_rate, 2)
            quote.total_amount = round(subtotal + quote.tax_amount, 2)

        self.db.commit()
        self.db.refresh(quote)
        return quote

    def soft_delete(self, quote_id: int) -> bool:
        quote = self.get_by_id(quote_id)
        if quote:
            quote.status = QuoteStatus.DELETED
            self.db.commit()
            return True
        return False

    def delete(self, quote_id: int) -> bool:
        quote = self.get_by_id(quote_id)
        if quote:
            self.db.delete(quote)
            self.db.commit()
            return True
        return False
