from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    legal_name = Column(String(200), nullable=True)
    tax_id = Column(String(50), nullable=True, index=True)  # RUT / Tax ID
    business_activity = Column(String(200), nullable=True)
    address = Column(String(250), nullable=True)
    contact_name = Column(String(150), nullable=True)
    email = Column(String(120), nullable=True)
    phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    events = relationship(
        "ClientEvent",
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="desc(ClientEvent.date)"
    )
    quotes = relationship("Quote", back_populates="client")
    projects = relationship("Project", back_populates="client")
    invoices = relationship("Invoice", back_populates="client")


class ClientEvent(Base):
    __tablename__ = "client_events"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    event_type = Column(String(50), nullable=False, default="NOTE")  # NOTE, CALL, EMAIL, MEETING, QUOTE_SENT, etc.
    description = Column(Text, nullable=False)
    quote_id = Column(Integer, nullable=True)
    purchase_order_id = Column(Integer, nullable=True)
    project_id = Column(Integer, nullable=True)
    invoice_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    client = relationship("Client", back_populates="events")
