from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class ProjectStatus:
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    ALL = [PLANNED, ACTIVE, PAUSED, COMPLETED, CANCELLED]


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    number = Column(String(100), nullable=False, index=True)
    # DECISIÓN DE NEGOCIO: La fecha de emisión representa la fecha comercial de la orden.
    issue_date = Column(DateTime, default=datetime.now, nullable=False)
    amount = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="ACCEPTED", nullable=False)
    document_path = Column(String(300), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    quote = relationship("Quote", back_populates="purchase_orders")
    client = relationship("Client")
    projects = relationship("Project", back_populates="purchase_order")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    quote_id = Column(Integer, ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    estimated_end_date = Column(DateTime, nullable=True)
    actual_end_date = Column(DateTime, nullable=True)
    status = Column(String(30), default=ProjectStatus.ACTIVE, nullable=False)
    progress = Column(Integer, default=0, nullable=False)  # 0 to 100%
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    client = relationship("Client", back_populates="projects")
    quote = relationship("Quote", back_populates="projects")
    purchase_order = relationship("PurchaseOrder", back_populates="projects")
    events = relationship(
        "ProjectEvent",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(ProjectEvent.date)"
    )
    invoices = relationship("Invoice", back_populates="project")


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    event_type = Column(String(50), default="UPDATE", nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="events")
