// TopN + descending sort on a metric (folds to ORDER BY ... LIMIT).
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Picked = Table.SelectColumns(View, {"REGION_NAME", "TOTAL_REVENUE"}),
    Sorted = Table.Sort(Picked, {{"TOTAL_REVENUE", Order.Descending}})
in
    Table.FirstN(Sorted, 3)
