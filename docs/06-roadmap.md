# 06. Roadmap

## Fase 0 - Descubrimiento / PoC (Completada ✅)

Objetivo: decidir si Flet es adecuado.

- [x] navegación reactiva y sidebar colapsable;
- [x] layout responsivo y tarjetas temáticas;
- [x] formularios reactivos con validaciones en caliente;
- [x] tablas con DataTables y DataRows nativas;
- [x] SQLite / Turso local desacoplado (SQLAlchemy 2.x);
- [x] empaquetado y preparación PyInstaller / Flet;
- [x] medición de rendimiento y arranque en frío.

## Fase 1 - Núcleo comercial (Completada ✅)

- [x] **empresa**: perfil corporativo completo y Business Model Canvas interactivo (9 bloques);
- [x] **clientes**: CRUD integral, validación de RUT chileno (algoritmo Módulo 11), filtro activo/inactivo y buscador en tiempo real;
- [x] **cotizaciones**: constructor dinámico de partidas, desglose neto + IVA (19%) + total, duplicación rápida y papelera (soft-delete);
- [x] **estados**: pipeline comercial (`DRAFT`, `SENT`, `NEGOTIATION`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `DELETED`) y visualización semáforo (`StatusChip`);
- [x] **seguimiento básico de clientes**: ficha técnica de cliente, resumen comercial consolidado y bitácora de eventos;
- [x] **proyectos**: creación manual y conversión automática en 1 clic desde cotización aceptada, control de avance porcentual y márgenes reales.

## Fase 2 - Gestión documental y financiera simple (Completada ✅)

- [x] **órdenes de compra (OC)**: CRUD integral, vínculo directo con cotizaciones, subida de PDF original, conversión a proyecto y tab dedicado con KPIs ejecutivos;
- [x] **facturas emitidas (ventas)**: registro completo con desglose de IVA (19%), vinculación a clientes/proyectos, control de saldos y folios SII;
- [x] **facturas recibidas (gastos/proveedores)**: registro con contraparte proveedor, categorización contable y parseo automático SII / extracción IA multimodal;
- [x] **pagos y pagos parciales**: registro de abonos monetarios, cálculo en tiempo real de saldos insolutos y actualización dinámica de estado (`PAID`, `PARTIAL`, `OVERDUE`);
- [x] **evidencias**: carga y almacenamiento local seguro de comprobantes de transferencia y vouchers bancarios con visualización directa o adjunto retroactivo;
- [x] **categorías de gasto**: categorización inteligente de egresos (Servicios Cloud, Licencias SaaS, Básicos, Oficina, etc.) con filtros dedicados;
- [x] **documentos adjuntos**: resguardo centralizado de archivos originales (PDF/XML) para facturas y OCs, con apertura en visor del sistema operativo y enlace directo en tablas y modales de detalle.

## Fase 3 - Dashboard y trazabilidad (Completada ✅)

- [x] **indicadores**: métricas ejecutivas en tiempo real (cotizaciones abiertas con monto en negociación, avance global promedio de proyectos, cartera activa, saldos y tasas de conversión);
- [x] **timelines**: línea de tiempo interactiva con bitácora cronológica unificada de eventos comerciales (`ClientEvent`), hitos de proyectos (`ProjectEvent`) y pagos registrados;
- [x] **pendientes**: panel de seguimiento de cotizaciones abiertas en negociación y cuentas activas por cobrar y por pagar;
- [x] **vencimientos**: detección y categorización automática de vencimientos críticos con cálculo de días y semáforo (Vencido en rojo, Vence pronto en amarillo, Al día en verde);
- [x] **facturado vs cobrado**: tarjeta visual con desglose de facturación emitida, cobro percibido efectivo, saldo por cobrar y barra de progreso de tasa de cobro;
- [x] **recibido vs pagado**: tarjeta visual con desglose de compras/gastos de proveedores, pagos abonados, saldo por pagar y barra de progreso de tasa de pago;
- [x] **documentación faltante**: auditoría documental proactiva con contador en cabecera y modal interactivo detallado con listado de facturas sin PDF/XML, pagos sin voucher y OCs sin archivo adjunto.

## Fase 4 - Exportación (Completada)

- [x] **reportes por periodo**: selector con presets rápidos (Mes actual, Mes anterior, Año en curso, Personalizado) con 4 KPIs en tiempo real (Ventas, Compras, Estimación F29 IVA y Flujo de Caja neto);
- [x] **exportación para contador**: Libro de Ventas y Libro de Compras en formato tabular estricto compatible con SII y softwares contables;
- [x] **conciliación de cobros y pagos**: exportación cronológica de abonos, medios de pago, referencias bancarias y estado de comprobantes de pago;
- [x] **CSV / Excel / PDF print-ready**: archivos CSV con codificación `utf-8-sig` (BOM) y delimitador configurable (`;` o `,`) para apertura directa en Microsoft Excel sin problemas de tildes o eñes, e informes HTML con CSS `@media print` para imprimir directo a PDF con membrete corporativo;
- [x] **listado de documentos faltantes**: exportación CSV y reporte imprimible HTML de auditoría documental para armar la carpeta tributaria del período;
- [x] **historial de descargas**: tabla interactiva en la vista de reportes con acceso directo para abrir el archivo o abrir la carpeta contenedora en el explorador del sistema operativo.

## Fase 5 - Cloud opcional (Completada ✅)

- [x] **Turso/libSQL cloud**: integración nativa y desacoplada mediante API HTTP/HTTPS (`libsql-client`), inmune a problemas de WebSocket;
- [x] **seguridad de credenciales (Vault criptográfico)**: almacenamiento de tokens con cifrado autenticado AES-256-GCM y derivación de clave con salt PBKDF2 (100.000 iteraciones) en `profile.json`, protegiendo el acceso a la base de datos sin texto plano;
- [x] **diagnóstico en vivo y latencia**: prueba de conexión interactiva, medición de ping en milisegundos y consulta remota de tablas;
- [x] **sincronización local / remota (Push & Pull)**: replicación parametrizada por lotes desde SQLite local a Turso Cloud (Push) y descarga desde la nube hacia la base local (Pull) con respaldo preventivo automático (`safety_backups/`);
- [x] **preparación multi-dispositivo y respaldo en nube**: sincronización de esquema completo y datos comerciales.


## Fase 6 - IA opcional (Completada ✅)

Módulo agnóstico de Inteligencia Artificial (Google Gemini y OpenRouter) desacoplado de la lógica de negocio y configurable granularmente por casos de uso específicos:

- [x] **arquitectura agnóstica a modelos**: soporte multi-proveedor para Google Gemini REST y OpenRouter (OpenAI / Llama / Gemini) con parámetros optimizados de tokens y temperatura;
- [x] **gestión granular de permisos en configuración**: activación selectiva e independiente de cada funcionalidad en Ajustes con badge dinámico de estado (`X/6 usos activos`);
- [x] **extracción y análisis de facturas / DTE SII (`invoices`)**: parseo y lectura inteligente de facturas electrónicas PDF y XML con reconciliación matemática (neto/IVA/total) y normalización;
- [x] **clasificación contable de gastos (`classify_expenses`)**: categorización automática de egresos y centros de costo basada en la glosa y giro del proveedor;
- [x] **mejorar textos de cotización (`improve_quotes`)**: redacción ejecutiva y persuasiva de observaciones, condiciones de pago y notas comerciales en cotizaciones;
- [x] **sugerir descripciones técnicas (`suggest_descriptions`)**: generación de especificaciones técnicas de alcance (SOW) y entregables para partidas de cotización;
- [x] **resumir historial del cliente (`summarize_client`)**: síntesis analítica y comercial en el timeline del cliente (volumen histórico, proyectos y comportamiento de pago);
- [x] **asistir en preparación de reportes (`assist_reports`)**: diagnóstico ejecutivo de salud financiera, balance operacional y proyección tributaria F29 (IVA débito vs crédito).
