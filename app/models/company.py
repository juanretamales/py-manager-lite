from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    legal_name = Column(String(200), nullable=False, default="")
    trade_name = Column(String(200), nullable=True)
    tax_id = Column(String(50), nullable=True)  # RUT / Tax ID
    business_activity = Column(String(200), nullable=True)  # Giro comercial
    address = Column(String(250), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=False, default="Chile")
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    website = Column(String(100), nullable=True)
    logo_path = Column(String(300), nullable=True)
    bank_information = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    canvas = relationship("BusinessCanvas", back_populates="company", uselist=False, cascade="all, delete-orphan")


class BusinessCanvas(Base):
    __tablename__ = "business_canvases"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True)
    key_partners = Column(Text, nullable=True)          # Socios clave
    key_activities = Column(Text, nullable=True)        # Actividades clave
    key_resources = Column(Text, nullable=True)         # Recursos clave
    value_propositions = Column(Text, nullable=True)    # Propuestas de valor
    customer_relationships = Column(Text, nullable=True)  # Relaciones con clientes
    channels = Column(Text, nullable=True)              # Canales
    customer_segments = Column(Text, nullable=True)     # Segmentos de clientes
    cost_structure = Column(Text, nullable=True)        # Estructura de costos
    revenue_streams = Column(Text, nullable=True)       # Fuentes de ingresos
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company", back_populates="canvas")
