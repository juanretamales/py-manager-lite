# 08. Instrucciones para Antigravity / Gemini

## Contexto

Este proyecto se encuentra en etapa de exploración técnica.

No asumir que todas las funcionalidades descritas deben implementarse de inmediato.

La prioridad actual es construir una **v0.1 pequeña en Flet** y usarla para evaluar el framework.

## Principios

1. Mantener el código simple.
2. Evitar sobreingeniería.
3. No agregar IA todavía.
4. No agregar Supabase todavía salvo solicitud expresa.
5. No implementar SII ni emisión de facturas.
6. Mantener separada la UI de la persistencia.
7. Usar SQLAlchemy 2 con SQLite en la primera etapa.
8. Diseñar pensando en una futura migración a PostgreSQL/Supabase, sin optimizar prematuramente.
9. No guardar documentos binarios dentro de SQLite inicialmente.
10. Mantener el dominio desacoplado de Flet.

## Arquitectura esperada

```text
app/
  core/
  db/
  models/
  repositories/
  services/
  views/
  components/
  main.py

assets/
data/
documents/
tests/
```

Esta estructura es orientativa. Puede simplificarse si mejora claridad.

## Primera iteración deseada

Construir una aplicación ejecutable que tenga:

- shell principal;
- menú lateral;
- navegación;
- pantalla Inicio;
- pantalla Mi Empresa;
- pantalla Clientes;
- pantalla Cotizaciones;
- pantalla Proyectos;
- pantalla Finanzas;
- persistencia SQLite mínima;
- formularios CRUD básicos.

El objetivo no es completar el producto, sino validar Flet.

## UX

La interfaz debe sentirse como una aplicación administrativa moderna, simple y clara.

Priorizar:

- espacios consistentes;
- formularios compactos;
- tablas legibles;
- estados visibles;
- navegación estable;
- feedback de guardado/error.

No utilizar animaciones o efectos innecesarios.

## Validación técnica solicitada

Al finalizar una iteración ejecutable, documentar:

- cómo ejecutar en desarrollo;
- cómo empaquetar;
- tamaño resultante;
- problemas conocidos;
- dependencias usadas;
- decisiones arquitectónicas relevantes.

## Restricción importante

No modificar el alcance funcional definido en estos documentos sin dejar explícito qué se propone cambiar y por qué.
