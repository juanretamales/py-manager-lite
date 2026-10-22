from typing import Dict, Any
from app.db.session import get_db_session
from app.repositories.company_repo import CompanyRepository


class CompanyService:
    def get_company(self) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = CompanyRepository(db)
            company = repo.get_company()
            return {
                "id": company.id,
                "legal_name": company.legal_name or "",
                "trade_name": company.trade_name or "",
                "tax_id": company.tax_id or "",
                "business_activity": company.business_activity or "",
                "address": company.address or "",
                "city": company.city or "",
                "country": company.country or "Chile",
                "phone": company.phone or "",
                "email": company.email or "",
                "website": company.website or "",
                "bank_information": company.bank_information or ""
            }

    def update_company(self, company_id: int, **data) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = CompanyRepository(db)
            company = repo.update_company(company_id, **data)
            return {
                "id": company.id,
                "legal_name": company.legal_name,
                "trade_name": company.trade_name,
                "tax_id": company.tax_id,
                "business_activity": company.business_activity,
                "address": company.address,
                "city": company.city,
                "country": company.country,
                "phone": company.phone,
                "email": company.email,
                "website": company.website,
                "bank_information": company.bank_information
            }

    def get_canvas(self, company_id: int) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = CompanyRepository(db)
            canvas = repo.get_canvas(company_id)
            return {
                "id": canvas.id,
                "company_id": canvas.company_id,
                "key_partners": canvas.key_partners or "",
                "key_activities": canvas.key_activities or "",
                "key_resources": canvas.key_resources or "",
                "value_propositions": canvas.value_propositions or "",
                "customer_relationships": canvas.customer_relationships or "",
                "channels": canvas.channels or "",
                "customer_segments": canvas.customer_segments or "",
                "cost_structure": canvas.cost_structure or "",
                "revenue_streams": canvas.revenue_streams or ""
            }

    def update_canvas(self, company_id: int, **data) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = CompanyRepository(db)
            canvas = repo.update_canvas(company_id, **data)
            return {
                "id": canvas.id,
                "company_id": canvas.company_id,
                "key_partners": canvas.key_partners or "",
                "key_activities": canvas.key_activities or "",
                "key_resources": canvas.key_resources or "",
                "value_propositions": canvas.value_propositions or "",
                "customer_relationships": canvas.customer_relationships or "",
                "channels": canvas.channels or "",
                "customer_segments": canvas.customer_segments or "",
                "cost_structure": canvas.cost_structure or "",
                "revenue_streams": canvas.revenue_streams or ""
            }
