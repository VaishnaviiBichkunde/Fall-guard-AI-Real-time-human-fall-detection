"""
Airline Flight Delay Analysis - Python EDA & Feature Engineering Pipeline
-----------------------------------------------------------------------
This script performs data loading, cleaning, feature engineering, statistical
aggregations, and outputs summary metrics used to power Power BI & Excel dashboards.
"""

import os
import pandas as pd
import numpy as np

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(base_dir, "data")

print("--- 1. LOADING DATASETS ---")
fact_flights = pd.read_csv(os.path.join(data_dir, "fact_flights.csv"))
dim_airlines = pd.read_csv(os.path.join(data_dir, "dim_airlines.csv"))
dim_airports = pd.read_csv(os.path.join(data_dir, "dim_airports.csv"))
dim_dates = pd.read_csv(os.path.join(data_dir, "dim_dates.csv"))
dim_reasons = pd.read_csv(os.path.join(data_dir, "dim_delay_reasons.csv"))

print(f"Fact Table Loaded: {fact_flights.shape[0]} rows, {fact_flights.shape[1]} columns")

print("\n--- 2. MERGING RELATIONAL MODEL ---")
df = fact_flights.merge(dim_airlines, on="AirlineID", how="left")
df = df.merge(dim_airports.add_prefix("Origin_"), left_on="OriginAirportID", right_on="Origin_AirportID", how="left")
df = df.merge(dim_airports.add_prefix("Dest_"), left_on="DestAirportID", right_on="Dest_AirportID", how="left")
df = df.merge(dim_dates, on="DateKey", how="left")
df = df.merge(dim_reasons, left_on="PrimaryDelayCategoryID", right_on="DelayCategoryID", how="left")

print("\n--- 3. FEATURE ENGINEERING ---")
# Category: Delay Severity
def categorize_delay(mins, is_cancelled):
    if is_cancelled == 1:
        return "Cancelled"
    elif mins <= 0:
        return "Early / On-Time"
    elif mins < 15:
        return "Minor Delay (<15m)"
    elif mins < 45:
        return "Moderate Delay (15-45m)"
    elif mins < 90:
        return "Significant Delay (45-90m)"
    else:
        return "Severe Delay (>90m)"

df["Delay_Severity"] = df.apply(lambda r: categorize_delay(r["ArrDelayMinutes"], r["IsCancelled"]), axis=1)

# Category: Flight Distance Group
def distance_group(miles):
    if miles < 500: return "Short Haul (<500 mi)"
    elif miles < 1500: return "Medium Haul (500-1500 mi)"
    else: return "Long Haul (>1500 mi)"

df["Distance_Group"] = df["DistanceMiles"].apply(distance_group)

# Time Window Slot
def dep_slot(hour):
    if 5 <= hour < 9: return "Morning Peak (05-09)"
    elif 9 <= hour < 14: return "Midday (09-14)"
    elif 14 <= hour < 19: return "Evening Peak (14-19)"
    else: return "Night (19-05)"

df["Dep_Time_Slot"] = df["ScheduledDepHour"].apply(dep_slot)

print("\n--- 4. EXECUTIVE KPI SUMMARY CALCULATIONS ---")
total_flights = len(df)
cancelled_flights = df["IsCancelled"].sum()
operated_flights = total_flights - cancelled_flights
delayed_flights = df["IsDelayed"].sum()
on_time_flights = operated_flights - delayed_flights

otp_rate = (on_time_flights / total_flights) * 100
avg_arr_delay = df["ArrDelayMinutes"].mean()
total_cost_usd = df["DelayCostUSD"].sum()

print(f"Total Flights Executed:     {total_flights:,}")
print(f"On-Time Flights:            {on_time_flights:,}")
print(f"Delayed Flights (>=15 min): {delayed_flights:,}")
print(f"Cancelled Flights:          {cancelled_flights:,}")
print(f"On-Time Performance Rate:   {otp_rate:.2f}%")
print(f"Average Arrival Delay:      {avg_arr_delay:.2f} mins")
print(f"Total Operational Loss:     ${total_cost_usd:,.2f}")

print("\n--- 5. AIRLINE SUMMARY METRICS ---")
airline_summary = df.groupby(["AirlineName", "IATA_Code"]).agg(
    Total_Flights=("FlightID", "count"),
    Delayed_Flights=("IsDelayed", "sum"),
    Avg_Dep_Delay=("DepDelayMinutes", "mean"),
    Avg_Arr_Delay=("ArrDelayMinutes", "mean"),
    Total_Cost_USD=("DelayCostUSD", "sum")
).reset_index()

airline_summary["OTP_Percentage"] = ((airline_summary["Total_Flights"] - airline_summary["Delayed_Flights"]) / airline_summary["Total_Flights"]) * 100
airline_summary = airline_summary.sort_values(by="OTP_Percentage", ascending=False)
print(airline_summary.to_string(index=False))

print("\n--- 6. DELAY REASON BREAKDOWN ---")
delay_reasons = df[df["IsDelayed"] == 1].groupby("CategoryName").agg(
    Incidents=("FlightID", "count"),
    Total_Mins=("ArrDelayMinutes", "sum"),
    Avg_Mins=("ArrDelayMinutes", "mean")
).reset_index().sort_values(by="Total_Mins", ascending=False)
print(delay_reasons.to_string(index=False))

# Export clean enriched dataset
enriched_path = os.path.join(data_dir, "enriched_fact_flights.csv")
df.to_csv(enriched_path, index=False)
print(f"\nSaved enriched analysis dataset to: {enriched_path}")
