"""
Servicio nativo para lectura y extracción automática de datos desde Facturas Electrónicas y DTE del SII (Chile).
Soporta archivos PDF oficiales del SII y archivos XML (DTE estándar SII) sin dependencias externas pesadas.
"""

import os
import re
import zlib
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any


def parse_sii_document(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Analiza un documento tributario chileno (PDF o XML) y extrae sus campos principales.
    Retorna un diccionario con los datos extraídos o None si el archivo no es procesable.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xml":
        return parse_sii_xml(file_path)
    elif ext == ".pdf":
        return parse_sii_pdf(file_path)
    return None


def parse_sii_xml(file_path: str) -> Optional[Dict[str, Any]]:
    """Parsea un archivo DTE XML del SII chileno."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Handle XML namespaces if present
        def find_text(elem, tag_names):
            if elem is None:
                return None
            for child in elem.iter():
                # strip namespace
                clean_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if clean_tag in tag_names and child.text:
                    return child.text.strip()
            return None

        # Folio
        folio = find_text(root, ["Folio"])
        if not folio:
            return None

        tipo_dte = find_text(root, ["TipoDTE"]) or "33"
        fch_emis = find_text(root, ["FchEmis"]) or ""

        # Determine document type label
        doc_type_map = {
            "33": "FACTURA ELECTRONICA",
            "34": "FACTURA EXENTA ELECTRONICA",
            "61": "NOTA DE CREDITO ELECTRONICA",
            "56": "NOTA DE DEBITO ELECTRONICA",
            "52": "GUIA DE DESPACHO ELECTRONICA",
        }
        doc_type = doc_type_map.get(tipo_dte, "FACTURA ELECTRONICA")

        # Emisor & Receptor
        rut_emisor = find_text(root, ["RUTEmisor"]) or ""
        rzn_emisor = find_text(root, ["RznSoc", "RznSocEmisor"]) or ""
        rut_recep = find_text(root, ["RUTRecep"]) or ""
        rzn_recep = find_text(root, ["RznSocRecep"]) or ""

        # Amounts
        def to_float(val):
            try:
                return float(val) if val else 0.0
            except ValueError:
                return 0.0

        neto = to_float(find_text(root, ["MntNeto"]))
        iva = to_float(find_text(root, ["IVA"]))
        total = to_float(find_text(root, ["MntTotal"]))

        # Items description
        items = []
        for child in root.iter():
            clean_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if clean_tag in ["NmbItem", "DscItem"] and child.text:
                txt = child.text.strip()
                if txt and txt not in items:
                    items.append(txt)

        return {
            "document_type": doc_type,
            "tipo_dte": tipo_dte,
            "number": str(folio),
            "issue_date": fch_emis,
            "emisor_name": rzn_emisor,
            "emisor_tax_id": rut_emisor,
            "receiver_name": rzn_recep,
            "receiver_tax_id": rut_recep,
            "net_amount": neto,
            "tax_amount": iva,
            "total_amount": total,
            "description": " / ".join(items[:3]) if items else "",
            "source_format": "XML_DTE"
        }
    except Exception:
        return None


def parse_sii_pdf(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parsea de forma nativa un PDF de Factura del Servicio de Impuestos Internos (SII) de Chile.
    Utiliza pypdf para extracción de texto con respaldo de descompresión de flujos PDF nativos.
    """
    try:
        page_lines = []

        # DECISIÓN DE ARQUITECTURA: Priorizar pypdf para máxima compatibilidad con PDFs modernos
        # (PDF 1.5+, Object Streams, compresión FlateDecode). Respaldo a zlib si pypdf no está disponible.
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    for line in extracted.splitlines():
                        clean = line.strip()
                        if clean:
                            page_lines.append(clean)
        except Exception:
            page_lines = []

        # Fallback: Descompresión de flujos zlib en caso de error o ausencia de texto en capas estándar
        if not page_lines:
            with open(file_path, "rb") as f:
                data = f.read()

            pos = 0
            while True:
                s_idx = data.find(b"stream", pos)
                if s_idx == -1:
                    break
                start_data = s_idx + 6
                if data[start_data:start_data+1] == b"\r":
                    start_data += 1
                if data[start_data:start_data+1] == b"\n":
                    start_data += 1
                e_idx = data.find(b"endstream", start_data)
                if e_idx == -1:
                    break
                chunk = data[start_data:e_idx].rstrip(b"\r\n")

                try:
                    dec = zlib.decompress(chunk)
                    strings = re.findall(rb"\((.*?)\)", dec)
                    lines = []
                    for s in strings:
                        def octal_repl(m):
                            return bytes([int(m.group(1), 8)])
                        s_unescaped = re.sub(rb"\\([0-7]{3})", octal_repl, s)
                        s_unescaped = s_unescaped.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
                        text = s_unescaped.decode("latin1", errors="ignore").strip()
                        if text:
                            lines.append(text)

                    joined_upper = " ".join(lines).upper()
                    if any(k in joined_upper for k in ["FACTURA", "NOTA DE CREDITO", "R.U.T", "RUT", "S.I.I"]):
                        page_lines.extend(lines)
                except Exception:
                    pass

                pos = e_idx + 9

        if not page_lines:
            return None

        full_text = "\n".join(page_lines)

        # 1. Document Type
        doc_type = "FACTURA ELECTRONICA"
        if "NOTA DE CREDITO" in full_text.upper():
            doc_type = "NOTA DE CREDITO ELECTRONICA"
        elif "EXENTA" in full_text.upper():
            doc_type = "FACTURA EXENTA ELECTRONICA"

        # 2. Folio / Number
        # Formatos: Nº27, N° 27, N\27227, FOLIO: 27, N27
        folio = None
        folio_m = re.search(r"(?:N[º°\uFFFD\.\s\-]*|FOLIO[:\s]*)\s*(\d+)", full_text, re.IGNORECASE)
        if folio_m:
            folio = folio_m.group(1)

        # 3. Emisor info (primeras líneas en facturas chilenas)
        emisor_lines = []
        emisor_stop_words = [
            "GIRO:", "R.U.T", "PJE", "CALLE", "AV.", "AVDA", "EMAIL",
            "TELEFONO", "SEÑOR", "TIPO DE VENTA"
        ]
        for line in page_lines[:10]:
            if any(stop in line.upper() for stop in emisor_stop_words):
                break
            emisor_lines.append(line)
        emisor_name = " ".join(emisor_lines).strip()

        # 4. Receptor info (Cuadro Señor(es))
        client_name = ""
        client_rut = ""
        receiver_stop_tags = [
            "R.U.T", "GIRO", "DIRECCION", "COMUNA", "CIUDAD", "CONTACTO", "TIPO DE"
        ]
        for idx, line in enumerate(page_lines):
            line_u = line.upper()
            if any(k in line_u for k in ["SEÑOR", "SENOR", "SE\\321OR", "SE\uFFFDOR"]):
                c_parts = []
                # Captura si el nombre del cliente continúa en la misma línea
                same_line_m = re.search(r"SE[ÑN\uFFFD\\]*(?:OR|\d+)?(?:\(ES\))?\s*:?\s*(.*)", line, re.IGNORECASE)
                if same_line_m and same_line_m.group(1).strip():
                    val = same_line_m.group(1).strip()
                    if not any(tag in val.upper() for tag in receiver_stop_tags):
                        c_parts.append(val)

                for j in range(idx + 1, min(idx + 6, len(page_lines))):
                    if any(tag in page_lines[j].upper() for tag in receiver_stop_tags):
                        break
                    c_parts.append(page_lines[j])
                client_name = " ".join(c_parts).strip()

                # Buscar RUT receptor en líneas inmediatamente siguientes
                for j in range(idx + 1, min(idx + 8, len(page_lines))):
                    rut_m = re.search(r"(\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK])", page_lines[j])
                    if rut_m:
                        client_rut = re.sub(r"\s+", "", rut_m.group(1))
                        break
                break

        # 5. Emisor RUT (usualmente en el recuadro rojo junto al Folio)
        emisor_rut = ""
        rut_matches = re.findall(
            r"R\.?U\.?T\.?\s*:?\s*(\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK])",
            full_text,
            re.IGNORECASE
        )
        for r in rut_matches:
            clean = re.sub(r"\s+", "", r)
            if clean != client_rut:
                emisor_rut = clean
                break

        # 6. Issue Date
        months = {
            "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
        }
        date_m = re.search(r"(\d{1,2})\s+de\s+([a-zA-Z]+)\s+del?\s+(\d{4})", full_text, re.IGNORECASE)
        issue_date = None
        if date_m:
            d = date_m.group(1).zfill(2)
            m = months.get(date_m.group(2).lower(), "01")
            y = date_m.group(3)
            issue_date = f"{y}-{m}-{d}"
        else:
            # Check numerical date dd/mm/yyyy or dd-mm-yyyy
            num_date_m = re.search(r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})", full_text)
            if num_date_m:
                d = num_date_m.group(1).zfill(2)
                m = num_date_m.group(2).zfill(2)
                y = num_date_m.group(3)
                issue_date = f"{y}-{m}-{d}"

        # 7. Amounts
        def parse_money(label_pat: str) -> float:
            m = re.search(label_pat + r"\s*[\$\s]*([\d\.]+)", full_text, re.IGNORECASE)
            if m:
                clean = m.group(1).replace(".", "")
                try:
                    return float(clean)
                except ValueError:
                    pass
            return 0.0

        net_amount = parse_money(r"MONTO\s+NETO")
        tax_amount = parse_money(r"I\.?V\.?A\.?\s*(?:19%)?")
        total_amount = parse_money(r"\bTOTAL\b")

        # 8. Description lines
        description_lines = []
        desc_start = False
        desc_stop_words = ["FORMA DE PAGO", "TIMBRE ELECTRONICO", "MONTO NETO", "TOTAL", "CEDIBLE"]
        desc_ignored_headers = {
            "-", "1", "Crédito", "Credito", "Precio", "%Impto", "Adic.*", "%Desc.", "Cantidad"
        }
        for line in page_lines:
            if "DESCRIPCION" in line.upper() or "VALOR" in line.upper():
                desc_start = True
                continue
            if desc_start:
                if any(stop in line.upper() for stop in desc_stop_words):
                    break
                # Ignore table headers and pure numbers
                if line not in desc_ignored_headers and not re.match(r"^[\d\.]+$", line):
                    description_lines.append(line)

        # If folio or amounts weren't found, this might not be an SII invoice
        if not folio and total_amount == 0.0:
            return None

        # DECISIÓN DE NEGOCIO (SII): Factura afecta es Tipo 33, Factura exenta es Tipo 34, Nota de Crédito es 61.
        tipo_dte = "34" if "EXENTA" in doc_type else ("61" if "CREDITO" in doc_type else "33")

        return {
            "document_type": doc_type,
            "tipo_dte": tipo_dte,
            "number": str(folio) if folio else "",
            "issue_date": issue_date or "",
            "emisor_name": emisor_name,
            "emisor_tax_id": emisor_rut,
            "receiver_name": client_name,
            "receiver_tax_id": client_rut,
            "net_amount": net_amount,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "description": " / ".join(description_lines) if description_lines else "",
            "source_format": "PDF_SII"
        }
    except Exception:
        return None
