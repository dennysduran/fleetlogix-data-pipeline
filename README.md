# 🚚 FleetLogix — Pipeline de Datos End-to-End

Proyecto integrador que simula una empresa ficticia de logística *last-mile* con 200 vehículos
operando en 5 ciudades de México. El proyecto cubre el ciclo completo de un pipeline de datos:
generación, almacenamiento, consulta optimizada, ETL a un Data Warehouse y diseño de arquitectura cloud.

## 📂 Estructura del proyecto

| Avance | Contenido | Stack |
|---|---|---|
| [`avance1/`](./avance1) | Generación de 500K+ registros sintéticos con integridad referencial | Python, Faker, PostgreSQL |
| [`avance2/`](./avance2) | 12 queries SQL avanzadas (CTEs, window functions) + optimización con índices | PostgreSQL, DBeaver |
| [`avance3/`](./avance3) | Esquema estrella + pipeline ETL completo a Snowflake | Python, Snowflake, sqlalchemy |
| [`avance4/`](./avance4) | Arquitectura AWS documentada (S3, Lambda, RDS) | AWS |

## 🗂️ Modelo de datos
6 tablas relacionadas: `vehicles`, `drivers`, `routes`, `trips`, `deliveries`, `maintenance`

## 🛠️ Stack técnico completo
`Python` `pandas` `numpy` `Faker` `sqlalchemy` `psycopg2` `PostgreSQL` `Snowflake` `AWS` `DBeaver`

## 📌 Highlights técnicos
- 505,797 registros sintéticos generados con integridad referencial completa
- Pipeline ETL con manejo de errores: timestamps, batch inserts, encoding de caracteres especiales
- Esquema estrella (6 dimensiones + 1 fact table) en Snowflake
- Optimización de queries con `EXPLAIN ANALYZE` antes/después de indexar
- Arquitectura AWS documentada para escalar el pipeline a producción

> Cada carpeta de avance incluye su propio README con el detalle técnico de esa etapa.
