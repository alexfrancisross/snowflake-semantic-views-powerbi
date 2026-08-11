// COUNTROWS combined with a real metric aggregate in the same GROUP BY -
// verifies the rowCountColumn selection (first available grouped
// dimension/fact source column) doesn't collide with, or get confused for,
// the other requested aggregate.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_CUSTOMER_ORDERS"]}[Data],
    Grouped = Table.Group(View, {"CUSTOMER_NAME"}, {
        {"OrderCount", each Table.RowCount(_), Int64.Type},
        {"TotalRevenue", each List.Sum([TOTAL_REVENUE]), type nullable number}
    })
in
    Table.Sort(Grouped, {{"CUSTOMER_NAME", Order.Ascending}})
