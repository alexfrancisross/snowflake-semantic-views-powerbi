// Leaf navigation level: all 17 semantic views in TPCH_RICH_SVS, with the
// enabled/disabled state (standard tables are disabled since v3.0).
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    Projected = Table.SelectColumns(Sch, {"name", "ItemKind", "IsLeaf"})
in
    Table.Sort(Projected, {{"name", Order.Ascending}})
