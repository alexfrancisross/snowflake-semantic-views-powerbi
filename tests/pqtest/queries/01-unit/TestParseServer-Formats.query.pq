// Snapshots ParseSnowflakeServer across every supported server URL format
// (issues #1/#2: account-name, legacy locator, PrivateLink org + locator,
// mixed-case preservation, and a bare account identifier).
let
    Servers = {
        "myaccount.snowflakecomputing.com",
        "myorg-myaccount.snowflakecomputing.com",
        "xy12345.eu-west-1.snowflakecomputing.com",
        "myorg-myaccount.privatelink.snowflakecomputing.com",
        "xy12345.eu-west-1.privatelink.snowflakecomputing.com",
        "MyOrg-MyAccount.snowflakecomputing.com",
        "cs83279.eu-west-2.aws",
        "myaccount"
    }
in
    List.Transform(Servers, each [Input = _, Parsed = SnowflakeSemanticViews.TestParseServer(_)])
