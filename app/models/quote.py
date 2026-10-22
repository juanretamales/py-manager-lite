from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class QuoteStatus:
    DRAFT = "DRAFT"
    SENT = "SENT"
    NEGOTIATION = "NEGOTIATION"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"

    ALL = [DRAFT, SENT, NEGOTIATION, ACCEPTED, REJECTED, EXPIRED]


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(50), nullable=False, unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    # DECISIÓN DE NEGOCIO: La fecha de emisión representa la fecha comercial local del negocio.
    issue_date = Column(DateTime, default=datetime.now, nullable=False)
    expiration_date = Column(DateTime, nullable=True)
    status = Column(String(30), default=QuoteStatus.DRAFT, nullable=False)
    subtotal = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    notes = Column(Text, nullable=True)
    terms = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    client = relationship("Client", back_populates="quotes")
    items = relationship(
        "QuoteItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteItem.position"
    )
    purchase_orders = relationship("PurchaseOrder", back_populates="quote")
    projects = relationship("Project", back_populates="quote")


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    description = Column(String(300), nullable=False)
    quantity = Column(Float, default=1.0, nullable=False)
    unit = Column(String(50), default="un", nullable=False)  # un, hrs, servicio, etc.
    unit_price = Column(Float, default=0.0, nullable=False)
    subtotal = Column(Float, default=0.0, nullable=False)
    position = Column(Integer, default=1, nullable=False)

    quote = relationship("Quote", back_populates="items")
