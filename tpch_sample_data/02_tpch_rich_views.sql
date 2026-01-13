/*
 * Script: 02_tpch_rich_views.sql
 * Purpose: Create TPCH_RICH_VIEWS schema with 7 analytical views
 *
 * This script creates views that provide different perspectives on the TPCH data:
 *   - V_DATE_DIM - Date dimension with time hierarchy
 *   - V_CUSTOMER_GEOGRAPHY - Denormalized customer with geography
 *   - V_SUPPLIER_GEOGRAPHY - Denormalized supplier with geography
 *   - V_ORDER_DETAIL - Order headers with customer info
 *   - V_LINEITEM_ENRICHED - Full lineitem context (33 columns)
 *   - V_DAILY_SALES_SUMMARY - Pre-aggregated daily sales
 *   - V_MONTHLY_REVENUE - Pre-aggregated monthly with YTD
 *
 * Prerequisites:
 *   - Run 01_tpch_rich_tables.sql first to create base tables
 *
 * Configuration:
 *   - Modify DB_NAME variable below to use a different database
 *
 * Execution:
 *   snow sql -f 02_tpch_rich_views.sql
 */

-- ============================================================================
-- CONFIGURATION
-- ============================================================================
SET DB_NAME = 'TPCH_RICH_DB';
SET BASE_SCHEMA = 'TPCH_RICH_TABLES';
SET VIEW_SCHEMA = 'TPCH_RICH_VIEWS';

-- ============================================================================
-- SETUP
-- ============================================================================
USE DATABASE IDENTIFIER($DB_NAME);
CREATE SCHEMA IF NOT EXISTS IDENTIFIER($VIEW_SCHEMA);
USE SCHEMA IDENTIFIER($VIEW_SCHEMA);

-- ============================================================================
-- VIEW: V_DATE_DIM
-- Date dimension with time hierarchy (derived from ORDERS dates)
-- ============================================================================
CREATE OR REPLACE VIEW V_DATE_DIM (
    DATE_KEY COMMENT 'Date key in YYYYMMDD format',
    FULL_DATE COMMENT 'Full date value',
    YEAR COMMENT 'Calendar year',
    QUARTER COMMENT 'Calendar quarter (1-4)',
    MONTH COMMENT 'Calendar month (1-12)',
    MONTH_NAME COMMENT 'Month name (January-December)',
    DAY_OF_MONTH COMMENT 'Day of month (1-31)',
    DAY_OF_WEEK COMMENT 'Day of week (0=Sunday to 6=Saturday)',
    WEEK_OF_YEAR COMMENT 'Week of year (1-53)',
    IS_WEEKEND COMMENT 'Weekend indicator (TRUE/FALSE)'
) COMMENT = 'Date dimension with time hierarchy attributes'
AS
SELECT DISTINCT
    TO_NUMBER(TO_CHAR(O_ORDERDATE, 'YYYYMMDD')) AS DATE_KEY,
    O_ORDERDATE AS FULL_DATE,
    YEAR(O_ORDERDATE) AS YEAR,
    QUARTER(O_ORDERDATE) AS QUARTER,
    MONTH(O_ORDERDATE) AS MONTH,
    MONTHNAME(O_ORDERDATE) AS MONTH_NAME,
    DAY(O_ORDERDATE) AS DAY_OF_MONTH,
    DAYOFWEEK(O_ORDERDATE) AS DAY_OF_WEEK,
    WEEKOFYEAR(O_ORDERDATE) AS WEEK_OF_YEAR,
    CASE WHEN DAYOFWEEK(O_ORDERDATE) IN (0, 6) THEN TRUE ELSE FALSE END AS IS_WEEKEND
FROM TPCH_RICH_TABLES.ORDERS
ORDER BY FULL_DATE;

-- ============================================================================
-- VIEW: V_CUSTOMER_GEOGRAPHY
-- Denormalized customer with full geography hierarchy
-- ============================================================================
CREATE OR REPLACE VIEW V_CUSTOMER_GEOGRAPHY (
    C_CUSTKEY COMMENT 'Unique customer identifier',
    CUSTOMER_NAME COMMENT 'Customer business name',
    CUSTOMER_ADDRESS COMMENT 'Customer street address',
    CUSTOMER_PHONE COMMENT 'Customer phone number including country and area code',
    ACCOUNT_BALANCE COMMENT 'Customer account balance - can be negative',
    MARKET_SEGMENT COMMENT 'Market segment (AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD, MACHINERY)',
    CUSTOMER_COMMENT COMMENT 'Free-form customer comments',
    NATION_NAME COMMENT 'Customer nation name',
    REGION_NAME COMMENT 'Customer geographic region (AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST)'
) COMMENT = 'Denormalized customer with full geography hierarchy'
AS
SELECT
    c.C_CUSTKEY,
    c.C_NAME AS CUSTOMER_NAME,
    c.C_ADDRESS AS CUSTOMER_ADDRESS,
    c.C_PHONE AS CUSTOMER_PHONE,
    c.C_ACCTBAL AS ACCOUNT_BALANCE,
    c.C_MKTSEGMENT AS MARKET_SEGMENT,
    c.C_COMMENT AS CUSTOMER_COMMENT,
    n.N_NAME AS NATION_NAME,
    r.R_NAME AS REGION_NAME
FROM TPCH_RICH_TABLES.CUSTOMER c
JOIN TPCH_RICH_TABLES.NATION n ON c.C_NATIONKEY = n.N_NATIONKEY
JOIN TPCH_RICH_TABLES.REGION r ON n.N_REGIONKEY = r.R_REGIONKEY;

-- ============================================================================
-- VIEW: V_SUPPLIER_GEOGRAPHY
-- Denormalized supplier with full geography hierarchy
-- ============================================================================
CREATE OR REPLACE VIEW V_SUPPLIER_GEOGRAPHY (
    S_SUPPKEY COMMENT 'Unique supplier identifier',
    SUPPLIER_NAME COMMENT 'Supplier business name',
    SUPPLIER_ADDRESS COMMENT 'Supplier street address',
    SUPPLIER_PHONE COMMENT 'Supplier phone number',
    ACCOUNT_BALANCE COMMENT 'Supplier account balance',
    SUPPLIER_COMMENT COMMENT 'Free-form supplier comments',
    NATION_NAME COMMENT 'Supplier nation name',
    REGION_NAME COMMENT 'Supplier geographic region'
) COMMENT = 'Denormalized supplier with full geography hierarchy'
AS
SELECT
    s.S_SUPPKEY,
    s.S_NAME AS SUPPLIER_NAME,
    s.S_ADDRESS AS SUPPLIER_ADDRESS,
    s.S_PHONE AS SUPPLIER_PHONE,
    s.S_ACCTBAL AS ACCOUNT_BALANCE,
    s.S_COMMENT AS SUPPLIER_COMMENT,
    n.N_NAME AS NATION_NAME,
    r.R_NAME AS REGION_NAME
FROM TPCH_RICH_TABLES.SUPPLIER s
JOIN TPCH_RICH_TABLES.NATION n ON s.S_NATIONKEY = n.N_NATIONKEY
JOIN TPCH_RICH_TABLES.REGION r ON n.N_REGIONKEY = r.R_REGIONKEY;

-- ============================================================================
-- VIEW: V_ORDER_DETAIL
-- Order headers with customer and geography information
-- ============================================================================
CREATE OR REPLACE VIEW V_ORDER_DETAIL (
    O_ORDERKEY COMMENT 'Unique order identifier',
    ORDER_DATE COMMENT 'Date when order was placed',
    ORDER_TOTAL COMMENT 'Total order value in dollars',
    ORDER_STATUS COMMENT 'Order status (F=Fulfilled, O=Open, P=Pending)',
    ORDER_PRIORITY COMMENT 'Order priority level (1-URGENT to 5-LOW)',
    CLERK COMMENT 'Clerk who processed the order',
    SHIP_PRIORITY COMMENT 'Shipping priority indicator',
    ORDER_COMMENT COMMENT 'Free-form order comments',
    C_CUSTKEY COMMENT 'Customer key (foreign key to CUSTOMER)',
    CUSTOMER_NAME COMMENT 'Customer business name',
    MARKET_SEGMENT COMMENT 'Customer market segment',
    CUSTOMER_ACCTBAL COMMENT 'Customer account balance',
    NATION_NAME COMMENT 'Customer nation name',
    REGION_NAME COMMENT 'Customer geographic region'
) COMMENT = 'Order header with customer information for order analysis'
AS
SELECT
    o.O_ORDERKEY,
    o.O_ORDERDATE AS ORDER_DATE,
    o.O_TOTALPRICE AS ORDER_TOTAL,
    o.O_ORDERSTATUS AS ORDER_STATUS,
    o.O_ORDERPRIORITY AS ORDER_PRIORITY,
    o.O_CLERK AS CLERK,
    o.O_SHIPPRIORITY AS SHIP_PRIORITY,
    o.O_COMMENT AS ORDER_COMMENT,
    c.C_CUSTKEY,
    c.C_NAME AS CUSTOMER_NAME,
    c.C_MKTSEGMENT AS MARKET_SEGMENT,
    c.C_ACCTBAL AS CUSTOMER_ACCTBAL,
    n.N_NAME AS NATION_NAME,
    r.R_NAME AS REGION_NAME
FROM TPCH_RICH_TABLES.ORDERS o
JOIN TPCH_RICH_TABLES.CUSTOMER c ON o.O_CUSTKEY = c.C_CUSTKEY
JOIN TPCH_RICH_TABLES.NATION n ON c.C_NATIONKEY = n.N_NATIONKEY
JOIN TPCH_RICH_TABLES.REGION r ON n.N_REGIONKEY = r.R_REGIONKEY;

-- ============================================================================
-- VIEW: V_DAILY_SALES_SUMMARY
-- Pre-aggregated daily sales by region and segment
-- ============================================================================
CREATE OR REPLACE VIEW V_DAILY_SALES_SUMMARY (
    SALE_DATE COMMENT 'Date of sales transactions',
    REGION_NAME COMMENT 'Geographic region name',
    MARKET_SEGMENT COMMENT 'Customer market segment',
    ORDER_COUNT COMMENT 'Number of orders on this date',
    TOTAL_REVENUE COMMENT 'Total revenue for the day in dollars',
    AVG_ORDER_VALUE COMMENT 'Average order value for the day'
) COMMENT = 'Pre-aggregated daily sales summary by region and segment'
AS
SELECT
    o.O_ORDERDATE AS SALE_DATE,
    r.R_NAME AS REGION_NAME,
    c.C_MKTSEGMENT AS MARKET_SEGMENT,
    COUNT(DISTINCT o.O_ORDERKEY) AS ORDER_COUNT,
    SUM(o.O_TOTALPRICE) AS TOTAL_REVENUE,
    AVG(o.O_TOTALPRICE) AS AVG_ORDER_VALUE
FROM TPCH_RICH_TABLES.ORDERS o
JOIN TPCH_RICH_TABLES.CUSTOMER c ON o.O_CUSTKEY = c.C_CUSTKEY
JOIN TPCH_RICH_TABLES.NATION n ON c.C_NATIONKEY = n.N_NATIONKEY
JOIN TPCH_RICH_TABLES.REGION r ON n.N_REGIONKEY = r.R_REGIONKEY
GROUP BY o.O_ORDERDATE, r.R_NAME, c.C_MKTSEGMENT;

-- ============================================================================
-- VIEW: V_MONTHLY_REVENUE
-- Pre-aggregated monthly revenue with YTD calculations
-- ============================================================================
CREATE OR REPLACE VIEW V_MONTHLY_REVENUE (
    YEAR COMMENT 'Calendar year',
    MONTH COMMENT 'Calendar month (1-12)',
    REGION_NAME COMMENT 'Geographic region name',
    MONTHLY_REVENUE COMMENT 'Total revenue for the month in dollars',
    CUMULATIVE_YTD_REVENUE COMMENT 'Year-to-date cumulative revenue',
    ORDER_COUNT COMMENT 'Number of orders in the month',
    MONTH_NAME COMMENT 'Month name (January-December)',
    YEAR_MONTH COMMENT 'Year-month in YYYY-MM format'
) COMMENT = 'Pre-aggregated monthly revenue with YTD calculations by region'
AS
SELECT
    YEAR(o.O_ORDERDATE) AS YEAR,
    MONTH(o.O_ORDERDATE) AS MONTH,
    r.R_NAME AS REGION_NAME,
    SUM(o.O_TOTALPRICE) AS MONTHLY_REVENUE,
    SUM(SUM(o.O_TOTALPRICE)) OVER (
        PARTITION BY r.R_NAME, YEAR(o.O_ORDERDATE)
        ORDER BY MONTH(o.O_ORDERDATE)
    ) AS CUMULATIVE_YTD_REVENUE,
    COUNT(DISTINCT o.O_ORDERKEY) AS ORDER_COUNT,
    MONTHNAME(o.O_ORDERDATE) AS MONTH_NAME,
    TO_CHAR(o.O_ORDERDATE, 'YYYY-MM') AS YEAR_MONTH
FROM TPCH_RICH_TABLES.ORDERS o
JOIN TPCH_RICH_TABLES.CUSTOMER c ON o.O_CUSTKEY = c.C_CUSTKEY
JOIN TPCH_RICH_TABLES.NATION n ON c.C_NATIONKEY = n.N_NATIONKEY
JOIN TPCH_RICH_TABLES.REGION r ON n.N_REGIONKEY = r.R_REGIONKEY
GROUP BY YEAR(o.O_ORDERDATE), MONTH(o.O_ORDERDATE), r.R_NAME, MONTHNAME(o.O_ORDERDATE), TO_CHAR(o.O_ORDERDATE, 'YYYY-MM');

-- ============================================================================
-- VIEW: V_LINEITEM_ENRICHED
-- Full lineitem context with all related dimensions
-- ============================================================================
CREATE OR REPLACE VIEW V_LINEITEM_ENRICHED (
    L_ORDERKEY COMMENT 'Order key (foreign key to ORDERS)',
    L_LINENUMBER COMMENT 'Line number within the order',
    L_QUANTITY COMMENT 'Quantity ordered',
    L_EXTENDEDPRICE COMMENT 'Extended price (quantity * unit price)',
    L_DISCOUNT COMMENT 'Discount percentage (0.00 to 0.10)',
    L_TAX COMMENT 'Tax percentage',
    L_RETURNFLAG COMMENT 'Return flag (A=returned and accepted, N=not returned, R=returned)',
    L_LINESTATUS COMMENT 'Line status (F=shipped, O=not shipped)',
    L_SHIPDATE COMMENT 'Date line item was shipped',
    L_COMMITDATE COMMENT 'Committed delivery date',
    L_RECEIPTDATE COMMENT 'Actual receipt date',
    L_SHIPINSTRUCT COMMENT 'Shipping instructions',
    L_SHIPMODE COMMENT 'Shipping mode (AIR, FOB, MAIL, RAIL, REG AIR, SHIP, TRUCK)',
    L_COMMENT COMMENT 'Line item comments',
    ORDER_DATE COMMENT 'Date when order was placed',
    ORDER_STATUS COMMENT 'Order status (F=Fulfilled, O=Open, P=Pending)',
    ORDER_PRIORITY COMMENT 'Order priority level (1-URGENT to 5-LOW)',
    ORDER_TOTAL COMMENT 'Total order value in dollars',
    CUSTOMER_NAME COMMENT 'Customer business name',
    MARKET_SEGMENT COMMENT 'Customer market segment',
    CUSTOMER_REGION COMMENT 'Customer geographic region',
    CUSTOMER_NATION COMMENT 'Customer nation name',
    PART_NAME COMMENT 'Full part name describing the product',
    BRAND COMMENT 'Part brand (Brand#11 to Brand#55)',
    PART_TYPE COMMENT 'Part type description',
    PART_SIZE COMMENT 'Part size measurement (1-50)',
    CONTAINER COMMENT 'Part container type (SM BOX, LG CASE, etc.)',
    RETAIL_PRICE COMMENT 'Suggested retail price',
    SUPPLIER_NAME COMMENT 'Supplier business name',
    SUPPLIER_REGION COMMENT 'Supplier geographic region',
    SUPPLIER_NATION COMMENT 'Supplier nation name',
    NET_PRICE COMMENT 'Net price after discount',
    TAX_AMOUNT COMMENT 'Tax amount in dollars'
) COMMENT = 'Lineitem fact with full context from orders, customer, part, supplier and geography'
AS
SELECT
    l.L_ORDERKEY,
    l.L_LINENUMBER,
    l.L_QUANTITY,
    l.L_EXTENDEDPRICE,
    l.L_DISCOUNT,
    l.L_TAX,
    l.L_RETURNFLAG,
    l.L_LINESTATUS,
    l.L_SHIPDATE,
    l.L_COMMITDATE,
    l.L_RECEIPTDATE,
    l.L_SHIPINSTRUCT,
    l.L_SHIPMODE,
    l.L_COMMENT,
    o.O_ORDERDATE AS ORDER_DATE,
    o.O_ORDERSTATUS AS ORDER_STATUS,
    o.O_ORDERPRIORITY AS ORDER_PRIORITY,
    o.O_TOTALPRICE AS ORDER_TOTAL,
    c.C_NAME AS CUSTOMER_NAME,
    c.C_MKTSEGMENT AS MARKET_SEGMENT,
    cr.R_NAME AS CUSTOMER_REGION,
    cn.N_NAME AS CUSTOMER_NATION,
    p.P_NAME AS PART_NAME,
    p.P_BRAND AS BRAND,
    p.P_TYPE AS PART_TYPE,
    p.P_SIZE AS PART_SIZE,
    p.P_CONTAINER AS CONTAINER,
    p.P_RETAILPRICE AS RETAIL_PRICE,
    s.S_NAME AS SUPPLIER_NAME,
    sr.R_NAME AS SUPPLIER_REGION,
    sn.N_NAME AS SUPPLIER_NATION,
    l.L_EXTENDEDPRICE * (1 - l.L_DISCOUNT) AS NET_PRICE,
    l.L_EXTENDEDPRICE * l.L_TAX AS TAX_AMOUNT
FROM TPCH_RICH_TABLES.LINEITEM l
JOIN TPCH_RICH_TABLES.ORDERS o ON l.L_ORDERKEY = o.O_ORDERKEY
JOIN TPCH_RICH_TABLES.CUSTOMER c ON o.O_CUSTKEY = c.C_CUSTKEY
JOIN TPCH_RICH_TABLES.NATION cn ON c.C_NATIONKEY = cn.N_NATIONKEY
JOIN TPCH_RICH_TABLES.REGION cr ON cn.N_REGIONKEY = cr.R_REGIONKEY
JOIN TPCH_RICH_TABLES.PART p ON l.L_PARTKEY = p.P_PARTKEY
JOIN TPCH_RICH_TABLES.SUPPLIER s ON l.L_SUPPKEY = s.S_SUPPKEY
JOIN TPCH_RICH_TABLES.NATION sn ON s.S_NATIONKEY = sn.N_NATIONKEY
JOIN TPCH_RICH_TABLES.REGION sr ON sn.N_REGIONKEY = sr.R_REGIONKEY;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'V_DATE_DIM' AS VIEW_NAME, COUNT(*) AS ROW_COUNT FROM V_DATE_DIM
UNION ALL SELECT 'V_CUSTOMER_GEOGRAPHY', COUNT(*) FROM V_CUSTOMER_GEOGRAPHY
UNION ALL SELECT 'V_SUPPLIER_GEOGRAPHY', COUNT(*) FROM V_SUPPLIER_GEOGRAPHY
UNION ALL SELECT 'V_ORDER_DETAIL', COUNT(*) FROM V_ORDER_DETAIL
UNION ALL SELECT 'V_DAILY_SALES_SUMMARY', COUNT(*) FROM V_DAILY_SALES_SUMMARY
UNION ALL SELECT 'V_MONTHLY_REVENUE', COUNT(*) FROM V_MONTHLY_REVENUE
UNION ALL SELECT 'V_LINEITEM_ENRICHED', COUNT(*) FROM V_LINEITEM_ENRICHED
ORDER BY VIEW_NAME;

SELECT 'Script 02_tpch_rich_views.sql completed successfully!' AS STATUS;
