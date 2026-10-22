from sqlalchemy.orm import Session
from app.models.company import Company, BusinessCanvas


class CompanyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_company(self) -> Company:
        company = self.db.query(Company).first()
        if not company:
            company = Company(
                legal_name="Mi Empresa SpA",
                trade_name="Mi Empresa",
                country="Chile",
                business_activity="Servicios Profesionales y Consultoría"
            )
            self.db.add(company)
            self.db.commit()
            self.db.refresh(company)
        return company

    def update_company(self, company_id: int, **kwargs) -> Company:
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if company:
            for k, v in kwargs.items():
                if hasattr(company, k):
                    setattr(company, k, v)
            self.db.commit()
            self.db.refresh(company)
        return company

    def get_canvas(self, company_id: int) -> BusinessCanvas:
        canvas = self.db.query(BusinessCanvas).filter(BusinessCanvas.company_id == company_id).first()
        if not canvas:
            canvas = BusinessCanvas(
                company_id=company_id,
                value_propositions="Soluciones a medida con alta agilidad y calidad técnica.",
                customer_segments="Pequeñas y medianas empresas, startups y profesionales independientes.",
                revenue_streams="Proyectos cerrados, soporte mensual, consultoría especializada.",
                channels="Contacto directo, recomendaciones, sitio web y redes profesionales.",
                customer_relationships="Atención cercana y personalizada, comunicación continua.",
                key_activities="Desarrollo de software, consultoría técnica, soporte e implementación.",
                key_resources="Conocimiento técnico, herramientas de desarrollo, infraestructura en la nube.",
                key_partners="Proveedores de hosting/cloud, contadores, red de aliados comerciales.",
                cost_structure="Herramientas de software, marketing, infraestructura, horas de trabajo."
            )
            self.db.add(canvas)
            self.db.commit()
            self.db.refresh(canvas)
        return canvas

    def update_canvas(self, company_id: int, **kwargs) -> BusinessCanvas:
        canvas = self.get_canvas(company_id)
        for k, v in kwargs.items():
            if hasattr(canvas, k):
                setattr(canvas, k, v)
        self.db.commit()
        self.db.refresh(canvas)
        return canvas
