# TPCH Sample Data Scripts

SQL scripts to create a complete TPCH-based sample environment for testing Snowflake Semantic Views with Power BI.

## Overview

These scripts create three schemas with sample data based on the TPC-H benchmark:

| Schema | Contents | Purpose |
|--------|----------|---------|
| `TPCH_RICH_TABLES` | 8 base tables | Source data with full column comments |
| `TPCH_RICH_VIEWS` | 7 analytical views | Pre-built views for common analysis patterns |
| `TPCH_RICH_SVS` | 13 semantic views | Snowflake Semantic Views demonstrating various patterns |

## Prerequisites

1. **Snowflake Account** - Any Snowflake edition
2. **SNOWFLAKE_SAMPLE_DATA Access** - This shared database comes with every Snowflake account
3. **Semantic Views Feature** - Requires Enterprise Edition or higher for semantic views
4. **Privileges** - CREATE DATABASE, CREATE SCHEMA permissions

## Quick Start

Run the scripts in order using Snowflake CLI or SnowSQL:

```bash
# Using Snowflake CLI
snow sql -f 01_tpch_rich_tables.sql
snow sql -f 02_tpch_rich_views.sql
snow sql -f 03_tpch_rich_svs.sql
```

## Configuration

Each script has a configuration section at the top. To use a different database:

```sql
-- Change this line at the top of each script
SET DB_NAME = 'YOUR_DATABASE_NAME';
```

## Schema Details

### TPCH_RICH_TABLES (Base Tables)

| Table | Rows | Description |
|-------|------|-------------|
| REGION | 5 | Geographic regions |
| NATION | 25 | Countries/nations |
| CUSTOMER | 150K | Customer master data |
| SUPPLIER | 10K | Supplier master data |
| PART | 200K | Product catalog |
| PARTSUPP | 800K | Part-supplier relationships |
| ORDERS | 1.5M | Order headers |
| LINEITEM | 6M | Order line items |

### TPCH_RICH_VIEWS (Analytical Views)

| View | Columns | Description |
|------|---------|-------------|
| V_DATE_DIM | 10 | Date dimension with time hierarchy |
| V_CUSTOMER_GEOGRAPHY | 9 | Denormalized customer + geography |
| V_SUPPLIER_GEOGRAPHY | 8 | Denormalized supplier + geography |
| V_ORDER_DETAIL | 14 | Orders with customer info |
| V_LINEITEM_ENRICHED | 33 | Full lineitem context |
| V_DAILY_SALES_SUMMARY | 6 | Pre-aggregated daily sales |
| V_MONTHLY_REVENUE | 8 | Pre-aggregated monthly with YTD |

### TPCH_RICH_SVS (Semantic Views)

All semantic views use **single-path relationships** to ensure compatibility with Power BI DirectQuery.

| Semantic View | Pattern | Tables | Use Case |
|---------------|---------|--------|----------|
| SV_REGIONAL_SALES | 2-table star | Orders → Customer → Nation → Region | Regional KPIs |
| SV_PRODUCT_PERFORMANCE | 2-table | Lineitem → Part | Product analytics |
| SV_CUSTOMER_ORDERS | Full star | Orders → Customer → Nation → Region | Customer analysis |
| SV_SUPPLIER_ANALYSIS | 4-table | Supplier → Nation → Region + Partsupp | Supplier scorecard |
| SV_LINEITEM_DETAIL | Star + FACTS | Lineitem → Orders → Customer → Nation → Region | Drill-through |
| SV_DAILY_SALES | Pre-aggregated | V_DAILY_SALES_SUMMARY | Daily trends |
| SV_MONTHLY_TRENDS | Time-based | V_MONTHLY_REVENUE | Monthly/YTD |
| SV_SUPPLY_CHAIN | M:M bridge | Partsupp → Supplier/Part → Nation → Region | Supply chain |
| SV_SHIPPING_ANALYSIS | Date hierarchies | Lineitem → Orders | Logistics |
| SV_CUSTOMER_VALUE | Calculated | Orders → Customer → Nation → Region | Lifetime value |
| SV_SALES_ANALYSIS | Single-path | Lineitem → Orders → Customer → Nation → Region | Sales by geography |
| SV_PRODUCT_SUPPLY | Single-path | Lineitem → Part | Product volume |
| SV_SUPPLIER_INVENTORY | Single-path | Partsupp → Supplier/Part → Nation → Region | Inventory value |

## Sample Queries

### Test Regional Sales
```sql
SELECT "REGION_NAME", AGG("TOTAL_REVENUE"), AGG("ORDER_COUNT")
FROM TPCH_RICH_DB.TPCH_RICH_SVS.SV_REGIONAL_SALES
GROUP BY "REGION_NAME";
```

### Test Sales Analysis (Single-Path)
```sql
SELECT "REGION_NAME", "MARKET_SEGMENT", AGG("NET_REVENUE"), AGG("CUSTOMER_COUNT")
FROM TPCH_RICH_DB.TPCH_RICH_SVS.SV_SALES_ANALYSIS
GROUP BY "REGION_NAME", "MARKET_SEGMENT"
LIMIT 10;
```

### Test Product Supply
```sql
SELECT "BRAND", AGG("TOTAL_QUANTITY"), AGG("PART_COUNT")
FROM TPCH_RICH_DB.TPCH_RICH_SVS.SV_PRODUCT_SUPPLY
GROUP BY "BRAND"
ORDER BY AGG("TOTAL_QUANTITY") DESC
LIMIT 10;
```

### Test Supplier Inventory
```sql
SELECT "REGION_NAME", "NATION_NAME", AGG("INVENTORY_VALUE"), AGG("SUPPLIER_COUNT")
FROM TPCH_RICH_DB.TPCH_RICH_SVS.SV_SUPPLIER_INVENTORY
GROUP BY "REGION_NAME", "NATION_NAME"
ORDER BY AGG("INVENTORY_VALUE") DESC
LIMIT 10;
```

### Simulate Power BI DirectQuery Pattern
```sql
-- Power BI generates subquery wrappers like this:
SELECT * FROM (
    SELECT "MARKET_SEGMENT" AS "MARKET_SEGMENT",
           "REGION_NAME" AS "REGION_NAME",
           AGG("TOTAL_EXTENDED_PRICE") AS "a0"
    FROM TPCH_RICH_DB.TPCH_RICH_SVS.SV_SALES_ANALYSIS
    WHERE "NATION_NAME" IN ('UNITED STATES', 'CANADA', 'BRAZIL')
    GROUP BY 1, 2
    LIMIT 1000001
) AS "_";
```

### Verify Row Counts
```sql
SELECT 'REGION' AS TABLE_NAME, COUNT(*) AS ROW_COUNT FROM TPCH_RICH_DB.TPCH_RICH_TABLES.REGION
UNION ALL SELECT 'NATION', COUNT(*) FROM TPCH_RICH_DB.TPCH_RICH_TABLES.NATION
UNION ALL SELECT 'CUSTOMER', COUNT(*) FROM TPCH_RICH_DB.TPCH_RICH_TABLES.CUSTOMER
UNION ALL SELECT 'SUPPLIER', COUNT(*) FROM TPCH_RICH_DB.TPCH_RICH_TABLES.SUPPLIER
UNION ALL SELECT 'PART', COUNT(*) FROM TPCH_RICH_DB.TPCH_RICH_TABLES.PART
UNION ALL SELECT 'PARTSUPP', COUNT(*) FROM TPCH_RICH_DB.TPCH_RICH_TABLES.PARTSUPP
UNION ALL SELECT 'ORDERS', COUNT(*) FROM TPCH_RICH_DB.TPCH_RICH_TABLES.ORDERS
UNION ALL SELECT 'LINEITEM', COUNT(*) FROM TPCH_RICH_DB.TPCH_RICH_TABLES.LINEITEM
ORDER BY TABLE_NAME;
```

### List All Semantic Views
```sql
SHOW SEMANTIC VIEWS IN TPCH_RICH_DB.TPCH_RICH_SVS;
```

### View Semantic View Metadata
```sql
SHOW SEMANTIC DIMENSIONS IN TPCH_RICH_DB.TPCH_RICH_SVS.SV_SALES_ANALYSIS;
SHOW SEMANTIC METRICS IN TPCH_RICH_DB.TPCH_RICH_SVS.SV_SALES_ANALYSIS;
SHOW SEMANTIC FACTS IN TPCH_RICH_DB.TPCH_RICH_SVS.SV_LINEITEM_DETAIL;
```

## Semantic View Design Notes

### Why Single-Path Relationships?

Snowflake Semantic Views require unambiguous join paths. Multi-path relationships (where a table can be reached via multiple routes) cause errors like:

```
SQL compilation error:
Multi-path relationship between the dimension entity 'X' and the base metric entity 'Y' is not supported.
```

The three "single-path" views (SV_SALES_ANALYSIS, SV_PRODUCT_SUPPLY, SV_SUPPLIER_INVENTORY) are designed specifically to avoid these issues by:

1. **SV_SALES_ANALYSIS** - Customer geography only (no supplier geography)
2. **SV_PRODUCT_SUPPLY** - Part attributes only (no supplier or geography)
3. **SV_SUPPLIER_INVENTORY** - Supplier geography only (no customer path)

### Recommended Views for Power BI

For best Power BI compatibility, use these semantic views:

| Use Case | Recommended View |
|----------|-----------------|
| Executive dashboards | SV_REGIONAL_SALES |
| Product analytics | SV_PRODUCT_PERFORMANCE, SV_PRODUCT_SUPPLY |
| Customer analysis | SV_CUSTOMER_ORDERS, SV_CUSTOMER_VALUE |
| Sales by geography | SV_SALES_ANALYSIS |
| Supply chain | SV_SUPPLIER_INVENTORY |
| Shipping/logistics | SV_SHIPPING_ANALYSIS |
| Time trends | SV_DAILY_SALES, SV_MONTHLY_TRENDS |

## Troubleshooting

### "SNOWFLAKE_SAMPLE_DATA not found"
This database should exist in every Snowflake account. Check your access:
```sql
SHOW DATABASES LIKE 'SNOWFLAKE_SAMPLE_DATA';
USE DATABASE SNOWFLAKE_SAMPLE_DATA;
SELECT COUNT(*) FROM TPCH_SF1.REGION;
```

### "Semantic views require Enterprise Edition"
Snowflake Semantic Views are an Enterprise+ feature. Check your edition:
```sql
SELECT CURRENT_VERSION();
```

### "Invalid identifier" in semantic view
Ensure scripts 01 and 02 completed successfully before running 03:
```sql
SHOW TABLES IN TPCH_RICH_DB.TPCH_RICH_TABLES;
SHOW VIEWS IN TPCH_RICH_DB.TPCH_RICH_VIEWS;
```

### "Multi-path relationship" error
Use one of the single-path semantic views instead:
- SV_SALES_ANALYSIS (customer geography)
- SV_PRODUCT_SUPPLY (product only)
- SV_SUPPLIER_INVENTORY (supplier geography)

### Script fails partway through
Scripts use `CREATE OR REPLACE` so they can be re-run safely. Simply re-execute the failed script.

## Using with Power BI

After running these scripts, you can connect from Power BI using:

1. **Native Snowflake Connector** - For standard views and tables
2. **Snowflake Semantic Views Connector** - For semantic views with DirectQuery

The semantic views support `AGG()` aggregation syntax required by the semantic view connector.

## File Manifest

| File | Size | Purpose |
|------|------|---------|
| `01_tpch_rich_tables.sql` | ~8 KB | Creates 8 base tables with data |
| `02_tpch_rich_views.sql` | ~12 KB | Creates 7 analytical views |
| `03_tpch_rich_svs.sql` | ~18 KB | Creates 13 semantic views |
| `README.md` | This file | Documentation |

## License

These scripts create sample data from Snowflake's publicly available SNOWFLAKE_SAMPLE_DATA database. Use freely for testing and development purposes.
