"""Servicio agnóstico de Inteligencia Artificial para py-manager-lite.

Proporciona integración desacoplada con múltiples proveedores de modelos de lenguaje (LLMs),
inicialmente Google Gemini y OpenRouter, permitiendo activar o desactivar la asistencia de IA
por casos de uso granulares y específicos (Fase 6):
1. Extracción y análisis de facturas / DTE SII ('invoices').
2. Clasificación contable inteligente de gastos y compras ('classify_expenses').
3. Mejora y redacción persuasiva de cotizaciones ('improve_quotes').
4. Sugerencia de descripciones técnicas de partidas ('suggest_descriptions').
5. Resumen ejecutivo de historial de clientes ('summarize_client').
6. Asistencia y diagnóstico en reportes financieros ('assist_reports').
"""

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import AI_CONFIG_FILE, PROFILE_DIR

# DECISIÓN DE ARQUITECTURA: Modelos por defecto confiables y rápidos para cada proveedor.
DEFAULT_MODELS: Dict[str, str] = {
    "gemini": "gemini-2.0-flash",
    "openrouter": "google/gemini-2.5-flash",
}

# DECISIÓN DE NEGOCIO: Granularización estricta de funcionalidades de IA.
# El usuario puede activar exclusivamente las funciones que desee delegar a la IA.
DEFAULT_FEATURES: Dict[str, bool] = {
    "invoices": True,
    "classify_expenses": False,
    "improve_quotes": False,
    "suggest_descriptions": False,
    "summarize_client": False,
    "assist_reports": False,
}

SYSTEM_INVOICE_PROMPT = """Eres un asistente experto en contabilidad tributaria chilena (SII)
y facturación internacional. Tu tarea es analizar el texto de una factura, DTE (Documento Tributario Electrónico),
o documento de cobro, y extraer con máxima precisión los datos clave en formato JSON estricto.

Reglas del SII y facturación:
1. 'document_type': 'FACTURA ELECTRONICA' (DTE 33), 'FACTURA EXENTA ELECTRONICA' (DTE 34),
   'NOTA DE CREDITO ELECTRONICA' (DTE 61), o 'FACTURA DE VENTA' / 'INVOICE'.
2. 'tipo_dte': '33', '34', '61' según corresponda, o '0' si es extranjera.
3. 'number': Folio numérico del documento.
4. 'issue_date': Fecha de emisión en formato YYYY-MM-DD.
5. 'due_date': Fecha de vencimiento en formato YYYY-MM-DD (si existe, sino null).
6. 'emisor_name': Razón social o nombre comercial de quien emite la factura (proveedor o emisor).
7. 'emisor_tax_id': RUT o Tax ID del emisor (ej: 76.123.456-7).
8. 'receiver_name': Razón social o nombre del cliente o receptor.
9. 'receiver_tax_id': RUT o Tax ID del receptor.
10. 'net_amount': Monto neto sin impuestos (número flotante o entero).
11. 'tax_amount': Monto de IVA (19% en Chile) u otros impuestos (número).
12. 'total_amount': Monto total a pagar (número).
13. 'category': Categoría sugerida entre:
    - 'Servicios Cloud & Hosting'
    - 'Licencias de Software'
    - 'Servicios Básicos (Luz, Agua, Internet)'
    - 'Insumos de Oficina'
    - 'Publicidad & Marketing'
    - 'Transporte & Logística'
    - 'Infraestructura & Equipamiento'
    - 'Servicios Profesionales & Honorarios'
14. 'description': Resumen claro y breve de los productos o servicios principales facturados.

IMPORTANTE: Responde ÚNICAMENTE con el objeto JSON válido, sin bloques de markdown adicionales ni explicaciones.
"""

SYSTEM_IMPROVE_QUOTE_PROMPT = """Eres un consultor de negocios y redactor comercial sénior experto en propuestas
y cotizaciones comerciales de servicios en Chile y Latinoamérica.
Tu tarea es perfeccionar y profesionalizar el texto de observaciones, notas y condiciones comerciales de una propuesta.
Haz que el texto sea claro, persuasivo, formal y comercialmente sólido, manteniendo intacta la intención original.
Responde ÚNICAMENTE con el texto pulido, sin introducciones ni despedidas."""

SYSTEM_SUGGEST_DESCRIPTION_PROMPT = """Eres un ingeniero de proyectos y redactor de alcances técnicos de servicios.
A partir de un concepto, servicio o partida breve, genera una descripción detallada, técnica y profesional de alcance
(SOW) adecuada para una línea de cotización comercial (incluyendo actividades clave y entregables).
Responde en 2 a 4 líneas concisas y directas, sin preámbulos."""

SYSTEM_CLASSIFY_EXPENSE_PROMPT = """Eres un contador auditor tributario experto en normativa chilena (SII)
y gestión de costos. Tu objetivo es clasificar un gasto o compra en la categoría contable más precisa a partir
del detalle de la glosa y el proveedor/emisor.
Devuelve un objeto JSON estricto con:
{
  "category": "Nombre exacto de la categoría más adecuada de la lista permitida",
  "reasoning": "Breve justificación de 1 frase"
}
Responde ÚNICAMENTE con el JSON válido."""

SYSTEM_SUMMARIZE_CLIENT_PROMPT = """Eres un director de relaciones comerciales y asesor financiero.
Analiza los datos y antecedentes históricos de un cliente (proyectos, cotizaciones, facturas y eventos)
y genera un resumen ejecutivo conciso (máximo 4 a 5 viñetas) que destaque:
- Perfil comercial y antigüedad.
- Volumen facturado y estado de cotizaciones.
- Comportamiento de pago y saldo adeudado.
- Recomendación u oportunidad comercial.
Redacta de manera ejecutiva y directa."""

SYSTEM_ASSIST_REPORT_PROMPT = """Eres un director financiero (CFO) y asesor tributario.
Analiza las métricas financieras de un período comercial (ingresos netos, egresos, IVA débito vs crédito,
margen operacional y cuentas por cobrar/pagar) y genera un diagnóstico ejecutivo conciso estructurado en 3 puntos:
1. Rendimiento y Margen Operacional: síntesis de rentabilidad y salud del flujo.
2. Posición Tributaria Estimada: situación preliminar de IVA F29 (crédito vs débito fiscal).
3. Recomendaciones de Gestión: alertas de cobranza, control de gastos o mitigación de riesgo.
Redacta en tono analítico, profesional y directo."""


class BaseAIProvider(ABC):
    """Interfaz base abstracta para proveedores de Inteligencia Artificial."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador del proveedor."""
        pass

    @abstractmethod
    def test_connection(self, api_key: str, model: str) -> Tuple[bool, str]:
        """Verifica la conectividad y validez de la API Key."""
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        api_key: str,
        model: str,
    ) -> Dict[str, Any]:
        """Genera una respuesta en formato JSON estructurado."""
        pass

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        api_key: str,
        model: str,
    ) -> str:
        """Genera una respuesta en texto continuo a partir de un prompt y contexto del sistema."""
        pass


class GeminiProvider(BaseAIProvider):
    """Proveedor para la API REST de Google Gemini."""

    @property
    def name(self) -> str:
        return "gemini"

    def test_connection(self, api_key: str, model: str) -> Tuple[bool, str]:
        if not api_key:
            return False, "La API Key de Gemini no puede estar vacía."
        target_model = model or DEFAULT_MODELS["gemini"]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": "Responde únicamente: PING_OK"}]}],
        }
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                return True, f"Conexión exitosa con Google Gemini ({target_model})."
            err_data = resp.json().get("error", {})
            err_msg = err_data.get("message", f"Código HTTP {resp.status_code}")
            return False, f"Error Gemini: {err_msg}"
        except Exception as exc:
            return False, f"Excepción al conectar con Gemini: {str(exc)}"

    def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        api_key: str,
        model: str,
    ) -> Dict[str, Any]:
        target_model = model or DEFAULT_MODELS["gemini"]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        )
        combined_text = f"{system_prompt}\n\nDOCUMENTO A PROCESAR:\n{prompt}"
        payload = {
            "contents": [{"parts": [{"text": combined_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }
        resp = requests.post(url, json=payload, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini no retornó candidatos de respuesta.")
        text_resp = candidates[0]["content"]["parts"][0]["text"]
        return _clean_and_parse_json(text_resp)

    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        api_key: str,
        model: str,
    ) -> str:
        target_model = model or DEFAULT_MODELS["gemini"]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        )
        combined_text = f"{system_prompt}\n\nSOLICITUD:\n{prompt}"
        payload = {
            "contents": [{"parts": [{"text": combined_text}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
            },
        }
        resp = requests.post(url, json=payload, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini no retornó candidatos de texto.")
        return candidates[0]["content"]["parts"][0]["text"].strip()


class OpenRouterProvider(BaseAIProvider):
    """Proveedor para la API de OpenRouter (compatible con OpenAI chat completions)."""

    @property
    def name(self) -> str:
        return "openrouter"

    def test_connection(self, api_key: str, model: str) -> Tuple[bool, str]:
        if not api_key:
            return False, "La API Key de OpenRouter no puede estar vacía."
        target_model = model or DEFAULT_MODELS["openrouter"]
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/py-manager-lite",
            "X-Title": "py-manager-lite",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": [{"role": "user", "content": "Responde únicamente: PING_OK"}],
            "max_tokens": 10,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                return True, f"Conexión exitosa con OpenRouter ({target_model})."
            err_data = resp.json().get("error", {})
            err_msg = err_data.get("message", f"Código HTTP {resp.status_code}")
            return False, f"Error OpenRouter: {err_msg}"
        except Exception as exc:
            return False, f"Excepción al conectar con OpenRouter: {str(exc)}"

    def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        api_key: str,
        model: str,
    ) -> Dict[str, Any]:
        target_model = model or DEFAULT_MODELS["openrouter"]
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/py-manager-lite",
            "X-Title": "py-manager-lite",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            # DECISIÓN DE ARQUITECTURA: max_tokens evita el error HTTP 402 en cuentas con crédito limitado.
            "max_tokens": 1500,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenRouter no retornó opciones de respuesta.")
        text_resp = choices[0]["message"]["content"]
        return _clean_and_parse_json(text_resp)

    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        api_key: str,
        model: str,
    ) -> str:
        target_model = model or DEFAULT_MODELS["openrouter"]
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/py-manager-lite",
            "X-Title": "py-manager-lite",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenRouter no retornó opciones de texto.")
        return choices[0]["message"]["content"].strip()


def _clean_and_parse_json(text: str) -> Dict[str, Any]:
    """Limpia posibles bloques markdown (```json ... ```) y parsea JSON de forma tolerante."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    start_idx = raw.find("{")
    end_idx = raw.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        raw = raw[start_idx:end_idx + 1]
    return json.loads(raw)


class AIService:
    """Servicio centralizado y desacoplado para la gestión y ejecución granular de IA."""

    def __init__(self, config_path: Path = AI_CONFIG_FILE) -> None:
        self.config_path = config_path
        self._providers: Dict[str, BaseAIProvider] = {
            "gemini": GeminiProvider(),
            "openrouter": OpenRouterProvider(),
        }

    def get_config(self) -> Dict[str, Any]:
        """Lee la configuración actual de IA o retorna valores por defecto con compatibilidad hacia atrás."""
        fallback = {
            "provider": "gemini",
            "api_key": "",
            "model": DEFAULT_MODELS["gemini"],
            "features": dict(DEFAULT_FEATURES),
        }
        if not self.config_path.exists():
            return fallback

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            provider = data.get("provider", "gemini")
            api_key = data.get("api_key", "").strip()

            # Fallback a .env o variables de entorno si la clave está vacía
            if not api_key:
                env_key = (
                    os.getenv("OPENROUTER_APIKEY")
                    or os.getenv("openrouter_apikey")
                    or os.getenv("GEMINI_API_KEY")
                )
                if not env_key and Path(".env").exists():
                    try:
                        with open(".env", "r", encoding="utf-8") as f_env:
                            for line in f_env:
                                if " = " in line and not line.strip().startswith("#"):
                                    k, v = line.strip().split(" = ", 1)
                                    if k.strip().lower() == "openrouter_apikey":
                                        env_key = v.strip()
                                        provider = "openrouter"
                                        break
                    except Exception:
                        pass
                if env_key:
                    api_key = env_key

            # Migración de configuración previa no granular (legacy quotes / reports)
            raw_feats = data.get("features", {})
            merged_feats = dict(DEFAULT_FEATURES)
            merged_feats.update(raw_feats)

            if "quotes" in raw_feats:
                legacy_q = bool(raw_feats["quotes"])
                merged_feats.setdefault("improve_quotes", legacy_q)
                merged_feats.setdefault("suggest_descriptions", legacy_q)
            if "reports" in raw_feats:
                merged_feats.setdefault("assist_reports", bool(raw_feats["reports"]))

            return {
                "provider": provider,
                "api_key": api_key,
                "model": data.get("model") or DEFAULT_MODELS.get(provider, ""),
                "features": merged_feats,
            }
        except Exception:
            return fallback

    def save_config(
        self,
        provider: str,
        api_key: str,
        model: Optional[str] = None,
        features: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        """Persiste la configuración de IA en el perfil local."""
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        prov = provider.lower().strip()
        default_model = DEFAULT_MODELS.get(prov, "")
        final_model = (model.strip() if model else "") or default_model

        curr_config = self.get_config()
        curr_features = dict(curr_config.get("features", DEFAULT_FEATURES))
        if features is not None:
            curr_features.update(features)

        data = {
            "provider": prov,
            "api_key": api_key.strip(),
            "model": final_model,
            "features": curr_features,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    def is_configured(self) -> bool:
        """Determina si la IA cuenta con proveedor y credencial válida."""
        cfg = self.get_config()
        return bool(cfg.get("api_key") and cfg["api_key"].strip())

    def is_feature_enabled(self, feature_key: str) -> bool:
        """Verifica si la IA está configurada y habilitada para un caso de uso específico."""
        if not self.is_configured():
            return False
        cfg = self.get_config()
        return bool(cfg.get("features", {}).get(feature_key, False))

    def test_connection(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Valida las credenciales contra el proveedor indicado o el configurado."""
        cfg = self.get_config()
        prov_key = (provider or cfg.get("provider", "gemini")).lower().strip()
        key = api_key if api_key is not None else cfg.get("api_key", "")
        mdl = model if model is not None else cfg.get("model", "")

        provider_impl = self._providers.get(prov_key)
        if not provider_impl:
            return False, f"Proveedor de IA no soportado: '{prov_key}'."
        return provider_impl.test_connection(api_key=key.strip(), model=mdl.strip())

    def _get_active_provider(self) -> Tuple[Optional[BaseAIProvider], str, str]:
        """Obtiene la instancia del proveedor activo, su API key y modelo configurado."""
        cfg = self.get_config()
        prov_key = cfg.get("provider", "gemini").lower().strip()
        provider_impl = self._providers.get(prov_key)
        return provider_impl, cfg.get("api_key", "").strip(), cfg.get("model", "")

    # =========================================================================
    # CASOS DE USO GRANULARES (FASE 6)
    # =========================================================================

    # 1. Facturas y DTE SII
    def extract_invoice_data(
        self,
        file_path: str,
        fallback_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extrae estructuradamente los datos de una factura usando el LLM configurado."""
        if not self.is_feature_enabled("invoices"):
            return fallback_data

        if not os.path.exists(file_path):
            return fallback_data

        text_content = self._extract_text_from_file(file_path)
        if not text_content:
            return fallback_data

        provider_impl, api_key, model = self._get_active_provider()
        if not provider_impl or not api_key:
            return fallback_data

        hint_text = ""
        if fallback_data:
            hint_text = f"\nDatos sugeridos por parser nativo: {json.dumps(fallback_data, ensure_ascii=False)}"

        prompt = f"Contenido del documento:\n{text_content[:8000]}{hint_text}"

        try:
            extracted = provider_impl.generate_json(
                prompt=prompt,
                system_prompt=SYSTEM_INVOICE_PROMPT,
                api_key=api_key,
                model=model,
            )
            return self._normalize_invoice_output(extracted, fallback_data, provider_impl.name)
        except Exception:
            # DECISIÓN DE NEGOCIO: Degradación amigable ante problemas de cuota o conectividad.
            return fallback_data

    # 2. Redacción y Mejora de Cotizaciones
    def improve_quote_text(self, text: str, context: Optional[str] = None) -> str:
        """Pule y mejora la redacción de notas, observaciones y condiciones comerciales de cotizaciones.

        Args:
            text: Texto borrador o notas escritas por el usuario.
            context: Contexto opcional (ej: nombre del cliente, tipo de proyecto).

        Returns:
            Texto formalizado y profesional o el texto original si la IA está deshabilitada o falla.
        """
        if not text or not text.strip() or not self.is_feature_enabled("improve_quotes"):
            return text

        provider_impl, api_key, model = self._get_active_provider()
        if not provider_impl or not api_key:
            return text

        prompt = f"Borrador original:\n{text.strip()}"
        if context:
            prompt += f"\n\nContexto comercial adicional:\n{context.strip()}"

        try:
            improved = provider_impl.generate_text(
                prompt=prompt,
                system_prompt=SYSTEM_IMPROVE_QUOTE_PROMPT,
                api_key=api_key,
                model=model,
            )
            return improved if improved else text
        except Exception:
            return text

    # 3. Sugerencia de Especificación Técnica de Partidas
    def suggest_item_description(self, service_or_keyword: str, business_activity: str = "") -> str:
        """Genera especificaciones técnicas de alcance (SOW) para una línea de cotización.

        Args:
            service_or_keyword: Término clave o servicio base (ej: 'Migración a la nube').
            business_activity: Giro o actividad comercial de la empresa prestadora.

        Returns:
            Descripción detallada para la partida o el término original si falla.
        """
        if not service_or_keyword or not service_or_keyword.strip():
            return service_or_keyword

        if not self.is_feature_enabled("suggest_descriptions"):
            return service_or_keyword

        provider_impl, api_key, model = self._get_active_provider()
        if not provider_impl or not api_key:
            return service_or_keyword

        prompt = f"Servicio / Partida: {service_or_keyword.strip()}"
        if business_activity:
            prompt += f"\nGiro de la empresa: {business_activity.strip()}"

        try:
            desc = provider_impl.generate_text(
                prompt=prompt,
                system_prompt=SYSTEM_SUGGEST_DESCRIPTION_PROMPT,
                api_key=api_key,
                model=model,
            )
            return desc if desc else service_or_keyword
        except Exception:
            return service_or_keyword

    # 4. Clasificación Contable de Gastos
    def classify_expense(
        self,
        description: str,
        emisor: str = "",
        allowed_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Determina la categoría tributaria y justificación contable para un gasto o compra.

        Args:
            description: Glosa o detalle del gasto.
            emisor: Nombre o RUT del emisor / proveedor.
            allowed_categories: Lista de categorías permitidas en el sistema.

        Returns:
            Diccionario con 'category' y 'reasoning'.
        """
        categories = allowed_categories or [
            "Servicios Profesionales & Honorarios",
            "Servicios Cloud & Hosting",
            "Licencias de Software",
            "Servicios Básicos (Luz, Agua, Internet)",
            "Insumos de Oficina",
            "Publicidad & Marketing",
            "Transporte & Logística",
            "Infraestructura & Equipamiento",
            "Otros Gastos Generales",
        ]
        fallback = {
            "category": categories[0],
            "reasoning": "Clasificación por defecto.",
        }

        if not self.is_feature_enabled("classify_expenses"):
            return fallback

        provider_impl, api_key, model = self._get_active_provider()
        if not provider_impl or not api_key:
            return fallback

        prompt = (
            f"Descripción o glosa: {description.strip() or 'No especificada'}\n"
            f"Emisor o Proveedor: {emisor.strip() or 'No especificado'}\n"
            f"Categorías permitidas: {json.dumps(categories, ensure_ascii=False)}"
        )

        try:
            res = provider_impl.generate_json(
                prompt=prompt,
                system_prompt=SYSTEM_CLASSIFY_EXPENSE_PROMPT,
                api_key=api_key,
                model=model,
            )
            cat = res.get("category", "")
            # Validar que pertenezca a la lista de permitidas
            matched_cat = next((c for c in categories if c.lower() == cat.lower()), None)
            return {
                "category": matched_cat or categories[0],
                "reasoning": res.get("reasoning", "Clasificado por IA."),
            }
        except Exception:
            return fallback

    # 5. Resumen Ejecutivo del Historial del Cliente
    def summarize_client_history(
        self,
        client_name: str,
        legal_name: str = "",
        tax_id: str = "",
        projects: Optional[List[Dict[str, Any]]] = None,
        quotes: Optional[List[Dict[str, Any]]] = None,
        invoices: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Genera un briefing ejecutivo del cliente integrando su actividad comercial global.

        Args:
            client_name: Nombre comercial del cliente.
            legal_name: Razón social.
            tax_id: RUT.
            projects: Lista de proyectos asociados.
            quotes: Lista de cotizaciones emitidas.
            invoices: Lista de facturas emitidas/pendientes.
            notes: Eventos o notas del timeline.

        Returns:
            Texto con el resumen ejecutivo generado por IA.
        """
        fallback_text = (
            f"• Cliente: {client_name} (RUT: {tax_id or 'Sin RUT registrado'}).\n"
            f"• Proyectos registrados: {len(projects or [])}.\n"
            f"• Cotizaciones registradas: {len(quotes or [])}.\n"
            f"• Documentos de cobro / facturas: {len(invoices or [])}."
        )

        if not self.is_feature_enabled("summarize_client"):
            return fallback_text

        provider_impl, api_key, model = self._get_active_provider()
        if not provider_impl or not api_key:
            return fallback_text

        prompt_data = {
            "cliente": {
                "nombre": client_name,
                "razon_social": legal_name,
                "rut": tax_id,
            },
            "proyectos_resumen": [
                {"name": p.get("name"), "status": p.get("status"), "budget": p.get("budget")}
                for p in (projects or [])[:10]
            ],
            "cotizaciones_resumen": [
                {"id": q.get("id"), "total": q.get("total_amount"), "status": q.get("status")}
                for q in (quotes or [])[:10]
            ],
            "facturas_resumen": [
                {"number": i.get("number"), "total": i.get("total_amount"), "balance": i.get("balance")}
                for i in (invoices or [])[:10]
            ],
            "notas_recientes": [n.get("description") for n in (notes or [])[:5]],
        }

        prompt = f"Datos históricos del cliente:\n{json.dumps(prompt_data, ensure_ascii=False, indent=2)}"

        try:
            summary = provider_impl.generate_text(
                prompt=prompt,
                system_prompt=SYSTEM_SUMMARIZE_CLIENT_PROMPT,
                api_key=api_key,
                model=model,
            )
            return summary if summary else fallback_text
        except Exception:
            return fallback_text

    # 6. Asistencia y Diagnóstico en Reportes Financieros
    def assist_report_analysis(
        self,
        period_label: str,
        metrics: Dict[str, Any],
        top_expenses: Optional[List[Dict[str, Any]]] = None,
        client_billing: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Elabora un diagnóstico analítico y tributario de un período financiero para gerencia o contador.

        Args:
            period_label: Nombre o rango del período (ej: 'Mes Actual - Septiembre 2026').
            metrics: Diccionario con total_income, total_expense, net_balance, iva_debito, iva_credito, etc.
            top_expenses: Desglose de principales egresos.
            client_billing: Desglose de ventas por cliente.

        Returns:
            Diagnóstico analítico formateado en texto estructurado.
        """
        fallback = (
            f"Diagnóstico preliminar para {period_label}:\n"
            f"- Ingresos Totales: ${metrics.get('total_income', 0):,.0f}\n"
            f"- Egresos Totales: ${metrics.get('total_expense', 0):,.0f}\n"
            f"- Balance Operacional: ${metrics.get('net_balance', 0):,.0f}\n"
            f"- IVA Estimado (Débito - Crédito): ${metrics.get('iva_debito', 0) - metrics.get('iva_credito', 0):,.0f}"
        )

        if not self.is_feature_enabled("assist_reports"):
            return fallback

        provider_impl, api_key, model = self._get_active_provider()
        if not provider_impl or not api_key:
            return fallback

        payload = {
            "periodo": period_label,
            "metricas": metrics,
            "principales_gastos": top_expenses or [],
            "facturacion_clientes": client_billing or [],
        }

        prompt = f"Métricas del período:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"

        try:
            diagnosis = provider_impl.generate_text(
                prompt=prompt,
                system_prompt=SYSTEM_ASSIST_REPORT_PROMPT,
                api_key=api_key,
                model=model,
            )
            return diagnosis if diagnosis else fallback
        except Exception:
            return fallback

    # =========================================================================
    # MÉTODOS DE SOPORTE Y PARSING DE ARCHIVOS
    # =========================================================================

    def _extract_text_from_file(self, file_path: str) -> str:
        """Extrae texto desde un PDF o XML usando pypdf o decodificación directa."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".xml":
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return ""

        if ext == ".pdf":
            try:
                import pypdf

                reader = pypdf.PdfReader(file_path)
                lines = []
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        lines.append(txt)
                if lines:
                    return "\n".join(lines)
            except Exception:
                pass

        return ""

    def _normalize_invoice_output(
        self,
        ai_data: Dict[str, Any],
        fallback_data: Optional[Dict[str, Any]],
        provider_name: str,
    ) -> Dict[str, Any]:
        """Normaliza y reconcilia los montos y campos extraídos por IA."""
        res: Dict[str, Any] = fallback_data.copy() if fallback_data else {}

        def to_num(val: Any) -> float:
            if val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            try:
                clean = re.sub(r"[^\d\.]", "", str(val))
                return float(clean) if clean else 0.0
            except ValueError:
                return 0.0

        net = to_num(ai_data.get("net_amount"))
        tax = to_num(ai_data.get("tax_amount"))
        total = to_num(ai_data.get("total_amount"))

        # Reconciliación matemática si falta alguno
        if total > 0 and net == 0.0 and tax == 0.0:
            net = round(total / 1.19, 2)
            tax = round(total - net, 2)
        elif net > 0 and total == 0.0:
            tax = round(net * 0.19, 2)
            total = round(net + tax, 2)

        res.update(
            {
                "document_type": ai_data.get("document_type") or res.get("document_type") or "FACTURA ELECTRONICA",
                "tipo_dte": str(ai_data.get("tipo_dte") or res.get("tipo_dte") or "33"),
                "number": str(ai_data.get("number") or res.get("number") or ""),
                "issue_date": ai_data.get("issue_date") or res.get("issue_date") or "",
                "due_date": ai_data.get("due_date") or res.get("due_date") or "",
                "emisor_name": ai_data.get("emisor_name") or res.get("emisor_name") or "",
                "emisor_tax_id": ai_data.get("emisor_tax_id") or res.get("emisor_tax_id") or "",
                "receiver_name": ai_data.get("receiver_name") or res.get("receiver_name") or "",
                "receiver_tax_id": ai_data.get("receiver_tax_id") or res.get("receiver_tax_id") or "",
                "net_amount": net,
                "tax_amount": tax,
                "total_amount": total,
                "category": ai_data.get("category") or res.get("category") or "Servicios Profesionales & Honorarios",
                "description": ai_data.get("description") or res.get("description") or "",
                "source_format": f"AI_{provider_name.upper()}",
                "ai_processed": True,
            }
        )
        return res
