// Dimension WHERE filter: nations within EUROPE only.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Picked = Table.SelectColumns(View, {"REGION_NAME", "NATION_NAME", "ORDER_COUNT"}),
    Filtered = Table.SelectRows(Picked, each [REGION_NAME] = "EUROPE"),
    Sorted = Table.Sort(Filtered, {{"NATION_NAME", Order.Ascending}})
in
    Sorted
