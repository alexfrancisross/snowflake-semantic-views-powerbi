// Core connector shape: dimension + metrics -> SELECT dim, AGG(m) GROUP BY dim.
// 5 regions in TPCH; explicit sort for snapshot determinism.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Picked = Table.SelectColumns(View, {"REGION_NAME", "TOTAL_REVENUE", "ORDER_COUNT"}),
    Sorted = Table.Sort(Picked, {{"REGION_NAME", Order.Ascending}})
in
    Sorted
