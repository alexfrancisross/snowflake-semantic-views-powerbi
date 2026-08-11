// Issue #7 regression: ORDER BY on a dimension after a single-value filter.
// SV_DAILY_SALES has multiple rows per REGION_NAME (one per SALE_DATE), so
// filtering to a single region does NOT collapse the result to one row -
// the sort spec on REGION_NAME must still resolve correctly even though the
// column is now constant, exercising BuildOrderByClause's ordinal-position
// resolution end-to-end against a live account.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_DAILY_SALES"]}[Data],
    Picked = Table.SelectColumns(View, {"SALE_DATE", "REGION_NAME", "TOTAL_REVENUE"}),
    Filtered = Table.SelectRows(Picked, each [REGION_NAME] = "EUROPE"),
    Sorted = Table.Sort(Filtered, {{"REGION_NAME", Order.Ascending}, {"SALE_DATE", Order.Ascending}})
in
    Sorted
