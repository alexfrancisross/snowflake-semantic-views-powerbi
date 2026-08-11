// Snapshots the generated SQL for the basic dims + metric shape:
// SELECT dim, dim, AGG(metric) ... GROUP BY dims.
let
    Metadata = {
        [ColumnName = "REGION_NAME", ColumnType = "TEXT", ColumnKind = "DIMENSION"],
        [ColumnName = "NATION_NAME", ColumnType = "TEXT", ColumnKind = "DIMENSION"],
        [ColumnName = "TOTAL_REVENUE", ColumnType = "NUMBER", ColumnKind = "METRIC"]
    }
in
    SnowflakeSemanticViews.TestGenerateSQL(
        "TPCH_RICH_DB.TPCH_RICH_SVS.SV_REGIONAL_SALES",
        {"REGION_NAME", "NATION_NAME", "TOTAL_REVENUE"},
        Metadata
    )
