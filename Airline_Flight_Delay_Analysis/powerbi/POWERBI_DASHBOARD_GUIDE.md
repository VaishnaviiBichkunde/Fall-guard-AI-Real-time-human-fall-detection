# 🟡 Power BI Dashboard & Visual Setup Guide - Airline Flight Delay Analysis

This guide details how to import the dataset into Power BI Desktop, build the relational Star Schema, implement DAX measures, and design an interactive dashboard.

---

## 1. 🔌 Data Import & Star Schema Data Model

### Step 1: Import Datasets
1. Open **Power BI Desktop** -> Click **Get Data** -> Select **Text/CSV**.
2. Import the following 5 CSV files from the `data/` directory:
   - `fact_flights.csv`
   - `dim_airlines.csv`
   - `dim_airports.csv`
   - `dim_dates.csv`
   - `dim_delay_reasons.csv`

### Step 2: Model Relationships (Model View)
Verify the automatic relationships or manually drag fields to establish a **Star Schema** (Single Direction Filtering `1 -> *`):
- `dim_airlines[AirlineID]` (1) ───> `fact_flights[AirlineID]` (*)
- `dim_airports[AirportID]` (1) ───> `fact_flights[OriginAirportID]` (*) *(Active)*
- `dim_airports[AirportID]` (1) ───> `fact_flights[DestAirportID]` (*) *(Inactive / Role-Playing)*
- `dim_dates[DateKey]` (1) ───> `fact_flights[DateKey]` (*)
- `dim_delay_reasons[DelayCategoryID]` (1) ───> `fact_flights[PrimaryDelayCategoryID]` (*)

---

## 2. 📐 Calculated Columns (Power Query / DAX)

Create the following calculated column in `fact_flights`:

```dax
Delay Severity Category = 
SWITCH(
    TRUE(),
    'fact_flights'[IsCancelled] = 1, "Cancelled",
    'fact_flights'[ArrDelayMinutes] <= 0, "On-Time / Early",
    'fact_flights'[ArrDelayMinutes] < 15, "Minor (<15m)",
    'fact_flights'[ArrDelayMinutes] < 45, "Moderate (15-45m)",
    'fact_flights'[ArrDelayMinutes] < 90, "Significant (45-90m)",
    "Severe (>90m)"
)
```

---

## 3. 🖼️ Power BI Dashboard Canvas Visual Layout

### Page 1: Executive Overview Dashboard
1. **Header Banner**:
   - Dark Navy Header `#1E3A8A` with title: **"Airline On-Time Performance & Flight Delay Command Center"**.
   - Subtitle: "Real-Time Fleet Reliability, Operational Bottlenecks & Financial Loss Analysis".

2. **Top KPI Cards (5 Visuals)**:
   - **Card 1**: Total Flights -> Measure `[Total Flights]`
   - **Card 2**: OTP % -> Measure `[On-Time Performance Rate (OTP %)]` (Format: `0.0%`)
   - **Card 3**: Avg Delay Mins -> Measure `[Average Arrival Delay Mins]`
   - **Card 4**: Cancelled Flights -> Measure `[Cancelled Flights]`
   - **Card 5**: Financial Impact -> Measure `[Total Financial Loss USD]` (Format: `$#,##0`)

3. **Visual 1 (Line & Stacked Column Chart)**: Monthly Trend
   - **Shared Axis**: `dim_dates[MonthName]`
   - **Column Values**: `[Delayed Flights]`
   - **Line Values**: `[On-Time Performance Rate (OTP %)]`

4. **Visual 2 (Bar Chart)**: Airline OTP Ranking
   - **Y-Axis**: `dim_airlines[AirlineName]`
   - **X-Axis**: `[On-Time Performance Rate (OTP %)]`
   - **Conditional Formatting Color**: Apply rule using `[OTP Color Status]` measure.

5. **Visual 3 (Donut Chart)**: Delay Reasons Breakdown
   - **Legend**: `dim_delay_reasons[CategoryName]`
   - **Values**: `[Total Arrival Delay Mins]`

6. **Visual 4 (Decomposition Tree / Matrix Visual)**: Route Risk Explorer
   - **Analyze**: `[Average Arrival Delay Mins]`
   - **Explain By**: `dim_airports[City]`, `dim_airlines[AirlineName]`, `dim_dates[Season]`

7. **Interactive Slicer Panel (Left Sidebar)**:
   - Airline Filter Slicer
   - Month / Season Slicer
   - Delay Category Slicer

---

## 4. 🎯 Interactivity & Slicer Interactions
- Enable **Cross-filtering** across all visual cards.
- Add **Edit Interactions** so clicking an airline highlights its specific route share in the Donut Chart.
- Add **Tooltip Page**: Hover over an airline bar to view top 3 delayed origin airports for that specific carrier!
