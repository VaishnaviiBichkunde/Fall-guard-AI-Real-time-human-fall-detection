-- ====================================================================
-- AIRLINE FLIGHT DELAY ANALYSIS - DATABASE SCHEMA & ANALYTICS QUERIES
-- RDBMS: MySQL / PostgreSQL / SQL Server / SQLite compatible
-- Author: Data Analytics Portfolio Project
-- ====================================================================

-- --------------------------------------------------------------------
-- 1. DATABASE & TABLE CREATION (STAR SCHEMA)
-- --------------------------------------------------------------------

-- Dimension: Airlines
CREATE TABLE dim_airlines (
    AirlineID INT PRIMARY KEY,
    AirlineName VARCHAR(100) NOT NULL,
    IATA_Code VARCHAR(5) NOT NULL,
    FleetSize INT,
    HubAirport VARCHAR(10)
);

-- Dimension: Airports
CREATE TABLE dim_airports (
    AirportID INT PRIMARY KEY,
    AirportCode VARCHAR(5) NOT NULL,
    AirportName VARCHAR(150) NOT NULL,
    City VARCHAR(100),
    State VARCHAR(50),
    Region VARCHAR(50)
);

-- Dimension: Date Calendar
CREATE TABLE dim_dates (
    DateKey INT PRIMARY KEY, -- Format YYYYMMDD
    FullDate DATE NOT NULL,
    Year INT NOT NULL,
    Quarter VARCHAR(5) NOT NULL,
    Month INT NOT NULL,
    MonthName VARCHAR(20) NOT NULL,
    DayOfWeek VARCHAR(15) NOT NULL,
    IsWeekend VARCHAR(5) NOT NULL,
    Season VARCHAR(20) NOT NULL
);

-- Dimension: Delay Categories
CREATE TABLE dim_delay_reasons (
    DelayCategoryID INT PRIMARY KEY,
    CategoryName VARCHAR(50) NOT NULL,
    Description TEXT,
    ControllableByAirline VARCHAR(5) NOT NULL
);

-- Fact: Flights
CREATE TABLE fact_flights (
    FlightID INT PRIMARY KEY,
    FlightNumber VARCHAR(20) NOT NULL,
    FlightDate DATE NOT NULL,
    DateKey INT NOT NULL,
    AirlineID INT NOT NULL,
    OriginAirportID INT NOT NULL,
    DestAirportID INT NOT NULL,
    ScheduledDepHour INT NOT NULL,
    ScheduledDepTime VARCHAR(10),
    DistanceMiles INT,
    DepDelayMinutes INT DEFAULT 0,
    ArrDelayMinutes INT DEFAULT 0,
    IsDelayed INT DEFAULT 0,
    IsCancelled INT DEFAULT 0,
    IsDiverted INT DEFAULT 0,
    PrimaryDelayCategoryID INT,
    CarrierDelayMins INT DEFAULT 0,
    WeatherDelayMins INT DEFAULT 0,
    NASDelayMins INT DEFAULT 0,
    SecurityDelayMins INT DEFAULT 0,
    LateAircraftDelayMins INT DEFAULT 0,
    DelayCostUSD DECIMAL(10, 2) DEFAULT 0.00,
    
    FOREIGN KEY (DateKey) REFERENCES dim_dates(DateKey),
    FOREIGN KEY (AirlineID) REFERENCES dim_airlines(AirlineID),
    FOREIGN KEY (OriginAirportID) REFERENCES dim_airports(AirportID),
    FOREIGN KEY (DestAirportID) REFERENCES dim_airports(AirportID),
    FOREIGN KEY (PrimaryDelayCategoryID) REFERENCES dim_delay_reasons(DelayCategoryID)
);

-- Indexing for Query Performance Optimization
CREATE INDEX idx_fact_date ON fact_flights(DateKey);
CREATE INDEX idx_fact_airline ON fact_flights(AirlineID);
CREATE INDEX idx_fact_origin ON fact_flights(OriginAirportID);
CREATE INDEX idx_fact_dest ON fact_flights(DestAirportID);


-- --------------------------------------------------------------------
-- 2. BUSINESS ANALYTICS & KPI SQL QUERIES
-- --------------------------------------------------------------------

-- QUERY 1: Executive KPI Summary (Total Flights, OTP %, Avg Delay, Total Cost)
SELECT 
    COUNT(f.FlightID) AS TotalFlights,
    SUM(CASE WHEN f.IsDelayed = 0 AND f.IsCancelled = 0 THEN 1 ELSE 0 END) AS OnTimeFlights,
    ROUND(
        (SUM(CASE WHEN f.IsDelayed = 0 AND f.IsCancelled = 0 THEN 1 ELSE 0 END) * 100.0) / COUNT(f.FlightID), 
        2
    ) AS OnTimePerformanceRate_Pct,
    SUM(f.IsDelayed) AS DelayedFlightsCount,
    ROUND((SUM(f.IsDelayed) * 100.0) / COUNT(f.FlightID), 2) AS DelayRate_Pct,
    SUM(f.IsCancelled) AS CancelledFlightsCount,
    ROUND(AVG(f.ArrDelayMinutes), 1) AS AvgArrivalDelayMinutes,
    ROUND(AVG(CASE WHEN f.ArrDelayMinutes > 0 THEN f.ArrDelayMinutes END), 1) AS AvgDelayWhenDelayedMinutes,
    SUM(f.DelayCostUSD) AS TotalDelayCostUSD
FROM fact_flights f;


-- QUERY 2: Airline On-Time Performance (OTP) Ranking & Financial Impact
SELECT 
    a.AirlineName,
    a.IATA_Code,
    COUNT(f.FlightID) AS TotalOperatedFlights,
    SUM(f.IsDelayed) AS DelayedFlights,
    ROUND(
        ((COUNT(f.FlightID) - SUM(f.IsDelayed) - SUM(f.IsCancelled)) * 100.0) / COUNT(f.FlightID), 
        2
    ) AS OTP_Percentage,
    ROUND(AVG(f.DepDelayMinutes), 1) AS AvgDepDelayMins,
    ROUND(AVG(f.ArrDelayMinutes), 1) AS AvgArrDelayMins,
    SUM(f.DelayCostUSD) AS TotalFinancialLossUSD,
    DENSE_RANK() OVER (
        ORDER BY ((COUNT(f.FlightID) - SUM(f.IsDelayed) - SUM(f.IsCancelled)) * 100.0) / COUNT(f.FlightID) DESC
    ) AS AirlineRankByOTP
FROM fact_flights f
JOIN dim_airlines a ON f.AirlineID = a.AirlineID
GROUP BY a.AirlineID, a.AirlineName, a.IATA_Code
ORDER BY OTP_Percentage DESC;


-- QUERY 3: Breakdown of Delays by Cause (Controllable vs Uncontrollable)
SELECT 
    r.CategoryName,
    r.ControllableByAirline,
    COUNT(f.FlightID) AS IncidentCount,
    SUM(f.ArrDelayMinutes) AS TotalDelayMinutes,
    ROUND(AVG(f.ArrDelayMinutes), 1) AS AvgDelayDurationMins,
    ROUND(
        (SUM(f.ArrDelayMinutes) * 100.0) / (SELECT SUM(ArrDelayMinutes) FROM fact_flights WHERE IsDelayed = 1), 
        2
    ) AS ShareOfTotalDelayTime_Pct
FROM fact_flights f
JOIN dim_delay_reasons r ON f.PrimaryDelayCategoryID = r.DelayCategoryID
WHERE f.IsDelayed = 1
GROUP BY r.CategoryName, r.ControllableByAirline
ORDER BY TotalDelayMinutes DESC;


-- QUERY 4: Monthly & Seasonal Delay Trends Analysis
SELECT 
    d.Year,
    d.Month,
    d.MonthName,
    d.Season,
    COUNT(f.FlightID) AS TotalFlights,
    SUM(f.IsDelayed) AS DelayedFlights,
    ROUND((SUM(f.IsDelayed) * 100.0) / COUNT(f.FlightID), 2) AS MonthlyDelayRate_Pct,
    ROUND(AVG(f.ArrDelayMinutes), 1) AS AvgArrivalDelayMins,
    SUM(f.CarrierDelayMins) AS TotalCarrierDelayMins,
    SUM(f.WeatherDelayMins) AS TotalWeatherDelayMins,
    SUM(f.NASDelayMins) AS TotalNASDelayMins
FROM fact_flights f
JOIN dim_dates d ON f.DateKey = d.DateKey
GROUP BY d.Year, d.Month, d.MonthName, d.Season
ORDER BY d.Month ASC;


-- QUERY 5: Top 10 Most Delayed Airport Routes (Origin -> Destination pair)
SELECT 
    o.AirportCode AS OriginCode,
    o.City AS OriginCity,
    d.AirportCode AS DestCode,
    d.City AS DestCity,
    COUNT(f.FlightID) AS RouteFlightVolume,
    SUM(f.IsDelayed) AS RouteDelayedFlights,
    ROUND((SUM(f.IsDelayed) * 100.0) / COUNT(f.FlightID), 2) AS RouteDelayRate_Pct,
    ROUND(AVG(f.ArrDelayMinutes), 1) AS AvgRouteDelayMins,
    SUM(f.DelayCostUSD) AS TotalRouteDelayCostUSD
FROM fact_flights f
JOIN dim_airports o ON f.OriginAirportID = o.AirportID
JOIN dim_airports d ON f.DestAirportID = d.AirportID
GROUP BY o.AirportCode, o.City, d.AirportCode, d.City
HAVING COUNT(f.FlightID) >= 20
ORDER BY RouteDelayRate_Pct DESC, AvgRouteDelayMins DESC
LIMIT 10;


-- QUERY 6: Departure Hour Risk Profile (Peak Hour Delay Heatmap Data)
SELECT 
    f.ScheduledDepHour,
    CONCAT(f.ScheduledDepHour, ':00 - ', f.ScheduledDepHour, ':59') AS TimeWindow,
    COUNT(f.FlightID) AS ScheduledFlights,
    SUM(f.IsDelayed) AS DelayedFlights,
    ROUND((SUM(f.IsDelayed) * 100.0) / COUNT(f.FlightID), 2) AS HourlyDelayRisk_Pct,
    ROUND(AVG(f.DepDelayMinutes), 1) AS AvgDepDelayMins
FROM fact_flights f
GROUP BY f.ScheduledDepHour
ORDER BY f.ScheduledDepHour ASC;


-- QUERY 7: Weekend vs Weekday Delay Comparison
SELECT 
    d.IsWeekend,
    COUNT(f.FlightID) AS TotalFlights,
    SUM(f.IsDelayed) AS DelayedFlights,
    ROUND((SUM(f.IsDelayed) * 100.0) / COUNT(f.FlightID), 2) AS DelayRate_Pct,
    ROUND(AVG(f.ArrDelayMinutes), 1) AS AvgDelayMins
FROM fact_flights f
JOIN dim_dates d ON f.DateKey = d.DateKey
GROUP BY d.IsWeekend;
