// Second navigation level: schemas of the fixture database.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Projected = Table.SelectColumns(Db, {"name", "ItemKind", "IsLeaf"})
in
    Table.Sort(Projected, {{"name", Order.Ascending}})
