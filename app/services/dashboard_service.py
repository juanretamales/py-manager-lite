from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
from app.db.session import get_db_session
from app.repositories.quote_repo import QuoteRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.finance_repo import FinanceRepository
from app.repositories.client_repo import ClientRepository
from app.repositories.purchase_order_repo import PurchaseOrderRepository
from app.models.quote import QuoteStatus
from app.models.project import ProjectStatus, ProjectEvent
from app.models.invoice import InvoiceType, PaymentStatus, Payment
from app.models.client import ClientEvent


class DashboardService:
    def get_metrics(self) -> Dict[str, Any]:
        """Calcula métricas e indicadores ejecutivos del dashboard según Fase 3."""
        with get_db_session() as db:
            quote_repo = QuoteRepository(db)
            project_repo = ProjectRepository(db)
            finance_repo = FinanceRepository(db)
            client_repo = ClientRepository(db)
            po_repo = PurchaseOrderRepository(db)

            # Quotes
            all_quotes = quote_repo.list_quotes()
            open_statuses = [QuoteStatus.DRAFT, QuoteStatus.SENT, QuoteStatus.NEGOTIATION]
            open_quotes = [q for q in all_quotes if q.status in open_statuses]
            accepted_quotes = [q for q in all_quotes if q.status == QuoteStatus.ACCEPTED]
            open_quotes_count = len(open_quotes)
            open_quotes_amount = sum(q.total_amount for q in open_quotes)
            accepted_quotes_amount = sum(q.total_amount for q in accepted_quotes)

            # Projects
            all_projects = project_repo.list_projects()
            active_projects = [p for p in all_projects if p.status == ProjectStatus.ACTIVE]
            active_projects_count = len(active_projects)
            total_projects_count = len(all_projects)
            avg_progress = (
                round(sum(p.progress for p in active_projects) / active_projects_count, 1)
                if active_projects_count > 0 else 0.0
            )

            # Invoices Issued (Ventas)
            issued_invoices = finance_repo.list_invoices(invoice_type=InvoiceType.ISSUED)
            total_issued = sum(inv.total_amount for inv in issued_invoices)
            total_collected = sum(sum(p.amount for p in inv.payments) for inv in issued_invoices)
            pending_collection = max(0.0, total_issued - total_collected)
            collection_rate = round((total_collected / total_issued * 100), 1) if total_issued > 0 else 0.0

            # Invoices Received (Gastos / Proveedores)
            received_invoices = finance_repo.list_invoices(invoice_type=InvoiceType.RECEIVED)
            total_received = sum(inv.total_amount for inv in received_invoices)
            total_paid = sum(sum(p.amount for p in inv.payments) for inv in received_invoices)
            pending_payment = max(0.0, total_received - total_paid)
            payment_rate = round((total_paid / total_received * 100), 1) if total_received > 0 else 0.0

            # Difference (Balance Operacional Registrado - explicitly not called "profit/utilidad")
            operational_balance = total_collected - total_paid

            # Clients count
            clients = client_repo.list_clients(active_only=True)
            active_clients_count = len(clients)

            # Missing documentation counts (invoices, payments without voucher, OCs without PDF)
            all_invoices = issued_invoices + received_invoices
            missing_invoice_docs = sum(
                1 for inv in all_invoices if not (inv.document_path and Path(inv.document_path).exists())
            )
            missing_vouchers = sum(
                1 for inv in all_invoices for p in inv.payments
                if not (p.evidence_path and Path(p.evidence_path).exists())
            )
            all_pos = po_repo.list_orders()
            missing_po_docs = sum(
                1 for po in all_pos if not (po.document_path and Path(po.document_path).exists())
            )
            total_missing_docs = missing_invoice_docs + missing_vouchers + missing_po_docs

            return {
                "open_quotes_count": open_quotes_count,
                "open_quotes_amount": round(open_quotes_amount, 2),
                "accepted_quotes_amount": round(accepted_quotes_amount, 2),
                "active_projects_count": active_projects_count,
                "total_projects_count": total_projects_count,
                "avg_project_progress": avg_progress,
                "issued_invoices_count": len(issued_invoices),
                "total_issued": round(total_issued, 2),
                "total_collected": round(total_collected, 2),
                "pending_collection": round(pending_collection, 2),
                "collection_rate": collection_rate,
                "received_invoices_count": len(received_invoices),
                "total_received": round(total_received, 2),
                "total_paid": round(total_paid, 2),
                "pending_payment": round(pending_payment, 2),
                "payment_rate": payment_rate,
                "operational_balance": round(operational_balance, 2),
                "active_clients_count": active_clients_count,
                "missing_docs_count": total_missing_docs,
                "missing_invoice_docs": missing_invoice_docs,
                "missing_vouchers": missing_vouchers,
                "missing_po_docs": missing_po_docs,
            }

    def get_deadlines(self) -> List[Dict[str, Any]]:
        """Retorna vencimientos activos: facturas con saldo insoluto y cotizaciones vigentes."""
        results: List[Dict[str, Any]] = []
        today = datetime.now().date()

        with get_db_session() as db:
            finance_repo = FinanceRepository(db)
            quote_repo = QuoteRepository(db)

            # Facturas con saldo pendiente
            invoices = finance_repo.list_invoices()
            for inv in invoices:
                summary = finance_repo.get_invoice_summary(inv)
                balance = summary["balance"]
                if balance > 0 and summary["status"] != PaymentStatus.ANNULLED:
                    if inv.due_date:
                        due = inv.due_date.date()
                        days_diff = (due - today).days
                    else:
                        due = None
                        days_diff = 999  # Sin fecha límite asignada

                    is_overdue = days_diff < 0 if due else False
                    is_urgent = 0 <= days_diff <= 7 if due else False

                    # Contraparte
                    if inv.type == InvoiceType.RECEIVED and inv.issuer_name:
                        counterparty = inv.issuer_name
                    elif inv.client:
                        counterparty = inv.client.name
                    else:
                        counterparty = inv.issuer_name or inv.receiver_name or "Sin contraparte"

                    tipo_label = "Venta por Cobrar" if inv.type == InvoiceType.ISSUED else "Gasto por Pagar"
                    results.append({
                        "id": inv.id,
                        "kind": "INVOICE",
                        "type": inv.type,
                        "type_label": tipo_label,
                        "number": inv.number,
                        "counterparty": counterparty,
                        "due_date": due.strftime("%Y-%m-%d") if due else "Sin fecha",
                        "days_diff": days_diff,
                        "is_overdue": is_overdue,
                        "is_urgent": is_urgent,
                        "total_amount": inv.total_amount,
                        "balance": balance,
                        "status": summary["status"],
                    })

            # Cotizaciones abiertas
            quotes = quote_repo.list_quotes()
            for q in quotes:
                if q.status in [QuoteStatus.SENT, QuoteStatus.NEGOTIATION]:
                    q_date = q.created_at.date() if q.created_at else today
                    days_active = (today - q_date).days
                    is_overdue = days_active > 15
                    is_urgent = 10 <= days_active <= 15
                    results.append({
                        "id": q.id,
                        "kind": "QUOTE",
                        "type": "QUOTE",
                        "type_label": "Cotización en Espera",
                        "number": q.number,
                        "counterparty": q.client.name if q.client else "Sin cliente",
                        "due_date": q_date.strftime("%Y-%m-%d"),
                        "days_diff": -days_active if is_overdue else 15 - days_active,
                        "is_overdue": is_overdue,
                        "is_urgent": is_urgent,
                        "total_amount": q.total_amount,
                        "balance": q.total_amount,
                        "status": q.status,
                    })

        # Ordenar: primero los vencidos (is_overdue=True), luego los más cercanos a vencer
        results.sort(key=lambda x: (not x["is_overdue"], x["days_diff"]))
        return results

    def get_missing_documentation(self) -> Dict[str, Any]:
        """Auditoría de respaldo: detecta facturas sin PDF/XML, pagos sin voucher y OCs sin archivo."""
        with get_db_session() as db:
            finance_repo = FinanceRepository(db)
            po_repo = PurchaseOrderRepository(db)

            invoices_missing: List[Dict[str, Any]] = []
            payments_missing: List[Dict[str, Any]] = []
            pos_missing: List[Dict[str, Any]] = []

            # 1. Facturas sin archivo original
            all_invoices = finance_repo.list_invoices()
            for inv in all_invoices:
                has_doc = bool(inv.document_path and Path(inv.document_path).exists())
                if not has_doc:
                    contraparte = (
                        inv.issuer_name if inv.type == InvoiceType.RECEIVED and inv.issuer_name
                        else (inv.client.name if inv.client else "N/A")
                    )
                    invoices_missing.append({
                        "id": inv.id,
                        "number": inv.number,
                        "type": inv.type,
                        "type_label": "Emitida (Venta)" if inv.type == InvoiceType.ISSUED else "Recibida (Gasto)",
                        "counterparty": contraparte,
                        "total_amount": inv.total_amount,
                        "issue_date": inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "-"
                    })

                # 2. Pagos sin voucher
                for p in inv.payments:
                    has_ev = bool(p.evidence_path and Path(p.evidence_path).exists())
                    if not has_ev:
                        payments_missing.append({
                            "id": p.id,
                            "invoice_id": inv.id,
                            "invoice_number": inv.number,
                            "amount": p.amount,
                            "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else "-",
                            "payment_method": p.payment_method or "Transferencia",
                            "reference": p.reference or "-"
                        })

            # 3. OCs sin PDF original
            all_pos = po_repo.list_orders()
            for po in all_pos:
                has_doc = bool(po.document_path and Path(po.document_path).exists())
                if not has_doc:
                    pos_missing.append({
                        "id": po.id,
                        "number": po.number,
                        "client_name": po.client.name if po.client else "N/A",
                        "amount": po.amount,
                        "status": po.status,
                        "issue_date": po.issue_date.strftime("%Y-%m-%d") if po.issue_date else "-"
                    })

            return {
                "invoices": invoices_missing,
                "payments": payments_missing,
                "purchase_orders": pos_missing,
                "total_missing": len(invoices_missing) + len(payments_missing) + len(pos_missing)
            }

    def get_activity_timeline(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Línea de tiempo cronológica unificada de eventos comerciales, pagos, proyectos y facturas."""
        timeline: List[Dict[str, Any]] = []

        with get_db_session() as db:
            # Eventos de clientes (Facturaciones, notas, pagos, cotizaciones)
            client_events = db.query(ClientEvent).order_by(ClientEvent.date.desc()).limit(limit).all()
            for ev in client_events:
                c_name = ev.client.name if ev.client else "Cliente"
                dt = ev.date or ev.created_at or datetime.now()
                timeline.append({
                    "timestamp": dt,
                    "date_str": dt.strftime("%Y-%m-%d %H:%M"),
                    "category": ev.event_type or "CLIENT",
                    "title": f"{c_name} · {ev.event_type}",
                    "description": ev.description,
                    "client_id": ev.client_id,
                    "project_id": ev.project_id,
                    "invoice_id": ev.invoice_id,
                })

            # Eventos de proyectos
            proj_events = db.query(ProjectEvent).order_by(ProjectEvent.date.desc()).limit(limit).all()
            for pev in proj_events:
                p_name = pev.project.name if pev.project else "Proyecto"
                dt = pev.date or pev.created_at or datetime.now()
                timeline.append({
                    "timestamp": dt,
                    "date_str": dt.strftime("%Y-%m-%d %H:%M"),
                    "category": "PROJECT",
                    "title": f"Proyecto: {p_name}",
                    "description": pev.description,
                    "project_id": pev.project_id,
                })

            # Pagos registrados
            payments = db.query(Payment).order_by(Payment.payment_date.desc()).limit(limit).all()
            for pay in payments:
                inv_num = pay.invoice.number if pay.invoice else f"ID {pay.invoice_id}"
                dt = pay.payment_date or datetime.now()
                voucher_tag = " (Voucher respaldado)" if pay.evidence_path else " (Sin voucher)"
                timeline.append({
                    "timestamp": dt,
                    "date_str": dt.strftime("%Y-%m-%d"),
                    "category": "PAYMENT",
                    "title": f"Pago registrado Factura #{inv_num}",
                    "description": (
                        f"Monto: ${pay.amount:,.0f} vía {pay.payment_method or 'Transferencia'}{voucher_tag}. "
                        f"Ref: {pay.reference or '-'}"
                    ),
                    "invoice_id": pay.invoice_id,
                })

        timeline.sort(
            key=lambda x: x["timestamp"] if isinstance(x["timestamp"], datetime) else datetime.min,
            reverse=True
        )
        return timeline[:limit]
