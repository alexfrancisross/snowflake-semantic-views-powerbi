// Issue #4 regression: every logical name differs from its physical column,
// with the region label reached across a 2-hop relationship. AVG metric is
// rounded to keep the snapshot deterministic.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_EDGE_LOGICAL_MISMATCH"]}[Data],
    Picked = Table.SelectColumns(View, {"CONTINENT_LABEL", "AVERAGE_BALANCE", "CUSTOMER_TOTAL"}),
    Rounded = Table.TransformColumns(Picked, {{"AVERAGE_BALANCE", each Number.Round(_, 2), type number}}),
    Sorted = Table.Sort(Rounded, {{"CONTINENT_LABEL", Order.Ascending}})
in
    Sorted
