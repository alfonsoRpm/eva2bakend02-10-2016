# API de Arriendo de Maquinaria de Construcción

Backend con Django 5.2 y Django REST Framework para el Proyecto 6. Gestiona catálogo público, usuarios con JWT, carros persistentes con fechas, contratos de arriendo y disponibilidad transaccional de flota.

## Requisitos

- Python 3.11
- PostgreSQL 16
- Docker Desktop con Docker Compose, o PostgreSQL 16 instalado localmente

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
```

Completa en `.env` la contraseña de PostgreSQL y los campos del estudiante. Abre Docker Desktop y, desde la carpeta del proyecto, levanta PostgreSQL:

```powershell
docker compose up -d db
```

Si no usas Docker, instala PostgreSQL 16 para Windows, inicia el servicio y crea una base de datos llamada `hardware_store` desde pgAdmin. En `.env`, configura `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST=127.0.0.1`, `POSTGRES_PORT=5432` y `POSTGRES_DB=hardware_store` con los valores de tu instalación.

Luego ejecuta:

```powershell
python manage.py migrate
python manage.py runserver
```

Swagger está disponible en `http://127.0.0.1:8000/api/docs/` y el esquema OpenAPI en `/api/schema/`.

## Roles

- `Empresa Constructora`: registro público, catálogo, carro, checkout y consulta de sus contratos.
- `Ejecutivo de Arriendos`: gestión CRUD de maquinaria y actualización del estado de los contratos.
- Las cuentas con `is_staff=True` pueden entrar al panel web de administración, gestionar el catálogo y ajustar el stock disponible.

El claim `role` del JWT contiene el nombre visible del rol. El carro no reserva unidades; al crear el contrato pendiente, el checkout valida y reserva el stock de forma atómica. Pasar el contrato a `PAGADO` conserva esa reserva sin descontar dos veces. Cancelar un contrato pendiente o pagado, o completarlo después de la devolución, libera las unidades. El catálogo consulta el stock actualizado al abrirse, al volver a la pestaña y cada cinco segundos mientras está visible.

## Endpoints

| Método | Ruta | Acceso |
| --- | --- | --- |
| GET | `/api/maquinarias/` | Público; admite filtros |
| POST, PUT, PATCH, DELETE | `/api/maquinarias/` | Ejecutivo de Arriendos |
| PATCH | `/api/maquinarias/{id}/agregar-stock/` | Personal (`is_staff`) |
| PATCH | `/api/maquinarias/{id}/retirar-stock/` | Personal (`is_staff`); solo unidades disponibles |
| GET, POST, DELETE | `/api/carro-arriendo/` | Empresa Constructora |
| POST | `/api/contratos/checkout/` | Empresa Constructora |
| GET | `/api/mis-contratos/` | Empresa Constructora |
| PATCH | `/api/contratos/{id}/estado/` | Ejecutivo de Arriendos |

El `POST` del carro recibe `maquinaria`, `cantidad`, `fecha_inicio` y `fecha_fin`. La eliminación recibe `?machinery_id={id}`. El catálogo permite `category`, `tarifa_min`, `tarifa_max`, `search` y `ordering`.

## Autenticación

- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`

## Pruebas

Las pruebas usan PostgreSQL, igual que la aplicación; levanta la base configurada antes de ejecutarlas:

```powershell
python manage.py test
```

La lógica de negocio y los escenarios cubiertos se describen en [INFORME_TECNICO.md](INFORME_TECNICO.md).
