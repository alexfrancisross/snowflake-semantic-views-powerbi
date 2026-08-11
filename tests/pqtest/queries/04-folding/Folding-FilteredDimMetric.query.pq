// Run with PQTest --failOnFoldingFailure (-foff): the whole expression must
// fold to a single Snowflake SQL statement (DirectQuery behavior). Filtered
// to one region so the un-sorted result stays snapshot-deterministic.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Picked = Table.SelectColumns(View, {"REGION_NAME", "TOTAL_REVENUE"}),
    Filtered = Table.SelectRows(Picked, each [REGION_NAME] = "EUROPE")
in
    Filtered
