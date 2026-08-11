// Runs the connector's built-in M unit tests (ParseSnowflakeServer,
// ResolveDuplicateColumnNames) and snapshots a stable summary record:
// adding new unit tests later doesn't churn the snapshot as long as they pass.
let
    Results = SnowflakeSemanticViews.RunUnitTests(),
    Failures = Table.Sort(Table.SelectRows(Results, each not [Pass]), {"TestName"})
in
    [
        AllPass = Table.IsEmpty(Failures),
        FailCount = Table.RowCount(Failures),
        Failures = Failures
    ]
