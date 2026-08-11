// Rigor follow-up to SV-RegionalSales-Filter.query.pq (dimension-only filter)
// and the DEFINE-MEASURE metric filter used by the DAX Studio suite's
// 08-metric-filter-outer-subquery.dax: this filters on the metric itself with
// a threshold that actually excludes some rows, confirming the connector's
// metric-filter (outer-subquery) path folds correctly on the exclusion case,
// not just the pass-through case.
let
    Source = SnowflakeSemanticViews.Contents("cs83279.eu-west-2.aws.snowflakecomputing.com", "XSMALL"),
    Db = Source{[name = "TPCH_RICH_DB"]}[Data],
    Sch = Db{[name = "TPCH_RICH_SVS"]}[Data],
    View = Sch{[name = "SV_REGIONAL_SALES"]}[Data],
    Picked = Table.SelectColumns(View, {"NATION_NAME", "TOTAL_REVENUE"}),
    Filtered = Table.SelectRows(Picked, each [TOTAL_REVENUE] > 9100000000),
    Sorted = Table.Sort(Filtered, {{"NATION_NAME", Order.Ascending}})
in
    Sorted
