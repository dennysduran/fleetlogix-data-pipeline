"""
FleetLogix - Pipeline ETL Automático
Extrae de PostgreSQL, Transforma y Carga en Snowflake
Ejecución diaria automatizada
"""

import psycopg2
import snowflake.connector
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import schedule
import time
import json
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import os
load_dotenv('credenciales.env')


# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('etl_pipeline.log'),
        logging.StreamHandler()
    ]
)

# Configuración de conexiones
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST'),
    'database': os.getenv('POSTGRES_DB'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'port': int(os.getenv('POSTGRES_PORT'))
}

SNOWFLAKE_CONFIG = {
    'user': os.getenv('SNOWFLAKE_USER'),
    'password': os.getenv('SNOWFLAKE_PASSWORD'),
    'account': os.getenv('SNOWFLAKE_ACCOUNT'),
    'warehouse': os.getenv('SNOWFLAKE_WAREHOUSE'),
    'database': os.getenv('SNOWFLAKE_DATABASE'),
    'schema': os.getenv('SNOWFLAKE_SCHEMA')
}

class FleetLogixETL:
    def __init__(self):
        self.pg_conn = None
        self.sf_conn = None
        self.batch_id = int(datetime.now().timestamp())
        self.metrics = {
            'records_extracted': 0,
            'records_transformed': 0,
            'records_loaded': 0,
            'errors': 0
        }
    
    def connect_databases(self):
        """Establecer conexiones con PostgreSQL y Snowflake"""
        try:
            # PostgreSQL
            self.pg_conn = psycopg2.connect(**POSTGRES_CONFIG)
            logging.info(" Conectado a PostgreSQL")
            
            # Snowflake
            self.sf_conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
            logging.info(" Conectado a Snowflake")
            
            return True
        except Exception as e:
            logging.error(f" Error en conexión: {e}")
            return False
    
    def extract_daily_data(self) -> pd.DataFrame:
        """Extraer datos del día anterior de PostgreSQL"""
        logging.info(" Iniciando extracción de datos...")
        
        query = """
        SELECT
            d.delivery_id,
            d.trip_id,
            d.tracking_number,
            d.customer_name,
            d.package_weight_kg,
            d.scheduled_datetime,
            d.delivered_datetime,
            d.delivery_status,
            d.recipient_signature,
            d.is_damaged,
            t.vehicle_id,
            t.driver_id,
            t.route_id,
            t.departure_datetime,
            t.arrival_datetime,
            t.fuel_consumed_liters,
            r.distance_km,
            r.toll_cost,
            r.destination_city
        FROM deliveries d
        JOIN trips t    ON d.trip_id    = t.trip_id
        JOIN routes r   ON t.route_id   = r.route_id
        WHERE d.delivery_status = 'delivered'
        """ 
        
        try:
            df = pd.read_sql(query, self.pg_conn)
            self.metrics['records_extracted'] = len(df)
            logging.info(f" Extraídos {len(df)} registros")
            return df
        except Exception as e:
            logging.error(f" Error en extracción: {e}")
            self.metrics['errors'] += 1
            return pd.DataFrame()
    
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transformar datos para el modelo dimensional"""
        logging.info(" Iniciando transformación de datos...")
        
        try:
            # Calcular métricas
            df['delivery_time_minutes'] = (
                (pd.to_datetime(df['delivered_datetime']) - 
                 pd.to_datetime(df['scheduled_datetime'])).dt.total_seconds() / 60
            ).round(2)
            
            df['delay_minutes'] = df['delivery_time_minutes'].apply(
                lambda x: max(0, x) if x > 0 else 0
            )
            
            df['is_on_time'] = df['delay_minutes'] <= 30
            
            # Calcular entregas por hora
            df['trip_duration_hours'] = (
                (pd.to_datetime(df['arrival_datetime']) - 
                 pd.to_datetime(df['departure_datetime'])).dt.total_seconds() / 3600
            ).round(2)
            
            # Agrupar entregas por trip para calcular entregas/hora
            deliveries_per_trip = df.groupby('trip_id').size()
            df['deliveries_in_trip'] = df['trip_id'].map(deliveries_per_trip)
            df['deliveries_per_hour'] = (
                df['deliveries_in_trip'] / df['trip_duration_hours']
            ).round(2)
            
            # Eficiencia de combustible
            df['fuel_efficiency_km_per_liter'] = (
                df['distance_km'] / df['fuel_consumed_liters']
            ).round(2)
            
            # Costo estimado por entrega
            df['cost_per_delivery'] = (
                (df['fuel_consumed_liters'] * 5000 + df['toll_cost']) / 
                df['deliveries_in_trip']
            ).round(2)
            
            # Revenue estimado (ejemplo: $20,000 base + $500 por kg)
            df['revenue_per_delivery'] = (20000 + df['package_weight_kg'] * 500).round(2)
            
            # Validaciones de calidad
            # No permitir tiempos negativos
            df = df[df['delivery_time_minutes'] >= 0]
            
            # No permitir pesos fuera de rango
            df = df[(df['package_weight_kg'] > 0) & (df['package_weight_kg'] < 10000)]
            
            # Manejar cambios históricos (SCD Type 2 para conductor/vehículo)
            df['valid_from'] = pd.to_datetime(df['scheduled_datetime']).dt.date
            df['valid_to'] = datetime(9999,12,31).date()
            df['is_current'] = True
            
            self.metrics['records_transformed'] = len(df)
            logging.info(f" Transformados {len(df)} registros")
            
            return df
            
        except Exception as e:
            logging.error(f" Error en transformación: {e}")
            self.metrics['errors'] += 1
            return pd.DataFrame()
    
    def load_date_dimension(self):
        """Generar y cargar dim_date con los últimos 10 días de dic 2024"""
        logging.info(" Cargando dim_date...")
        cursor = self.sf_conn.cursor()
        
        try:
            fechas = [datetime(2024, 12, 22) + timedelta(days=i) for i in range(10)]
            
            for fecha in fechas:
                date_key = int(fecha.strftime('%Y%m%d'))
                es_finde = fecha.weekday() >= 5
                
                cursor.execute("""
                    MERGE INTO dim_date d
                    USING (SELECT %s as date_key) s
                    ON d.date_key = s.date_key
                    WHEN NOT MATCHED THEN
                        INSERT (date_key, full_date, day_of_week, day_name,
                                day_of_month, day_of_year, week_of_year,
                                month_num, month_name, quarter, year,
                                is_weekend, is_holiday, holiday_name,
                                fiscal_quarter, fiscal_year)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    date_key,
                    date_key,
                    fecha.date(),
                    fecha.weekday() + 1,
                    fecha.strftime('%A'),
                    fecha.day,
                    fecha.timetuple().tm_yday,
                    fecha.isocalendar()[1],
                    fecha.month,
                    fecha.strftime('%B'),
                    (fecha.month - 1) // 3 + 1,
                    fecha.year,
                    es_finde,
                    False,
                    None,
                    (fecha.month - 1) // 3 + 1,
                    fecha.year
                ))
            
            self.sf_conn.commit()
            logging.info(" dim_date cargada — 10 días")
            
        except Exception as e:
            logging.error(f" Error cargando dim_date: {e}")
    

    def load_time_dimension(self):
        """Generar  y cargar dim_time con las 24 horas del día"""
        logging.info('cargando dim_time...')
        cursor  = self.sf_conn.cursor()
        
        try:
            for hour in range(24):
                #Determinar turno y time_of_day
                if 0 <= hour <= 5:
                    turno       = 'turno 4'
                    time_of_day = 'Madrugada'
                elif 6 <= hour <= 11:
                    turno       = 'turno 1'
                    time_of_day = 'Manana'
                elif 12 <= hour <= 19:
                    turno       = 'turno 2'
                    time_of_day = 'Tarde'
                else:
                    turno       = 'turno 3'
                    time_of_day = 'Noche'
                
                time_key= hour * 100
                hour_24= f'{hour:02d}:00'
                hour_12= f'{hour % 12 or 12:02d}:00 {"AM" if hour < 12 else "PM"}'
                am_pm=   'AM' if hour < 12 else 'PM'
                
                cursor.execute("""
                    MERGE INTO dim_time t
                    USING (SELECT %s as time_key) s
                    ON t.time_key = s.time_key
                    WHEN NOT MATCHED THEN
                        INSERT (time_key, hour, minute, second,
                                time_of_day, hour_24, hour_12,
                                am_pm, is_business_hour, shift)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    time_key,
                    time_key,
                    hour,
                    0,
                    0,
                    time_of_day,
                    hour_24,
                    hour_12,
                    am_pm,
                    True,
                    turno
                ))
            self.sf_conn.commit()
            logging.info("dim_time cargada - 24 horas")
        
        except Exception as e:
            logging.error(f'Error cargando dim_time:{e}')       

                    
                
     
    
    def load_dimensions(self, df: pd.DataFrame):
        """Cargar o actualizar dimensiones en Snowflake"""
        logging.info(" Cargando dimensiones...")
        
        cursor = self.sf_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        hoy = datetime.now().date()
        
        try:
            # Cargar dim_customer
            pg_cursor.execute("""
                SELECT 
                    d.customer_name,
                    r.destination_city as city,
                    MIN(d.delivered_datetime) as first_delivery_date,
                    COUNT(*) as total_deliveries
                FROM deliveries d
                JOIN trips t ON d.trip_id = t.trip_id
                JOIN routes r ON t.route_id = r.route_id
                WHERE d.delivery_status = 'delivered'
                GROUP BY d.customer_name, r.destination_city
                ORDER BY total_deliveries DESC
                LIMIT 10000
            """)
            customers = pg_cursor.fetchall()
            
            customer_data = []
            for idx, row in enumerate(customers):
                total = row[3]
                if total >= 10:
                    cat = 'Premium'
                elif total >= 3:
                    cat = 'Regular'
                else:
                    cat = 'Ocasional'
                customer_data.append((
                    idx + 1,
                    row[0],
                    row[1],
                    pd.to_datetime(row[2]).date(),
                    int(total),
                    cat
                ))
            
            batch_size = 1000
            for i in range(0, len(customer_data), batch_size):
                batch = customer_data[i:i + batch_size]
                cursor.executemany("""
                    INSERT INTO dim_customer
                        (customer_key, customer_name, customer_type, city,
                         first_delivery_date, total_deliveries, customer_category)
                    VALUES (%s, %s, 'Individual', %s, %s, %s, %s)
                """, batch)
                logging.info(f" dim_customer lote {i//batch_size + 1} cargado")
            
            # Cargar dim_vehicle
            pg_cursor.execute("""
                SELECT vehicle_id, MAX(maintenance_date) as last_maintenance_date
                FROM maintenance GROUP BY vehicle_id
            """)
            maintenance = {row[0]: row[1] for row in pg_cursor.fetchall()}
            
            pg_cursor.execute("""
                SELECT vehicle_id, license_plate, vehicle_type, capacity_kg,
                       fuel_type, acquisition_date, status FROM vehicles
            """)
            vehicle_data = []
            for row in pg_cursor.fetchall():
                age_months = (hoy - row[5]).days // 30
                vehicle_data.append((
                    row[0], row[1], row[2], row[3], row[4],
                    row[5], age_months, row[6],
                    maintenance.get(row[0]),
                    hoy, datetime(2050, 12, 31).date(), True
                ))
            
            cursor.executemany("""
                INSERT INTO dim_vehicle
                    (vehicle_id, license_plate, vehicle_type, capacity_kg,
                     fuel_type, acquisition_date, age_months, status,
                     last_maintenance_date, valid_from, valid_to, is_current)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, vehicle_data)
            logging.info(" dim_vehicle cargada")
            
            # Cargar dim_driver
            pg_cursor.execute("""
                SELECT d.driver_id, d.employee_code, d.first_name, d.last_name,
                       d.license_number, d.license_expiry, d.phone, d.hire_date, d.status,
                       COUNT(*) as total_entregas,
                       SUM(CASE WHEN de.delivery_status = 'delivered' THEN 1 ELSE 0 END) as exitosas
                FROM drivers d
                JOIN trips t ON t.driver_id = d.driver_id
                JOIN deliveries de ON de.trip_id = t.trip_id
                GROUP BY d.driver_id, d.employee_code, d.first_name, d.last_name,
                         d.license_number, d.license_expiry, d.phone, d.hire_date, d.status
            """)
            driver_data = []
            for row in pg_cursor.fetchall():
                full_name = f"{row[2]} {row[3]}"
                experience_months = (hoy - row[7]).days // 30
                pct = row[10] * 100 / row[9]
                perf = 'Alto' if pct >= 85 else 'Medio' if pct >= 70 else 'Bajo'
                driver_data.append((
                    row[0], row[1], full_name, row[4], row[5],
                    row[6], row[7], experience_months, row[8],
                    perf, hoy, datetime(2050, 12, 31).date(), True
                ))
            
            cursor.executemany("""
                INSERT INTO dim_driver
                    (driver_id, employee_code, full_name, license_number,
                     license_expiry, phone, hire_date, experience_months,
                     status, performance_category, valid_from, valid_to, is_current)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, driver_data)
            logging.info(" dim_driver cargada")
            
            # Cargar dim_route
            pg_cursor.execute("SELECT * FROM routes")
            route_data = []
            for row in pg_cursor.fetchall():
                diff = 'Facil' if row[4] < 500 else 'Medio' if row[4] <= 1500 else 'Dificil'
                rtype = 'Autopista' if 'EXP' in row[1] else 'Federal' if 'FED' in row[1] else 'Libre'
                route_data.append((
                    row[0], row[1], row[2], row[3],
                    row[4], row[5], row[6], diff, rtype
                ))
            
            cursor.executemany("""
                INSERT INTO dim_route
                    (route_id, route_code, origin_city, destination_city,
                     distance_km, estimated_duration_hours, toll_cost,
                     difficulty_level, route_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, route_data)
            logging.info(" dim_route cargada")
            
            self.sf_conn.commit()
            logging.info(" Dimensiones actualizadas")
            
        except Exception as e:
            logging.error(f" Error cargando dimensiones: {e}")
            self.sf_conn.rollback()
            self.metrics['errors'] += 1        
            
            # Actualizar dimensiones SCD Type 2 si hay cambios
            # (Ejemplo simplificado para dim_driver)
            cursor.execute("""
                UPDATE dim_driver 
                SET valid_to = CURRENT_DATE() - 1, is_current = FALSE
                WHERE driver_id IN (
                    SELECT DISTINCT driver_id 
                    FROM staging_daily_load
                ) AND is_current = TRUE
            """)
            
            self.sf_conn.commit()
            logging.info(" Dimensiones actualizadas")
            
        except Exception as e:
            logging.error(f" Error cargando dimensiones: {e}")
            self.sf_conn.rollback()
            self.metrics['errors'] += 1
    
    def load_facts(self, df: pd.DataFrame):
        """Cargar hechos en Snowflake"""
        logging.info(" Cargando tabla de hechos...")
        
        cursor = self.sf_conn.cursor()
        
        try:
            # Preparar datos para inserción
            fact_data = []
            for _, row in df.iterrows():
                # Obtener keys de dimensiones
                date_key = int(pd.to_datetime(row['scheduled_datetime']).strftime('%Y%m%d'))
                scheduled_time_key = pd.to_datetime(row['scheduled_datetime']).hour * 100
                delivered_time_key = pd.to_datetime(row['delivered_datetime']).hour * 100
                
                fact_data.append((
                    date_key,
                    scheduled_time_key,
                    delivered_time_key,
                    row['vehicle_id'],  # Simplificado, debería buscar vehicle_key
                    row['driver_id'],   # Simplificado, debería buscar driver_key
                    row['route_id'],    # Simplificado, debería buscar route_key
                    1,  # customer_key placeholder
                    row['delivery_id'],
                    row['trip_id'],
                    row['tracking_number'],
                    row['package_weight_kg'],
                    row['distance_km'],
                    row['fuel_consumed_liters'],
                    row['delivery_time_minutes'],
                    row['delay_minutes'],
                    row['deliveries_per_hour'],
                    row['fuel_efficiency_km_per_liter'],
                    row['cost_per_delivery'],
                    row['revenue_per_delivery'],
                    row['is_on_time'],
                    False,  # is_damaged
                    row['recipient_signature'],
                    row['delivery_status'],
                    self.batch_id
                ))
            
            
            # Insertar en batch
            batch_size = 1000
            for i in range(0, len(fact_data), batch_size):
                batch = fact_data[i:i + batch_size]
                cursor.executemany("""
                    INSERT INTO fact_deliveries (
                        date_key, scheduled_time_key, delivered_time_key,
                        vehicle_key, driver_key, route_key, customer_key,
                        delivery_id, trip_id, tracking_number,
                        package_weight_kg, distance_km, fuel_consumed_liters,
                        delivery_time_minutes, delay_minutes, deliveries_per_hour,
                        fuel_efficiency_km_per_liter, cost_per_delivery, revenue_per_delivery,
                        is_on_time, is_damaged, has_signature, delivery_status,
                        etl_batch_id
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, batch)
                logging.info(f" Lote {i//batch_size + 1} cargado — {len(batch)} registros")
            
            self.sf_conn.commit()
            self.metrics['records_loaded'] = len(fact_data)
            logging.info(f" Cargados {len(fact_data)} registros en fact_deliveries")

            
        except Exception as e:
            logging.error(f" Error cargando hechos: {e}")
            self.sf_conn.rollback()
            self.metrics['errors'] += 1
    
    def run_etl(self):
        """Ejecutar pipeline ETL completo"""
        start_time = datetime.now()
        logging.info(f" Iniciando ETL - Batch ID: {self.batch_id}")
        
        try:
            # Conectar
            if not self.connect_databases():
                return
            
            # ETL
            self.load_date_dimension()
            self.load_time_dimension()
            df = self.extract_daily_data()
            if not df.empty:
                df_transformed = self.transform_data(df)
                if not df_transformed.empty:
                    self.load_dimensions(df_transformed)
                    self.load_facts(df_transformed)
            
            # Calcular totales para reportes
            self._calculate_daily_totals()
            
            # Cerrar conexiones
            self.close_connections()
            
            # Log final
            duration = (datetime.now() - start_time).total_seconds()
            logging.info(f" ETL completado en {duration:.2f} segundos")
            logging.info(f" Métricas: {json.dumps(self.metrics, indent=2)}")
            
        except Exception as e:
            logging.error(f" Error fatal en ETL: {e}")
            self.metrics['errors'] += 1
            self.close_connections()
    
    def _calculate_daily_totals(self):
        """Pre-calcular totales para reportes rápidos"""
        cursor = self.sf_conn.cursor()
        
        try:
            # Crear tabla de totales si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_totals(
                    batch_id            INT,
                    report_date         DATE,
                    total_entregas      INT,
                    entregas_exitosas   INT,
                    entregas_a_tiempo   INT,
                    entregas_danadas    INT,
                    revenue_total       DECIMAL(15,2),
                    etl_timestamp TIMESTAMP_NTZ DEFAULT  CURRENT_TIMESTAMP()
                ) 
                           """)
            
            # Insertar totales del día
            cursor.execute("""
                INSERT INTO daily_totals(
                    batch_id,
                    report_date,
                    total_entregas,
                    entregas_exitosas,
                    entregas_a_tiempo,
                    entregas_danadas,
                    revenue_total
                )
                SELECT
                    %s,
                    CURRENT_DATE(),
                    COUNT(*),
                    SUM(CASE WHEN delivery_status = 'delivered' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END),
                    SUM(CASE WHEN is_damaged THEN 1 ELSE 0 END),
                    SUM(revenue_per_delivery)
                FROM fact_deliveries
                WHERE etl_batch_id = %s
                           """, (self.batch_id, self.batch_id))
            
            self.sf_conn.commit()
            logging.info(" Totales diarios calculados")
            
        except Exception as e:
            logging.error(f" Error calculando totales: {e}")    

    def close_connections(self):
        """Cerrar conexiones a bases de datos"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.sf_conn:
            self.sf_conn.close()
        logging.info(" Conexiones cerradas")

def job():
    """Función para programar con schedule"""
    etl = FleetLogixETL()
    etl.run_etl()

def main():
    """Función principal - Automatización diaria"""
    logging.info(" Pipeline ETL FleetLogix iniciado")
    
    # Programar ejecución diaria a las 2:00 AM
    schedule.every().day.at("02:00").do(job)
    
    logging.info(" ETL programado para ejecutarse diariamente a las 2:00 AM")
    logging.info("Presiona Ctrl+C para detener")
    
    # Ejecutar una vez al inicio (para pruebas)
    job()
    
    # Loop infinito esperando la hora programada
    while True:
        schedule.run_pending()
        time.sleep(60)  # Verificar cada minuto

if __name__ == "__main__":
    main()
    
    
    
