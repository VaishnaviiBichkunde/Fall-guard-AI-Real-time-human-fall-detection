# 📊 Excel Dashboard & Data Modeling Guide - Airline Flight Delay Analysis

This guide provides step-by-step instructions to set up, build, and customize an interactive **Airline Flight Delay Analysis Dashboard** in Microsoft Excel.

---

## 1. 🏗️ Relational Data Model Setup (Excel Power Pivot)

Excel supports relational data modeling without requiring messy `VLOOKUP` formulas using **Power Pivot**.

### Steps to Create Relationships:
1. Open Excel and navigate to the **Data** tab -> Click **Data Model / Manage Data Model**.
2. Go to **Diagram View**.
3. Create the following **1-to-Many Relationships**:
   - `Dim_Airlines[AirlineID]` (1) ───< `Fact_Flights[AirlineID]` (*)
   - `Dim_Airports[AirportID]` (1) ───< `Fact_Flights[OriginAirportID]` (*)
   - `Dim_Airports[AirportID]` (1) ───< `Fact_Flights[DestAirportID]` (*)
   - `Dim_Dates[DateKey]` (1) ───< `Fact_Flights[DateKey]` (*)
   - `Dim_DelayReasons[DelayCategoryID]` (1) ───< `Fact_Flights[PrimaryDelayCategoryID]` (*)

---

## 2. 🧮 Key Excel Formulas & Calculated Columns

### 🔹 Modern Formulas Used:
1. **`XLOOKUP` (Dynamic Header Lookup)**:
   ```excel
   =XLOOKUP(E2, Dim_Airlines!A:A, Dim_Airlines!B:B, "Unknown")
   ```
   *Fetches Airline Name dynamically based on AirlineID.*

2. **`SUMIFS` (Conditional Operational Cost Aggregation)**:
   ```excel
   =SUMIFS(Fact_Flights!V:V, Fact_Flights!W:W, "SkyWings Airlines")
   ```
   *Sums delay financial loss for a specific airline.*

3. **`AVERAGEIFS` (Average Delay Mins per Carrier)**:
   ```excel
   =AVERAGEIFS(Fact_Flights!M:M, Fact_Flights!W:W, "Apex Airways")
   ```
   *Calculates mean delay duration for delayed flights.*

4. **`COUNTIFS` (On-Time Performance Count)**:
   ```excel
   =COUNTIFS(Fact_Flights!M:M, "<15", Fact_Flights!N:N, 0)
   ```
   *Counts flights arriving under 15 minutes of scheduled time.*

5. **`IF` + `AND` (Delay Status Categorization Column)**:
   ```excel
   =IF(N2=1, "Cancelled", IF(M2>=15, "Delayed", "On-Time"))
   ```

---

## 3. 📈 Pivot Tables & Pivot Charts Setup

### Pivot Table 1: Airline On-Time Performance (OTP %)
- **Rows**: `AirlineName`
- **Values**: 
  - `Count of FlightID` (Renamed: Total Flights)
  - `Sum of IsDelayed` (Renamed: Delayed Count)
  - **Calculated Field**: `= (Total Flights - Delayed Count) / Total Flights` (Formatted as `%`)
- **Pivot Chart**: 100% Stacked Column Chart or Clustered Bar Chart.

### Pivot Table 2: Primary Delay Cause Distribution
- **Rows**: `CategoryName` (from `Dim_DelayReasons`)
- **Values**: `Sum of ArrDelayMinutes` (Formatted as `#,##0 Mins`)
- **Pivot Chart**: Donut Chart / Doughnut Chart with data labels percentage.

### Pivot Table 3: Monthly Delay Severity Trend
- **Rows**: `MonthName` (Sorted by `Month`)
- **Values**: `Average of ArrDelayMinutes`
- **Pivot Chart**: Smooth Line Chart with Markers.

### Pivot Table 4: Departure Time Window vs Delay Frequency
- **Rows**: `ScheduledDepHour`
- **Values**: `Count of IsDelayed`
- **Pivot Chart**: Area Chart or Conditional Formatting Heatmap.

---

## 4. 🎛️ Adding Interactive Slicers & Timeline

1. Click on any Pivot Chart -> Go to **PivotChart Analyze** -> **Insert Slicer**.
2. Select Slicers for:
   - ✈️ **Airline Name**
   - 📅 **Month / Quarter**
   - ⚠️ **Delay Category**
   - 🏙️ **Origin Airport Region**
3. **Connect Slicers across all charts**:
   - Right-click Slicer -> **Report Connections** -> Check boxes for **ALL Pivot Tables**.
   - Now clicking any airline or month updates every chart simultaneously!

---

## 5. 🎨 Dashboard Formatting & UI Best Practices

- **Color Palette**: Use dark navy headers (`#1E3A8A`), slate backgrounds (`#F8FAFC`), emerald green for On-Time (`#10B981`), amber for minor delay (`#F59E0B`), and coral red for severe delay (`#EF4444`).
- **KPI Cards**: Merge cells (e.g. B6:C7), set thick borders, bold centered text, large font size (18pt-24pt).
- **Hide Gridlines**: Uncheck **Gridlines** under View tab for a modern app-like dashboard feel.
