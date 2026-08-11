// Issue #4 regression: filter on a METRIC column (outer-subquery wrap when
// folded) with a mismatched logical name.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_EDGE_METRIC_FILTER"]}[Data],
    Picked = Table.SelectColumns(View, {"SEGMENT_NAME", "REVENUE_TOTAL"}),
    Filtered = Table.SelectRows(Picked, each [REVENUE_TOTAL] > 1000000),
    Sorted = Table.Sort(Filtered, {{"SEGMENT_NAME", Order.Ascending}})
in
    Sorted
