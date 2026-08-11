// Issue #4 regression: mixed-case and space-containing quoted logical names.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_EDGE_QUOTED_MIXED_CASE"]}[Data],
    Picked = Table.SelectColumns(View, {"Market Segment", "Total Balance"}),
    Sorted = Table.Sort(Picked, {{"Market Segment", Order.Ascending}})
in
    Sorted
