# 03. Arquitectura

## Objetivo arquitectónico

Mantener el proyecto pequeño y entendible, evitando sobreingeniería.

Separación recomendada:

```text
View → Service → Repository → SQLAlchemy → Database
```

## Responsabilidades

### Views

- Componentes Flet.
- Formularios.
- Tablas.
- Navegación.
- Validaciones de presentación.
- No ejecutar SQL directamente.

### Services

- Reglas de negocio.
- Cálculos.
- Cambios de estado.
- Orquestación entre repositorios.

Ejemplos:

- QuoteService
- ProjectService
- InvoiceService
- PaymentService
- DashboardService

### Repositories

- CRUD y consultas a persistencia.
- Sin lógica visual.
- Sin dependencias de Flet.

### Models

- Entidades ORM.
- Relaciones.
- Constraints básicos.

## Persistencia inicial

### Recomendación para v0.1

SQLite mediante SQLAlchemy 2.

Razones:

- cero servidor;
- un archivo local;
- ideal para CRUD;
- fácil de respaldar;
- apropiado para escritorio;
- permite evaluar Flet sin agregar complejidad de red.

### Alternativas futuras

- PostgreSQL / Supabase.
- libSQL / Turso.
- Otra base remota.

La migración futura debe ser posible sin reescribir la UI.

## Documentos

No guardar PDFs o evidencias como BLOB inicialmente.

Estructura sugerida:

```text
data/
  py-manager.db

documents/
  quotes/
  purchase_orders/
  invoices/
    issued/
    received/
  payments/
```

La base guarda rutas relativas.

## Consideraciones de cloud

La sincronización cloud no forma parte de v0.1.

Primero se debe validar:

- Flet como framework.
- comportamiento del ejecutable.
- persistencia local.
- navegación.
- rendimiento.

Después se decidirá si la aplicación permanece local o adopta una base remota/sincronizada.
