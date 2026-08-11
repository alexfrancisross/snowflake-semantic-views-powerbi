// Column names and M types the connector assigns to a semantic view table
// (dimension/metric discovery + Snowflake->M type mapping).
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Schema = Table.SelectColumns(Table.Schema(View), {"Name", "TypeName", "Kind"})
in
    Table.Sort(Schema, {{"Name", Order.Ascending}})
