"""Pruebas unitarias para OperationProgressModal y ejecución con progreso en tiempo real."""

import unittest
from unittest.mock import MagicMock
import flet as ft

from app.components.progress_modal import OperationProgressModal, run_operation_with_progress


class TestProgressModal(unittest.TestCase):
    """Verifica el funcionamiento del modal de progreso, cálculo porcentual y registro de logs."""

    def setUp(self) -> None:
        self.mock_page = MagicMock(spec=ft.Page)
        self.mock_page.overlay = []

    def test_modal_initialization_and_open_close(self) -> None:
        modal = OperationProgressModal(
            page=self.mock_page,
            title="Prueba de Carga",
            initial_status="Comprobando...",
            initial_log="Log inicial de prueba",
        )
        self.assertEqual(modal.title_label.value, "Prueba de Carga")
        self.assertEqual(modal.hero_status.value, "Comprobando...")
        self.assertEqual(len(modal.log_lines_column.controls), 1)

        modal.open()
        self.assertIn(modal.dialog, self.mock_page.overlay)
        self.assertTrue(modal.dialog.open)

        modal.close()
        self.assertFalse(modal.dialog.open)
        self.assertIn(modal.dialog, self.mock_page.overlay)

    def test_update_progress_and_logs(self) -> None:
        modal = OperationProgressModal(
            page=self.mock_page,
            title="Progreso Test",
        )
        modal.update_progress(
            progress=0.45,
            status="Cargando para mejorar la experiencia de usuario...",
            log_message="Paso intermedio ejecutado",
        )
        self.assertEqual(modal.progress_bar.value, 0.45)
        self.assertEqual(modal.hero_status.value, "Cargando para mejorar la experiencia de usuario...")
        self.assertEqual(len(modal.log_lines_column.controls), 1)
        self.assertIn("Paso intermedio ejecutado", modal.log_lines_column.controls[0].value)

    def test_modal_complete_state(self) -> None:
        callback_called = False

        def on_close() -> None:
            nonlocal callback_called
            callback_called = True

        modal = OperationProgressModal(
            page=self.mock_page,
            title="Final Test",
        )
        modal.complete(
            final_message="¡Demostración lista!",
            final_log="Finalización correcta",
            on_close=on_close,
        )
        self.assertTrue(modal.is_completed)
        self.assertEqual(modal.progress_bar.value, 1.0)
        self.assertFalse(modal.action_button.disabled)
        self.assertFalse(modal.close_icon_button.disabled)
        self.assertFalse(modal.dialog.modal)

        # Simular clic en botón de cierre
        modal._on_action_click(MagicMock())
        self.assertTrue(callback_called)

    def test_modal_error_state(self) -> None:
        modal = OperationProgressModal(
            page=self.mock_page,
            title="Error Test",
        )
        modal.set_error("Fallo de conexión", error_details="Detalle técnico")
        self.assertTrue(modal.has_error)
        self.assertFalse(modal.action_button.disabled)
        self.assertFalse(modal.close_icon_button.disabled)
        self.assertFalse(modal.dialog.modal)
        self.assertEqual(modal.action_button.text, "Cerrar")
        self.assertIn("Fallo de conexión", modal.hero_status.value)

    def test_run_operation_with_progress_success(self) -> None:
        recorded_calls = []

        def sample_worker(progress_cb):
            progress_cb(0.3, "Comprobando...", "Paso 1")
            progress_cb(0.9, "Afinando para el perfil del usuario...", "Paso 2")
            return "RESULT_OK"

        def sample_success(res):
            recorded_calls.append(res)

        run_operation_with_progress(
            page=self.mock_page,
            title="Tarea Asíncrona",
            worker_fn=sample_worker,
            on_success=sample_success,
            auto_close_delay=0.05,
        )

        import time
        time.sleep(0.3)
        self.assertIn("RESULT_OK", recorded_calls)


if __name__ == "__main__":
    unittest.main()
