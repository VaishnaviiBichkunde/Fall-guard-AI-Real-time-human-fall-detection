import os
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.formatting.rule import ColorScaleRule

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(base_dir, "data")
excel_dir = os.path.join(base_dir, "excel")
os.makedirs(excel_dir, exist_ok=True)

excel_path = os.path.join(excel_dir, "Airline_Flight_Delay_Dashboard.xlsx")

print("Building Excel Workbook with Data Model, Formulas, and Executive Dashboard Layout...")

# Create Workbook
wb = openpyxl.Workbook()
# Default sheet
ws_dash = wb.active
ws_dash.title = "Executive_Dashboard"

# Add extra sheets
ws_fact = wb.create_sheet(title="Fact_Flights")
ws_airlines = wb.create_sheet(title="Dim_Airlines")
ws_airports = wb.create_sheet(title="Dim_Airports")
ws_dates = wb.create_sheet(title="Dim_Dates")
ws_reasons = wb.create_sheet(title="Dim_DelayReasons")

# Load CSV data
fact_df = pd.read_csv(os.path.join(data_dir, "fact_flights.csv"))
airlines_df = pd.read_csv(os.path.join(data_dir, "dim_airlines.csv"))
airports_df = pd.read_csv(os.path.join(data_dir, "dim_airports.csv"))
dates_df = pd.read_csv(os.path.join(data_dir, "dim_dates.csv"))
reasons_df = pd.read_csv(os.path.join(data_dir, "dim_delay_reasons.csv"))

# Populate Dimension Sheets
for row in dataframe_to_rows(airlines_df, index=False, header=True):
    ws_airlines.append(row)

for row in dataframe_to_rows(airports_df, index=False, header=True):
    ws_airports.append(row)

for row in dataframe_to_rows(dates_df, index=False, header=True):
    ws_dates.append(row)

for row in dataframe_to_rows(reasons_df, index=False, header=True):
    ws_reasons.append(row)

# Populate Fact Sheet (Sample top 1000 rows for Excel size efficiency + formula demonstration)
fact_sample = fact_df.head(1000).copy()
for row in dataframe_to_rows(fact_sample, index=False, header=True):
    ws_fact.append(row)

# Add Excel Calculated Columns via Formulas on Fact Sheet
ws_fact.cell(row=1, column=len(fact_sample.columns)+1, value="AirlineName_XLOOKUP")
ws_fact.cell(row=1, column=len(fact_sample.columns)+2, value="OriginCity_XLOOKUP")
ws_fact.cell(row=1, column=len(fact_sample.columns)+3, value="DelayStatus_IF")

max_r = len(fact_sample) + 1
col_airline_id = fact_sample.columns.get_loc("AirlineID") + 1
col_origin_id = fact_sample.columns.get_loc("OriginAirportID") + 1
col_arr_delay = fact_sample.columns.get_loc("ArrDelayMinutes") + 1

for r in range(2, max_r + 1):
    # XLOOKUP formula for Airline Name
    ws_fact.cell(row=r, column=len(fact_sample.columns)+1, value=f'=XLOOKUP(E{r}, Dim_Airlines!A:A, Dim_Airlines!B:B, "Unknown")')
    # XLOOKUP formula for Origin City
    ws_fact.cell(row=r, column=len(fact_sample.columns)+2, value=f'=XLOOKUP(F{r}, Dim_Airports!A:A, Dim_Airports!D:D, "Unknown")')
    # IF formula for Delay Status
    ws_fact.cell(row=r, column=len(fact_sample.columns)+3, value=f'=IF(M{r}>=15, "Delayed", IF(N{r}=1, "Cancelled", "On-Time"))')

# --- DESIGN EXECUTIVE DASHBOARD TAB ---
ws_dash.views.sheetView[0].showGridLines = True

# Title Header
ws_dash.merge_cells("B2:K3")
title_cell = ws_dash["B2"]
title_cell.value = "✈️ AIRLINE FLIGHT DELAY ANALYTICS DASHBOARD"
title_cell.font = Font(name="Segoe UI", size=18, bold=True, color="FFFFFF")
title_cell.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
title_cell.alignment = Alignment(horizontal="center", vertical="center")

# Subtitle
ws_dash.merge_cells("B4:K4")
sub_cell = ws_dash["B4"]
sub_cell.value = "Key Performance Indicators (KPIs), Airline OTP Ranking & Cause Breakdown | Data Source: Operational Flights 2024"
sub_cell.font = Font(name="Segoe UI", size=10, italic=True, color="475569")
sub_cell.alignment = Alignment(horizontal="center", vertical="center")

# KPI Cards Block (Row 6 to Row 8)
kpis = [
    {"col_start": "B", "col_end": "C", "title": "TOTAL FLIGHTS", "formula": "=COUNT(Fact_Flights!A2:A1001)", "fmt": "#,##0", "color": "3B82F6"},
    {"col_start": "D", "col_end": "E", "title": "ON-TIME RATE (OTP %)", "formula": '=COUNTIFS(Fact_Flights!M2:M1001, "<15", Fact_Flights!N2:N1001, 0)/COUNT(Fact_Flights!A2:A1001)', "fmt": "0.0%", "color": "10B981"},
    {"col_start": "F", "col_end": "G", "title": "AVG ARRIVAL DELAY", "formula": "=AVERAGE(Fact_Flights!M2:M1001)", "fmt": '0.0" mins"', "color": "F59E0B"},
    {"col_start": "H", "col_end": "I", "title": "DELAYED FLIGHTS (>=15m)", "formula": '=COUNTIFS(Fact_Flights!M2:M1001, ">=15")', "fmt": "#,##0", "color": "EF4444"},
    {"col_start": "J", "col_end": "K", "title": "TOTAL FINANCIAL LOSS", "formula": "=SUM(Fact_Flights!V2:V1001)", "fmt": "$#,##0", "color": "8B5CF6"}
]

for kpi in kpis:
    # Header box
    h_cell = ws_dash[f"{kpi['col_start']}6"]
    ws_dash.merge_cells(f"{kpi['col_start']}6:{kpi['col_end']}6")
    h_cell.value = kpi["title"]
    h_cell.font = Font(name="Segoe UI", size=9, bold=True, color="FFFFFF")
    h_cell.fill = PatternFill(start_color=kpi["color"], end_color=kpi["color"], fill_type="solid")
    h_cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Value box
    v_cell = ws_dash[f"{kpi['col_start']}7"]
    ws_dash.merge_cells(f"{kpi['col_start']}7:{kpi['col_end']}8")
    v_cell.value = kpi["formula"]
    v_cell.font = Font(name="Segoe UI", size=16, bold=True, color="1E293B")
    v_cell.number_format = kpi["fmt"]
    v_cell.alignment = Alignment(horizontal="center", vertical="center")
    v_cell.fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

# Table 1: Airline Performance Summary Table (Row 11)
ws_dash.merge_cells("B11:G11")
t1_head = ws_dash["B11"]
t1_head.value = "📊 Airline Performance Summary (SUMIFS / AVERAGEIFS Formulas)"
t1_head.font = Font(name="Segoe UI", size=12, bold=True, color="1E3A8A")

headers_t1 = ["Airline Name", "Total Flights", "Delayed Flights", "OTP %", "Avg Delay (Mins)", "Total Delay Cost"]
cols_t1 = ["B", "C", "D", "E", "F", "G"]

for col_letter, h_text in zip(cols_t1, headers_t1):
    c = ws_dash[f"{col_letter}12"]
    c.value = h_text
    c.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    c.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    c.alignment = Alignment(horizontal="center", vertical="center")

# Fill sample airlines
sample_airlines = ["SkyWings Airlines", "Apex Airways", "BlueHorizon Air", "Pacific Express", "Eagle Jet", "SunCountry Global"]
for idx, al in enumerate(sample_airlines, start=13):
    ws_dash[f"B{idx}"] = al
    ws_dash[f"C{idx}"] = f'=COUNTIFS(Fact_Flights!W2:W1001, B{idx})'
    ws_dash[f"D{idx}"] = f'=COUNTIFS(Fact_Flights!W2:W1001, B{idx}, Fact_Flights!M2:M1001, ">=15")'
    ws_dash[f"E{idx}"] = f'=(C{idx}-D{idx})/C{idx}'
    ws_dash[f"F{idx}"] = f'=AVERAGEIFS(Fact_Flights!M2:M1001, Fact_Flights!W2:W1001, B{idx})'
    ws_dash[f"G{idx}"] = f'=SUMIFS(Fact_Flights!V2:V1001, Fact_Flights!W2:W1001, B{idx})'
    
    # Formats
    ws_dash[f"C{idx}"].number_format = "#,##0"
    ws_dash[f"D{idx}"].number_format = "#,##0"
    ws_dash[f"E{idx}"].number_format = "0.0%"
    ws_dash[f"F{idx}"].number_format = "0.0"
    ws_dash[f"G{idx}"].number_format = "$#,##0"

# Table 2: Delay Cause Breakdown Table (Row 11, Col I:K)
ws_dash.merge_cells("I11:K11")
t2_head = ws_dash["I11"]
t2_head.value = "⚠️ Delay Primary Cause Distribution"
t2_head.font = Font(name="Segoe UI", size=12, bold=True, color="1E3A8A")

headers_t2 = ["Delay Category", "Incident Count", "Avg Delay (Mins)"]
cols_t2 = ["I", "J", "K"]
for col_letter, h_text in zip(cols_t2, headers_t2):
    c = ws_dash[f"{col_letter}12"]
    c.value = h_text
    c.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    c.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    c.alignment = Alignment(horizontal="center", vertical="center")

causes = ["Carrier Delay", "Weather Delay", "NAS Delay", "Security Delay", "Late Aircraft Delay"]
for idx, cs in enumerate(causes, start=13):
    ws_dash[f"I{idx}"] = cs
    ws_dash[f"J{idx}"] = f'=COUNTIFS(Fact_Flights!P2:P1001, XLOOKUP(I{idx}, Dim_DelayReasons!B:B, Dim_DelayReasons!A:A))'
    ws_dash[f"K{idx}"] = f'=AVERAGEIFS(Fact_Flights!M2:M1001, Fact_Flights!P2:P1001, XLOOKUP(I{idx}, Dim_DelayReasons!B:B, Dim_DelayReasons!A:A))'
    
    ws_dash[f"J{idx}"].number_format = "#,##0"
    ws_dash[f"K{idx}"].number_format = "0.0"

# Save workbook
wb.save(excel_path)
print(f"Successfully generated Excel Dashboard at: {excel_path}")
