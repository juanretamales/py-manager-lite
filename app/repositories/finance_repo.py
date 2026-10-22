from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.invoice import Invoice, InvoiceType, Payment, PaymentStatus


class FinanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_invoices(
        self,
        invoice_type: Optional[str] = None,
        client_id: Optional[int] = None,
        category: Optional[str] = None,
        project_id: Optional[int] = None
    ) -> List[Invoice]:
        query = self.db.query(Invoice)
        if invoice_type and invoice_type != "ALL":
            query = query.filter(Invoice.type == invoice_type)
        if client_id:
            query = query.filter(Invoice.client_id == client_id)
        if category and category != "ALL":
            query = query.filter(Invoice.category == category)
        if project_id:
            query = query.filter(Invoice.project_id == project_id)
        return query.order_by(Invoice.issue_date.desc(), Invoice.id.desc()).all()

    def get_invoice_by_id(self, invoice_id: int) -> Optional[Invoice]:
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    def unlink_project(self, invoice_id: int) -> bool:
        inv = self.get_invoice_by_id(invoice_id)
        if inv:
            inv.project_id = None
            self.db.commit()
            self.db.refresh(inv)
            return True
        return False

    def create_invoice(self, **kwargs) -> Invoice:
        # Calculate totals if not explicitly given
        net = float(kwargs.get("net_amount", 0.0))
        tax = float(kwargs.get("tax_amount", 0.0))
        total = float(kwargs.get("total_amount", 0.0))
        if total == 0.0 and net > 0.0:
            if tax == 0.0:
                tax = round(net * 0.19, 2)
            total = round(net + tax, 2)
            kwargs["tax_amount"] = tax
            kwargs["total_amount"] = total

        invoice_kwargs = dict(kwargs)
        raw_issue = invoice_kwargs.get("issue_date")
        if isinstance(raw_issue, str) and raw_issue.strip():
            try:
                invoice_kwargs["issue_date"] = datetime.strptime(raw_issue[:10], "%Y-%m-%d")
            except ValueError:
                pass

        raw_due = invoice_kwargs.get("due_date")
        if isinstance(raw_due, str) and raw_due.strip():
            try:
                invoice_kwargs["due_date"] = datetime.strptime(raw_due[:10], "%Y-%m-%d")
            except ValueError:
                pass

        invoice = Invoice(**invoice_kwargs)
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def create_credit_note(
        self,
        reference_invoice_id: int,
        number: str,
        amount: float,
        reason: str,
        is_total_annulment: bool = True,
        **kwargs
    ) -> Invoice:
        ref_inv = self.get_invoice_by_id(reference_invoice_id)
        net = round(amount / 1.19, 2)
        tax = round(amount - net, 2)

        credit_note = Invoice(
            type=InvoiceType.CREDIT_NOTE,
            number=number,
            reference_invoice_id=reference_invoice_id,
            annulment_reason=reason,
            client_id=ref_inv.client_id if ref_inv else kwargs.get("client_id"),
            project_id=ref_inv.project_id if ref_inv else kwargs.get("project_id"),
            net_amount=net,
            tax_amount=tax,
            total_amount=amount,
            category="Nota de Crédito SII",
            document_path=kwargs.get("document_path"),
            notes=(
                f"Nota de Crédito SII para Factura #{ref_inv.number if ref_inv else reference_invoice_id}. "
                f"Motivo: {reason}"
            )
        )
        self.db.add(credit_note)

        if ref_inv and is_total_annulment:
            annulment_tag = f"[Anulada con NC #{number}: {reason}]"
            ref_inv.notes = f"{annulment_tag}\n{ref_inv.notes}" if ref_inv.notes else annulment_tag

        self.db.commit()
        self.db.refresh(credit_note)
        return credit_note

    def update_invoice(self, invoice_id: int, **kwargs) -> Optional[Invoice]:
        invoice = self.get_invoice_by_id(invoice_id)
        if not invoice:
            return None

        # Recalculate if net amount was updated
        if "net_amount" in kwargs and "total_amount" not in kwargs:
            net = float(kwargs["net_amount"])
            tax = round(net * 0.19, 2)
            kwargs["tax_amount"] = tax
            kwargs["total_amount"] = round(net + tax, 2)

        for k, v in kwargs.items():
            if hasattr(invoice, k):
                setattr(invoice, k, v)

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def delete_invoice(self, invoice_id: int) -> bool:
        inv = self.get_invoice_by_id(invoice_id)
        if inv:
            self.db.delete(inv)
            self.db.commit()
            return True
        return False

    def list_categories(self) -> List[str]:
        """Returns distinct categories of invoices registered in DB."""
        results = (
            self.db.query(Invoice.category)
            .filter(Invoice.category.isnot(None), Invoice.category != "")
            .distinct()
            .all()
        )
        return [r[0] for r in results]

    def add_payment(self, invoice_id: int, amount: float, **kwargs) -> Payment:
        payment = Payment(
            invoice_id=invoice_id,
            amount=amount,
            payment_date=kwargs.get("payment_date", datetime.now(timezone.utc)),
            payment_method=kwargs.get("payment_method"),
            reference=kwargs.get("reference"),
            evidence_path=kwargs.get("evidence_path"),
            notes=kwargs.get("notes")
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def delete_payment(self, payment_id: int) -> bool:
        p = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if p:
            self.db.delete(p)
            self.db.commit()
            return True
        return False

    def update_payment_evidence(self, payment_id: int, evidence_path: str) -> bool:
        """Actualiza la ruta del archivo de comprobante o voucher de un pago existente."""
        p = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if p:
            p.evidence_path = evidence_path
            self.db.commit()
            self.db.refresh(p)
            return True
        return False

    def get_invoice_summary(self, invoice: Invoice) -> Dict[str, Any]:
        # If it's a Credit Note itself
        if invoice.type == InvoiceType.CREDIT_NOTE:
            return {
                "invoice": invoice,
                "total_amount": invoice.total_amount,
                "total_paid": invoice.total_amount,
                "total_credit": 0.0,
                "balance": 0.0,
                "status": "CREDIT_NOTE",
                "payments_count": 0,
                "has_evidence": bool(invoice.document_path)
            }

        total_paid = sum(p.amount for p in invoice.payments)
        credit_notes = getattr(invoice, "credit_notes", []) or []
        total_credit = sum(cn.total_amount for cn in credit_notes)

        # Check if fully annulled by credit note
        is_annulled = any(
            cn.total_amount >= invoice.total_amount or "Anula" in (cn.annulment_reason or "")
            for cn in credit_notes
        )

        if is_annulled:
            return {
                "invoice": invoice,
                "total_amount": invoice.total_amount,
                "total_paid": round(total_paid, 2),
                "total_credit": round(total_credit, 2),
                "balance": 0.0,
                "status": PaymentStatus.ANNULLED,
                "payments_count": len(invoice.payments),
                "has_evidence": any(p.evidence_path for p in invoice.payments)
            }

        balance = round(max(0.0, invoice.total_amount - total_paid - total_credit), 2)

        # Payment status derivation
        now = datetime.now()
        is_past_due = invoice.due_date is not None and invoice.due_date.replace(tzinfo=None) < now

        if total_paid <= 0 and total_credit <= 0:
            status = PaymentStatus.OVERDUE if (is_past_due and balance > 0) else PaymentStatus.PENDING
        elif balance <= 0:
            status = PaymentStatus.PAID
        else:
            status = PaymentStatus.OVERDUE if is_past_due else PaymentStatus.PARTIAL

        return {
            "invoice": invoice,
            "total_amount": invoice.total_amount,
            "total_paid": round(total_paid, 2),
            "total_credit": round(total_credit, 2),
            "balance": balance,
            "status": status,
            "payments_count": len(invoice.payments),
            "has_evidence": any(p.evidence_path for p in invoice.payments)
        }
