/*
 * Script: 03_tpch_rich_svs.sql
 * Purpose: Create TPCH_RICH_SVS schema with 13 Snowflake Semantic Views
 *
 * This script creates semantic views demonstrating various patterns:
 *   - SV_REGIONAL_SALES - 2-table star schema
 *   - SV_PRODUCT_PERFORMANCE - 2-table product focus
 *   - SV_CUSTOMER_ORDERS - Full star schema
 *   - SV_SUPPLIER_ANALYSIS - Mixed tables with geography
 *   - SV_LINEITEM_DETAIL - Star with FACTS for drill-through
 *   - SV_DAILY_SALES - Pre-aggregated view base
 *   - SV_MONTHLY_TRENDS - Time-based with YTD
 *   - SV_SUPPLY_CHAIN - M:M relationship via PARTSUPP
 *   - SV_SHIPPING_ANALYSIS - Date hierarchies with transit metrics
 *   - SV_CUSTOMER_VALUE - Calculated lifetime metrics
 *   - SV_SALES_ANALYSIS - Sales with customer geography (single-path)
 *   - SV_PRODUCT_SUPPLY - Product analysis (single-path)
 *   - SV_SUPPLIER_INVENTORY - Supplier inventory (single-path)
 *
 * Prerequisites:
 *   - Run 01_tpch_rich_tables.sql first to create base tables
 *   - Run 02_tpch_rich_views.sql to create supporting views
 *   - Snowflake account with Semantic Views enabled (requires Enterprise+)
 *
 * Configuration:
 *   - Modify DB_NAME variable below to use a different database
 *
 * Execution:
 *   snow sql -f 03_tpch_rich_svs.sql
 */

-- ============================================================================
-- CONFIGURATION
-- ============================================================================
SET DB_NAME = 'TPCH_RICH_DB';
SET BASE_SCHEMA = 'TPCH_RICH_TABLES';
SET VIEW_SCHEMA = 'TPCH_RICH_VIEWS';
SET SV_SCHEMA = 'TPCH_RICH_SVS';

-- ============================================================================
-- SETUP
-- ============================================================================
USE DATABASE IDENTIFIER($DB_NAME);
CREATE SCHEMA IF NOT EXISTS IDENTIFIER($SV_SCHEMA);
USE SCHEMA IDENTIFIER($SV_SCHEMA);

-- ============================================================================
-- SEMANTIC VIEW: SV_REGIONAL_SALES
-- Pattern: 2-table star schema (Orders -> Customer geography)
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_REGIONAL_SALES
TABLES (
    TPCH_RICH_TABLES.ORDERS PRIMARY KEY (O_ORDERKEY),
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    ORDER_CUSTOMER AS ORDERS(O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY),
    CUSTOMER_NATION AS CUSTOMER(C_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
DIMENSIONS (
    ORDERS.ORDER_STATUS AS O_ORDERSTATUS COMMENT = 'Order status: F=Fulfilled, O=Open, P=Pending',
    ORDERS.ORDER_PRIORITY AS O_ORDERPRIORITY COMMENT = 'Order priority (1-URGENT to 5-LOW)',
    CUSTOMER.MARKET_SEGMENT AS C_MKTSEGMENT COMMENT = 'Market segment (AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD, MACHINERY)',
    NATION.NATION_NAME AS N_NAME COMMENT = 'Nation name (e.g., UNITED STATES, CHINA, GERMANY)',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Region name (AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST)'
)
METRICS (
    ORDERS.TOTAL_REVENUE AS SUM(O_TOTALPRICE) COMMENT = 'Total order value in dollars',
    ORDERS.ORDER_COUNT AS COUNT(O_ORDERKEY) COMMENT = 'Number of orders placed',
    ORDERS.AVG_ORDER_VALUE AS AVG(O_TOTALPRICE) COMMENT = 'Average order value in dollars'
)
COMMENT = 'Regional sales analysis - 2-table star schema joining Orders to Customer geography';

-- ============================================================================
-- SEMANTIC VIEW: SV_PRODUCT_PERFORMANCE
-- Pattern: 2-table model (Lineitem -> Part)
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_PRODUCT_PERFORMANCE
TABLES (
    TPCH_RICH_TABLES.LINEITEM PRIMARY KEY (L_ORDERKEY, L_LINENUMBER),
    TPCH_RICH_TABLES.PART PRIMARY KEY (P_PARTKEY)
)
RELATIONSHIPS (
    LINEITEM_PART AS LINEITEM(L_PARTKEY) REFERENCES PART(P_PARTKEY)
)
DIMENSIONS (
    PART.BRAND AS P_BRAND COMMENT = 'Part brand (Brand#11 to Brand#55)',
    PART.TYPE AS P_TYPE COMMENT = 'Part type description',
    PART.SIZE AS P_SIZE COMMENT = 'Part size measurement (1-50)',
    PART.CONTAINER AS P_CONTAINER COMMENT = 'Part container type (SM BOX, LG CASE, etc.)',
    PART.MANUFACTURER AS P_MFGR COMMENT = 'Part manufacturer (Manufacturer#1 to Manufacturer#5)',
    LINEITEM.RETURN_FLAG AS L_RETURNFLAG COMMENT = 'Return flag (A=returned and accepted, N=not returned, R=returned)',
    LINEITEM.LINE_STATUS AS L_LINESTATUS COMMENT = 'Line status (F=shipped, O=not shipped)',
    LINEITEM.SHIP_MODE AS L_SHIPMODE COMMENT = 'Shipping mode (AIR, FOB, MAIL, RAIL, REG AIR, SHIP, TRUCK)'
)
METRICS (
    LINEITEM.TOTAL_EXTENDED_PRICE AS SUM(L_EXTENDEDPRICE) COMMENT = 'Total extended price (quantity * unit price)',
    LINEITEM.TOTAL_QUANTITY AS SUM(L_QUANTITY) COMMENT = 'Total quantity ordered',
    LINEITEM.AVG_DISCOUNT AS AVG(L_DISCOUNT) COMMENT = 'Average discount percentage',
    LINEITEM.NET_REVENUE AS SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT)) COMMENT = 'Net revenue after discounts',
    LINEITEM.LINE_COUNT AS COUNT(*) COMMENT = 'Count of line items'
)
COMMENT = 'Product performance analysis - 2-table model joining Lineitem to Part';

-- ============================================================================
-- SEMANTIC VIEW: SV_CUSTOMER_ORDERS
-- Pattern: Full star schema with all dimensions
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_CUSTOMER_ORDERS
TABLES (
    TPCH_RICH_TABLES.ORDERS PRIMARY KEY (O_ORDERKEY),
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    ORDER_CUSTOMER AS ORDERS(O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY),
    CUSTOMER_NATION AS CUSTOMER(C_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
DIMENSIONS (
    ORDERS.ORDER_DATE AS O_ORDERDATE COMMENT = 'Date when order was placed',
    ORDERS.ORDER_STATUS AS O_ORDERSTATUS COMMENT = 'Order status (F=Fulfilled, O=Open, P=Pending)',
    ORDERS.ORDER_PRIORITY AS O_ORDERPRIORITY COMMENT = 'Order priority level (1-URGENT to 5-LOW)',
    ORDERS.CLERK AS O_CLERK COMMENT = 'Clerk who processed the order',
    CUSTOMER.CUSTOMER_NAME AS C_NAME COMMENT = 'Customer business name',
    CUSTOMER.MARKET_SEGMENT AS C_MKTSEGMENT COMMENT = 'Market segment (AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD, MACHINERY)',
    NATION.NATION_NAME AS N_NAME COMMENT = 'Nation name',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Region name (AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST)'
)
METRICS (
    ORDERS.TOTAL_REVENUE AS SUM(O_TOTALPRICE) COMMENT = 'Total order value in dollars',
    ORDERS.ORDER_COUNT AS COUNT(O_ORDERKEY) COMMENT = 'Number of orders placed',
    ORDERS.AVG_ORDER_VALUE AS AVG(O_TOTALPRICE) COMMENT = 'Average order value in dollars',
    CUSTOMER.CUSTOMER_COUNT AS COUNT(DISTINCT C_CUSTKEY) COMMENT = 'Count of unique customers'
)
COMMENT = 'Complete customer order analysis - full star schema with all dimensions';

-- ============================================================================
-- SEMANTIC VIEW: SV_SUPPLIER_ANALYSIS
-- Pattern: Mixed tables with geography
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_SUPPLIER_ANALYSIS
TABLES (
    TPCH_RICH_TABLES.SUPPLIER PRIMARY KEY (S_SUPPKEY),
    TPCH_RICH_TABLES.PARTSUPP PRIMARY KEY (PS_PARTKEY, PS_SUPPKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    SUPPLIER_NATION AS SUPPLIER(S_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY),
    PARTSUPP_SUPPLIER AS PARTSUPP(PS_SUPPKEY) REFERENCES SUPPLIER(S_SUPPKEY)
)
DIMENSIONS (
    SUPPLIER.SUPPLIER_NAME AS S_NAME COMMENT = 'Supplier business name',
    NATION.NATION_NAME AS N_NAME COMMENT = 'Supplier nation name',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Supplier geographic region'
)
METRICS (
    SUPPLIER.SUPPLIER_COUNT AS COUNT(DISTINCT S_SUPPKEY) COMMENT = 'Count of unique suppliers',
    SUPPLIER.AVG_ACCT_BAL AS AVG(S_ACCTBAL) COMMENT = 'Average supplier account balance',
    PARTSUPP.TOTAL_SUPPLY_COST AS SUM(PS_SUPPLYCOST) COMMENT = 'Total supply cost',
    PARTSUPP.TOTAL_AVAIL_QTY AS SUM(PS_AVAILQTY) COMMENT = 'Total available quantity',
    PARTSUPP.AVG_SUPPLY_COST AS AVG(PS_SUPPLYCOST) COMMENT = 'Average supply cost'
)
COMMENT = 'Supplier performance analysis - mixed tables with nation/region geography';

-- ============================================================================
-- SEMANTIC VIEW: SV_LINEITEM_DETAIL
-- Pattern: Star with FACTS for drill-through
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_LINEITEM_DETAIL
TABLES (
    TPCH_RICH_TABLES.LINEITEM PRIMARY KEY (L_ORDERKEY, L_LINENUMBER),
    TPCH_RICH_TABLES.ORDERS PRIMARY KEY (O_ORDERKEY),
    TPCH_RICH_TABLES.PART PRIMARY KEY (P_PARTKEY),
    TPCH_RICH_TABLES.SUPPLIER PRIMARY KEY (S_SUPPKEY),
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    LINEITEM_ORDER AS LINEITEM(L_ORDERKEY) REFERENCES ORDERS(O_ORDERKEY),
    LINEITEM_PART AS LINEITEM(L_PARTKEY) REFERENCES PART(P_PARTKEY),
    LINEITEM_SUPPLIER AS LINEITEM(L_SUPPKEY) REFERENCES SUPPLIER(S_SUPPKEY),
    ORDER_CUSTOMER AS ORDERS(O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY),
    CUSTOMER_NATION AS CUSTOMER(C_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
FACTS (
    LINEITEM.ORDER_KEY AS L_ORDERKEY COMMENT = 'Order identifier - part of composite primary key',
    LINEITEM.LINE_NUMBER AS L_LINENUMBER COMMENT = 'Line item number within order',
    LINEITEM.QUANTITY AS L_QUANTITY COMMENT = 'Quantity ordered',
    LINEITEM.EXTENDED_PRICE AS L_EXTENDEDPRICE COMMENT = 'Extended price (qty * unit price)',
    LINEITEM.DISCOUNT AS L_DISCOUNT COMMENT = 'Discount percentage',
    LINEITEM.TAX AS L_TAX COMMENT = 'Tax percentage'
)
DIMENSIONS (
    LINEITEM.SHIP_DATE AS L_SHIPDATE COMMENT = 'Date line item was shipped',
    LINEITEM.RETURN_FLAG AS L_RETURNFLAG COMMENT = 'Return flag (A/N/R)',
    LINEITEM.LINE_STATUS AS L_LINESTATUS COMMENT = 'Line status (F=shipped, O=not shipped)',
    LINEITEM.SHIP_MODE AS L_SHIPMODE COMMENT = 'Shipping mode',
    ORDERS.ORDER_DATE AS O_ORDERDATE COMMENT = 'Date when order was placed',
    ORDERS.ORDER_STATUS AS O_ORDERSTATUS COMMENT = 'Order status',
    PART.BRAND AS P_BRAND COMMENT = 'Part brand',
    PART.TYPE AS P_TYPE COMMENT = 'Part type',
    SUPPLIER.SUPPLIER_NAME AS S_NAME COMMENT = 'Supplier name',
    CUSTOMER.MARKET_SEGMENT AS C_MKTSEGMENT COMMENT = 'Market segment',
    NATION.NATION_NAME AS N_NAME COMMENT = 'Nation name',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Region name'
)
METRICS (
    LINEITEM.TOTAL_EXTENDED_PRICE AS SUM(L_EXTENDEDPRICE) COMMENT = 'Total extended price',
    LINEITEM.TOTAL_QUANTITY AS SUM(L_QUANTITY) COMMENT = 'Total quantity',
    LINEITEM.NET_REVENUE AS SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT)) COMMENT = 'Net revenue after discounts',
    LINEITEM.LINE_COUNT AS COUNT(*) COMMENT = 'Count of line items'
)
COMMENT = 'Line-level drill-through analysis - star with FACTS for detail';

-- ============================================================================
-- SEMANTIC VIEW: SV_DAILY_SALES
-- Pattern: Pre-aggregated view base
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_DAILY_SALES
TABLES (
    TPCH_RICH_VIEWS.V_DAILY_SALES_SUMMARY PRIMARY KEY (SALE_DATE, REGION_NAME, MARKET_SEGMENT)
)
DIMENSIONS (
    V_DAILY_SALES_SUMMARY.SALE_DATE AS SALE_DATE COMMENT = 'Date of sales transactions',
    V_DAILY_SALES_SUMMARY.REGION_NAME AS REGION_NAME COMMENT = 'Geographic region name',
    V_DAILY_SALES_SUMMARY.MARKET_SEGMENT AS MARKET_SEGMENT COMMENT = 'Customer market segment'
)
METRICS (
    V_DAILY_SALES_SUMMARY.TOTAL_REVENUE AS SUM(TOTAL_REVENUE) COMMENT = 'Total revenue for the day',
    V_DAILY_SALES_SUMMARY.ORDER_COUNT AS SUM(ORDER_COUNT) COMMENT = 'Number of orders',
    V_DAILY_SALES_SUMMARY.AVG_ORDER_VALUE AS AVG(AVG_ORDER_VALUE) COMMENT = 'Average order value'
)
COMMENT = 'Daily sales trends - based on pre-aggregated summary view';

-- ============================================================================
-- SEMANTIC VIEW: SV_MONTHLY_TRENDS
-- Pattern: Time-based with YTD
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_MONTHLY_TRENDS
TABLES (
    TPCH_RICH_VIEWS.V_MONTHLY_REVENUE PRIMARY KEY (YEAR, MONTH, REGION_NAME)
)
DIMENSIONS (
    V_MONTHLY_REVENUE.YEAR AS YEAR COMMENT = 'Calendar year',
    V_MONTHLY_REVENUE.MONTH AS MONTH COMMENT = 'Calendar month (1-12)',
    V_MONTHLY_REVENUE.MONTH_NAME AS MONTH_NAME COMMENT = 'Month name',
    V_MONTHLY_REVENUE.YEAR_MONTH AS YEAR_MONTH COMMENT = 'Year-month in YYYY-MM format',
    V_MONTHLY_REVENUE.REGION_NAME AS REGION_NAME COMMENT = 'Geographic region name'
)
METRICS (
    V_MONTHLY_REVENUE.MONTHLY_REVENUE AS SUM(MONTHLY_REVENUE) COMMENT = 'Total monthly revenue',
    V_MONTHLY_REVENUE.ORDER_COUNT AS SUM(ORDER_COUNT) COMMENT = 'Number of orders in month',
    V_MONTHLY_REVENUE.CUMULATIVE_YTD AS SUM(CUMULATIVE_YTD_REVENUE) COMMENT = 'Year-to-date revenue'
)
COMMENT = 'Monthly trend analysis with YTD - time-based metrics from pre-aggregated view';

-- ============================================================================
-- SEMANTIC VIEW: SV_SUPPLY_CHAIN
-- Pattern: M:M relationship via PARTSUPP bridge
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_SUPPLY_CHAIN
TABLES (
    TPCH_RICH_TABLES.LINEITEM PRIMARY KEY (L_ORDERKEY, L_LINENUMBER),
    TPCH_RICH_TABLES.PARTSUPP PRIMARY KEY (PS_PARTKEY, PS_SUPPKEY),
    TPCH_RICH_TABLES.SUPPLIER PRIMARY KEY (S_SUPPKEY),
    TPCH_RICH_TABLES.PART PRIMARY KEY (P_PARTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    LINEITEM_PARTSUPP AS LINEITEM(L_PARTKEY, L_SUPPKEY) REFERENCES PARTSUPP(PS_PARTKEY, PS_SUPPKEY),
    PARTSUPP_SUPPLIER AS PARTSUPP(PS_SUPPKEY) REFERENCES SUPPLIER(S_SUPPKEY),
    PARTSUPP_PART AS PARTSUPP(PS_PARTKEY) REFERENCES PART(P_PARTKEY),
    SUPPLIER_NATION AS SUPPLIER(S_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
DIMENSIONS (
    PART.BRAND AS P_BRAND COMMENT = 'Part brand',
    PART.TYPE AS P_TYPE COMMENT = 'Part type',
    SUPPLIER.SUPPLIER_NAME AS S_NAME COMMENT = 'Supplier name',
    NATION.NATION_NAME AS N_NAME COMMENT = 'Supplier nation',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Supplier region'
)
METRICS (
    LINEITEM.TOTAL_EXTENDED_PRICE AS SUM(L_EXTENDEDPRICE) COMMENT = 'Total extended price',
    LINEITEM.TOTAL_QUANTITY AS SUM(L_QUANTITY) COMMENT = 'Total quantity',
    PARTSUPP.TOTAL_SUPPLY_COST AS SUM(PS_SUPPLYCOST) COMMENT = 'Total supply cost',
    PARTSUPP.TOTAL_AVAIL_QTY AS SUM(PS_AVAILQTY) COMMENT = 'Total available quantity'
)
COMMENT = 'Supply chain analysis - M:M relationship via PARTSUPP bridge table';

-- ============================================================================
-- SEMANTIC VIEW: SV_SHIPPING_ANALYSIS
-- Pattern: Date hierarchies with transit metrics
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_SHIPPING_ANALYSIS
TABLES (
    TPCH_RICH_TABLES.LINEITEM PRIMARY KEY (L_ORDERKEY, L_LINENUMBER),
    TPCH_RICH_TABLES.ORDERS PRIMARY KEY (O_ORDERKEY)
)
RELATIONSHIPS (
    LINEITEM_ORDER AS LINEITEM(L_ORDERKEY) REFERENCES ORDERS(O_ORDERKEY)
)
DIMENSIONS (
    LINEITEM.SHIP_DATE AS L_SHIPDATE COMMENT = 'Date line item was shipped',
    LINEITEM.COMMIT_DATE AS L_COMMITDATE COMMENT = 'Committed delivery date',
    LINEITEM.RECEIPT_DATE AS L_RECEIPTDATE COMMENT = 'Actual receipt date',
    LINEITEM.SHIP_MODE AS L_SHIPMODE COMMENT = 'Shipping mode',
    LINEITEM.SHIP_INSTRUCT AS L_SHIPINSTRUCT COMMENT = 'Shipping instructions',
    ORDERS.ORDER_DATE AS O_ORDERDATE COMMENT = 'Date when order was placed',
    ORDERS.ORDER_PRIORITY AS O_ORDERPRIORITY COMMENT = 'Order priority'
)
METRICS (
    LINEITEM.SHIPMENT_COUNT AS COUNT(*) COMMENT = 'Count of shipments',
    LINEITEM.TOTAL_QUANTITY AS SUM(L_QUANTITY) COMMENT = 'Total quantity shipped',
    LINEITEM.TOTAL_EXTENDED_PRICE AS SUM(L_EXTENDEDPRICE) COMMENT = 'Total extended price',
    LINEITEM.AVG_TRANSIT_DAYS AS AVG(DATEDIFF(DAY, L_SHIPDATE, L_RECEIPTDATE)) COMMENT = 'Average transit days'
)
COMMENT = 'Shipping performance with date hierarchies and transit metrics';

-- ============================================================================
-- SEMANTIC VIEW: SV_CUSTOMER_VALUE
-- Pattern: Calculated lifetime metrics
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_CUSTOMER_VALUE
TABLES (
    TPCH_RICH_TABLES.ORDERS PRIMARY KEY (O_ORDERKEY),
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    ORDER_CUSTOMER AS ORDERS(O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY),
    CUSTOMER_NATION AS CUSTOMER(C_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
DIMENSIONS (
    CUSTOMER.CUSTOMER_NAME AS C_NAME COMMENT = 'Customer business name',
    CUSTOMER.MARKET_SEGMENT AS C_MKTSEGMENT COMMENT = 'Market segment',
    NATION.NATION_NAME AS N_NAME COMMENT = 'Customer nation',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Customer region'
)
METRICS (
    CUSTOMER.CUSTOMER_COUNT AS COUNT(DISTINCT C_CUSTKEY) COMMENT = 'Count of unique customers',
    ORDERS.LIFETIME_VALUE AS SUM(O_TOTALPRICE) COMMENT = 'Customer lifetime value (total orders)',
    ORDERS.ORDER_COUNT AS COUNT(O_ORDERKEY) COMMENT = 'Total orders per customer',
    ORDERS.AVG_ORDER_VALUE AS AVG(O_TOTALPRICE) COMMENT = 'Average order value',
    CUSTOMER.AVG_ACCT_BALANCE AS AVG(C_ACCTBAL) COMMENT = 'Average customer account balance'
)
COMMENT = 'Customer lifetime value analysis - calculated metrics focus';

-- ============================================================================
-- SEMANTIC VIEW: SV_SALES_ANALYSIS
-- Pattern: Sales analysis with customer geography (single-path)
-- Replaces SV_TPCH_COMPLETE to avoid multi-path relationship errors
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_SALES_ANALYSIS
TABLES (
    TPCH_RICH_TABLES.LINEITEM PRIMARY KEY (L_ORDERKEY, L_LINENUMBER),
    TPCH_RICH_TABLES.ORDERS PRIMARY KEY (O_ORDERKEY),
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    -- Single path: LINEITEM → ORDERS → CUSTOMER → NATION → REGION
    LINEITEM_ORDER AS LINEITEM(L_ORDERKEY) REFERENCES ORDERS(O_ORDERKEY),
    ORDER_CUSTOMER AS ORDERS(O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY),
    CUSTOMER_NATION AS CUSTOMER(C_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
DIMENSIONS (
    -- Time dimensions from LINEITEM
    LINEITEM.SHIP_YEAR AS YEAR(L_SHIPDATE) COMMENT = 'Year from ship date',
    LINEITEM.SHIP_QUARTER AS QUARTER(L_SHIPDATE) COMMENT = 'Quarter from ship date',
    LINEITEM.SHIP_MODE AS L_SHIPMODE COMMENT = 'Shipping mode',
    LINEITEM.RETURN_FLAG AS L_RETURNFLAG COMMENT = 'Return flag (A/N/R)',
    LINEITEM.LINE_STATUS AS L_LINESTATUS COMMENT = 'Line status (F/O)',

    -- Order dimensions
    ORDERS.ORDER_YEAR AS YEAR(O_ORDERDATE) COMMENT = 'Order year',
    ORDERS.ORDER_MONTH AS MONTH(O_ORDERDATE) COMMENT = 'Order month',
    ORDERS.ORDER_STATUS AS O_ORDERSTATUS COMMENT = 'Order status (F/O/P)',
    ORDERS.ORDER_PRIORITY AS O_ORDERPRIORITY COMMENT = 'Order priority',
    ORDERS.ORDER_CLERK AS O_CLERK COMMENT = 'Clerk who processed the order',

    -- Customer dimensions
    CUSTOMER.CUSTOMER_NAME AS C_NAME COMMENT = 'Customer business name',
    CUSTOMER.MARKET_SEGMENT AS C_MKTSEGMENT COMMENT = 'Market segment',

    -- Geography (customer path only - avoids multi-path)
    NATION.NATION_NAME AS N_NAME COMMENT = 'Customer nation name',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Customer geographic region'
)
METRICS (
    LINEITEM.TOTAL_EXTENDED_PRICE AS SUM(L_EXTENDEDPRICE) COMMENT = 'Total extended price',
    LINEITEM.NET_REVENUE AS SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT)) COMMENT = 'Net revenue after discounts',
    LINEITEM.TOTAL_QUANTITY AS SUM(L_QUANTITY) COMMENT = 'Total quantity',
    LINEITEM.LINE_COUNT AS COUNT(*) COMMENT = 'Count of line items',
    ORDERS.ORDER_COUNT AS COUNT(DISTINCT O_ORDERKEY) COMMENT = 'Count of distinct orders',
    ORDERS.AVG_ORDER_VALUE AS AVG(O_TOTALPRICE) COMMENT = 'Average order value',
    CUSTOMER.CUSTOMER_COUNT AS COUNT(DISTINCT C_CUSTKEY) COMMENT = 'Count of unique customers'
)
COMMENT = 'Sales analysis - LINEITEM grain with customer geography (single-path, Power BI compatible)';

-- ============================================================================
-- SEMANTIC VIEW: SV_PRODUCT_SUPPLY
-- Pattern: Product analysis (LINEITEM → PART only)
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_PRODUCT_SUPPLY
TABLES (
    TPCH_RICH_TABLES.LINEITEM PRIMARY KEY (L_ORDERKEY, L_LINENUMBER),
    TPCH_RICH_TABLES.PART PRIMARY KEY (P_PARTKEY)
)
RELATIONSHIPS (
    -- Single path: LINEITEM → PART
    LINEITEM_PART AS LINEITEM(L_PARTKEY) REFERENCES PART(P_PARTKEY)
)
DIMENSIONS (
    LINEITEM.SHIP_MODE AS L_SHIPMODE COMMENT = 'Shipping mode',
    LINEITEM.RETURN_FLAG AS L_RETURNFLAG COMMENT = 'Return flag (A/N/R)',
    PART.BRAND AS P_BRAND COMMENT = 'Part brand',
    PART.TYPE AS P_TYPE COMMENT = 'Part type',
    PART.SIZE AS P_SIZE COMMENT = 'Part size',
    PART.CONTAINER AS P_CONTAINER COMMENT = 'Part container',
    PART.MANUFACTURER AS P_MFGR COMMENT = 'Part manufacturer'
)
METRICS (
    LINEITEM.TOTAL_EXTENDED_PRICE AS SUM(L_EXTENDEDPRICE) COMMENT = 'Total extended price',
    LINEITEM.TOTAL_QUANTITY AS SUM(L_QUANTITY) COMMENT = 'Total quantity',
    LINEITEM.LINE_COUNT AS COUNT(*) COMMENT = 'Count of line items',
    PART.PART_COUNT AS COUNT(DISTINCT P_PARTKEY) COMMENT = 'Count of unique parts'
)
COMMENT = 'Product analysis - LINEITEM grain with part attributes (single-path, Power BI compatible)';

-- ============================================================================
-- SEMANTIC VIEW: SV_SUPPLIER_INVENTORY
-- Pattern: Supplier inventory with geography (PARTSUPP grain)
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_SUPPLIER_INVENTORY
TABLES (
    TPCH_RICH_TABLES.PARTSUPP PRIMARY KEY (PS_PARTKEY, PS_SUPPKEY),
    TPCH_RICH_TABLES.SUPPLIER PRIMARY KEY (S_SUPPKEY),
    TPCH_RICH_TABLES.PART PRIMARY KEY (P_PARTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    -- Single path: PARTSUPP → SUPPLIER → NATION → REGION
    -- Single path: PARTSUPP → PART
    PARTSUPP_SUPPLIER AS PARTSUPP(PS_SUPPKEY) REFERENCES SUPPLIER(S_SUPPKEY),
    PARTSUPP_PART AS PARTSUPP(PS_PARTKEY) REFERENCES PART(P_PARTKEY),
    SUPPLIER_NATION AS SUPPLIER(S_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
DIMENSIONS (
    SUPPLIER.SUPPLIER_NAME AS S_NAME COMMENT = 'Supplier business name',
    PART.BRAND AS P_BRAND COMMENT = 'Part brand',
    PART.TYPE AS P_TYPE COMMENT = 'Part type',
    NATION.NATION_NAME AS N_NAME COMMENT = 'Supplier nation name',
    REGION.REGION_NAME AS R_NAME COMMENT = 'Supplier geographic region'
)
METRICS (
    PARTSUPP.TOTAL_SUPPLY_COST AS SUM(PS_SUPPLYCOST) COMMENT = 'Total supply cost',
    PARTSUPP.TOTAL_AVAIL_QTY AS SUM(PS_AVAILQTY) COMMENT = 'Total available quantity',
    PARTSUPP.INVENTORY_VALUE AS SUM(PS_AVAILQTY * PS_SUPPLYCOST) COMMENT = 'Total inventory value',
    SUPPLIER.SUPPLIER_COUNT AS COUNT(DISTINCT S_SUPPKEY) COMMENT = 'Count of unique suppliers',
    PART.PART_COUNT AS COUNT(DISTINCT P_PARTKEY) COMMENT = 'Count of unique parts'
)
COMMENT = 'Supplier inventory - PARTSUPP grain with supplier geography (single-path, Power BI compatible)';

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SHOW SEMANTIC VIEWS IN SCHEMA;

SELECT 'Script 03_tpch_rich_svs.sql completed successfully!' AS STATUS;
SELECT '13 Semantic Views created in TPCH_RICH_DB.TPCH_RICH_SVS' AS SUMMARY;
