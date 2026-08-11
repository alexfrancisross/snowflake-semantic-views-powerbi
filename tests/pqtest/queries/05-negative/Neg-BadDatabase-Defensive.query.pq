// Negative test: the defensive navigation pattern the generators now emit
// (Table.SelectRows + Table.IsEmpty instead of a raw key lookup) must fail
// fast with a clear error for a nonexistent database. PQTest treats raw
// errors as test failures, so the error is captured with `try` and the
// snapshot asserts on the error record.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    DbRows = Table.SelectRows(Source, each [name] = "NO_SUCH_DATABASE_12345"),
    Db = if Table.IsEmpty(DbRows)
        then error Error.Record("DataSource.Error", "Database 'NO_SUCH_DATABASE_12345' not found - it may have been dropped or renamed, or your role may not have access")
        else DbRows{0}[Data],
    Result = try Db
in
    if Result[HasError] then
        [HasError = true, Reason = Result[Error][Reason], Message = Result[Error][Message]]
    else
        [HasError = false, Reason = null, Message = "expected an error but got a table"]
