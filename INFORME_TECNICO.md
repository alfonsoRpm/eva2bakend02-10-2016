# Informe técnico: arriendo de maquinaria de construcción

## 1. Objetivo

La API REST implementa el Proyecto 6 con dos perfiles: Empresa Constructora y Ejecutivo de Arriendos. Permite consultar y administrar maquinaria, solicitar períodos de arriendo, confirmar contratos y controlar las unidades de la flota.

## 2. Arquitectura

- `config/settings.py`: PostgreSQL, JWT, filtros, OpenAPI y datos visibles del alumno.
- `accounts/`: usuario con roles, registro, emisión/refresco de tokens y permisos.
- `inventory/models.py`: categorías, maquinaria, carro persistente y contratos con estados.
- `inventory/services.py`: reglas de fechas, disponibilidad y movimientos transaccionales de flota.
- `inventory/views.py`: catálogo, carro, checkout, contratos propios y gestión de estados.
- `inventory/tests.py`: pruebas de roles, períodos, montos, inventario y documentación.

La configuración de aplicación y pruebas usa PostgreSQL. No se configura SQLite.

## 3. Modelos y cálculo

`Machinery` mantiene tarifa diaria, garantía fija, unidades totales y unidades disponibles, vinculada por Foreign Key a `Category`. `Cart` mantiene una relación OneToOne con el usuario; cada `CartItem` requiere cantidad, fecha de inicio y fecha de fin.

El costo se calcula por línea como tarifa diaria por días por cantidad, más garantía fija por unidad. El contrato conserva una copia de tarifa, garantía, fechas e identidad del equipo para preservar el acuerdo aunque cambie el catálogo.

Los estados permitidos son `PENDIENTE`, `PAGADO`, `ENTREGADO`, `COMPLETADO` y `CANCELADO`.

## 4. Disponibilidad y transacciones

Agregar al carro no reserva ni descuenta unidades. Checkout verifica el rango contra contratos pagados/entregados que se solapen y crea el contrato en estado `PENDIENTE`; si el rango no tiene unidades libres, se rechaza.

Al cambiar a `PAGADO`, el servicio vuelve a comprobar el período y las unidades disponibles dentro de `transaction.atomic()`, bloquea las filas de maquinaria y descuenta mediante una actualización condicional. Si una línea falla, toda la transacción se revierte. El estado `COMPLETADO` representa la devolución y repone las unidades. Cancelar un contrato pagado o entregado también las repone; cancelar uno pendiente no altera el inventario.

## 5. Autenticación y permisos

Los endpoints `/api/auth/register/`, `/api/auth/token/` y `/api/auth/token/refresh/` entregan autenticación JWT. El claim `role` expone `Empresa Constructora` o `Ejecutivo de Arriendos`.

El catálogo GET es público. Carro, checkout y consulta de contratos requieren una Empresa Constructora autenticada. CRUD de maquinaria y cambio de estado requieren Ejecutivo de Arriendos. El panel web de administración permite buscar equipos por nombre, marca, SKU o categoría, editar el catálogo y administrar contratos.

## 6. Endpoints

| Método | Ruta | Acceso |
| --- | --- | --- |
| GET | `/api/maquinarias/` | Público |
| POST, PUT, PATCH, DELETE | `/api/maquinarias/` y detalle | Ejecutivo de Arriendos |
| PATCH | `/api/maquinarias/{id}/agregar-stock/` | Personal (`is_staff`) |
| PATCH | `/api/maquinarias/{id}/retirar-stock/` | Personal (`is_staff`); solo unidades disponibles |
| GET, POST, DELETE | `/api/carro-arriendo/` | Empresa Constructora |
| POST | `/api/contratos/checkout/` | Empresa Constructora |
| GET | `/api/mis-contratos/` | Empresa Constructora |
| PATCH | `/api/contratos/{id}/estado/` | Ejecutivo de Arriendos |

El catálogo permite filtrar por categoría (`category`), marca, SKU y rango de tarifa (`tarifa_min`, `tarifa_max`), además de búsqueda textual y ordenamiento.

El retiro de stock bloquea la maquinaria dentro de una transacción y reduce las unidades totales y disponibles; no permite retirar unidades comprometidas en contratos.

## 7. OpenAPI y datos del alumno

Swagger UI funciona en `/api/docs/`; el esquema está disponible en `/api/schema/`. La página raíz incluye placeholders configurables para Nombre Completo, Sección y Año mediante variables de entorno.

## 8. Ejecución y pruebas

Configura `.env`, levanta PostgreSQL con `podman compose up -d db`, aplica `python manage.py migrate` y ejecuta `python manage.py runserver`. Para validar usa `python manage.py test` con PostgreSQL activo.
