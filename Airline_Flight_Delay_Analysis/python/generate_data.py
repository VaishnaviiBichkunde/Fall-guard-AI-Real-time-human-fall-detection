import os
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Create directory structure
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(base_dir, "data")
os.makedirs(data_dir, exist_ok=True)

np.random.seed(42)
random.seed(42)

print("Generating Airline Data Dimensions and Fact Table...")

# 1. DIM_AIRLINES
airlines_data = [
    {"AirlineID": 101, "AirlineName": "SkyWings Airlines", "IATA_Code": "SW", "FleetSize": 240, "HubAirport": "ATL"},
    {"AirlineID": 102, "AirlineName": "Apex Airways", "IATA_Code": "AP", "FleetSize": 180, "HubAirport": "ORD"},
    {"AirlineID": 103, "AirlineName": "BlueHorizon Air", "IATA_Code": "BH", "FleetSize": 310, "HubAirport": "DFW"},
    {"AirlineID": 104, "AirlineName": "Pacific Express", "IATA_Code": "PE", "FleetSize": 150, "HubAirport": "LAX"},
    {"AirlineID": 105, "AirlineName": "Eagle Jet", "IATA_Code": "EJ", "FleetSize": 195, "HubAirport": "JFK"},
    {"AirlineID": 106, "AirlineName": "SunCountry Global", "IATA_Code": "SG", "FleetSize": 120, "HubAirport": "DEN"}
]
dim_airlines = pd.DataFrame(airlines_data)
dim_airlines.to_csv(os.path.join(data_dir, "dim_airlines.csv"), index=False)

# 2. DIM_AIRPORTS
airports_data = [
    {"AirportID": 1, "AirportCode": "ATL", "AirportName": "Hartsfield-Jackson Atlanta Int", "City": "Atlanta", "State": "GA", "Region": "Southeast"},
    {"AirportID": 2, "AirportCode": "ORD", "AirportName": "O'Hare International", "City": "Chicago", "State": "IL", "Region": "Midwest"},
    {"AirportID": 3, "AirportCode": "DFW", "AirportName": "Dallas/Fort Worth Int", "City": "Dallas", "State": "TX", "Region": "South"},
    {"AirportID": 4, "AirportCode": "DEN", "AirportName": "Denver International", "City": "Denver", "State": "CO", "Region": "West"},
    {"AirportID": 5, "AirportCode": "LAX", "AirportName": "Los Angeles International", "City": "Los Angeles", "State": "CA", "Region": "West"},
    {"AirportID": 6, "AirportCode": "JFK", "AirportName": "John F. Kennedy Int", "City": "New York", "State": "NY", "Region": "Northeast"},
    {"AirportID": 7, "AirportCode": "SFO", "AirportName": "San Francisco Int", "City": "San Francisco", "State": "CA", "Region": "West"},
    {"AirportID": 8, "AirportCode": "MIA", "AirportName": "Miami International", "City": "Miami", "State": "FL", "Region": "Southeast"},
    {"AirportID": 9, "AirportCode": "SEA", "AirportName": "Seattle-Tacoma Int", "City": "Seattle", "State": "WA", "Region": "Northwest"},
    {"AirportID": 10, "AirportCode": "BOS", "AirportName": "Boston Logan Int", "City": "Boston", "State": "MA", "Region": "Northeast"}
]
dim_airports = pd.DataFrame(airports_data)
dim_airports.to_csv(os.path.join(data_dir, "dim_airports.csv"), index=False)

# 3. DIM_DELAY_REASONS
delay_reasons_data = [
    {"DelayCategoryID": 1, "CategoryName": "Carrier Delay", "Description": "Maintenance, crew issues, cleaning, baggage loading", "ControllableByAirline": "Yes"},
    {"DelayCategoryID": 2, "CategoryName": "Weather Delay", "Description": "Extreme weather events, thunderstorm, snowstorms", "ControllableByAirline": "No"},
    {"DelayCategoryID": 3, "CategoryName": "NAS Delay", "Description": "National Airspace System, heavy traffic, airport ops", "ControllableByAirline": "No"},
    {"DelayCategoryID": 4, "CategoryName": "Security Delay", "Description": "Security breaches, line delays, terminal re-screening", "ControllableByAirline": "No"},
    {"DelayCategoryID": 5, "CategoryName": "Late Aircraft Delay", "Description": "Previous flight arrived late causing domino effect", "ControllableByAirline": "Yes"},
    {"DelayCategoryID": 0, "CategoryName": "On Time", "Description": "Flight arrived on time or early", "ControllableByAirline": "N/A"}
]
dim_delay_reasons = pd.DataFrame(delay_reasons_data)
dim_delay_reasons.to_csv(os.path.join(data_dir, "dim_delay_reasons.csv"), index=False)

# 4. DIM_DATES (Year 2024 full calendar)
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 12, 31)
date_list = []
curr = start_date
while curr <= end_date:
    season = "Winter"
    if curr.month in [3, 4, 5]: season = "Spring"
    elif curr.month in [6, 7, 8]: season = "Summer"
    elif curr.month in [9, 10, 11]: season = "Fall"
    
    date_list.append({
        "DateKey": int(curr.strftime("%Y%m%d")),
        "FullDate": curr.strftime("%Y-%m-%d"),
        "Year": curr.year,
        "Quarter": f"Q{(curr.month - 1) // 3 + 1}",
        "Month": curr.month,
        "MonthName": curr.strftime("%B"),
        "DayOfWeek": curr.strftime("%A"),
        "IsWeekend": "Yes" if curr.weekday() in [5, 6] else "No",
        "Season": season
    })
    curr += timedelta(days=1)

dim_dates = pd.DataFrame(date_list)
dim_dates.to_csv(os.path.join(data_dir, "dim_dates.csv"), index=False)

# 5. FACT_FLIGHTS (5000 flights)
num_flights = 5000
flight_records = []

airport_ids = dim_airports["AirportID"].tolist()
airline_ids = dim_airlines["AirlineID"].tolist()
date_keys = dim_dates["DateKey"].tolist()
date_lookup = dict(zip(dim_dates["DateKey"], dim_dates["FullDate"]))

for i in range(1, num_flights + 1):
    d_key = random.choice(date_keys)
    f_date_str = date_lookup[d_key]
    airline_id = random.choice(airline_ids)
    
    orig_id, dest_id = random.sample(airport_ids, 2)
    
    # Distance based on arbitrary distance matrix simulation
    distance = random.randint(300, 2600)
    
    # Hour of flight
    sched_dep_hour = random.choices(range(5, 23), weights=[5,7,9,10,10,9,8,8,9,10,10,9,8,7,6,5,4,3])[0]
    sched_dep_min = random.choice([0, 15, 30, 45])
    sched_dep_time = f"{sched_dep_hour:02d}:{sched_dep_min:02d}"
    
    # Delay distribution: 75% on time / early, 25% delayed
    is_delayed = np.random.choice([0, 1], p=[0.72, 0.28])
    is_cancelled = np.random.choice([0, 1], p=[0.985, 0.015])
    is_diverted = np.random.choice([0, 1], p=[0.993, 0.007]) if not is_cancelled else 0
    
    if is_cancelled:
        dep_delay = 0
        arr_delay = 0
        primary_cause_id = 0
        carrier_mins = weather_mins = nas_mins = sec_mins = late_mins = 0
    elif is_delayed:
        # Delay minutes exponential/gamma shape
        dep_delay = int(np.random.gamma(shape=2.5, scale=18)) + 15
        arr_delay = dep_delay + random.randint(-10, 15)
        arr_delay = max(15, arr_delay)
        
        # Primary cause breakdown
        causes = [1, 2, 3, 4, 5]
        # Summer/Winter higher weather, peak hours higher late aircraft
        weights = [0.30, 0.15, 0.20, 0.05, 0.30]
        primary_cause_id = random.choices(causes, weights=weights)[0]
        
        carrier_mins = arr_delay if primary_cause_id == 1 else (random.randint(0, 10) if random.random() < 0.2 else 0)
        weather_mins = arr_delay if primary_cause_id == 2 else (random.randint(0, 10) if random.random() < 0.1 else 0)
        nas_mins = arr_delay if primary_cause_id == 3 else (random.randint(0, 10) if random.random() < 0.2 else 0)
        sec_mins = arr_delay if primary_cause_id == 4 else 0
        late_mins = arr_delay if primary_cause_id == 5 else (random.randint(0, 10) if random.random() < 0.25 else 0)
    else:
        dep_delay = random.randint(-10, 14)
        arr_delay = dep_delay + random.randint(-10, 5)
        primary_cause_id = 0
        carrier_mins = weather_mins = nas_mins = sec_mins = late_mins = 0
        
    # Cost calculation ($75 per delay minute estimated industry cost)
    delay_cost = max(0, arr_delay) * 75.0 if not is_cancelled else 3500.0
    
    flight_records.append({
        "FlightID": i,
        "FlightNumber": f"FL-{random.randint(100, 999)}",
        "FlightDate": f_date_str,
        "DateKey": d_key,
        "AirlineID": airline_id,
        "OriginAirportID": orig_id,
        "DestAirportID": dest_id,
        "ScheduledDepHour": sched_dep_hour,
        "ScheduledDepTime": sched_dep_time,
        "DistanceMiles": distance,
        "DepDelayMinutes": dep_delay,
        "ArrDelayMinutes": arr_delay,
        "IsDelayed": 1 if arr_delay >= 15 and not is_cancelled else 0,
        "IsCancelled": is_cancelled,
        "IsDiverted": is_diverted,
        "PrimaryDelayCategoryID": primary_cause_id,
        "CarrierDelayMins": carrier_mins,
        "WeatherDelayMins": weather_mins,
        "NASDelayMins": nas_mins,
        "SecurityDelayMins": sec_mins,
        "LateAircraftDelayMins": late_mins,
        "DelayCostUSD": round(delay_cost, 2)
    })

fact_flights = pd.DataFrame(flight_records)
fact_flights.to_csv(os.path.join(data_dir, "fact_flights.csv"), index=False)

print(f"Data Generation Complete! Created {len(fact_flights)} flight records across 5 relational tables.")
