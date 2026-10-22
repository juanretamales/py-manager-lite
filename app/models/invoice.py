from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class InvoiceType:
    ISSUED = "ISSUED"      # Factura Emitida (Venta)
    RECEIVED = "RECEIVED"  # Factura Recibida (Gasto/Proveedor)
    CREDIT_NOTE = "CREDIT_NOTE"  # Nota de Crédito (SII)

    ALL = [ISSUED, RECEIVED, CREDIT_NOTE]


class PaymentStatus:
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    ANNULLED = "ANNULLED"  # Anulada formalmente con Nota de Crédito

    ALL = [PENDING, PARTIAL, PAID, OVERDUE, ANNULLED]


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), default=InvoiceType.ISSUED, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    reference_invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    number = Column(String(50), nullable=False, index=True)
    # DECISIÓN DE NEGOCIO: La fecha de emisión representa la fecha comercial tributaria local.
    issue_date = Column(DateTime, default=datetime.now, nullable=False)
    due_date = Column(DateTime, nullable=True)
    issuer_tax_id = Column(String(50), nullable=True)
    issuer_name = Column(String(200), nullable=True)
    receiver_tax_id = Column(String(50), nullable=True)
    receiver_name = Column(String(200), nullable=True)
    net_amount = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    category = Column(String(100), nullable=True)  # Operacional, Servicios, Honorarios, etc.
    annulment_reason = Column(String(250), nullable=True)  # Motivo de anulación o nota de crédito
    document_path = Column(String(300), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    client = relationship("Client", back_populates="invoices")
    project = relationship("Project", back_populates="invoices")
    payments = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="desc(Payment.payment_date)"
    )
    reference_invoice = relationship(
        "Invoice",
        remote_side=[id],
        foreign_keys=[reference_invoice_id],
        backref="credit_notes"
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    payment_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    amount = Column(Float, default=0.0, nullable=False)
    payment_method = Column(String(50), nullable=True)  # Transferencia, Cheque, Efectivo, etc.
    reference = Column(String(100), nullable=True)      # N° de transacción / comprobante
    evidence_path = Column(String(300), nullable=True)  # Archivo de comprobante opcional
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoice = relationship("Invoice", back_populates="payments")
