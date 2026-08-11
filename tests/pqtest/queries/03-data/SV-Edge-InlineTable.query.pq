// Issue #4 regression: SQL-defined (inline-view) logical table with
// mismatched logical names.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_EDGE_INLINE_TABLE"]}[Data],
    Picked = Table.SelectColumns(View, {"MARKET_SEGMENT", "TOTAL_BALANCE"}),
    Sorted = Table.Sort(Picked, {{"MARKET_SEGMENT", Order.Ascending}})
in
    Sorted
