"""Pruebas unitarias para el servicio de Inteligencia Artificial (AIService).

Valida la arquitectura agnóstica a modelos (Gemini y OpenRouter),
la persistencia de credenciales y configuración granular por casos de uso (features Fase 6),
y la ejecución desacoplada de cada caso de uso:
1. Extracción de facturas ('invoices').
2. Redacción de cotizaciones ('improve_quotes').
3. Sugerencia de descripciones técnicas ('suggest_descriptions').
4. Clasificación contable de gastos ('classify_expenses').
5. Resumen ejecutivo de clientes ('summarize_client').
6. Asistencia en reportes financieros ('assist_reports').
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.ai_service import AIService, DEFAULT_MODELS, _clean_and_parse_json


class TestAIService(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "ai_config.json"
        self.ai_service = AIService(config_path=self.config_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_configuration(self) -> None:
        """Verifica que sin archivo previo devuelva la configuración predeterminada segura."""
        cfg = self.ai_service.get_config()
        self.assertEqual(cfg["provider"], "gemini")
        self.assertEqual(cfg["api_key"], "")
        self.assertEqual(cfg["model"], DEFAULT_MODELS["gemini"])
        self.assertTrue(cfg["features"]["invoices"])
        self.assertFalse(cfg["features"]["classify_expenses"])
        self.assertFalse(cfg["features"]["improve_quotes"])
        self.assertFalse(cfg["features"]["suggest_descriptions"])
        self.assertFalse(cfg["features"]["summarize_client"])
        self.assertFalse(cfg["features"]["assist_reports"])
        self.assertFalse(self.ai_service.is_configured())
        self.assertFalse(self.ai_service.is_feature_enabled("invoices"))

    def test_save_and_read_granular_configuration(self) -> None:
        """Verifica el guardado y recuperación de configuración y selección granular de features."""
        saved = self.ai_service.save_config(
            provider="openrouter",
            api_key="sk-or-test-key-12345",
            model="google/gemini-2.5-flash",
            features={
                "invoices": True,
                "classify_expenses": True,
                "improve_quotes": True,
                "suggest_descriptions": False,
                "summarize_client": True,
                "assist_reports": False,
            },
        )
        self.assertEqual(saved["provider"], "openrouter")
        self.assertEqual(saved["api_key"], "sk-or-test-key-12345")
        self.assertTrue(self.ai_service.is_configured())
        self.assertTrue(self.ai_service.is_feature_enabled("invoices"))
        self.assertTrue(self.ai_service.is_feature_enabled("classify_expenses"))
        self.assertTrue(self.ai_service.is_feature_enabled("improve_quotes"))
        self.assertFalse(self.ai_service.is_feature_enabled("suggest_descriptions"))
        self.assertTrue(self.ai_service.is_feature_enabled("summarize_client"))
        self.assertFalse(self.ai_service.is_feature_enabled("assist_reports"))

    def test_clean_and_parse_json_markdown(self) -> None:
        """Verifica la decodificación de respuestas de LLM con bloques ```json."""
        raw_markdown = '```json\n{"number": "1234", "total_amount": 119000}\n```'
        parsed = _clean_and_parse_json(raw_markdown)
        self.assertEqual(parsed["number"], "1234")
        self.assertEqual(parsed["total_amount"], 119000)

        # JSON con texto circundante
        noisy = 'Aquí está el resultado:\n{"status": "ok"}\nEspero te sirva.'
        parsed_noisy = _clean_and_parse_json(noisy)
        self.assertEqual(parsed_noisy["status"], "ok")

    @patch("requests.post")
    def test_test_connection_gemini_success(self, mock_post: MagicMock) -> None:
        """Verifica la validación de conexión exitosa con Gemini."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, msg = self.ai_service.test_connection(
            provider="gemini",
            api_key="AIzaSyValidKey",
            model="gemini-2.0-flash",
        )
        self.assertTrue(ok)
        self.assertIn("Conexión exitosa", msg)

    @patch("requests.post")
    def test_test_connection_gemini_failure(self, mock_post: MagicMock) -> None:
        """Verifica el manejo de error en API Key inválida para Gemini."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": {"message": "API key not valid"}}
        mock_post.return_value = mock_resp

        ok, msg = self.ai_service.test_connection(
            provider="gemini",
            api_key="AIzaSyInvalidKey",
        )
        self.assertFalse(ok)
        self.assertIn("API key not valid", msg)

    @patch("requests.post")
    def test_test_connection_openrouter_success(self, mock_post: MagicMock) -> None:
        """Verifica la validación de conexión exitosa con OpenRouter."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, msg = self.ai_service.test_connection(
            provider="openrouter",
            api_key="sk-or-valid-key",
            model="google/gemini-2.5-flash",
        )
        self.assertTrue(ok)
        self.assertIn("Conexión exitosa", msg)

    @patch("requests.post")
    def test_extract_invoice_data_with_ai(self, mock_post: MagicMock) -> None:
        """Verifica la extracción y normalización de factura usando el LLM."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            model="gemini-2.0-flash",
            features={"invoices": True},
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "document_type": "FACTURA ELECTRONICA",
                                    "tipo_dte": "33",
                                    "number": "54321",
                                    "issue_date": "2026-03-20",
                                    "due_date": "2026-04-20",
                                    "emisor_name": "Servicios Digitales SpA",
                                    "emisor_tax_id": "76.555.444-3",
                                    "receiver_name": "Mi Empresa SpA",
                                    "receiver_tax_id": "77.111.222-3",
                                    "net_amount": 500000,
                                    "tax_amount": 95000,
                                    "total_amount": 595000,
                                    "category": "Licencias de Software",
                                    "description": "Suscripción anual a plataforma cloud",
                                })
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        test_file = Path(self.temp_dir.name) / "test_dte.xml"
        test_file.write_text("<DTE><Folio>54321</Folio></DTE>", encoding="utf-8")

        result = self.ai_service.extract_invoice_data(str(test_file))
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], "54321")
        self.assertEqual(result["net_amount"], 500000.0)
        self.assertEqual(result["tax_amount"], 95000.0)
        self.assertEqual(result["total_amount"], 595000.0)
        self.assertEqual(result["emisor_name"], "Servicios Digitales SpA")
        self.assertEqual(result["category"], "Licencias de Software")
        self.assertTrue(result["ai_processed"])
        self.assertEqual(result["source_format"], "AI_GEMINI")

    def test_extract_invoice_disabled_returns_fallback(self) -> None:
        """Verifica que si la feature de facturas está desactivada se retorna el fallback nativo."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"invoices": False},
        )
        fallback = {"number": "999", "total_amount": 1000}
        res = self.ai_service.extract_invoice_data("dummy_path.pdf", fallback_data=fallback)
        self.assertEqual(res, fallback)

    @patch("requests.post")
    def test_improve_quote_text_enabled(self, mock_post: MagicMock) -> None:
        """Verifica la mejora de redacción comercial de cotizaciones."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"improve_quotes": True},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "El pago se efectuará contra entrega conforme en un plazo de 30 días hábiles."}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        draft = "pago a 30 dias cuando entregemos"
        res = self.ai_service.improve_quote_text(draft)
        self.assertEqual(res, "El pago se efectuará contra entrega conforme en un plazo de 30 días hábiles.")

    def test_improve_quote_text_disabled(self) -> None:
        """Verifica que si improve_quotes está desactivado devuelve el borrador sin tocar."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"improve_quotes": False},
        )
        draft = "pago a 30 dias"
        res = self.ai_service.improve_quote_text(draft)
        self.assertEqual(res, draft)

    @patch("requests.post")
    def test_suggest_item_description_enabled(self, mock_post: MagicMock) -> None:
        """Verifica la generación de alcance técnico para una partida de cotización."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"suggest_descriptions": True},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "Auditoría de seguridad perimetral, escaneo de vulnerabilidades OWASP "
                                "y entrega de informe de remediación ejecutiva."
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = self.ai_service.suggest_item_description("Auditoría de seguridad")
        self.assertIn("Auditoría de seguridad perimetral", res)

    @patch("requests.post")
    def test_classify_expense_enabled(self, mock_post: MagicMock) -> None:
        """Verifica la clasificación contable de un gasto o compra con IA."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"classify_expenses": True},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "category": "Servicios Cloud & Hosting",
                                    "reasoning": "Corresponde a computación en la nube AWS.",
                                })
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = self.ai_service.classify_expense(description="AWS Cloud EC2", emisor="Amazon Web Services")
        self.assertEqual(res["category"], "Servicios Cloud & Hosting")
        self.assertIn("computación en la nube", res["reasoning"])

    def test_classify_expense_disabled(self) -> None:
        """Verifica el fallback por defecto si classify_expenses está apagado."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"classify_expenses": False},
        )
        res = self.ai_service.classify_expense(description="Compra toner")
        self.assertIn("category", res)
        self.assertIn("reasoning", res)

    @patch("requests.post")
    def test_summarize_client_history_enabled(self, mock_post: MagicMock) -> None:
        """Verifica la síntesis ejecutiva del perfil comercial de un cliente."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"summarize_client": True},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "• Cliente estratégico con 3 proyectos concluidos.\n"
                                "• Facturación acumulada de $15.000.000 sin morosidad.\n"
                                "• Alta propensión a contratación de soporte continuo."
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        summary = self.ai_service.summarize_client_history(
            client_name="Banco Regional",
            tax_id="76.111.222-3",
        )
        self.assertIn("Cliente estratégico", summary)

    @patch("requests.post")
    def test_assist_report_analysis_enabled(self, mock_post: MagicMock) -> None:
        """Verifica la generación del diagnóstico analítico y tributario en reportes."""
        self.ai_service.save_config(
            provider="gemini",
            api_key="valid-key",
            features={"assist_reports": True},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "1. Rendimiento: Margen operacional saludable del 45%.\n"
                                "2. Posición Tributaria: Saldo a favor de crédito fiscal IVA.\n"
                                "3. Recomendaciones: Acelerar cobro de facturas por vencer."
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        diagnosis = self.ai_service.assist_report_analysis(
            period_label="Septiembre 2026",
            metrics={"total_income": 1000000, "total_expense": 550000, "net_balance": 450000},
        )
        self.assertIn("Margen operacional", diagnosis)

    @patch("requests.post")
    def test_openrouter_text_generation(self, mock_post: MagicMock) -> None:
        """Verifica la generación de texto a través del provider OpenRouter."""
        self.ai_service.save_config(
            provider="openrouter",
            api_key="sk-or-valid-key",
            model="google/gemini-2.5-flash",
            features={"improve_quotes": True},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Propuesta formal pulida por OpenRouter."
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = self.ai_service.improve_quote_text("borrador de prueba")
        self.assertEqual(res, "Propuesta formal pulida por OpenRouter.")


if __name__ == "__main__":
    unittest.main()
