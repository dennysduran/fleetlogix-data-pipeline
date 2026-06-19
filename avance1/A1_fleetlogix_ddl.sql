-- FleetLogix - DDL PostgreSQL
-- Avance 1 - Modelo Relacional
-- public.drivers definition
-- Drop table
-- DROP TABLE public.drivers;

CREATE TABLE public.drivers (
	driver_id serial4 NOT NULL,
	employee_code varchar(20) NOT NULL,
	first_name varchar(100) NOT NULL,
	last_name varchar(100) NOT NULL,
	license_number varchar(50) NOT NULL,
	license_expiry date NULL,
	phone varchar(20) NULL,
	hire_date date NULL,
	status varchar(20) DEFAULT 'active'::character varying NULL,
	CONSTRAINT drivers_employee_code_key UNIQUE (employee_code),
	CONSTRAINT drivers_license_number_key UNIQUE (license_number),
	CONSTRAINT drivers_pkey PRIMARY KEY (driver_id)
);
CREATE INDEX idx_drivers_status_license ON public.drivers USING btree (status, license_expiry) WHERE ((status)::text = 'active'::text);


-- public.routes definition

-- Drop table

-- DROP TABLE public.routes;

CREATE TABLE public.routes (
	route_id serial4 NOT NULL,
	route_code varchar(20) NOT NULL,
	origin_city varchar(100) NOT NULL,
	destination_city varchar(100) NOT NULL,
	distance_km numeric(10, 2) NULL,
	estimated_duration_hours numeric(5, 2) NULL,
	toll_cost numeric(10, 2) DEFAULT 0 NULL,
	CONSTRAINT routes_pkey PRIMARY KEY (route_id),
	CONSTRAINT routes_route_code_key UNIQUE (route_code)
);
CREATE INDEX idx_routes_metrics ON public.routes USING btree (route_id, distance_km, destination_city);


-- public.vehicles definition

-- Drop table

-- DROP TABLE public.vehicles;

CREATE TABLE public.vehicles (
	vehicle_id serial4 NOT NULL,
	license_plate varchar(20) NOT NULL,
	vehicle_type varchar(50) NOT NULL,
	capacity_kg numeric(10, 2) NULL,
	fuel_type varchar(20) NULL,
	acquisition_date date NULL,
	status varchar(20) DEFAULT 'active'::character varying NULL,
	CONSTRAINT vehicles_license_plate_key UNIQUE (license_plate),
	CONSTRAINT vehicles_pkey PRIMARY KEY (vehicle_id)
);
CREATE INDEX idx_vehicles_status ON public.vehicles USING btree (status);


-- public.maintenance definition

-- Drop table

-- DROP TABLE public.maintenance;

CREATE TABLE public.maintenance (
	maintenance_id serial4 NOT NULL,
	vehicle_id int4 NULL,
	maintenance_date date NOT NULL,
	maintenance_type varchar(50) NOT NULL,
	description text NULL,
	"cost" numeric(10, 2) NULL,
	next_maintenance_date date NULL,
	performed_by varchar(200) NULL,
	CONSTRAINT maintenance_pkey PRIMARY KEY (maintenance_id),
	CONSTRAINT maintenance_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id)
);
CREATE INDEX idx_maintenance_vehicle_cost ON public.maintenance USING btree (vehicle_id, cost);


-- public.trips definition

-- Drop table

-- DROP TABLE public.trips;

CREATE TABLE public.trips (
	trip_id serial4 NOT NULL,
	vehicle_id int4 NULL,
	driver_id int4 NULL,
	route_id int4 NULL,
	departure_datetime timestamp NOT NULL,
	arrival_datetime timestamp NULL,
	fuel_consumed_liters numeric(10, 2) NULL,
	total_weight_kg numeric(10, 2) NULL,
	status varchar(20) DEFAULT 'in_progress'::character varying NULL,
	CONSTRAINT trips_pkey PRIMARY KEY (trip_id),
	CONSTRAINT trips_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(driver_id),
	CONSTRAINT trips_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(route_id),
	CONSTRAINT trips_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id)
);
CREATE INDEX idx_trips_composite_joins ON public.trips USING btree (vehicle_id, driver_id, route_id, departure_datetime) WHERE ((status)::text = 'completed'::text);
CREATE INDEX idx_trips_departure ON public.trips USING btree (departure_datetime);


-- public.deliveries definition

-- Drop table

-- DROP TABLE public.deliveries;

CREATE TABLE public.deliveries (
	delivery_id serial4 NOT NULL,
	trip_id int4 NULL,
	tracking_number varchar(50) NOT NULL,
	customer_name varchar(200) NOT NULL,
	delivery_address text NOT NULL,
	package_weight_kg numeric(10, 2) NULL,
	scheduled_datetime timestamp NULL,
	delivered_datetime timestamp NULL,
	delivery_status varchar(20) DEFAULT 'pending'::character varying NULL,
	recipient_signature bool DEFAULT false NULL,
	CONSTRAINT deliveries_pkey PRIMARY KEY (delivery_id),
	CONSTRAINT deliveries_tracking_number_key UNIQUE (tracking_number),
	CONSTRAINT deliveries_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES public.trips(trip_id)
);
CREATE INDEX idx_deliveries_scheduled_datetime ON public.deliveries USING btree (scheduled_datetime, delivery_status) WHERE ((delivery_status)::text = 'delivered'::text);
CREATE INDEX idx_deliveries_status ON public.deliveries USING btree (delivery_status);
