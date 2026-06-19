-- =====================================================
-- FLEETLOGIX — AVANCE 2: ANÁLISIS SQL Y OPTIMIZACIÓN
-- Archivo del estudiante
-- =====================================================
-- INSTRUCCIONES:
--   1. Resolvé las queries obligatorias + las que elegís (ver abajo)
--   2. Ejecutá EXPLAIN ANALYZE de cada query ANTES de crear los índices
--      → Capturá un screenshot del plan de ejecución
--   3. Ejecutá el archivo A2-03_optimization_indexes.sql (5 índices)
--   4. Repetí EXPLAIN ANALYZE de cada query DESPUÉS de los índices
--      → Capturá otro screenshot y compará los tiempos
--   5. Documentá todo en Manual_Consultas_SQL.pdf:
--      · 2-3 líneas por query: qué problema resuelve y qué métricas obtiene
--      · Los 2 screenshots de EXPLAIN ANALYZE (antes y después) por query
--
-- SELECCIÓN:
--   Obligatorias : Q1, Q2, Q3, Q4, Q5, Q9
--   Elegir 1 de  : Q6, Q7, Q8
--   Elegir 1 de  : Q10, Q11, Q12
--   Total        : 8 queries
-- =====================================================

-- =====================================================
-- QUERIES BÁSICAS (Q1–Q3) — TODAS OBLIGATORIAS
-- =====================================================


-- Query 1: Contar vehículos por tipo
-- Problema de negocio: Conocer la composición de la flota
explain ANALYZE 
select vehicle_type, count(*) as cantidad
from vehicles
group by vehicle_type 
order by cantidad desc;



-- Query 2: Listar conductores con licencia próxima a vencer
-- Problema de negocio: Prevenir problemas legales por licencias vencidas
explain analyze 
select first_name,
	   last_name,
	   license_number,
	   license_expiry 
from   drivers
where  license_expiry > (select MAX(license_expiry)from drivers ) - interval '1 year'
order by license_expiry; 



-- Query 3: Total de viajes por estado
-- Problema de negocio: Monitorear operaciones en curso
explain ANALYZE
select  status , count(*) as estado
from trips
group by status 
order by estado desc;



-- =====================================================
-- QUERIES INTERMEDIAS (Q4–Q8)
-- =====================================================

-- Query 4: Total de entregas por ciudad destino en los últimos 2 meses
-- Problema de negocio: Identificar demanda por ciudad para planificación de recursos
-- Tablas a usar: routes, trips, deliveries
explain ANALYZE
select r.destination_city, count(*) as total_entregas
from deliveries d 
join trips t 	on d.trip_id	= t.trip_id 
join routes r 	on t.route_id	= r.route_id 
where d.delivery_status = 'delivered' and d.delivered_datetime > (select MAX(delivered_datetime)from deliveries) 
																						  - interval '2 months'
group by r.destination_city; 


-- Query 5: Conductores activos con cantidad de viajes completados
-- Problema de negocio: Evaluar carga de trabajo por conductor
-- Tablas a usar: drivers, trips
explain ANALYZE
select first_name, last_name, count(*) as viajes_completados
from drivers d 
join trips t  on t.driver_id = d.driver_id 
where d.status='active'  and  t.status='completed'
group by d.first_name , d.last_name  
order by viajes_completados desc;

-- Query 6: Promedio de entregas por conductor en los últimos 6 meses
-- Problema de negocio: Medir productividad individual de conductores
-- Tablas a usar: drivers, trips, deliveries
EXPLAIN ANALYZE
select first_name, last_name, count(*) promedio_entrega
from drivers d 
join trips t		on t.driver_id 	= d.driver_id 
join deliveries 	on deliveries.trip_id  = t.trip_id 
where deliveries.delivery_status = 'delivered' and 
deliveries.delivered_datetime  > (select MAX(delivered_datetime)from deliveries) - interval '6 month'
group by d.first_name ,d.last_name 
order by promedio_entrega desc;


-- Query 7: Rutas con mayor consumo de combustible por kilómetro
-- Problema de negocio: Identificar rutas ineficientes para optimización
-- Tablas a usar: routes, trips
explain ANALYZE
select AVG(r.distance_km /t.fuel_consumed_liters)as km_por_lt , r.route_code 
from routes r 
join trips t  on t.route_id = r.route_id 
group by r.route_code 
order by km_por_lt  desc;



-- Query 8: Análisis de entregas retrasadas por día de la semana
-- Problema de negocio: Identificar patrones de retraso para mejorar planificación
-- Tablas a usar: deliveries
explain ANALYZE
select to_char(d.scheduled_datetime, 'day' ) as dia_semana, count(*) as total_pendiente
from deliveries d 
where d.delivery_status = 'pending' 
group by to_char(d.scheduled_datetime, 'day')
order by count(*)  desc;


-- ==================================================
-- QUERIES COMPLEJAS (Q9–Q12)
-- =====================================================

-- Query 9: Costo de mantenimiento por kilómetro recorrido
-- Problema de negocio: Evaluar costo-beneficio de cada tipo de vehículo
-- Técnica requerida: CTE (WITH)
-- Tablas a usar: vehicles, trips, routes, maintenance
explain ANALYZE
with km_por_vehicle as (
	select t.vehicle_id, sum (r.distance_km) as total_km
	from trips t
	join routes r on t.route_id = r.route_id 
	group by t.vehicle_id 
),
costo_por_vehiculo as (
	select vehicle_id, sum(cost) as total_costo
	from maintenance m 
	group by m.vehicle_id 
)
select v.vehicle_type,
	   SUM(c.total_costo) / sum (k.total_km) as costo_por_km
from km_por_vehicle k
join costo_por_vehiculo c on k.vehicle_id = c.vehicle_id
join vehicles v on v.vehicle_id = k.vehicle_id 
group by v.vehicle_type
order by costo_por_km desc;



-- Query 10 : Ranking de conductores por eficiencia
-- Problema de negocio: Identificar top performers para programas de incentivos
-- Técnica requerida: Window Functions (RANK)
-- Tablas a usar: drivers, trips, routes, deliveries
explain ANALYZE
with eficiencia_conductores as (
	select d.driver_id,
		   d.first_name,
		   d.last_name,
		   COUNT(*) as total_entregas,
		   COUNT(*) filter (where de.delivery_status= 'delivered') as entregas_exitosas
	from drivers d
	join trips t 		on t.driver_id = d.driver_id
	join deliveries de  on  de.trip_id = t.trip_id
	group by d.driver_id, d.first_name, d.last_name
)
select 
	first_name,
	last_name,
	entregas_exitosas * 100 / total_entregas as porcentaje_eficiencia,
	RANK() over (order by entregas_exitosas * 100 / total_entregas) as ranking
from eficiencia_conductores
order by ranking desc;



-- Query 11: Análisis de tendencia de viajes con LAG y LEAD
-- Problema de negocio: Proyectar necesidades futuras basadas en tendencias históricas
-- Técnica requerida: LAG, LEAD, promedio móvil
-- Tablas a usar: trips
explain ANALYZE	
with viajes_por_mes as(
		select
		date_trunc('month', departure_datetime ) as mes,
		count (*) as total_viajes
	from trips 
	group by date_trunc('month', departure_datetime )
	)
	select 
		mes,
		total_viajes,
		lag(total_viajes)	OVER(order by mes) as mes_anterior,
		lead(total_viajes)	OVER(order by mes) as mes_siguiente
	from viajes_por_mes 
	order by mes desc;


-- Query 12: Distribución de entregas por hora y día de la semana
-- Problema de negocio: Optimizar horarios de operación y asignación de personal
-- Técnica requerida: PIVOT con CASE WHEN
-- Tablas a usar: deliveries
	explain analyze
	select
	extract (hour from scheduled_datetime) as hora,
		sum (case when TRIM(LOWER (TO_CHAR(scheduled_datetime, 'Day'))) =  'monday' 		THEN 1 ELSE 0 end) as Lunes,
		sum (case when TRIM(LOWER (TO_CHAR(scheduled_datetime, 'Day'))) =  'tuesday' 	THEN 1 ELSE 0 end) as Martes,
		sum (case when TRIM(LOWER (TO_CHAR(scheduled_datetime, 'Day'))) =  'wednesday' 	THEN 1 ELSE 0 end) as Miercoles,
		sum (case when TRIM(LOWER (TO_CHAR(scheduled_datetime, 'Day'))) =  'thursday' 	THEN 1 ELSE 0 end) as Jueves,
		sum (case when TRIM(LOWER (TO_CHAR(scheduled_datetime, 'Day'))) =  'friday' 		THEN 1 ELSE 0 end) as Viernes,
		sum (case when TRIM(LOWER (TO_CHAR(scheduled_datetime, 'Day'))) =  'saturday' 	THEN 1 ELSE 0 end) as Sabado,
		sum (case when TRIM(LOWER (TO_CHAR(scheduled_datetime, 'Day'))) =  'sunday' 		THEN 1 ELSE 0 end) as Domingo
	from deliveries
	group by hora
	order by hora;
	

	
