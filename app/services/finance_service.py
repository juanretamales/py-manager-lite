import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.config import get_documents_dir
from app.db.session import get_db_session
from app.repositories.finance_repo import FinanceRepository
from app.repositories.client_repo import ClientRepository
from app.repositories.project_repo import ProjectRepository
from app.models.invoice import InvoiceType

DEFAULT_EXPENSE_CATEGORIES = [
    "Servicios Profesionales & Honorarios",
    "Servicios Cloud & Hosting",
    "Licencias de Software",
    "Insumos de Oficina",
    "Servicios Básicos (Luz, Agua, Internet)",
    "Publicidad & Marketing",
    "Transporte & Logística",
    "Infraestructura & Equipamiento",
    "Otros Gastos Operacionales",
]


def save_document(source_path: str, subfolder: str, prefix: str = "doc") -> Optional[str]:
    """Copies an external file into the application documents directory safely."""
    if not source_path or not os.path.exists(source_path):
        return source_path if source_path else None
    try:
        source_p = Path(source_path)
        ext = source_p.suffix.lower()
        target_dir = get_documents_dir() / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prefix = "".join(c for c in prefix if c.isalnum() or c in ("-", "_"))[:30]
        safe_name = f"{safe_prefix}_{timestamp}{ext}"
        destination = target_dir / safe_name
        shutil.copy2(source_path, destination)
        return str(destination)
    except Exception:
        return source_path


def open_document(file_path: str) -> bool:
    """Opens a document using the operating system's default viewer."""
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", file_path])
        else:
            subprocess.run(["xdg-open", file_path])
        return True
    except Exception:
        return False


class FinanceService:
    def list_invoices(
        self,
        invoice_type: Optional[str] = None,
        client_id: Optional[int] = None,
        category: Optional[str] = None,
        project_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            invoices = repo.list_invoices(
                invoice_type=invoice_type,
                client_id=client_id,
                category=category,
                project_id=project_id
            )
            result = []
            for inv in invoices:
                summary = repo.get_invoice_summary(inv)
                # DECISIÓN DE NEGOCIO: Para facturas recibidas (gastos), la contraparte principal es el Proveedor.
                if inv.type == InvoiceType.RECEIVED and inv.issuer_name:
                    contraparte = inv.issuer_name
                elif inv.client:
                    contraparte = inv.client.name
                else:
                    contraparte = inv.issuer_name or inv.receiver_name or "N/A"

                result.append({
                    "id": inv.id,
                    "type": inv.type,
                    "number": inv.number,
                    "client_id": inv.client_id,
                    "client_name": contraparte,
                    "issuer_name": inv.issuer_name or "",
                    "issuer_tax_id": inv.issuer_tax_id or "",
                    "receiver_name": inv.receiver_name or "",
                    "receiver_tax_id": inv.receiver_tax_id or "",
                    "project_id": inv.project_id,
                    "project_name": inv.project.name if inv.project else "",
                    "reference_invoice_id": inv.reference_invoice_id,
                    "reference_invoice_number": inv.reference_invoice.number if inv.reference_invoice else "",
                    "annulment_reason": inv.annulment_reason or "",
                    "category": inv.category or "General",
                    "net_amount": inv.net_amount,
                    "tax_amount": inv.tax_amount,
                    "total_amount": inv.total_amount,
                    "total_paid": summary["total_paid"],
                    "balance": summary["balance"],
                    "status": summary["status"],
                    "payments_count": summary["payments_count"],
                    "has_document": bool(inv.document_path and os.path.exists(inv.document_path)),
                    "document_path": inv.document_path or "",
                    "issue_date": inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "",
                    "due_date": inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "-"
                })
            return result

    def get_invoice(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            inv = repo.get_invoice_by_id(invoice_id)
            if not inv:
                return None
            summary = repo.get_invoice_summary(inv)
            return {
                "id": inv.id,
                "type": inv.type,
                "number": inv.number,
                "client_id": inv.client_id,
                "client_name": inv.client.name if inv.client else "",
                "project_id": inv.project_id,
                "project_name": inv.project.name if inv.project else "",
                "reference_invoice_id": inv.reference_invoice_id,
                "reference_invoice_number": inv.reference_invoice.number if inv.reference_invoice else "",
                "annulment_reason": inv.annulment_reason or "",
                "issuer_tax_id": inv.issuer_tax_id or "",
                "issuer_name": inv.issuer_name or "",
                "receiver_tax_id": inv.receiver_tax_id or "",
                "receiver_name": inv.receiver_name or "",
                "net_amount": inv.net_amount,
                "tax_amount": inv.tax_amount,
                "total_amount": inv.total_amount,
                "total_paid": summary["total_paid"],
                "balance": summary["balance"],
                "status": summary["status"],
                "category": inv.category or "",
                "document_path": inv.document_path or "",
                "notes": inv.notes or "",
                "issue_date": inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "",
                "due_date": inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "",
                "credit_notes": [
                    {
                        "id": cn.id,
                        "number": cn.number,
                        "total_amount": cn.total_amount,
                        "reason": cn.annulment_reason or "",
                        "issue_date": cn.issue_date.strftime("%Y-%m-%d") if cn.issue_date else "",
                        "has_document": bool(cn.document_path and os.path.exists(cn.document_path)),
                        "document_path": cn.document_path or ""
                    }
                    for cn in getattr(inv, "credit_notes", [])
                ],
                "payments": [
                    {
                        "id": p.id,
                        "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else "",
                        "amount": p.amount,
                        "payment_method": p.payment_method or "Transferencia",
                        "reference": p.reference or "-",
                        "evidence_path": p.evidence_path or "",
                        "notes": p.notes or ""
                    }
                    for p in inv.payments
                ]
            }

    def create_invoice(self, **data) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            client_repo = ClientRepository(db)
            project_repo = ProjectRepository(db)
            invoice = repo.create_invoice(**data)

            if invoice.client_id:
                tipo_str = "emitida" if invoice.type == InvoiceType.ISSUED else "recibida"
                proj_suffix = f" (Proyecto: {invoice.project.name})" if invoice.project else ""
                client_desc = (
                    f"Factura {tipo_str} #{invoice.number} registrada por "
                    f"${invoice.total_amount:,.0f}{proj_suffix}"
                )
                client_repo.add_event(
                    client_id=invoice.client_id,
                    event_type="INVOICE",
                    description=client_desc,
                    invoice_id=invoice.id,
                    project_id=invoice.project_id
                )

            if invoice.project_id:
                inv_kind = "Venta" if invoice.type == InvoiceType.ISSUED else "Gasto"
                proj_desc = (
                    f"Factura #{invoice.number} ({inv_kind}) asociada al proyecto "
                    f"por ${invoice.total_amount:,.0f}"
                )
                project_repo.add_event(
                    project_id=invoice.project_id,
                    event_type="FACTURACION",
                    description=proj_desc
                )

            return {"id": invoice.id, "number": invoice.number, "total_amount": invoice.total_amount}

    def create_credit_note(
        self,
        reference_invoice_id: int,
        number: str,
        amount: float,
        reason: str,
        is_total_annulment: bool = True,
        document_path: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            client_repo = ClientRepository(db)
            project_repo = ProjectRepository(db)

            ref_inv = repo.get_invoice_by_id(reference_invoice_id)
            if not ref_inv:
                raise ValueError("Factura de referencia no encontrada.")

            credit_note = repo.create_credit_note(
                reference_invoice_id=reference_invoice_id,
                number=number,
                amount=amount,
                reason=reason,
                is_total_annulment=is_total_annulment,
                document_path=document_path
            )

            # Audit events
            annulment_text = "anulación total" if is_total_annulment else "ajuste parcial"
            if ref_inv.client_id:
                cn_client_desc = (
                    f"Nota de Crédito #{number} ({annulment_text}) emitida para "
                    f"Factura #{ref_inv.number} por ${amount:,.0f}. Motivo: {reason}"
                )
                client_repo.add_event(
                    client_id=ref_inv.client_id,
                    event_type="CREDIT_NOTE",
                    description=cn_client_desc,
                    invoice_id=credit_note.id,
                    project_id=ref_inv.project_id
                )

            if ref_inv.project_id:
                cn_proj_desc = (
                    f"Nota de Crédito #{number} aplicada a Factura #{ref_inv.number} "
                    f"({annulment_text} por ${amount:,.0f}). Motivo: {reason}"
                )
                project_repo.add_event(
                    project_id=ref_inv.project_id,
                    event_type="FACTURACION",
                    description=cn_proj_desc
                )

            return {
                "id": credit_note.id,
                "number": credit_note.number,
                "total_amount": credit_note.total_amount,
                "reference_invoice_number": ref_inv.number
            }

    def unlink_invoice_from_project(self, invoice_id: int) -> bool:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            client_repo = ClientRepository(db)
            project_repo = ProjectRepository(db)

            inv = repo.get_invoice_by_id(invoice_id)
            if not inv or not inv.project_id:
                return False

            old_project_id = inv.project_id
            old_project_name = inv.project.name if inv.project else f"#{old_project_id}"

            # Log audit event in project before unlinking
            project_repo.add_event(
                project_id=old_project_id,
                event_type="FACTURACION",
                description=f"Factura #{inv.number} (${inv.total_amount:,.0f}) desvinculada del proyecto."
            )

            if inv.client_id:
                unlink_desc = (
                    f"Factura #{inv.number} desvinculada del proyecto '{old_project_name}'. "
                    f"Permanece registrada en Finanzas."
                )
                client_repo.add_event(
                    client_id=inv.client_id,
                    event_type="NOTE",
                    description=unlink_desc,
                    invoice_id=inv.id
                )

            return repo.unlink_project(invoice_id)

    def register_payment(self, invoice_id: int, amount: float, **data) -> Dict[str, Any]:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            client_repo = ClientRepository(db)
            payment = repo.add_payment(invoice_id, amount, **data)
            invoice = repo.get_invoice_by_id(invoice_id)
            summary = repo.get_invoice_summary(invoice)

            if invoice.client_id:
                pay_desc = (
                    f"Pago de ${amount:,.0f} registrado para factura #{invoice.number}. "
                    f"Saldo restante: ${summary['balance']:,.0f}"
                )
                client_repo.add_event(
                    client_id=invoice.client_id,
                    event_type="PAYMENT",
                    description=pay_desc,
                    invoice_id=invoice.id
                )

            return {
                "payment_id": payment.id,
                "invoice_id": invoice.id,
                "amount": payment.amount,
                "balance": summary["balance"],
                "status": summary["status"]
            }

    def update_payment_evidence(self, payment_id: int, evidence_path: str) -> bool:
        """Asocia o actualiza la ruta del comprobante de transferencia a un pago."""
        with get_db_session() as db:
            repo = FinanceRepository(db)
            return repo.update_payment_evidence(payment_id, evidence_path)

    def attach_invoice_document(self, invoice_id: int, file_path: str) -> Optional[str]:
        """Guarda y asocia un documento (PDF/XML) a una factura existente."""
        dest_path = save_document(file_path, "invoices", prefix=f"inv_{invoice_id}")
        if dest_path:
            self.update_invoice(invoice_id, document_path=dest_path)
            return dest_path
        return None

    def attach_payment_evidence(self, payment_id: int, file_path: str) -> Optional[str]:
        """Guarda y asocia un comprobante de transferencia a un pago existente."""
        dest_path = save_document(file_path, "payments", prefix=f"pay_{payment_id}")
        if dest_path:
            self.update_payment_evidence(payment_id, dest_path)
            return dest_path
        return None

    def update_invoice(self, invoice_id: int, **data) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            client_repo = ClientRepository(db)
            invoice = repo.update_invoice(invoice_id, **data)
            if not invoice:
                return None

            if invoice.client_id:
                client_repo.add_event(
                    client_id=invoice.client_id,
                    event_type="NOTE",
                    description=f"Factura #{invoice.number} actualizada. Total: ${invoice.total_amount:,.0f}",
                    invoice_id=invoice.id
                )
            return {"id": invoice.id, "number": invoice.number, "total_amount": invoice.total_amount}

    def delete_invoice(self, invoice_id: int, reason: str = "Sin motivo especificado") -> bool:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            client_repo = ClientRepository(db)
            project_repo = ProjectRepository(db)

            inv = repo.get_invoice_by_id(invoice_id)
            if not inv:
                return False

            inv_number = inv.number
            client_id = inv.client_id
            project_id = inv.project_id
            total_amount = inv.total_amount

            # Audit event in Client
            if client_id:
                client_repo.add_event(
                    client_id=client_id,
                    event_type="AUDIT",
                    description=f"Factura #{inv_number} (${total_amount:,.0f}) eliminada del sistema. Motivo: {reason}"
                )

            # Audit event in Project if it was linked
            if project_id:
                project_repo.add_event(
                    project_id=project_id,
                    event_type="AUDIT",
                    description=f"Factura #{inv_number} (${total_amount:,.0f}) eliminada del sistema. Motivo: {reason}"
                )

            return repo.delete_invoice(invoice_id)

    def list_categories(self) -> List[str]:
        with get_db_session() as db:
            repo = FinanceRepository(db)
            db_cats = repo.list_categories()
            # Combine defaults and custom DB categories
            all_cats = list(dict.fromkeys(DEFAULT_EXPENSE_CATEGORIES + db_cats))
            return all_cats
