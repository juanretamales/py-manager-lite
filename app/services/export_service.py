import csv
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from app.core.config import get_documents_dir
from app.db.session import get_db_session
from app.models.invoice import Invoice, InvoiceType, Payment
from app.repositories.finance_repo import FinanceRepository
from app.repositories.purchase_order_repo import PurchaseOrderRepository
from app.services.company_service import CompanyService
from app.services.currency_service import format_currency

logger = logging.getLogger(__name__)


def get_preset_dates(preset: str) -> Tuple[Optional[str], Optional[str]]:
    """Calcula las fechas de inicio y fin para los filtros de período estándar."""
    today = date.today()
    if preset == "THIS_MONTH":
        first_day = today.replace(day=1)
        return first_day.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif preset == "LAST_MONTH":
        first_current = today.replace(day=1)
        # Último día del mes anterior
        from datetime import timedelta
        last_prev = first_current - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.strftime("%Y-%m-%d"), last_prev.strftime("%Y-%m-%d")
    elif preset == "THIS_YEAR":
        first_year = today.replace(month=1, day=1)
        return first_year.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    return None, None


class ExportService:
    @staticmethod
    def get_preset_dates(preset: str) -> Tuple[Optional[str], Optional[str]]:
        return get_preset_dates(preset)

    def __init__(self) -> None:
        self.company_service = CompanyService()

    @property
    def exports_dir(self) -> Path:
        """Retorna la ruta actual de exportaciones basada en la carpeta activa de almacenamiento."""
        p = get_documents_dir() / "exports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _filter_by_date(
        self,
        item_date: Optional[date],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> bool:
        if not item_date:
            return True
        if start_date:
            start_d = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
            if item_date < start_d:
                return False
        if end_date:
            end_d = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
            if item_date > end_d:
                return False
        return True

    def get_period_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calcula el consolidado financiero y tributario para el período seleccionado."""
        with get_db_session() as db:
            finance_repo = FinanceRepository(db)
            all_invoices = finance_repo.list_invoices()

            issued: List[Invoice] = []
            received: List[Invoice] = []
            period_payments: List[Payment] = []

            for inv in all_invoices:
                inv_d = inv.issue_date.date() if inv.issue_date else None
                if self._filter_by_date(inv_d, start_date, end_date):
                    if inv.type == InvoiceType.ISSUED:
                        issued.append(inv)
                    elif inv.type == InvoiceType.RECEIVED:
                        received.append(inv)

                # Pagos del periodo
                for p in inv.payments:
                    pay_d = p.payment_date.date() if p.payment_date else None
                    if self._filter_by_date(pay_d, start_date, end_date):
                        period_payments.append(p)

            # Ventas (Facturación emitida)
            sales_net = sum(inv.net_amount for inv in issued)
            sales_tax = sum(inv.tax_amount for inv in issued)
            sales_total = sum(inv.total_amount for inv in issued)
            sales_paid = sum(sum(p.amount for p in inv.payments) for inv in issued)
            sales_balance = max(0.0, sales_total - sales_paid)

            # Compras y Gastos (Facturación recibida)
            purchases_net = sum(inv.net_amount for inv in received)
            purchases_tax = sum(inv.tax_amount for inv in received)
            purchases_total = sum(inv.total_amount for inv in received)
            purchases_paid = sum(sum(p.amount for p in inv.payments) for inv in received)
            purchases_balance = max(0.0, purchases_total - purchases_paid)

            # NOTA TRIBUTARIA: Estimación referencial del IVA F29 chileno (Débito Fiscal - Crédito Fiscal).
            # No sustituye la presentación formal ante el Servicio de Impuestos Internos (SII).
            vat_balance = sales_tax - purchases_tax

            # Cobros en efectivo del periodo (pagos asociados a facturas emitidas)
            collected_cash = sum(
                p.amount for p in period_payments if p.invoice and p.invoice.type == InvoiceType.ISSUED
            )
            # Pagos a proveedores del periodo (pagos asociados a facturas recibidas)
            paid_cash = sum(
                p.amount for p in period_payments if p.invoice and p.invoice.type == InvoiceType.RECEIVED
            )
            operational_cash_flow = collected_cash - paid_cash

            return {
                "start_date": start_date or "Inicio histórico",
                "end_date": end_date or "A la fecha",
                "sales_net": round(sales_net, 2),
                "sales_tax": round(sales_tax, 2),
                "sales_total": round(sales_total, 2),
                "sales_paid": round(sales_paid, 2),
                "sales_balance": round(sales_balance, 2),
                "sales_count": len(issued),
                "purchases_net": round(purchases_net, 2),
                "purchases_tax": round(purchases_tax, 2),
                "purchases_total": round(purchases_total, 2),
                "purchases_paid": round(purchases_paid, 2),
                "purchases_balance": round(purchases_balance, 2),
                "purchases_count": len(received),
                "vat_balance": round(vat_balance, 2),
                "sales_vat_debit": round(sales_tax, 2),
                "purchases_vat_credit": round(purchases_tax, 2),
                "f29_estimated_vat": round(vat_balance, 2),
                "collected_cash": round(collected_cash, 2),
                "paid_cash": round(paid_cash, 2),
                "operational_cash_flow": round(operational_cash_flow, 2),
                "cashflow_collected": round(collected_cash, 2),
                "cashflow_paid": round(paid_cash, 2),
                "cashflow_net": round(operational_cash_flow, 2),
                "payments_count": len(period_payments),
            }

    def export_sales_book_csv(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        delimiter: str = ";"
    ) -> str:
        """Exporta el Libro de Ventas en formato CSV compatible con Microsoft Excel (BOM utf-8-sig)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"libro_ventas_{timestamp}.csv"
        file_path = self.exports_dir / filename

        with get_db_session() as db:
            finance_repo = FinanceRepository(db)
            invoices = finance_repo.list_invoices(invoice_type=InvoiceType.ISSUED)

            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file, delimiter=delimiter)
                # Encabezados contables estándar
                writer.writerow([
                    "Folio Factura",
                    "Tipo DTE",
                    "Fecha Emisión",
                    "Fecha Vencimiento",
                    "RUT Receptor / Cliente",
                    "Razón Social Cliente",
                    "Monto Neto ($)",
                    "IVA 19% ($)",
                    "Monto Total ($)",
                    "Total Pagado ($)",
                    "Saldo Pendiente ($)",
                    "Estado Pago",
                    "Proyecto Asociado",
                    "Tiene Archivo PDF/XML",
                    "Notas",
                ])

                for inv in invoices:
                    inv_d = inv.issue_date.date() if inv.issue_date else None
                    if not self._filter_by_date(inv_d, start_date, end_date):
                        continue

                    summary = finance_repo.get_invoice_summary(inv)
                    client_rut = inv.receiver_tax_id or (inv.client.tax_id if inv.client else "")
                    client_name = inv.client.name if inv.client else (inv.receiver_name or "N/A")
                    has_doc = "SÍ" if inv.document_path and Path(inv.document_path).exists() else "NO"

                    writer.writerow([
                        inv.number,
                        "33 - Factura Electrónica",
                        inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "",
                        inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "",
                        client_rut,
                        client_name,
                        int(inv.net_amount),
                        int(inv.tax_amount),
                        int(inv.total_amount),
                        int(summary["total_paid"]),
                        int(summary["balance"]),
                        summary["status"],
                        inv.project.name if inv.project else "",
                        has_doc,
                        (inv.notes or "").replace("\n", " "),
                    ])

        return str(file_path)

    def export_purchases_book_csv(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        delimiter: str = ";"
    ) -> str:
        """Exporta el Libro de Compras y Gastos en formato CSV compatible con Microsoft Excel (BOM utf-8-sig)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"libro_compras_{timestamp}.csv"
        file_path = self.exports_dir / filename

        with get_db_session() as db:
            finance_repo = FinanceRepository(db)
            invoices = finance_repo.list_invoices(invoice_type=InvoiceType.RECEIVED)

            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file, delimiter=delimiter)
                writer.writerow([
                    "Folio Factura",
                    "Tipo DTE",
                    "Fecha Emisión",
                    "Fecha Vencimiento",
                    "RUT Emisor / Proveedor",
                    "Razón Social Proveedor",
                    "Categoría de Gasto",
                    "Monto Neto ($)",
                    "IVA Crédito 19% ($)",
                    "Monto Total ($)",
                    "Total Pagado ($)",
                    "Saldo Pendiente ($)",
                    "Estado Pago",
                    "Tiene Archivo PDF/XML",
                    "Notas",
                ])

                for inv in invoices:
                    inv_d = inv.issue_date.date() if inv.issue_date else None
                    if not self._filter_by_date(inv_d, start_date, end_date):
                        continue

                    summary = finance_repo.get_invoice_summary(inv)
                    provider_rut = inv.issuer_tax_id or ""
                    provider_name = inv.issuer_name or (inv.client.name if inv.client else "N/A")
                    has_doc = "SÍ" if inv.document_path and Path(inv.document_path).exists() else "NO"

                    writer.writerow([
                        inv.number,
                        "33 - Factura Electrónica",
                        inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "",
                        inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "",
                        provider_rut,
                        provider_name,
                        inv.category or "General",
                        int(inv.net_amount),
                        int(inv.tax_amount),
                        int(inv.total_amount),
                        int(summary["total_paid"]),
                        int(summary["balance"]),
                        summary["status"],
                        has_doc,
                        (inv.notes or "").replace("\n", " "),
                    ])

        return str(file_path)

    def export_payments_reconciliation_csv(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        delimiter: str = ";"
    ) -> str:
        """Exporta la Conciliación de Pagos y Cobros en formato CSV compatible con Excel."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conciliacion_pagos_{timestamp}.csv"
        file_path = self.exports_dir / filename

        with get_db_session() as db:
            finance_repo = FinanceRepository(db)
            all_invoices = finance_repo.list_invoices()

            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file, delimiter=delimiter)
                writer.writerow([
                    "ID Pago",
                    "Fecha Pago",
                    "Tipo Flujo",
                    "Folio Factura",
                    "Contraparte",
                    "Monto Abonado ($)",
                    "Medio de Pago",
                    "Referencia / N° Operación",
                    "Voucher Adjunto",
                    "Notas",
                ])

                for inv in all_invoices:
                    contraparte = (
                        inv.issuer_name if inv.type == InvoiceType.RECEIVED and inv.issuer_name
                        else (inv.client.name if inv.client else "N/A")
                    )
                    flow_type = "Cobro (Ingreso)" if inv.type == InvoiceType.ISSUED else "Pago Proveedor (Egreso)"

                    for p in inv.payments:
                        pay_d = p.payment_date.date() if p.payment_date else None
                        if not self._filter_by_date(pay_d, start_date, end_date):
                            continue

                        has_voucher = "SÍ" if p.evidence_path and Path(p.evidence_path).exists() else "NO"
                        writer.writerow([
                            p.id,
                            p.payment_date.strftime("%Y-%m-%d") if p.payment_date else "",
                            flow_type,
                            inv.number,
                            contraparte,
                            int(p.amount),
                            p.payment_method or "Transferencia",
                            p.reference or "-",
                            has_voucher,
                            (p.notes or "").replace("\n", " "),
                        ])

        return str(file_path)

    def export_missing_documents_csv(self, delimiter: str = ";") -> str:
        """Exporta el reporte de auditoría documental faltante para revisión del contador."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auditoria_documentos_faltantes_{timestamp}.csv"
        file_path = self.exports_dir / filename

        with get_db_session() as db:
            finance_repo = FinanceRepository(db)
            po_repo = PurchaseOrderRepository(db)
            all_invoices = finance_repo.list_invoices()
            all_pos = po_repo.list_orders()

            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file, delimiter=delimiter)
                writer.writerow([
                    "Categoría",
                    "Tipo de Documento",
                    "Identificador / Folio",
                    "Contraparte / Cliente",
                    "Monto Asociado ($)",
                    "Fecha",
                    "Condición Faltante",
                ])

                # 1. Facturas sin archivo original
                for inv in all_invoices:
                    if not (inv.document_path and Path(inv.document_path).exists()):
                        c_name = (
                            inv.issuer_name if inv.type == InvoiceType.RECEIVED and inv.issuer_name
                            else (inv.client.name if inv.client else "N/A")
                        )
                        t_lbl = "Factura Venta" if inv.type == InvoiceType.ISSUED else "Factura Compra"
                        writer.writerow([
                            "Facturación",
                            t_lbl,
                            inv.number,
                            c_name,
                            int(inv.total_amount),
                            inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "",
                            "Falta archivo digital original (PDF / XML SII)",
                        ])

                # 2. Pagos sin voucher
                for inv in all_invoices:
                    for p in inv.payments:
                        if not (p.evidence_path and Path(p.evidence_path).exists()):
                            c_name = (
                                inv.issuer_name if inv.type == InvoiceType.RECEIVED and inv.issuer_name
                                else (inv.client.name if inv.client else "N/A")
                            )
                            writer.writerow([
                                "Cobros y Pagos",
                                f"Abono Factura #{inv.number}",
                                f"Pago ID {p.id}",
                                c_name,
                                int(p.amount),
                                p.payment_date.strftime("%Y-%m-%d") if p.payment_date else "",
                                "Falta comprobante / voucher de transferencia bancaria",
                            ])

                # 3. OCs sin PDF
                for po in all_pos:
                    if not (po.document_path and Path(po.document_path).exists()):
                        c_name = po.client.name if po.client else "N/A"
                        writer.writerow([
                            "Órdenes de Compra",
                            "Orden de Compra (OC)",
                            po.number,
                            c_name,
                            int(po.amount),
                            po.issue_date.strftime("%Y-%m-%d") if po.issue_date else "",
                            "Falta archivo PDF original emitido por cliente",
                        ])

        return str(file_path)

    def generate_executive_report_html(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """Genera un reporte financiero ejecutivo e imprimible (HTML print-ready para PDF)."""
        summary = self.get_period_summary(start_date, end_date)
        company = self.company_service.get_company()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_financiero_{timestamp}.html"
        file_path = self.exports_dir / filename

        vat_class = "positive" if summary["vat_balance"] >= 0 else "negative"
        vat_desc = "IVA Débito a pagar al Fisco (F29)" if summary["vat_balance"] >= 0 else "Remanente Crédito Fiscal"

        cash_class = "positive" if summary["operational_cash_flow"] >= 0 else "negative"

        fmt = {
            "sales_total": format_currency(summary["sales_total"]),
            "sales_net": format_currency(summary["sales_net"]),
            "sales_tax": format_currency(summary["sales_tax"]),
            "purchases_total": format_currency(summary["purchases_total"]),
            "purchases_net": format_currency(summary["purchases_net"]),
            "purchases_tax": format_currency(summary["purchases_tax"]),
            "vat_balance": format_currency(abs(summary["vat_balance"])),
            "collected_cash": format_currency(summary["collected_cash"]),
            "paid_cash": format_currency(summary["paid_cash"]),
            "cash_flow": format_currency(summary["operational_cash_flow"]),
            "sales_paid": format_currency(summary["sales_paid"]),
            "sales_balance": format_currency(summary["sales_balance"]),
            "purchases_paid": format_currency(summary["purchases_paid"]),
            "purchases_balance": format_currency(summary["purchases_balance"]),
        }

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Reporte Financiero y Contable - {company.get('name', 'Empresa')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            background-color: #f8fafc;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            padding: 40px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .company-info h1 {{
            margin: 0 0 6px 0;
            font-size: 24px;
            color: #0f172a;
        }}
        .company-info p {{
            margin: 2px 0;
            font-size: 13px;
            color: #64748b;
        }}
        .report-meta {{
            text-align: right;
        }}
        .badge {{
            display: inline-block;
            background: #e0f2fe;
            color: #0369a1;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
            margin-bottom: 8px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
        }}
        .card .title {{
            font-size: 12px;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .card .value {{
            font-size: 20px;
            font-weight: bold;
            color: #0f172a;
            margin: 6px 0 2px 0;
        }}
        .card .sub {{
            font-size: 11px;
            color: #94a3b8;
        }}
        .card.positive .value {{ color: #15803d; }}
        .card.negative .value {{ color: #b91c1c; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0 24px 0;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            font-weight: 600;
        }}
        .text-right {{ text-align: right; }}
        .section-title {{
            font-size: 16px;
            font-weight: bold;
            color: #1e293b;
            margin: 24px 0 8px 0;
            border-left: 4px solid #3b82f6;
            padding-left: 8px;
        }}
        .print-btn {{
            background: #0f172a;
            color: #ffffff;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 20px;
        }}
        .print-btn:hover {{ background: #334155; }}
        .notice {{
            font-size: 11px;
            color: #94a3b8;
            margin-top: 30px;
            border-top: 1px solid #e2e8f0;
            padding-top: 12px;
            text-align: center;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .container {{ box-shadow: none; border-radius: 0; padding: 0; max-width: 100%; }}
            .print-btn {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <button class="print-btn" onclick="window.print()">🖨️ Imprimir o Guardar en PDF</button>

        <div class="header">
            <div class="company-info">
                <h1>{company.get('name') or company.get('legal_name') or 'py-manager-lite'}</h1>
                <p><strong>RUT:</strong> {company.get('tax_id') or 'N/A'}</p>
                <p><strong>Giro / Actividad:</strong> {company.get('activity') or 'Consultoría y Servicios'}</p>
                <p><strong>Email:</strong> {company.get('email') or '-'}</p>
                <p><strong>Teléfono:</strong> {company.get('phone') or '-'}</p>
            </div>
            <div class="report-meta">
                <span class="badge">REPORTE CONTABLE Y FINANCIERO</span>
                <p><strong>Período:</strong> {summary['start_date']} al {summary['end_date']}</p>
                <p><strong>Emisión:</strong> {now_str}</p>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="title">Facturación Emitida (Ventas)</div>
                <div class="value">{fmt['sales_total']}</div>
                <div class="sub">Neto: {fmt['sales_net']} | IVA: {fmt['sales_tax']}</div>
            </div>
            <div class="card">
                <div class="title">Facturación Recibida (Gastos)</div>
                <div class="value">{fmt['purchases_total']}</div>
                <div class="sub">Neto: {fmt['purchases_net']} | IVA: {fmt['purchases_tax']}</div>
            </div>
            <div class="card {vat_class}">
                <div class="title">Estimación F29 (IVA)</div>
                <div class="value">{fmt['vat_balance']}</div>
                <div class="sub">{vat_desc}</div>
            </div>
        </div>

        <div class="grid">
            <div class="card positive">
                <div class="title">Cobrado Efectivo en Período</div>
                <div class="value">{fmt['collected_cash']}</div>
                <div class="sub">Ingresos percibidos en caja</div>
            </div>
            <div class="card negative">
                <div class="title">Pagado a Proveedores</div>
                <div class="value">{fmt['paid_cash']}</div>
                <div class="sub">Egresos abonados en caja</div>
            </div>
            <div class="card {cash_class}">
                <div class="title">Flujo Neto en Caja</div>
                <div class="value">{fmt['cash_flow']}</div>
                <div class="sub">Diferencia Cobrado - Pagado</div>
            </div>
        </div>

        <div class="section-title">Resumen de Cuentas por Cobrar y por Pagar</div>
        <table>
            <thead>
                <tr>
                    <th>Concepto</th>
                    <th class="text-right">Total Facturado</th>
                    <th class="text-right">Monto Pagado / Cobrado</th>
                    <th class="text-right">Saldo Insoluto Pendiente</th>
                    <th class="text-right">Cant. Documentos</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Ventas (Cuentas por Cobrar)</strong></td>
                    <td class="text-right">{fmt['sales_total']}</td>
                    <td class="text-right" style="color:#15803d">{fmt['sales_paid']}</td>
                    <td class="text-right" style="color:#c2410c;font-weight:bold">{fmt['sales_balance']}</td>
                    <td class="text-right">{summary['sales_count']}</td>
                </tr>
                <tr>
                    <td><strong>Compras y Gastos (Cuentas por Pagar)</strong></td>
                    <td class="text-right">{fmt['purchases_total']}</td>
                    <td class="text-right" style="color:#15803d">{fmt['purchases_paid']}</td>
                    <td class="text-right" style="color:#b91c1c;font-weight:bold">
                        {fmt['purchases_balance']}
                    </td>
                    <td class="text-right">{summary['purchases_count']}</td>
                </tr>
            </tbody>
        </table>

        <div class="notice">
            Este reporte fue generado de forma automatizada por py-manager-lite.
            Los cálculos tributarios de IVA y saldos operacionales tienen carácter referencial y deben ser validados
            por el contador de la empresa para la declaración mensual del Formulario 29 ante el SII.
        </div>
    </div>
</body>
</html>
"""
        with open(file_path, mode="w", encoding="utf-8") as f:
            f.write(html_content)

        return str(file_path)

    def generate_missing_documents_report_html(self) -> str:
        """Genera un reporte imprimible de auditoría documental para carpeta tributaria."""
        from app.services.dashboard_service import DashboardService
        dash = DashboardService()
        data = dash.get_missing_documentation()
        company = self.company_service.get_company()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auditoria_documentacion_faltante_{timestamp}.html"
        file_path = self.exports_dir / filename

        inv_rows_html = "".join([
            f"<tr><td>{i['type_label']}</td><td><strong>#{i['number']}</strong></td><td>{i['counterparty']}</td>"
            f"<td class='text-right'>{format_currency(i['total_amount'])}</td><td>{i['issue_date']}</td>"
            f"<td style='color:#b91c1c;'>Sin archivo PDF/XML</td></tr>"
            for i in data["invoices"]
        ])
        if not inv_rows_html:
            inv_rows_html = (
                "<tr><td colspan='6' style='text-align:center;'>Todas las facturas cuentan con respaldo.</td></tr>"
            )

        pay_rows_html = "".join([
            f"<tr><td>Pago ID #{p['id']}</td><td>Factura #{p['invoice_number']}</td>"
            f"<td class='text-right'>{format_currency(p['amount'])}</td><td>{p['payment_method']}</td>"
            f"<td>{p['payment_date']}</td><td style='color:#b91c1c;'>Sin voucher de transferencia</td></tr>"
            for p in data["payments"]
        ])
        if not pay_rows_html:
            pay_rows_html = (
                "<tr><td colspan='6' style='text-align:center;'>Todos los pagos tienen voucher adjunto.</td></tr>"
            )

        po_rows_html = "".join([
            f"<tr><td><strong>OC #{p['number']}</strong></td><td>{p['client_name']}</td>"
            f"<td class='text-right'>{format_currency(p['amount'])}</td>"
            f"<td>{p['status']}</td><td>{p['issue_date']}</td>"
            f"<td style='color:#b91c1c;'>Sin PDF de cliente</td></tr>"
            for p in data["purchase_orders"]
        ])
        if not po_rows_html:
            po_rows_html = (
                "<tr><td colspan='6' style='text-align:center;'>Todas las órdenes de compra cuentan con PDF.</td></tr>"
            )

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Auditoría de Documentación Faltante - {company.get('name', 'Empresa')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            background-color: #f8fafc;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            padding: 40px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .company-info h1 {{ margin: 0 0 6px 0; font-size: 22px; color: #0f172a; }}
        .company-info p {{ margin: 2px 0; font-size: 13px; color: #64748b; }}
        .report-meta {{ text-align: right; }}
        .alert-box {{
            background: #fef2f2;
            border: 1px solid #fecaca;
            color: #991b1b;
            padding: 14px 18px;
            border-radius: 8px;
            font-weight: 600;
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0 24px 0;
            font-size: 13px;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{ background: #f1f5f9; color: #475569; font-weight: 600; }}
        .text-right {{ text-align: right; }}
        .section-title {{
            font-size: 15px;
            font-weight: bold;
            color: #0f172a;
            margin: 20px 0 8px 0;
            border-left: 4px solid #ef4444;
            padding-left: 8px;
        }}
        .print-btn {{
            background: #0f172a;
            color: #ffffff;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 20px;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .container {{ box-shadow: none; border-radius: 0; padding: 0; max-width: 100%; }}
            .print-btn {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <button class="print-btn" onclick="window.print()">🖨️ Imprimir / Guardar en PDF</button>

        <div class="header">
            <div class="company-info">
                <h1>{company.get('name') or company.get('legal_name') or 'py-manager-lite'}</h1>
                <p><strong>RUT:</strong> {company.get('tax_id') or 'N/A'}</p>
                <p><strong>Auditoría Contable de Documentación y Respaldos</strong></p>
            </div>
            <div class="report-meta">
                <p><strong>Fecha de Auditoría:</strong> {now_str}</p>
            </div>
        </div>

        <div class="alert-box">
            ⚠️ Se han detectado <strong>{data['total_missing']} documentos o evidencias faltantes</strong> que requieren
            regularización para la carpeta tributaria del período.
        </div>

        <div class="section-title">1. Facturas sin Archivo Digital de Respaldo (PDF / XML SII)</div>
        <table>
            <thead>
                <tr>
                    <th>Tipo</th>
                    <th>N° Folio</th>
                    <th>Contraparte</th>
                    <th class="text-right">Total ($)</th>
                    <th>Emisión</th>
                    <th>Estado de Respaldo</th>
                </tr>
            </thead>
            <tbody>
                {inv_rows_html}
            </tbody>
        </table>

        <div class="section-title">2. Pagos Registrados sin Comprobante de Transferencia (Voucher)</div>
        <table>
            <thead>
                <tr>
                    <th>ID Pago</th>
                    <th>Referencia Factura</th>
                    <th class="text-right">Monto ($)</th>
                    <th>Medio</th>
                    <th>Fecha Pago</th>
                    <th>Estado de Respaldo</th>
                </tr>
            </thead>
            <tbody>
                {pay_rows_html}
            </tbody>
        </table>

        <div class="section-title">3. Órdenes de Compra sin Documento PDF del Cliente</div>
        <table>
            <thead>
                <tr>
                    <th>N° OC</th>
                    <th>Cliente</th>
                    <th class="text-right">Monto ($)</th>
                    <th>Estado</th>
                    <th>Fecha Emisión</th>
                    <th>Estado de Respaldo</th>
                </tr>
            </thead>
            <tbody>
                {po_rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        with open(file_path, mode="w", encoding="utf-8") as f:
            f.write(html_content)

        return str(file_path)
