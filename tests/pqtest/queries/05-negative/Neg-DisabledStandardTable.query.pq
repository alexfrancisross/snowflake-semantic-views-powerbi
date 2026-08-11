// Negative test: standard tables are disabled since v3.0 - accessing one
// through the connector must raise the "Standard tables are not supported"
// guidance error pointing at the native Snowflake connector. PQTest treats
// raw errors as test failures, so the error is captured with `try` and the
// snapshot asserts on the error record.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_TABLES"]}[Data],
    Result = try Table.RowCount(Sch{[name = "ORDERS"]}[Data])
in
    if Result[HasError] then
        [HasError = true, Reason = Result[Error][Reason], Message = Result[Error][Message]]
    else
        [HasError = false, Reason = null, Message = "expected an error but got a table"]
