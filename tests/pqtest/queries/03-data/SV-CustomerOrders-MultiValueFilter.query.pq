// Multi-value / OR filter: an IN-list-style filter on a dimension, exercising
// the connector's OR/IN WHERE-clause generation (all prior filter cases were
// single-value equality).
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_CUSTOMER_ORDERS"]}[Data],
    Picked = Table.SelectColumns(View, {"REGION_NAME", "TOTAL_REVENUE"}),
    Filtered = Table.SelectRows(Picked, each [REGION_NAME] = "EUROPE" or [REGION_NAME] = "ASIA"),
    Sorted = Table.Sort(Filtered, {{"REGION_NAME", Order.Ascending}})
in
    Sorted
