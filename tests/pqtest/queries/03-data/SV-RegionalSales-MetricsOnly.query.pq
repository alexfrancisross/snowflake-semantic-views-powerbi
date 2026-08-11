// Bare-metric "card" shape: metrics with no grouping dimension -> single row.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Picked = Table.SelectColumns(View, {"TOTAL_REVENUE", "ORDER_COUNT"})
in
    Picked
