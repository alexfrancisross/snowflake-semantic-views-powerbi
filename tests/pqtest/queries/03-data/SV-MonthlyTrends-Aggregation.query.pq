// Onboards SV_MONTHLY_TRENDS (pre-aggregated time-series view over
// V_MONTHLY_REVENUE) - a time-intelligence shape not exercised by any other
// case: filter to one YEAR, project the period metric alongside the
// pre-computed year-to-date cumulative metric.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_MONTHLY_TRENDS"]}[Data],
    Picked = Table.SelectColumns(View, {"YEAR_MONTH", "YEAR", "MONTHLY_REVENUE", "CUMULATIVE_YTD"}),
    Filtered = Table.SelectRows(Picked, each [YEAR] = 1997),
    Sorted = Table.Sort(Filtered, {{"YEAR_MONTH", Order.Ascending}})
in
    Sorted
