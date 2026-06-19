import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta
import logging

print("Todo instalado correctamente ✓")


# ── Configuración inicial ────────────────────────────────────────────────────
fake = Faker('es_MX')
random.seed(42)
np.random.seed(42)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('fleetlogix_carga.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── Constantes de negocio ────────────────────────────────────────────────────
CIUDADES = ['Ciudad de México', 'Guadalajara', 'Monterrey', 'Puebla', 'Tijuana']

TIPOS_VEHICULO = {
    'Camión Grande':  {'cantidad': 50, 'capacidad': (5000, 10000), 'combustible': ['Diesel']},
    'Camión Mediano': {'cantidad': 60, 'capacidad': (2000, 5000),  'combustible': ['Diesel', 'Gas Natural']},
    'Van':            {'cantidad': 60, 'capacidad': (500, 2000),   'combustible': ['Gasolina', 'Eléctrico']},
    'Motocicleta':    {'cantidad': 30, 'capacidad': (50, 200),     'combustible': ['Gasolina', 'Eléctrico']},
}

# ── Generadores Vehiculos──────────────────────────────────────────────────────────────
def generate_vehicles():
    log.info("Generando tabla vehicles...")
    records = []
    vehicle_id = 1

    for tipo, config in TIPOS_VEHICULO.items():
        for _ in range(config['cantidad']):
            records.append({
                'vehicle_id':       vehicle_id,
                'license_plate':    fake.unique.bothify(text='???-###-??').upper(),
                'vehicle_type':     tipo,
                'capacity_kg':      round(random.uniform(*config['capacidad']), 2),
                'fuel_type':        random.choice(config['combustible']),
                'acquisition_date': fake.date_between(start_date='-5y', end_date='-6m'),
                'status':           random.choices(['active', 'inactive', 'maintenance'],
                                                   weights=[85, 10, 5])[0]
            })
            vehicle_id += 1

    df = pd.DataFrame(records)
    log.info(f"vehicles generados: {len(df)} registros")
    return df

# ── Generadores Drivers──────────────────────────────────────────────────────────────
def generate_drivers ():
    log.info('Generando tabla de Drivers...')
    records= []
    Licencias= ['A','B','C','D']
    
    for driver_id in range(1,401):
     hire_date = fake.date_between(start_date='-5y', end_date='-6m')
     license_expiry= fake.date_between(
             start_date= hire_date + timedelta(days=365),
             end_date= hire_date + timedelta(days=365*5)
         )
     records.append({
            'driver_id':       driver_id,
            'employee_code':   f'EMP-{driver_id:04d}',
            'first_name':      fake.first_name(),
            'last_name':       fake.last_name(),
            'license_number':  f'LIC-{random.choice(Licencias)}-{fake.unique.bothify(text="######")}',
            'license_expiry':  license_expiry,
            'phone':           fake.phone_number(),
            'hire_date':       hire_date,
            'status':          random.choices(['active', 'inactive'],
                                              weights=[90, 10])[0]
        })

    df = pd.DataFrame(records)
    log.info(f'Drivers generados... {len(df)} registros')
    return df

# ── Generadores Routes──────────────────────────────────────────────────────────────
def generate_routes():
    log.info ("Generando tabla Routes...")
    records =[]
    route_id = 1
    
    CIUDADES_ABREV = {
        'Ciudad de México': 'CDMX',
        'Guadalajara':      'GDL',
        'Monterrey':        'MTY',
        'Puebla':           'PUE',
        'Tijuana':          'TIJ'
    }
    
    # Distancias reales aproximadas entre ciudades (km)
    DISTANCIAS= {
            ('Ciudad de México', 'Guadalajara'): 540,
        ('Ciudad de México', 'Monterrey'):   940,
        ('Ciudad de México', 'Puebla'):      130,
        ('Ciudad de México', 'Tijuana'):    2800,
        ('Guadalajara',      'Monterrey'):   700,
        ('Guadalajara',      'Puebla'):      470,
        ('Guadalajara',      'Tijuana'):    1100,
        ('Monterrey',        'Puebla'):      870,
        ('Monterrey',        'Tijuana'):    1600,
        ('Puebla',           'Tijuana'):    2900,
    }

    VARIANTES= {
        'EXP':{'dist_factor':0.90, 'vel_kmh':100, 'peaje_factor':1.5},
        'FED':{'dist_factor':1.00, 'vel_kmh':80, 'peaje_factor':1.0},
        'ECO':{'dist_factor':1.20, 'vel_kmh':65, 'peaje_factor':0.5},
    }
    
    for (origen, destino), dist_base in DISTANCIAS.items():
        for variante, config in VARIANTES.items():
            for direccion in [(origen, destino), (destino, origen)]:
                orig, dest = direccion
                orig_abrev = CIUDADES_ABREV[orig]
                dest_abrev = CIUDADES_ABREV[dest]
                distancia  = round(dist_base * config['dist_factor'], 2)
                duracion   = round(distancia / config['vel_kmh'], 2)
                peaje      = round((distancia * 0.8) * config['peaje_factor'], 2)

                records.append({
                    'route_id':                 route_id,
                    'route_code':               f'{orig_abrev}-{dest_abrev}-{variante}',
                    'origin_city':              orig,
                    'destination_city':         dest,
                    'distance_km':              distancia,
                    'estimated_duration_hours': duracion,
                    'toll_cost':                peaje
                })
                route_id += 1

    # Recortar a exactamente 50
    df = pd.DataFrame(records[:50])
    log.info(f"routes generadas: {len(df)} registros")
    return df 
    
# ── Auxiliar de distribución horaria ────────────────────────────────────────
def get_hourly_distribution (vehicle_type):
    if vehicle_type in ['Camión Grande','Camión Mediano']:
        horas = list(range(24))    
        pesos = [1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3]
    elif vehicle_type in ['Van']:
        horas = list(range(24))
        pesos  = [1,1,1,1,1,1,1,2,4,4,4,4,3,3,3,3,2,2,2,2,1,1,1,1]
    elif vehicle_type in ['Motocicleta']:
        horas = list(range(24))
        pesos =  [1,1,1,1,1,1,1,1,2,3,4,4,4,4,4,4,4,3,3,2,2,1,1,1]
    else:
        raise ValueError(f"Tipo de vehículo inválido: {vehicle_type}")
    return random.choices (horas, weights=pesos)[0]

# ── Generadores Trips──────────────────────────────────────────────────────────────
def generate_trips (df_vehicles,df_drivers,df_routes):
    log.info('Generando tabla trips...')
    records = []
    
    #IDs válidos de tablas maestras
    vehicle_ids= df_vehicles['vehicle_id'].tolist()
    driver_ids= df_drivers['driver_id'].tolist()
    route_ids= df_routes['route_id'].tolist()

    #Rango de 2 operación
    fecha_inicio = datetime (2023,1,1)
    fecha_fin    = datetime (2024,12,31)
    
    for trip_id in range (1,100001):
        #Elegir vehículo y obtener ruta
        vehicle_id = random.choice(vehicle_ids)
        vehicle_type = df_vehicles[df_vehicles['vehicle_id'] == vehicle_id]['vehicle_type'].values[0]
    
        #Elegir conductor y ruta
        driver_id = random.choice(driver_ids)
        route_id = random.choice(route_ids)
    
        #Obtener duración estimada de la ruta
        duracion_hrs = df_routes[df_routes['route_id'] == route_id]['estimated_duration_hours'].values[0]
    
        #Generar fecha y hora de salida con distribución realista
        dias_totales = (fecha_fin - fecha_inicio).days
        dia_random   = fecha_inicio + timedelta(days=random.randint(0,dias_totales))
        hora_salida  = get_hourly_distribution(vehicle_type)
        minuto       = random.randint(0,59)
    
        departure = datetime(
            dia_random.year,
            dia_random.month,
            dia_random.day,
            hora_salida,
            minuto
        )
        
        #Arrival siempre después de departure
        variacion = random.uniform(0.9,1.2) #Entre 90% y 120% del tiempo estimado
        arrival   = departure + timedelta(hours= duracion_hrs * variacion)
        
        #Peso total basado en capacidad del vehículo
        capacidad_kg = df_vehicles[df_vehicles['vehicle_id'] == vehicle_id]['capacity_kg'].values[0]
        peso_total   = round(random.uniform(capacidad_kg * 0.5, capacidad_kg * 0.95),2)
        
        records.append({
            'trip_id':               trip_id,
                'vehicle_id':            vehicle_id,
                'driver_id':             driver_id,
                'route_id':              route_id,
                'departure_datetime':    departure,
                'arrival_datetime':      arrival,
                'fuel_consumed_liters':  round(random.uniform(20, 300), 2),
                'total_weight_kg':       peso_total,
                'status':                random.choices(
                                            ['completed', 'in_progress', 'cancelled'],
                                            weights=[85, 10, 5])[0]
        })
     
        if trip_id % 1000 == 0:
            log.info(f'trips generados: {trip_id}/100000')
    
    df= pd.DataFrame(records)
    log.info (f'trips generados: {len(df)} registros')
    return df 

# ── Generadores Deliveries──────────────────────────────────────────────────────────────  
def generate_deliveries(df_trips):
    log.info('Generando tabla Deliveries...')
    records = []
    delivery_id = 1

    for _, trip in df_trips.iterrows():
        num_entregas = random.choices([2, 3, 4, 5, 6],
                                      weights=[10, 15, 50, 15, 10])[0]

        for _ in range(num_entregas):
            scheduled = trip['departure_datetime'] + timedelta(
                hours=random.uniform(0.5, trip['arrival_datetime'].hour or 1)
            )
            delivered = scheduled + timedelta(minutes=random.randint(10, 60))

            records.append({
                'delivery_id':         delivery_id,
                'trip_id':             trip['trip_id'],
                'tracking_number':     f'TRK-{delivery_id:08d}',
                'customer_name':       fake.name(),
                'delivery_address':    fake.address(),
                'package_weight_kg':   round(random.uniform(0.5, 50), 2),
                'scheduled_datetime':  scheduled,
                'delivered_datetime':  delivered,
                'delivery_status':     random.choices(
                                           ['delivered', 'pending', 'failed'],
                                           weights=[80, 15, 5])[0],
                'recipient_signature': random.choices([True, False],
                                                      weights=[75, 25])[0]
            })
            delivery_id += 1

        if trip['trip_id'] % 10000 == 0:
            log.info(f"  procesados {trip['trip_id']}/100000 viajes")

    df = pd.DataFrame(records)
    log.info(f'deliveries generadas: {len(df)} registros')
    print(df.head(10)) 
    return df 


# ── Generadores Maintenance──────────────────────────────────────────────────────────────      
def generate_maintenance(df_vehicles, df_trips):
    log.info('Generando tabla Maintenance...')
    records = []
    
    TIPOS_MANTENIMIENTO= [
        'Cambio de aceite',
        'Revisión de frenos',
        'Cambios de llantas',
        'Revisión general',
        'Revisión de motor',
        'Alineación y balanceo'
    ]
    
    #5000 registros distribuidos entre 200 vehículos = -25 por vehículo
    mantenimientos_por_vehiculos = 25
    maintenance_id= 1
    for _, vehicle in df_vehicles.iterrows():
        acquisition_date = vehicle['acquisition_date']
        for _ in range(mantenimientos_por_vehiculos):
            maintenance_date = fake.date_between(
                start_date= acquisition_date,
                end_date= 'today'
            )   
            next_maintenance = maintenance_date + timedelta(
                days= random.randint (30,365)
            )
            tipo= random.choice(TIPOS_MANTENIMIENTO)
            
            records.append({
                'maintenance_id':       maintenance_id,
                'vehicle_id':           vehicle['vehicle_id'],
                'maintenance_date':     maintenance_date,
                'maintenance_type':     tipo,
                'description':          f'{tipo} realizado según programa de mantenimiento',
                'cost':                 round(random.uniform(500, 15000), 2),
                'next_maintenance_date': next_maintenance,
                'performed_by':         fake.name()
            })
            maintenance_id +=1 
            
    df= pd.DataFrame(records)
    log.info(f'Maintenance generados: {len(df)} registros')
    return df 


# ── Validación ─────────────────────────────────────────────────────────────────────    
def validar_calidad (df_vehicles, df_drivers, df_routes, 
                     df_trips, df_deliveries, df_maintenance):
    log.info('='*50)
    log.info('INICIANDO CONTROL DE CALIDAD')
    log.info('='*50)
    errores = 0
    
    # ── 3.1 Integridad referencial ───────────────────────────────────────
    # trips → vehicles
    ids_invalidos=  ~df_trips['vehicle_id'].isin(df_vehicles['vehicle_id'])
    n = ids_invalidos.sum()
    if n > 0:
        log.error(f"❌ trips con driver_id inválido: {n}")
        errores += n
    else:
        log.info("✅ trips.driver_id — integridad OK")
        
    # trips → routes
    ids_invalidos = ~df_trips['route_id'].isin(df_routes['route_id'])
    n = ids_invalidos.sum()
    if n > 0:
        log.error(f"❌ trips con route_id inválido: {n}")
        errores += n
    else:
        log.info("✅ trips.route_id — integridad OK")
    
     # deliveries → trips
    ids_invalidos = ~df_deliveries['trip_id'].isin(df_trips['trip_id'])
    n = ids_invalidos.sum()
    if n > 0:
        log.error(f"❌ deliveries con trip_id inválido: {n}")
        errores += n
    else:
        log.info("✅ deliveries.trip_id — integridad OK")
    
        # maintenance → vehicles
    ids_invalidos = ~df_maintenance['vehicle_id'].isin(df_vehicles['vehicle_id'])
    n = ids_invalidos.sum()
    if n > 0:
        log.error(f"❌ maintenance con vehicle_id inválido: {n}")
        errores += n
    else:
        log.info("✅ maintenance.vehicle_id — integridad OK")
        
    
    # ── 3.2 Consistencia temporal ────────────────────────────────────────
    # arrival > departure en trips
    inconsistences = df_trips['arrival_datetime'] <= df_trips['departure_datetime']
    n = inconsistences.sum()
    if n > 0:
        log.error(f"❌ trips con arrival <= departure: {n}")
        errores += n
    else:
        log.info ("✅ trips — consistencia temporal OK")
    
    # delivered > scheduled en deliveries
    inconsistences = df_deliveries['delivered_datetime'] <= df_deliveries['scheduled_datetime']
    n = inconsistences.sum()
    if n > 0:
        log.error(f"❌ deliveries con delivered <= scheduled: {n}")
        errores += n
    else:
        log.info("✅ deliveries — consistencia temporal OK")
    
    #maintenance_date >= acquisition_date
    df_merged = df_maintenance.merge(
        df_vehicles[['vehicle_id','acquisition_date']],
        on= 'vehicle_id'
    ) 
    inconsistences= df_merged['maintenance_date']< df_merged['acquisition_date']
    n= inconsistences.sum()
    if n > 0:
        log.error(f"❌ maintenance antes de acquisition_date: {n}")
        errores += n
    else:
        log.info("✅ maintenance — fechas coherentes con acquisition OK")
    

    # ── Resumen ──────────────────────────────────────────────────────────
    log.info('='*50)
    if errores == 0:
        log.info("✅ CONTROL DE CALIDAD PASSED — 0 errores encontrados")
    else:
        log.error(f"❌ CONTROL DE CALIDAD FAILED — {errores} errores encontrados")
    log.info("="*50)
    return errores

    # ── Cargar a Postgresql ──────────────────────────────────────────────────────────
def cargar_a_postgresql(df_vehicles, df_drivers, df_routes,
                         df_trips, df_deliveries, df_maintenance):
    import sqlalchemy
    log.info("Conectando a PostgreSQL...")

    connection_string = "postgresql+psycopg2://postgres:Minino580@localhost:5432/fleetlogix"

    engine = sqlalchemy.create_engine(connection_string)

    tablas = [
        ('vehicles',    df_vehicles),
        ('drivers',     df_drivers),
        ('routes',      df_routes),
        ('trips',       df_trips),
        ('deliveries',  df_deliveries),
        ('maintenance', df_maintenance),
    ]

    try:
        with engine.connect() as conn:
            for tabla, df in tablas:
                log.info(f"Cargando {tabla}...")
                df.to_sql(tabla, con=conn, if_exists='append',
                         index=False)
                conn.commit()
                log.info(f"[OK] {tabla} — {len(df)} registros")

        log.info("="*50)
        log.info("CARGA COMPLETA EXITOSA")
        log.info("="*50)

    except Exception as e:
        log.error(f"[ERROR] durante la carga: {e}")
        raise
# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    df_vehicles    = generate_vehicles()
    df_drivers     = generate_drivers()
    df_routes      = generate_routes()
    df_trips       = generate_trips(df_vehicles, df_drivers, df_routes)
    df_deliveries  = generate_deliveries(df_trips)
    df_maintenance = generate_maintenance(df_vehicles, df_trips)
    validar_calidad(df_vehicles, df_drivers, df_routes,
                    df_trips, df_deliveries, df_maintenance)
    cargar_a_postgresql(df_vehicles, df_drivers, df_routes,
                       df_trips, df_deliveries, df_maintenance)
    

    