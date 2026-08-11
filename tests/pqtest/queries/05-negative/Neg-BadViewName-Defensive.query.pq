// Negative test: the defensive navigation pattern the generators now emit
// (Table.SelectRows + Table.IsEmpty instead of a raw key lookup) must fail
// fast with a clear error for a nonexistent semantic view. PQTest treats
// raw errors as test failures, so the error is captured with `try` and the
// snapshot asserts on the error record.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    DbRows = Table.SelectRows(Source, each [name] = "TPCH_RICH_DB"),
    Db = if Table.IsEmpty(DbRows)
        then error Error.Record("DataSource.Error", "Database 'TPCH_RICH_DB' not found - it may have been dropped or renamed, or your role may not have access")
        else DbRows{0}[Data],
    SchemaRows = Table.SelectRows(Db, each [name] = "TPCH_RICH_SVS"),
    Sch = if Table.IsEmpty(SchemaRows)
        then error Error.Record("DataSource.Error", "Schema 'TPCH_RICH_DB.TPCH_RICH_SVS' not found - it may have been dropped or renamed, or your role may not have access")
        else SchemaRows{0}[Data],
    ViewRows = Table.SelectRows(Sch, each [name] = "SV_DOES_NOT_EXIST"),
    View = if Table.IsEmpty(ViewRows)
        then error Error.Record("DataSource.Error", "Semantic view 'TPCH_RICH_DB.TPCH_RICH_SVS.SV_DOES_NOT_EXIST' not found - it may have been dropped or renamed, or your role may not have access")
        else ViewRows{0}[Data],
    Result = try View
in
    if Result[HasError] then
        [HasError = true, Reason = Result[Error][Reason], Message = Result[Error][Message]]
    else
        [HasError = false, Reason = null, Message = "expected an error but got a table"]
