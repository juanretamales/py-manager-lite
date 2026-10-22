# py-manager-lite 🚀

> **Prueba de Concepto (PoC) Educativa y de Estudio sobre Python + Flet**  
> *Gestión liviana de ciclo comercial, proyectos, finanzas y respaldos para profesionales independientes.*

---

## ⚠️ AVISO LEGAL Y DESCARGO DE RESPONSABILIDAD (DISCLAIMER)

> ### 🛑 PROYECTO EXCLUSIVAMENTE PARA ESTUDIO - PROHIBIDO USO COMERCIAL
>
> Este repositorio es un proyecto de **código abierto (Open Source)** desarrollado exclusivamente con fines **académicos, educativos, de investigación y estudio técnico** de la tecnología **Python + Flet** en entornos de escritorio.
>
> 1. **No para uso comercial:** Este software **NO** está diseñado, certificado ni destinado para uso comercial, productivo, contable o tributario formal en empresas o negocios reales.
> 2. **Sin garantías:** El software se suministra **"TAL CUAL" (*AS IS*)**, sin garantías de ningún tipo, explícitas o implícitas, incluyendo, sin limitación, garantías de comerciabilidad, idoneidad para un fin determinado o ausencia de errores.
> 3. **Exención total de responsabilidad:** El autor y los colaboradores **no asumen responsabilidad alguna** por ninguna pérdida de datos, daño a sistemas, discrepancias en cálculos contables o tributarios (SII o internacional), fallas de sincronización local o remota, pérdidas económicas, sanciones fiscales, lucro cesante o cualquier daño directo, indirecto, incidental o consecuencial que pudiera derivarse de la instalación, ejecución o uso de este software.
>
> **Cualquier persona que ejecute o modifique este código lo hace bajo su exclusiva cuenta, riesgo y responsabilidad.**

---

## 📌 Estado del Proyecto: PoC Cumplida y Validada ✅

La **Prueba de Concepto (PoC)** original ha sido completada con éxito. Se validó la viabilidad técnica y experiencia de desarrollo de una aplicación de escritorio desacoplada utilizando **Python + Flet**, cubriendo:

- ✅ **Fase 1 (MVP Base):** Arquitectura desacoplada (*Views Flet* $\to$ *Services* $\to$ *Repositories* $\to$ *Models / DB*), ciclo comercial y Canvas.
- ✅ **Fase 2 (Gestión Documental y Soft-Delete):** Asociación de archivos PDF/XML a facturas, comprobantes de pago y recuperación de cotizaciones eliminadas.
- ✅ **Fase 3 (Trazabilidad y KPIs Ejecutivos):** Centro de mando con semáforo de vencimientos, auditoría de documentos faltantes y bitácora unificada.
- ✅ **Fase 4 (Exportación Contable y Formato Monetario):** Generador de Libros de Compras/Ventas SII en CSV, reportes HTML imprimibles y selector global de divisa (CLP, UF, USD, EUR).
- ✅ **Fase 5 (Cloud Opcional y Vault Criptográfico):** Sincronización Push/Pull con Turso/libSQL cloud vía HTTPS, medición de latencia y almacenamiento cifrado de credenciales con **AES-256-GCM** y salt **PBKDF2**.
- ✅ **Fase 6 (Inteligencia Artificial Agnóstica y Granular):** Asistencia opcional desacoplada del proveedor (Google Gemini y OpenRouter) con 6 permisos granulares independientes.

---

## 🧭 Flujo Comercial y Alcance Funcional

Permite simular y estudiar el flujo operativo completo de un profesional o agencia:

```text
Cliente ──► Cotización ──► Aceptación / OC ──► Proyecto ──► Factura Emitida ──► Cobro ──► Evidencia
                                                                   ▲
Factura Recibida (Gasto) ──────────────────────────────────────────┘
```

### Funcionalidades Implementadas

1. **Dashboard & KPIs:** Tasas de cobro/pago, alertas de vencimiento próximas y auditoría de documentos tributarios faltantes.
2. **Empresa & Business Model Canvas:** Configuración de razón social, RUT y matriz visual interactiva del Canvas.
3. **Gestión de Clientes:** Ficha técnica, estados de relación, timeline de interacciones y resumen ejecutivo asistido por IA.
4. **Cotizaciones:** Generador dinámico de partidas, cálculo de IVA, sugerencia técnica de alcances (SOW) y redacción comercial con IA.
5. **Órdenes de Compra y Proyectos:** Conversión directa a proyecto, control de presupuesto, márgenes y vinculación documental.
6. **Finanzas & DTE:** Pestañas para Facturas Emitidas (Ventas), Recibidas (Gastos) y Órdenes de Compra; registro de pagos parciales, notas de crédito SII y extracción multimodal asistida por IA.
7. **Reportes & Exportaciones:** Libros de compras y ventas para contador en CSV delimitado (`utf-8-sig`), reportes imprimibles y diagnóstico financiero de período con IA.
8. **Configuración & Respaldos:**
   - Selector de moneda del sistema (CLP con separador de miles con punto, UF con coma decimal, USD, etc.).
   - Vault de seguridad con contraseña maestra y PIN rápido protegidos por PBKDF2 (100.000 iteraciones).
   - Exportación binaria atómica `.db` (Turso), volcado `.sql` y paquetes comprimidos `.zip` con respaldos preventivos automáticos.
   - Conexión y sincronización remota con Turso Cloud vía API HTTPS (`libsql-client`).
   - Módulo de IA agnóstico con switches granulares independientes para activar o desactivar cada uso.

---

## 🛠️ Stack Tecnológico

- **Lenguaje:** Python 3.10+
- **Interfaz Gráfica (GUI):** [Flet](https://flet.dev/) (Flutter sobre Python)
- **Persistencia & ORM:** SQLAlchemy 2.0 + SQLite / Turso libSQL
- **Criptografía:** `cryptography` (PBKDF2 HMAC-SHA256, AES-256-GCM)
- **Procesamiento Documental:** `pypdf` (extracción y lectura nativa de DTE SII)
- **Conectividad Cloud & LLMs:** `libsql-client`, `requests` (Google Gemini REST & OpenRouter API)
- **Calidad de Código:** `flake8` (PEP 8 $\le$ 120 caracteres, tipado estricto PEP 560/484)

---

## 💻 Instalación y Ejecución

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/py-manager-lite.git
cd py-manager-lite
```

### 2. Crear y Activar Entorno Virtual

En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependencias

```powershell
pip install -r requirements.txt
```

### 4. Ejecutar la Aplicación

```powershell
python run.py
```

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una suite completa de **71 pruebas unitarias** que validan la lógica de negocio, cálculos de IVA, soft-delete, criptografía, respaldos y el servicio de IA:

```powershell
python -m unittest discover tests
```

Para verificar el cumplimiento del estándar de estilo y formato PEP 8:

```powershell
flake8 app/ tests/ --max-line-length=120
```

---

## 📦 Empaquetado a Ejecutable Standalone (Windows)

El proyecto incluye el archivo de especificación [`py-manager-lite.spec`](file:///d:/ProyectoPython/py-manager-lite/py-manager-lite.spec) optimizado para compilar un binario ejecutable sin requerir Python instalado en la máquina cliente:

```powershell
pyinstaller --noconfirm py-manager-lite.spec
```

El ejecutable standalone se genera en:
```text
dist\py-manager-lite\py-manager-lite.exe
```

---

## 📚 Documentación Técnica Detallada

Para consultar las especificaciones de diseño, modelo y arquitectura:

- [01. Alcance Funcional](docs/01-scope.md)
- [02. Modelo de Dominio y Entidades](docs/02-domain-model.md)
- [03. Arquitectura del Sistema](docs/03-architecture.md)
- [04. Flujos Principales](docs/04-flows.md)
- [05. Especificación v0.1](docs/05-v0.1.md)
- [06. Hoja de Ruta (Roadmap)](docs/06-roadmap.md)
- [07. Reglas de Negocio e Impuestos](docs/07-business-rules.md)
- [08. Notas de IA y Contexto Técnico](docs/08-ai-handoff.md)
- [09. Árbol de Proyecto y Mapa de Archivos](docs/09-project-tree.md)

---

## 📄 Licencia

Este proyecto se distribuye bajo fines de estudio y experimentación académica de código abierto. **Prohibida su utilización con fines comerciales o en entornos de producción.**
