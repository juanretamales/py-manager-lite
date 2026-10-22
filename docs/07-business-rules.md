# 07. Reglas de negocio

## Cotizaciones

- Cada cotización pertenece a un cliente.
- Una cotización tiene uno o más ítems.
- Los valores de sus ítems quedan congelados al guardar la cotización.
- Una cotización aceptada puede originar una o más órdenes de compra.
- Una cotización aceptada puede originar un proyecto.

## Órdenes de compra

- Pueden asociarse a una cotización.
- Deben permitir adjuntar el documento original.
- No todas las ventas requieren necesariamente una OC.

## Proyectos

- Pertenecen a un cliente.
- Pueden asociarse a una cotización y/o una OC.
- Tienen seguimiento propio.

## Facturas

- Son documentos existentes externamente.
- El sistema no las emite.
- Pueden ser ISSUED o RECEIVED.
- El archivo adjunto puede ser opcional, aunque debe señalarse visualmente cuando falta.

## Pagos

- Un pago pertenece a una factura.
- Una factura puede tener cero, uno o múltiples pagos.
- El total pagado es la suma de los pagos registrados.
- El saldo es `total_factura - total_pagado`.
- No usar un booleano `paid` como fuente primaria de verdad.
- La evidencia de pago es opcional.
- Un pago sin evidencia debe seguir siendo válido como registro del usuario.

## Estados de pago

- PENDING: sin pagos o saldo completo pendiente.
- PARTIAL: total pagado > 0 y saldo > 0.
- PAID: saldo <= 0.
- OVERDUE puede ser un estado visual derivado si la fecha de vencimiento pasó y existe saldo.

## Dashboard

No llamar "utilidad" a una simple diferencia entre ingresos y egresos registrados.

Usar términos como:

- flujo registrado;
- balance registrado;
- diferencia operacional simple.

La aplicación no reemplaza contabilidad profesional.
