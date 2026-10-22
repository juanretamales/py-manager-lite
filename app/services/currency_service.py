import json
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Union
from app.core.config import CURRENCY_CONFIG_FILE

logger = logging.getLogger(__name__)

# DECISIÓN DE NEGOCIO: En Chile y Latinoamérica el estándar contable es el peso con separador
# de miles de punto (.) y sin decimales en CLP. Para la UF se requiere coma decimal (,) con 2 a 4 decimales.
DEFAULT_CURRENCY_CONFIG: Dict[str, Any] = {
    "preset": "CLP",
    "code": "CLP",
    "symbol": "$",
    "symbol_position": "prefix",  # "prefix" o "suffix"
    "thousand_separator": ".",
    "decimal_separator": ",",
    "decimals": 0,
    "show_code": False,
}

CURRENCY_PRESETS: Dict[str, Dict[str, Any]] = {
    "CLP": {
        "preset": "CLP",
        "code": "CLP",
        "symbol": "$",
        "symbol_position": "prefix",
        "thousand_separator": ".",
        "decimal_separator": ",",
        "decimals": 0,
        "show_code": False,
        "label": "Chile - Peso Chileno ($ 1.250.000)",
    },
    "UF": {
        "preset": "UF",
        "code": "UF",
        "symbol": "UF",
        "symbol_position": "suffix",
        "thousand_separator": ".",
        "decimal_separator": ",",
        "decimals": 2,
        "show_code": False,
        "label": "Chile - Unidad de Fomento (12,50 UF)",
    },
    "USD": {
        "preset": "USD",
        "code": "USD",
        "symbol": "$",
        "symbol_position": "prefix",
        "thousand_separator": ",",
        "decimal_separator": ".",
        "decimals": 2,
        "show_code": False,
        "label": "Internacional - Dólar Estadounidense ($ 1,250.00)",
    },
    "EUR": {
        "preset": "EUR",
        "code": "EUR",
        "symbol": "€",
        "symbol_position": "suffix",
        "thousand_separator": ".",
        "decimal_separator": ",",
        "decimals": 2,
        "show_code": False,
        "label": "Europa - Euro (1.250,00 €)",
    },
    "CUSTOM": {
        "preset": "CUSTOM",
        "code": "CLP",
        "symbol": "$",
        "symbol_position": "prefix",
        "thousand_separator": ".",
        "decimal_separator": ",",
        "decimals": 0,
        "show_code": False,
        "label": "Personalizado",
    },
}


class CurrencyService:
    """Servicio centralizado y reactivo para la gestión y formateo de monedas a nivel de sistema."""

    _instance: Optional["CurrencyService"] = None

    def __new__(cls) -> "CurrencyService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración de moneda desde tmp/profile/currency_config.json."""
        if CURRENCY_CONFIG_FILE.exists():
            try:
                data = json.loads(CURRENCY_CONFIG_FILE.read_text(encoding="utf-8"))
                merged = dict(DEFAULT_CURRENCY_CONFIG)
                merged.update(data)
                return merged
            except Exception as ex:
                logger.error("Error al leer configuración de moneda: %s", ex)
        return dict(DEFAULT_CURRENCY_CONFIG)

    def get_config(self) -> Dict[str, Any]:
        """Retorna una copia de la configuración activa del sistema."""
        return dict(self._config)

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Actualiza y persiste la configuración global en disco."""
        self._config.update(new_config)
        try:
            CURRENCY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CURRENCY_CONFIG_FILE.write_text(
                json.dumps(self._config, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info("Configuración de moneda guardada: %s", self._config)
        except Exception as ex:
            logger.error("Error al persistir configuración de moneda: %s", ex)

    def reset_to_preset(self, preset_key: str) -> Dict[str, Any]:
        """Aplica un perfil predeterminado (CLP, UF, USD, EUR)."""
        preset = CURRENCY_PRESETS.get(preset_key, DEFAULT_CURRENCY_CONFIG)
        clean = {k: v for k, v in preset.items() if k != "label"}
        self.update_config(clean)
        return self.get_config()

    def format_amount(
        self,
        amount: Optional[Union[float, int, Decimal, str]],
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Formatea un monto numérico según las reglas de formato monetario del sistema.

        Ejemplos:
            - CLP: 1250000 -> "$ 1.250.000"
            - CLP con código: 1250000 -> "$ 1.250.000 CLP"
            - UF: 35.5 -> "35,50 UF"
            - USD: 1250.5 -> "$ 1,250.50"
            - Negativos: -45000 -> "-$ 45.000" o "-12,50 UF"
        """
        cfg = custom_config or self._config

        # 1. Parseo seguro de monto
        if amount is None or amount == "":
            val = 0.0
        else:
            try:
                val = float(amount)
            except (ValueError, TypeError):
                return str(amount)

        is_negative = val < 0
        abs_val = abs(val)

        # 2. Desglose en parte entera y decimales
        decimals_count = int(cfg.get("decimals", 0))
        thousand_sep = str(cfg.get("thousand_separator", "."))
        decimal_sep = str(cfg.get("decimal_separator", ","))

        if decimals_count > 0:
            formatted_raw = f"{abs_val:.{decimals_count}f}"
            parts = formatted_raw.split(".")
            integer_part = parts[0]
            decimal_part = parts[1] if len(parts) > 1 else "0" * decimals_count
        else:
            integer_part = str(int(round(abs_val)))
            decimal_part = ""

        # 3. Inserción de separadores de miles
        int_with_sep = ""
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                int_with_sep = thousand_sep + int_with_sep
            int_with_sep = digit + int_with_sep

        # 4. Ensamble de parte numérica
        if decimals_count > 0 and decimal_part:
            num_str = f"{int_with_sep}{decimal_sep}{decimal_part}"
        else:
            num_str = int_with_sep

        # 5. Adición de símbolo y divisa
        symbol = str(cfg.get("symbol", "$")).strip()
        pos = cfg.get("symbol_position", "prefix")
        show_code = bool(cfg.get("show_code", False))
        code = str(cfg.get("code", "CLP")).strip().upper()

        if pos == "prefix":
            core_str = f"{symbol} {num_str}" if symbol else num_str
        else:
            core_str = f"{num_str} {symbol}" if symbol else num_str

        # Agregar divisa al final si está activado y no es redundante con el símbolo
        if show_code and code and code != symbol:
            core_str = f"{core_str} {code}"

        # 6. Anteposición de signo negativo
        return f"-{core_str}" if is_negative else core_str


# Instancia singleton para acceso inmediato
_service = CurrencyService()


def format_currency(
    amount: Optional[Union[float, int, Decimal, str]],
    custom_config: Optional[Dict[str, Any]] = None,
) -> str:
    """Función de conveniencia global para formatear montos en toda la aplicación."""
    return _service.format_amount(amount, custom_config)


def get_currency_service() -> CurrencyService:
    """Retorna la instancia global del servicio de moneda."""
    return _service
