# 04. Flujos principales

## Flujo comercial

```text
Cliente
  ↓
Cotización
  ↓
Enviada
  ↓
Negociación
  ↓
Aceptada / Rechazada
```

## Flujo de trabajo aceptado

```text
Cotización aceptada
  ↓
Orden de compra o confirmación
  ↓
Proyecto
  ↓
Seguimiento
  ↓
Finalización
```

Una orden de compra puede no existir en todos los casos.

## Flujo de factura emitida

```text
Proyecto / Cliente
  ↓
Factura emitida externamente
  ↓
Registro en py-manager-lite
  ↓
Pago pendiente
  ↓
Pago parcial o total
  ↓
Evidencia opcional
```

## Flujo de factura recibida

```text
Proveedor / gasto
  ↓
Factura recibida
  ↓
Registro
  ↓
Pago
  ↓
Evidencia opcional
```

## Timeline del cliente

Debe permitir ver en un solo lugar eventos como:

- reunión;
- contacto;
- envío de cotización;
- aceptación;
- recepción de OC;
- inicio de proyecto;
- factura emitida;
- pago registrado.

## Timeline del proyecto

Debe estar separado del timeline comercial del cliente.

Ejemplos:

- inicio;
- requerimiento recibido;
- desarrollo;
- QA;
- entrega;
- cambio solicitado;
- cierre.
