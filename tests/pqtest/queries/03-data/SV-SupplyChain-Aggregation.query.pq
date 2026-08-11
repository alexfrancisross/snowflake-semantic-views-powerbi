// Onboards SV_SUPPLY_CHAIN - a genuine M:M relationship via the PARTSUPP
// bridge table (6 tables, 5 relationships). README already documents
// Navigator preview errors for this view ("Preview Errors for Complex
// Semantic Views"); this exercises a compatible dimension/metric combination
// (both from the PART/PARTSUPP side of the bridge) through the connector's
// live SQL generation.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_SUPPLY_CHAIN"]}[Data],
    Picked = Table.SelectColumns(View, {"BRAND", "TOTAL_SUPPLY_COST", "TOTAL_AVAIL_QTY"}),
    Sorted = Table.Sort(Picked, {{"BRAND", Order.Ascending}})
in
    Sorted
