# 02. Modelo de dominio

## Entidades principales

### Company

Representa la empresa o actividad principal del usuario.

Campos conceptuales:

- id
- legal_name
- trade_name
- tax_id
- business_activity
- address
- city
- country
- phone
- email
- website
- logo_path
- bank_information
- created_at
- updated_at

La aplicación está pensada inicialmente para una sola empresa activa.

---

### BusinessCanvas

Representa el Business Model Canvas de la empresa.

Campos:

- id
- company_id
- key_partners
- key_activities
- key_resources
- value_propositions
- customer_relationships
- channels
- customer_segments
- cost_structure
- revenue_streams
- updated_at

No pertenece a un proyecto específico.

---

### Client

Campos sugeridos:

- id
- name
- legal_name
- tax_id
- business_activity
- address
- contact_name
- email
- phone
- notes
- active
- created_at
- updated_at

---

### ClientEvent

Permite llevar un timeline del cliente.

Campos:

- id
- client_id
- date
- event_type
- description
- quote_id nullable
- purchase_order_id nullable
- project_id nullable
- invoice_id nullable
- created_at

Tipos iniciales sugeridos:

- NOTE
- CALL
- EMAIL
- MEETING
- QUOTE_SENT
- QUOTE_ACCEPTED
- PURCHASE_ORDER
- PROJECT
- INVOICE
- PAYMENT
- OTHER

---

### Quote

Campos:

- id
- number
- client_id
- issue_date
- expiration_date
- status
- subtotal
- tax_amount
- total_amount
- notes
- terms
- created_at
- updated_at

Estados iniciales:

- DRAFT
- SENT
- NEGOTIATION
- ACCEPTED
- REJECTED
- EXPIRED

---

### QuoteItem

Campos:

- id
- quote_id
- description
- quantity
- unit
- unit_price
- subtotal
- position

Los valores deben quedar congelados en la cotización y no depender de un catálogo externo futuro.

---

### PurchaseOrder

Campos:

- id
- quote_id nullable
- client_id
- number
- issue_date
- amount
- status
- document_path
- notes
- created_at

Debe permitirse que una cotización pueda eventualmente relacionarse con más de una orden de compra.

---

### Project

Campos:

- id
- client_id
- quote_id nullable
- purchase_order_id nullable
- name
- description
- start_date
- estimated_end_date
- actual_end_date nullable
- status
- progress
- notes
- created_at
- updated_at

Estados iniciales:

- PLANNED
- ACTIVE
- PAUSED
- COMPLETED
- CANCELLED

---

### ProjectEvent

Campos:

- id
- project_id
- date
- event_type
- description
- created_at

Su objetivo es documentar la ejecución del trabajo.

---

### Invoice

Representa una factura existente, emitida o recibida externamente.

Campos:

- id
- type
- client_id nullable
- project_id nullable
- purchase_order_id nullable
- number
- issue_date
- due_date nullable
- issuer_tax_id
- issuer_name
- receiver_tax_id
- receiver_name
- net_amount
- tax_amount
- total_amount
- category nullable
- document_path nullable
- notes
- created_at

Tipos:

- ISSUED
- RECEIVED

La factura no se genera desde la aplicación.

---

### Payment

Representa un pago declarado por el usuario.

Campos:

- id
- invoice_id
- payment_date
- amount
- payment_method nullable
- reference nullable
- evidence_path nullable
- notes
- created_at

El pago puede existir sin evidencia adjunta.

El estado de pago de una factura debe derivarse de la suma de pagos:

- PENDING
- PARTIAL
- PAID

Puede mostrarse como OVERDUE cuando la fecha de vencimiento ya pasó y existe saldo pendiente.

---

## Relaciones principales

```text
Company
  └── BusinessCanvas

Client
  ├── ClientEvent
  ├── Quote
  │    └── QuoteItem
  ├── PurchaseOrder
  ├── Project
  │    └── ProjectEvent
  └── Invoice (ISSUED)

Invoice
  └── Payment
```
