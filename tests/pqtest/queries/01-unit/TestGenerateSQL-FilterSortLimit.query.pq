// Snapshots generated SQL with a dimension WHERE filter, ORDER BY, and LIMIT.
let
    Metadata = {
        [ColumnName = "REGION_NAME", ColumnType = "TEXT", ColumnKind = "DIMENSION"],
        [ColumnName = "TOTAL_REVENUE", ColumnType = "NUMBER", ColumnKind = "METRIC"]
    },
    Filters = {
        [Column = "REGION_NAME", Operator = "=", Value = "EUROPE"]
    },
    OrderBy = {
        [Name = "TOTAL_REVENUE", Order = Order.Descending]
    }
in
    SnowflakeSemanticViews.TestGenerateSQL(
        "TPCH_RICH_DB.TPCH_RICH_SVS.SV_REGIONAL_SALES",
        {"REGION_NAME", "TOTAL_REVENUE"},
        Metadata,
        10,
        null,
        OrderBy,
        null,
        null,
        Filters
    )
