/*
 * Script: 01_tpch_rich_tables.sql
 * Purpose: Create TPCH_RICH_TABLES schema with sample data from SNOWFLAKE_SAMPLE_DATA
 *
 * This script creates 8 tables based on the TPC-H benchmark schema:
 *   - REGION (5 rows) - Geographic regions
 *   - NATION (25 rows) - Countries/nations
 *   - CUSTOMER (150K rows) - Customer master data
 *   - SUPPLIER (10K rows) - Supplier master data
 *   - PART (200K rows) - Part/product catalog
 *   - PARTSUPP (800K rows) - Part-supplier relationship
 *   - ORDERS (1.5M rows) - Order headers
 *   - LINEITEM (6M rows) - Order line items
 *
 * Prerequisites:
 *   - Access to SNOWFLAKE_SAMPLE_DATA.TPCH_SF1 (comes with every Snowflake account)
 *   - CREATE DATABASE and CREATE SCHEMA privileges
 *
 * Configuration:
 *   - Modify DB_NAME variable below to use a different database
 *
 * Execution:
 *   snow sql -f 01_tpch_rich_tables.sql
 *
 */

-- ============================================================================
-- CONFIGURATION
-- ============================================================================
SET DB_NAME = 'TPCH_RICH_DB';
SET SCHEMA_NAME = 'TPCH_RICH_TABLES';

-- ============================================================================
-- SETUP
-- ============================================================================
CREATE DATABASE IF NOT EXISTS IDENTIFIER($DB_NAME);
USE DATABASE IDENTIFIER($DB_NAME);
CREATE SCHEMA IF NOT EXISTS IDENTIFIER($SCHEMA_NAME);
USE SCHEMA IDENTIFIER($SCHEMA_NAME);

-- ============================================================================
-- TABLE: REGION
-- Geographic regions (5 rows)
-- ============================================================================
CREATE OR REPLACE TABLE REGION AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.REGION;

COMMENT ON TABLE REGION IS 'Geographic regions for customer and supplier location hierarchy';
COMMENT ON COLUMN REGION.R_REGIONKEY IS 'Unique region identifier';
COMMENT ON COLUMN REGION.R_NAME IS 'Region name (AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST)';
COMMENT ON COLUMN REGION.R_COMMENT IS 'Free-form region comments';

ALTER TABLE REGION ADD CONSTRAINT PK_REGION PRIMARY KEY (R_REGIONKEY);

-- ============================================================================
-- TABLE: NATION
-- Countries/nations (25 rows)
-- ============================================================================
CREATE OR REPLACE TABLE NATION AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION;

COMMENT ON TABLE NATION IS 'Nations/countries linked to geographic regions';
COMMENT ON COLUMN NATION.N_NATIONKEY IS 'Unique nation identifier';
COMMENT ON COLUMN NATION.N_NAME IS 'Nation name';
COMMENT ON COLUMN NATION.N_REGIONKEY IS 'Region key (foreign key to REGION)';
COMMENT ON COLUMN NATION.N_COMMENT IS 'Free-form nation comments';

ALTER TABLE NATION ADD CONSTRAINT PK_NATION PRIMARY KEY (N_NATIONKEY);
ALTER TABLE NATION ADD CONSTRAINT FK_NATION_REGION FOREIGN KEY (N_REGIONKEY) REFERENCES REGION(R_REGIONKEY);

-- ============================================================================
-- TABLE: CUSTOMER
-- Customer master data (150K rows)
-- ============================================================================
CREATE OR REPLACE TABLE CUSTOMER AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER;

COMMENT ON TABLE CUSTOMER IS 'Customer master data with market segment and geography';
COMMENT ON COLUMN CUSTOMER.C_CUSTKEY IS 'Unique customer identifier';
COMMENT ON COLUMN CUSTOMER.C_NAME IS 'Customer business name';
COMMENT ON COLUMN CUSTOMER.C_ADDRESS IS 'Customer street address';
COMMENT ON COLUMN CUSTOMER.C_NATIONKEY IS 'Nation key (foreign key to NATION)';
COMMENT ON COLUMN CUSTOMER.C_PHONE IS 'Customer phone number including country and area code';
COMMENT ON COLUMN CUSTOMER.C_ACCTBAL IS 'Customer account balance - can be negative';
COMMENT ON COLUMN CUSTOMER.C_MKTSEGMENT IS 'Market segment (AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD, MACHINERY)';
COMMENT ON COLUMN CUSTOMER.C_COMMENT IS 'Free-form customer comments';

ALTER TABLE CUSTOMER ADD CONSTRAINT PK_CUSTOMER PRIMARY KEY (C_CUSTKEY);
ALTER TABLE CUSTOMER ADD CONSTRAINT FK_CUSTOMER_NATION FOREIGN KEY (C_NATIONKEY) REFERENCES NATION(N_NATIONKEY);

-- ============================================================================
-- TABLE: SUPPLIER
-- Supplier master data (10K rows)
-- ============================================================================
CREATE OR REPLACE TABLE SUPPLIER AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.SUPPLIER;

COMMENT ON TABLE SUPPLIER IS 'Supplier master data with geography information';
COMMENT ON COLUMN SUPPLIER.S_SUPPKEY IS 'Unique supplier identifier';
COMMENT ON COLUMN SUPPLIER.S_NAME IS 'Supplier business name';
COMMENT ON COLUMN SUPPLIER.S_ADDRESS IS 'Supplier street address';
COMMENT ON COLUMN SUPPLIER.S_NATIONKEY IS 'Nation key (foreign key to NATION)';
COMMENT ON COLUMN SUPPLIER.S_PHONE IS 'Supplier phone number';
COMMENT ON COLUMN SUPPLIER.S_ACCTBAL IS 'Supplier account balance';
COMMENT ON COLUMN SUPPLIER.S_COMMENT IS 'Free-form supplier comments';

ALTER TABLE SUPPLIER ADD CONSTRAINT PK_SUPPLIER PRIMARY KEY (S_SUPPKEY);
ALTER TABLE SUPPLIER ADD CONSTRAINT FK_SUPPLIER_NATION FOREIGN KEY (S_NATIONKEY) REFERENCES NATION(N_NATIONKEY);

-- ============================================================================
-- TABLE: PART
-- Part/product catalog (200K rows)
-- ============================================================================
CREATE OR REPLACE TABLE PART AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.PART;

COMMENT ON TABLE PART IS 'Part/product catalog with attributes';
COMMENT ON COLUMN PART.P_PARTKEY IS 'Unique part identifier';
COMMENT ON COLUMN PART.P_NAME IS 'Full part name describing the product';
COMMENT ON COLUMN PART.P_MFGR IS 'Part manufacturer (Manufacturer#1 to Manufacturer#5)';
COMMENT ON COLUMN PART.P_BRAND IS 'Part brand (Brand#11 to Brand#55)';
COMMENT ON COLUMN PART.P_TYPE IS 'Part type description';
COMMENT ON COLUMN PART.P_SIZE IS 'Part size measurement (1-50)';
COMMENT ON COLUMN PART.P_CONTAINER IS 'Part container type (SM BOX, LG CASE, etc.)';
COMMENT ON COLUMN PART.P_RETAILPRICE IS 'Suggested retail price';
COMMENT ON COLUMN PART.P_COMMENT IS 'Free-form part comments';

ALTER TABLE PART ADD CONSTRAINT PK_PART PRIMARY KEY (P_PARTKEY);

-- ============================================================================
-- TABLE: PARTSUPP
-- Part-supplier relationship (800K rows)
-- ============================================================================
CREATE OR REPLACE TABLE PARTSUPP AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.PARTSUPP;

COMMENT ON TABLE PARTSUPP IS 'Part-supplier relationship with supply cost and availability';
COMMENT ON COLUMN PARTSUPP.PS_PARTKEY IS 'Part key (foreign key to PART)';
COMMENT ON COLUMN PARTSUPP.PS_SUPPKEY IS 'Supplier key (foreign key to SUPPLIER)';
COMMENT ON COLUMN PARTSUPP.PS_AVAILQTY IS 'Available quantity from this supplier';
COMMENT ON COLUMN PARTSUPP.PS_SUPPLYCOST IS 'Supply cost from this supplier';
COMMENT ON COLUMN PARTSUPP.PS_COMMENT IS 'Free-form part-supplier comments';

ALTER TABLE PARTSUPP ADD CONSTRAINT PK_PARTSUPP PRIMARY KEY (PS_PARTKEY, PS_SUPPKEY);
ALTER TABLE PARTSUPP ADD CONSTRAINT FK_PARTSUPP_PART FOREIGN KEY (PS_PARTKEY) REFERENCES PART(P_PARTKEY);
ALTER TABLE PARTSUPP ADD CONSTRAINT FK_PARTSUPP_SUPPLIER FOREIGN KEY (PS_SUPPKEY) REFERENCES SUPPLIER(S_SUPPKEY);

-- ============================================================================
-- TABLE: ORDERS
-- Order headers (1.5M rows)
-- ============================================================================
CREATE OR REPLACE TABLE ORDERS AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS;

COMMENT ON TABLE ORDERS IS 'Order headers with customer and status information';
COMMENT ON COLUMN ORDERS.O_ORDERKEY IS 'Unique order identifier';
COMMENT ON COLUMN ORDERS.O_CUSTKEY IS 'Customer key (foreign key to CUSTOMER)';
COMMENT ON COLUMN ORDERS.O_ORDERSTATUS IS 'Order status (F=Fulfilled, O=Open, P=Pending)';
COMMENT ON COLUMN ORDERS.O_TOTALPRICE IS 'Total order value in dollars';
COMMENT ON COLUMN ORDERS.O_ORDERDATE IS 'Date when order was placed';
COMMENT ON COLUMN ORDERS.O_ORDERPRIORITY IS 'Order priority level (1-URGENT to 5-LOW)';
COMMENT ON COLUMN ORDERS.O_CLERK IS 'Clerk who processed the order';
COMMENT ON COLUMN ORDERS.O_SHIPPRIORITY IS 'Shipping priority indicator';
COMMENT ON COLUMN ORDERS.O_COMMENT IS 'Free-form order comments';

ALTER TABLE ORDERS ADD CONSTRAINT PK_ORDERS PRIMARY KEY (O_ORDERKEY);
ALTER TABLE ORDERS ADD CONSTRAINT FK_ORDERS_CUSTOMER FOREIGN KEY (O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY);

-- ============================================================================
-- TABLE: LINEITEM
-- Order line items (6M rows)
-- ============================================================================
CREATE OR REPLACE TABLE LINEITEM AS
SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM;

COMMENT ON TABLE LINEITEM IS 'Order line items with pricing and shipping details';
COMMENT ON COLUMN LINEITEM.L_ORDERKEY IS 'Order key (foreign key to ORDERS)';
COMMENT ON COLUMN LINEITEM.L_PARTKEY IS 'Part key (foreign key to PART)';
COMMENT ON COLUMN LINEITEM.L_SUPPKEY IS 'Supplier key (foreign key to SUPPLIER)';
COMMENT ON COLUMN LINEITEM.L_LINENUMBER IS 'Line number within the order';
COMMENT ON COLUMN LINEITEM.L_QUANTITY IS 'Quantity ordered';
COMMENT ON COLUMN LINEITEM.L_EXTENDEDPRICE IS 'Extended price (quantity * unit price)';
COMMENT ON COLUMN LINEITEM.L_DISCOUNT IS 'Discount percentage (0.00 to 0.10)';
COMMENT ON COLUMN LINEITEM.L_TAX IS 'Tax percentage';
COMMENT ON COLUMN LINEITEM.L_RETURNFLAG IS 'Return flag (A=returned and accepted, N=not returned, R=returned)';
COMMENT ON COLUMN LINEITEM.L_LINESTATUS IS 'Line status (F=shipped, O=not shipped)';
COMMENT ON COLUMN LINEITEM.L_SHIPDATE IS 'Date line item was shipped';
COMMENT ON COLUMN LINEITEM.L_COMMITDATE IS 'Committed delivery date';
COMMENT ON COLUMN LINEITEM.L_RECEIPTDATE IS 'Actual receipt date';
COMMENT ON COLUMN LINEITEM.L_SHIPINSTRUCT IS 'Shipping instructions';
COMMENT ON COLUMN LINEITEM.L_SHIPMODE IS 'Shipping mode (AIR, FOB, MAIL, RAIL, REG AIR, SHIP, TRUCK)';
COMMENT ON COLUMN LINEITEM.L_COMMENT IS 'Line item comments';

ALTER TABLE LINEITEM ADD CONSTRAINT PK_LINEITEM PRIMARY KEY (L_ORDERKEY, L_LINENUMBER);
ALTER TABLE LINEITEM ADD CONSTRAINT FK_LINEITEM_ORDER FOREIGN KEY (L_ORDERKEY) REFERENCES ORDERS(O_ORDERKEY);
ALTER TABLE LINEITEM ADD CONSTRAINT FK_LINEITEM_PART FOREIGN KEY (L_PARTKEY) REFERENCES PART(P_PARTKEY);
ALTER TABLE LINEITEM ADD CONSTRAINT FK_LINEITEM_SUPPLIER FOREIGN KEY (L_SUPPKEY) REFERENCES SUPPLIER(S_SUPPKEY);
ALTER TABLE LINEITEM ADD CONSTRAINT FK_LINEITEM_PARTSUPP FOREIGN KEY (L_PARTKEY, L_SUPPKEY) REFERENCES PARTSUPP(PS_PARTKEY, PS_SUPPKEY);

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'REGION' AS TABLE_NAME, COUNT(*) AS ROW_COUNT FROM REGION
UNION ALL SELECT 'NATION', COUNT(*) FROM NATION
UNION ALL SELECT 'CUSTOMER', COUNT(*) FROM CUSTOMER
UNION ALL SELECT 'SUPPLIER', COUNT(*) FROM SUPPLIER
UNION ALL SELECT 'PART', COUNT(*) FROM PART
UNION ALL SELECT 'PARTSUPP', COUNT(*) FROM PARTSUPP
UNION ALL SELECT 'ORDERS', COUNT(*) FROM ORDERS
UNION ALL SELECT 'LINEITEM', COUNT(*) FROM LINEITEM
ORDER BY TABLE_NAME;

SELECT 'Script 01_tpch_rich_tables.sql completed successfully!' AS STATUS;
