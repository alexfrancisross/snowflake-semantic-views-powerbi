// Navigation root: asserts the fixture database appears at the top level.
// Projects only stable columns (other databases on the account may churn).
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Fixture = Table.SelectRows(Source, each [name] = "TPCH_RICH_DB")
in
    Table.SelectColumns(Fixture, {"name", "ItemKind", "IsLeaf"})
