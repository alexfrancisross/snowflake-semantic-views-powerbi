// v3.3.2 regression: COUNTROWS must render as COUNT("<dimension_or_fact_column>"),
// not bare COUNT(*)/AGG(*) (Snowflake semantic views reject both as invalid
// metric expressions). Table.Group's OnGroup fold hands the connector a
// Table.RowCount lambda wrapper, which ParseAggregateRecord must probe-detect
// as a true row-counter rather than falling through to the metric fallback.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Grouped = Table.Group(View, {"REGION_NAME"}, {{"RowCount", each Table.RowCount(_), Int64.Type}})
in
    Table.Sort(Grouped, {{"REGION_NAME", Order.Ascending}})
