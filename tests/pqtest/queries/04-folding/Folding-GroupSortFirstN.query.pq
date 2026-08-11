// Run with PQTest --failOnFoldingFailure (-foff): the whole expression must
// fold to a single Snowflake SQL statement (DirectQuery behavior).
//
// This proves the connector's own M layer folds a Table.Group -> Table.Sort
// -> Table.FirstN chain correctly (GROUP BY ... ORDER BY ... LIMIT in one
// query). Sorted by CUSTOMER_NAME as a secondary key (in addition to
// ORDER_DATE) so the top-200 selection is deterministic even when many rows
// tie on the most common ORDER_DATE. It intentionally does NOT reproduce the
// DAX Studio / Power BI Desktop "TOPN over SUMMARIZECOLUMNS doesn't fold"
// issue documented in
// README.md "Known Limitations" - that gap is in Analysis Services' own
// DirectQuery fold negotiation (a layer above the M runtime that decides
// whether to push a DAX-generated M plan to the source at all), not in this
// connector's Table.View handlers. Keeping this case guards against a
// regression at the connector layer even though the AS-layer limitation is
// out of the connector's control.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_CUSTOMER_ORDERS"]}[Data],
    Picked = Table.SelectColumns(View, {"CUSTOMER_NAME", "ORDER_DATE", "TOTAL_REVENUE"}),
    Grouped = Table.Group(Picked, {"CUSTOMER_NAME", "ORDER_DATE"}, {{"Total Revenue", each List.Sum([TOTAL_REVENUE]), type number}}),
    Sorted = Table.Sort(Grouped, {{"ORDER_DATE", Order.Descending}, {"CUSTOMER_NAME", Order.Ascending}}),
    Limited = Table.FirstN(Sorted, 200)
in
    Limited
