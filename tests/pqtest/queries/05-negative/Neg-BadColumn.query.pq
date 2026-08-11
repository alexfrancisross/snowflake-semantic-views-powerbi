// Negative test: selecting a nonexistent column from a valid semantic view
// must raise a clear expression error (fails fast, client-side). PQTest
// treats raw errors as test failures, so the error is captured with `try`
// and the snapshot asserts on the error record.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Result = try Table.SelectColumns(View, {"NO_SUCH_COLUMN"})
in
    if Result[HasError] then
        [HasError = true, Reason = Result[Error][Reason], Message = Result[Error][Message]]
    else
        [HasError = false, Reason = null, Message = "expected an error but got a table"]
