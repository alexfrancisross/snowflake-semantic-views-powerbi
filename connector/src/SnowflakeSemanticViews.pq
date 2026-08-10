// SnowflakeSemanticViews Power BI Connector
// Version 3.3.2
//
// Connects to Snowflake Semantic Views with full DirectQuery support.
// Supports PAT, KeyPair, and Microsoft Account (OAuth) authentication.
// Uses ADBC (Arrow Database Connectivity) for query execution.

[Version = "3.3.2"]
section SnowflakeSemanticViews;

// =============================================================================
// EXTENSION.LOADFUNCTION DEFINITION
// =============================================================================
// Define Extension.LoadFunction before using it (required for .pqm modules)
// This function loads .pqm module files from the .mez archive
// Standard pattern for loading .pqm module files
Extension.LoadFunction = (name as text) =>
    let
        binary = Extension.Contents(name),
        asText = Text.FromBinary(binary)
    in
        Expression.Evaluate(asText, #shared);

// =============================================================================
// DEBUG CONFIGURATION
// =============================================================================
// Set to true for debugging, false for production
// When false, all Diagnostics.LogValue calls become no-ops with zero overhead
EnableTraceOutput = false;  // ← SET TO TRUE ONLY FOR LOCAL DEBUGGING

// =============================================================================
// STRICT FOLDING MODE
// =============================================================================
// STRICT_FOLDING_MODE: Control behavior when filters cannot be folded to SQL
//   true  = Throw error (prevents incorrect aggregations from client-side filtering)
//   false = Allow fallback to client-side filtering (may return incorrect results)
//
// RECOMMENDATION: Set to true for analytical correctness. When a filter cannot
// be pushed to Snowflake, client-side filtering on LIMIT'd data may produce
// incorrect aggregated values. Strict mode forces users to remove unsupported filters.
STRICT_FOLDING_MODE = true;  // ← SET TO TRUE FOR ANALYTICAL CORRECTNESS

// =============================================================================
// DIAGNOSTICS MODULE
// =============================================================================
// Load Diagnostics.pqm module (will be configured inside functions that use it)
DiagnosticsModule = Extension.LoadFunction("Diagnostics.pqm");

// =============================================================================
// SQL GENERATOR MODULE (Phase 3)
// =============================================================================
// Load SqlGenerator.pqm module for query folding support
// Provides date functions (Date.StartOfMonth -> DATE_TRUNC), text functions, etc.
SqlGenerator = Extension.LoadFunction("SqlGenerator.pqm");

// =============================================================================
// ADBC SQL GENERATOR (for Standard Tables DirectQuery) - DISABLED FOR DEBUGGING
// =============================================================================
// TODO: Re-enable once SqlGeneratorCommon.pqm loading issue is resolved
// SqlGeneratorHelpers = Extension.LoadFunction("SqlGeneratorCommon.pqm");
// AdbcSqlGenerator = null;  // Placeholder

// =============================================================================
// FILTER PARSER MODULE
// =============================================================================
// Load FilterParser.pqm module for OnSelectRows filter expression parsing
// Converts Power BI filter expressions to SQL WHERE conditions
FilterParser = Extension.LoadFunction("FilterParser.pqm");

// =============================================================================
// ERROR HANDLING MODULE
// =============================================================================
// Load ErrorHandling.pqm module for error detection and handling
// Provides warehouse suspended, OAuth expiration, and validation functions
ErrorHandling = Extension.LoadFunction("ErrorHandling.pqm");

// =============================================================================
// STRING CONSTANTS
// =============================================================================
// Column kinds (from semantic view metadata)
KIND_DIMENSION = "DIMENSION";
KIND_METRIC = "METRIC";
KIND_FACT = "FACT";
KIND_ROW_COUNT = "ROW_COUNT";
KIND_COLUMN = "COLUMN";  // For regular tables

// Object types in navigation
OBJECT_TABLE = "Table";
OBJECT_VIEW = "View";
OBJECT_SEMANTIC_VIEW = "SemanticView";

// Navigation item kinds (for Power BI icons)
ITEM_DATABASE = "Database";
ITEM_SCHEMA = "Schema";
ITEM_TABLE = "Table";
ITEM_VIEW = "View";
ITEM_CUBE_VIEW = "CubeView";  // For semantic views

// Error types (from ErrorHandling module for consistency)
ERROR_DATA_SOURCE = ErrorHandling[ERROR_DATA_SOURCE];
ERROR_EXPRESSION = ErrorHandling[ERROR_EXPRESSION];
ERROR_CREDENTIAL = ErrorHandling[ERROR_CREDENTIAL];
ERROR_FOLDING = ErrorHandling[ERROR_FOLDING];
ERROR_RATE_LIMIT = ErrorHandling[ERROR_RATE_LIMIT];
ERROR_PREVIEW_TIMEOUT = ErrorHandling[ERROR_PREVIEW_TIMEOUT];
ERROR_NO_COLUMNS = ErrorHandling[ERROR_NO_COLUMNS];
ERROR_FILTER = ErrorHandling[ERROR_FILTER];

// Default limits
DEFAULT_PREVIEW_LIMIT = 100;
DEFAULT_COMMAND_TIMEOUT = 300;  // 5 minutes
DEFAULT_CONNECTION_TIMEOUT = 60;  // 1 minute

//
// CREDENTIAL RETRIEVAL FUNCTION
// Returns credentials from Power BI UI (Extension.CurrentCredential)
// NOTE: server and warehouse are REQUIRED (enforced by function signature)
// v3.2.0: Uses ParseSnowflakeServer for proper account extraction (supports PrivateLink)
//
GetCredentials = (server as text, warehouse as text, optional role as text) as record =>
    if server = null or server = "" then
        // Production mode: server is REQUIRED - show clear error
        error Error.Record(ERROR_DATA_SOURCE,
            "Server name is required. Please enter your Snowflake server URL (e.g., xy12345.snowflakecomputing.com).")
    else if warehouse = null or warehouse = "" then
        // Production mode: warehouse is REQUIRED - show clear error
        error Error.Record(ERROR_DATA_SOURCE,
            "Warehouse name is required. Please enter your Snowflake warehouse name.")
    else
        let
            Credential = Extension.CurrentCredential(),
            AuthKind = Credential[AuthenticationKind],
            // v3.2.0: Use ParseSnowflakeServer for proper account extraction (supports PrivateLink)
            serverInfo = ParseSnowflakeServer(server),
            Account = serverInfo[Account],

            // For UsernamePassword, the Password field contains PAT
            PasswordContent = if AuthKind = "UsernamePassword" then Credential[Password] else null,

            // For KeyPair auth, get privatekey and passphrase from Credential
            // Certificate.Type shows as a text area for pasting PEM content
            PrivateKeyRaw = if AuthKind = "KeyPair" then Credential[privatekey]? else null,
            PassphraseRaw = if AuthKind = "KeyPair" then Credential[passphrase]? else null,

            // Debug: Log credential detection
            _ = Diagnostics.Trace(TraceLevel.Information, "GetCredentials",
                [
                    AuthKind = AuthKind ?? "(null)",
                    Server = server ?? "(null)",
                    Account = Account ?? "(null)",
                    IsPrivateLink = serverInfo[IsPrivateLink],
                    HasPrivateKey = PrivateKeyRaw <> null,
                    PrivateKeyType = if PrivateKeyRaw <> null then Value.Type(PrivateKeyRaw) else null,
                    PasswordLength = if PasswordContent <> null then Text.Length(PasswordContent) else 0
                ])
        in
            [
                Account = Account,
                Server = server,
                // Username from UsernamePassword or KeyPair auth
                Username = if AuthKind = "UsernamePassword" then Credential[Username]
                    else if AuthKind = "KeyPair" then Credential[Username]
                    else null,
                // Password only for PAT (UsernamePassword auth)
                Password = if AuthKind = "UsernamePassword" then PasswordContent else null,
                // Private key for KeyPair auth (from file picker)
                PrivateKey = PrivateKeyRaw,
                // Passphrase for encrypted private keys
                Passphrase = PassphraseRaw,
                Role = role,  // User-specified role (from connector UI)
                Warehouse = warehouse,
                Database = null,
                Schema = null,
                Token = if AuthKind = "OAuth" or AuthKind = "Aad" then Credential[access_token] else null,
                AuthKind = AuthKind
            ];

//
// GET AUTH TOKEN
// Returns the authentication token from credentials
// Supports: OAuth/Aad, UsernamePassword (PAT), KeyPair (JWT via ADBC)
//
// For UsernamePassword: Password field contains Programmatic Access Token (PAT)
//   - PAT: Create in Snowflake: Account Menu → Security → Programmatic Access Tokens
// For KeyPair: Private key file selected via file picker, JWT generated via ADBC driver
// For OAuth/Aad: Uses access_token from Microsoft authentication
//
GetAuthToken = (credentials as record) as record =>
    let
        existingToken = credentials[Token]?,
        authKind = credentials[AuthKind]?,
        password = credentials[Password]?,
        privateKey = credentials[PrivateKey]?
    in
        if existingToken <> null and Text.Length(existingToken) > 10 then
            // OAuth/Aad token already available
            let
                tokenType = if authKind = "Aad" or authKind = "OAuth" then "OAUTH" else "KEYPAIR_JWT"
            in
                [Token = existingToken, TokenType = tokenType]
        else if authKind = "KeyPair" then
            // KeyPair authentication - use ADBC driver which handles JWT generation internally
            let
                _ = Diagnostics.Trace(TraceLevel.Information, "GetAuthToken/KeyPair",
                    [
                        AuthKind = authKind,
                        HasPrivateKey = privateKey <> null,
                        PrivateKeyType = if privateKey <> null then Value.Type(privateKey) else null,
                        PrivateKeyLength = if privateKey <> null then
                            (if Value.Is(privateKey, type text) then Text.Length(privateKey)
                            else if Value.Is(privateKey, type binary) then Binary.Length(privateKey)
                            else -1)
                        else 0
                    ])
            in
                if privateKey = null then
                    error Error.Record(ERROR_DATA_SOURCE,
                        "Private key not found in credentials. " &
                        "Please select your .pem or .p8 private key file using the file picker.")
                else
                    // Return special marker to indicate ADBC should be used with KeyPair JWT
                    [Token = "USE_ADBC_KEYPAIR", TokenType = "KEYPAIR_ADBC"]
        else if authKind = "UsernamePassword" then
            // Password field contains PAT (Programmatic Access Token)
            // PAT tokens are JWTs but use different auth header than KeyPair JWTs
            // Don't add X-Snowflake-Authorization-Token-Type header for PAT - Snowflake auto-detects
            if password = null then
                error Error.Record(ERROR_DATA_SOURCE,
                    "No token provided. Please clear credentials and re-authenticate. " &
                    "Go to: File → Options → Data source settings → Clear Permissions")
            else if Text.Length(password) < 10 then
                error Error.Record(ERROR_DATA_SOURCE,
                    "Token too short. Password field must contain a PAT (Programmatic Access Token).")
            else
                // All tokens from UsernamePassword auth are treated as PAT
                // PAT tokens don't need X-Snowflake-Authorization-Token-Type header
                [Token = password, TokenType = "PAT"]
        else if authKind = "Anonymous" then
            error Error.Record(ERROR_DATA_SOURCE,
                "Anonymous authentication is not supported in production mode. " &
                "Please use Snowflake, KeyPair, or Microsoft Account authentication.")
        else
            error Error.Record(ERROR_DATA_SOURCE,
                "No authentication token available. Auth type: " & (authKind ?? "Unknown") &
                ". Please use Snowflake, KeyPair, or Microsoft Account authentication.");

//
// Main Connector Function
//
[DataSource.Kind="SnowflakeSemanticViews", Publish="SnowflakeSemanticViews.Publish"]
shared SnowflakeSemanticViews.Contents = Value.ReplaceType(
    SnowflakeSemanticViewsImpl,
    SnowflakeSemanticViewsType
);

// DirectQuery capabilities table
DirectQueryCapabilitiesTable = #table({"Name", "Value"}, {
    // NOTE: Table.Group should NOT be declared for DirectQuery compatibility
    // OnGroup handler is still called automatically when needed
    {"Core", null},
    {"LiteralCount", 1000},
    {"Table.FirstN", null},
    {"Table.Sort", null},
    // REMOVED: {"Table.Group", null}, - Declaring this causes DirectQuery validation to fail
    {"Table.RowCount", null},
    {"List.Sum", null},        // Enable SUM aggregation for metrics
    {"List.Average", null},
    {"List.Min", null},
    {"List.Max", null},
    {"List.Count", null},
    {"List.Distinct", null},
    {"List.First", null},      // Enable FIRST aggregation
    {"List.Last", null},       // Enable LAST aggregation
    {"List.StandardDeviation", null},  // STDEV aggregation
    {"List.Variance", null},           // VAR aggregation
    {"List.Median", null}              // MEDIAN aggregation
});

// Statistical function mapping: M function -> Snowflake SQL function
// These map Power BI statistical aggregations to native Snowflake functions
StatisticalFunctionMapping = [
    #"List.StandardDeviation" = "STDDEV_SAMP",
    #"List.Variance" = "VAR_SAMP",
    #"List.Median" = "MEDIAN"
];

//
// Function Type Definition
// Server and Warehouse are REQUIRED - this ensures Power BI shows the
// parameter dialog BEFORE the authentication dialog
//
SnowflakeSemanticViewsType =
    type function (
        server as (type text meta [
            Documentation.FieldCaption = "Server",
            Documentation.FieldDescription = "The full server name of your Snowflake account (e.g., account.region.snowflakecomputing.com).",
            Documentation.SampleValues = { "account.region.snowflakecomputing.com" }
        ]),
        warehouse as (type text meta [
            Documentation.FieldCaption = "Warehouse",
            Documentation.FieldDescription = "The name of the Snowflake warehouse to use for executing queries.",
            Documentation.SampleValues = { "COMPUTE_WH" }
        ]),
        optional role as (type text meta [
            Documentation.FieldCaption = "Role (optional)",
            Documentation.FieldDescription = "Snowflake role to use for the session. Leave empty for default role.",
            Documentation.SampleValues = { "ACCOUNTADMIN", "PUBLIC" }
        ]),
        optional connectionTimeout as (type number meta [
            Documentation.FieldCaption = "Connection Timeout (seconds)",
            Documentation.FieldDescription = "Number of seconds to wait for connection. Default is 60.",
            Documentation.SampleValues = { 60 }
        ]),
        optional commandTimeout as (type number meta [
            Documentation.FieldCaption = "Command Timeout (seconds)",
            Documentation.FieldDescription = "Number of seconds to wait for a query to execute. Default is 300 (5 minutes). Increase for large semantic views.",
            Documentation.SampleValues = { 300 }
        ]),
        optional useHighPrecision as (type logical meta [
            Documentation.FieldCaption = "Use High Precision",
            Documentation.FieldDescription = "Use Decimal type for numeric values (true) or Int64/Double (false). Default is true (high precision).",
            Documentation.AllowedValues = { true, false }
        ]),
        optional dateTimePrecision as (type text meta [
            Documentation.FieldCaption = "DateTime Precision",
            Documentation.FieldDescription = "Precision for datetime values. Default is 'microseconds' (Power BI limit).",
            Documentation.AllowedValues = { "microseconds", "nanoseconds" }
        ])
    ) as table meta [
        Documentation.Name = "Snowflake Semantic Views Connector",
        Documentation.LongDescription = "Connect to Snowflake Semantic Views using DirectQuery with full query folding support via ADBC."
    ];

//
// Main Implementation Function
// ADBC.DataSource Architecture - delegates all navigation to custom driver
// NOTE: server and warehouse are REQUIRED parameters
//       This ensures Power BI shows parameter dialog BEFORE authentication
//
SnowflakeSemanticViewsImpl = (
    server as text,
    warehouse as text,
    optional role as text,
    optional connectionTimeout as number,
    optional commandTimeout as number,
    optional useHighPrecision as logical,
    optional dateTimePrecision as text
) as table =>
    let
        // Get credentials - server and warehouse are guaranteed to be present
        credentials = GetCredentials(server, warehouse, role),

        // Phase 6.3: Validate server name before connecting
        // This catches malformed URLs, invalid hosts, and OAuth domain requirements
        authKind = Extension.CurrentCredential()[AuthenticationKind]? ?? "Unknown",
        validatedServer = ErrorHandling[ValidateServerName](credentials[Server], authKind),

        actualServer = validatedServer,
        actualAccount = credentials[Account],
        actualUsername = credentials[Username],
        actualWarehouse = credentials[Warehouse],
        authResult = GetAuthToken(credentials),
        actualToken = authResult[Token],
        actualTokenType = authResult[TokenType],  // "KEYPAIR_JWT" or "SNOWFLAKE"
        actualRole = credentials[Role],

        // Connection timeout: user-specified or default 60 seconds (for initial connection)
        actualConnectionTimeout = if connectionTimeout <> null then connectionTimeout else DEFAULT_CONNECTION_TIMEOUT,

        // Command timeout: user-specified or default 300 seconds (5 minutes) for query execution
        actualCommandTimeout = if commandTimeout <> null then commandTimeout else DEFAULT_COMMAND_TIMEOUT,

        // UseHighPrecision: true = Decimal type for numbers, false = Int64/Double
        // Default is true (high precision) to preserve data accuracy
        actualUseHighPrecision = if useHighPrecision <> null then useHighPrecision else true,

        // DateTimePrecision: "microseconds" or "nanoseconds"
        // Default is "microseconds" because Power BI DateTime only supports microsecond precision
        actualDateTimePrecision = if dateTimePrecision <> null then dateTimePrecision else "microseconds",

        // ============================================================================
        // CREATE DIRECTQUERY VIEW (ADBC Pattern)
        // ============================================================================
        // Full Table.View implementation with all handlers for DirectQuery support
        // Uses ADBC (Arrow Database Connectivity) for query execution
        // GetExpression returns NotImplemented pattern to prevent Power BI SQL generation
        // ============================================================================

        CreateDirectQueryView = (initialState as record) as table =>
            let
                _ = Diagnostics.Trace(TraceLevel.Information,
                    "SemanticView/CreateDirectQueryView/START",
                    [Database = initialState[Database], Schema = initialState[Schema], Table = initialState[Table]]),

                // Precompute qualified name
                qualifiedName = EscapeIdentifier(initialState[Database]) & "." &
                               EscapeIdentifier(initialState[Schema]) & "." &
                               EscapeIdentifier(initialState[Table]),

                // Enhanced initial state with qualified name
                stateWithQualifiedName = initialState & [QualifiedName = qualifiedName],

                // Generate initial query
                allColumns = List.Transform(initialState[Metadata], each [ColumnName]),
                initialQuery = GenerateSemanticViewQuery(
                    qualifiedName,
                    allColumns,
                    initialState[Metadata],
                    1000,
                    null,  // offset
                    null,  // orderBy
                    null,  // aliasMap
                    null,  // distinctCountMap
                    null,  // filterConditions
                    null,  // statisticalFuncMap
                    null,  // distinct
                    null,  // rowCountMap
                    null   // computedColumns
                ),

                // Add initial Query to state
                capturedState = stateWithQualifiedName & [Query = initialQuery],

                // RECURSIVE VIEW FUNCTION - Stateful pattern for DirectQuery
                View = (state as record) as table =>
                    let
                        // Configure Diagnostics module in View function scope
                        // Extract each function as a separate variable with dotted names
                        Diagnostics = DiagnosticsModule[GetFunctions](EnableTraceOutput),
                        Diagnostics.LogValue = Diagnostics[LogValue],
                        Diagnostics.LogValue2 = Diagnostics[LogValue2],
                        Diagnostics.WrapHandlers = Diagnostics[WrapHandlers],

                        // ─────────────────────────────────────────────────────────
                        // HELPER FUNCTIONS (use current state)
                        // ─────────────────────────────────────────────────────────

                        // Generate SQL from current state
                        GenerateSQL = () as text =>
                            let
                                selectedColumns = state[SelectedColumns]? ??
                                    List.Transform(state[Metadata], each [ColumnName]),
                                limit = state[Limit]?,
                                skip = state[Skip]?,
                                orderBy = state[OrderBy]?,
                                sql = GenerateSemanticViewQuery(
                                    state[QualifiedName],
                                    selectedColumns,
                                    state[Metadata],
                                    limit,
                                    skip,
                                    orderBy,
                                    state[AliasMap]?,
                                    state[DistinctCountMap]?,
                                    state[FilterConditions]?,
                                    state[StatisticalFuncMap]?,
                                    state[Distinct]?,
                                    state[RowCountMap]?,
                                    state[ComputedColumns]?)
                            in
                                sql,

                        // Get type for selected columns only
                        // Use type number for metrics to enable sigma icons and proper aggregation
                        GetSelectedType = () as type =>
                            let
                                // CRITICAL: Check for both null AND empty list - empty list should also trigger fallback
                                selectedColumns = if state[SelectedColumns]? <> null and not List.IsEmpty(state[SelectedColumns]) then
                                    state[SelectedColumns]
                                else
                                    List.Transform(state[Metadata], each [ColumnName]),

                                // Get AliasMap if available (from OnGroup) to resolve alias → real column
                                aliasMap = state[AliasMap]? ?? [],

                                // Get RowCountMap to identify COUNTROWS columns (they return integer)
                                rowCountMap = state[RowCountMap]? ?? [],

                                // CRITICAL FIX: Preserve Power BI's requested column order
                                // AND resolve aliases (a0, a1, etc.) to their real column types
                                selectedMetadata = List.Transform(
                                    selectedColumns,
                                    (colName) =>
                                        let
                                            // Check if this is a COUNTROWS column (returns integer)
                                            isRowCount = Record.HasFields(rowCountMap, colName),

                                            // Check if this is an alias (a0, a1, etc.) via AliasMap
                                            realColName = if Record.HasFields(aliasMap, colName) then
                                                Record.Field(aliasMap, colName)
                                            else
                                                colName,

                                            // Look up metadata using the REAL column name
                                            matches = List.Select(state[Metadata], each [ColumnName] = realColName),

                                            result = if isRowCount then
                                                // COUNTROWS returns integer - use INT64 type and ROW_COUNT kind
                                                // ROW_COUNT kind triggers Int64.Type in BuildMinimalTableType (not floating-point number)
                                                [ColumnName = colName, ColumnType = "INT64", ColumnKind = KIND_ROW_COUNT]
                                            else if List.IsEmpty(matches) then
                                                // Column not found - if it looks like an alias (a0-a9), treat as METRIC
                                                if Text.StartsWith(colName, "a") and Text.Length(colName) <= 3 then
                                                    [ColumnName = colName, ColumnType = "NUMBER", ColumnKind = KIND_METRIC]
                                                else
                                                    [ColumnName = colName, ColumnType = "TEXT", ColumnKind = KIND_DIMENSION]
                                            else
                                                // Found in metadata - use real type but keep alias name for column
                                                let
                                                    metaRecord = List.First(matches)
                                                in
                                                    [ColumnName = colName,
                                                     ColumnType = metaRecord[ColumnType],
                                                     ColumnKind = metaRecord[ColumnKind]]
                                        in
                                            result
                                ),

                                _logMeta = Diagnostics.LogValue("GetSelectedType/SelectedMetadata", selectedMetadata),

                                // Add computed columns from OnAddColumn handler
                                // Infer type from function name: Date.* → DATE, Text.* → TEXT, Number.* → NUMBER
                                computedCols = state[ComputedColumns]? ?? {},
                                computedMetadata = List.Transform(computedCols, (cc) =>
                                    let
                                        funcName = cc[Function],
                                        // Infer column type from function name
                                        colType = if Text.StartsWith(funcName, "Date.") then "DATE"
                                            else if Text.StartsWith(funcName, "Text.") then "TEXT"
                                            else if Text.StartsWith(funcName, "Number.") or Text.StartsWith(funcName, "Int") then "NUMBER"
                                            else "TEXT",
                                        colKind = "DIMENSION"  // Computed columns are dimensions (not aggregated)
                                    in
                                        [ColumnName = cc[Name], ColumnType = colType, ColumnKind = colKind]
                                ),

                                // Combine regular columns with computed columns
                                allMetadata = List.Combine({selectedMetadata, computedMetadata}),

                                // Use type number for metrics (ADBC returns proper numeric types)
                                typeWithAggregation = BuildMinimalTableType(allMetadata),
                                _ = Diagnostics.Trace(TraceLevel.Information,
                                    "SemanticView/GetSelectedType/WithAggregation",
                                    [Strategy = "alias resolution via AliasMap for proper types",
                                     ColumnCount = List.Count(selectedMetadata),
                                     ColumnOrder = List.Transform(selectedMetadata, each [ColumnName]),
                                     AliasMap = aliasMap])
                            in
                                typeWithAggregation,

                        // ─────────────────────────────────────────────────────────
                        // TABLE.VIEW WITH DIRECTQUERY HANDLERS
                        // ─────────────────────────────────────────────────────────

                        // Create Table.View with DirectQuery handlers
                        // CRITICAL: Diagnostics.WrapHandlers enables Power BI query folding!
                        // Without it, OnSelectColumns/OnGroup handlers are never called.
                        view = Table.View(null, Diagnostics.WrapHandlers([
                            GetType = () => GetSelectedType(),

                            GetRows = () =>
                                let
                                    // DEBUG: Log table name and metadata info (using LogValue which forces evaluation)
                                    tableName = Diagnostics.LogValue("GetRows/TableName", state[QualifiedName]),

                                    allDimensions = List.Select(state[Metadata], each [ColumnKind] = KIND_DIMENSION),
                                    allMetrics = List.Select(state[Metadata], each [ColumnKind] = KIND_METRIC),
                                    allDimensionNames = List.Transform(allDimensions, each [ColumnName]),
                                    allMetricNames = List.Transform(allMetrics, each [ColumnName]),
                                    dimCount = List.Count(allDimensions),
                                    metricCount = List.Count(allMetrics),
                                    _logCounts = Diagnostics.LogValue("GetRows/DimCount=" & Text.From(dimCount) & "_MetricCount=" & Text.From(metricCount), [DimCount = dimCount, MetricCount = metricCount]),

                                    // Check if we're in a grouped context (OnGroup was called)
                                    isGrouped = Diagnostics.LogValue("GetRows/IsGrouped", state[IsGrouped]? ?? false),
                                    groupByKeys = Diagnostics.LogValue("GetRows/GroupByKeys", state[GroupByKeys]? ?? {}),
                                    existingFilterConditions = state[FilterConditions]? ?? {},

                                    // Check if explicit columns were selected via OnSelectColumns
                                    // CRITICAL: Check for both null AND empty list - empty list should also trigger fallback
                                    hasExplicitColumns = state[SelectedColumns]? <> null and not List.IsEmpty(state[SelectedColumns]? ?? {}),
                                    _logHasExplicit = Diagnostics.LogValue("GetRows/HasExplicitColumns", hasExplicitColumns),

                                    // Check if aggregation context exists (OnGroup was called)
                                    hasAggregationContext = state[IsGrouped]? = true,
                                    aggregationKeys = state[GroupByKeys]? ?? {},
                                    lastMetrics = state[LastMetrics]? ?? {},

                                    // OPTION 3 FIX: Smart column selection based on context
                                    // Priority: 1) Explicit columns from OnSelectColumns
                                    //           2) GroupBy keys + LastMetrics from OnGroup (for DirectQuery)
                                    //           3) Fall back to all columns (for navigation/preview)
                                    selectedColumns = if hasExplicitColumns then
                                        Diagnostics.LogValue("GetRows/SelectedColumns/Explicit", state[SelectedColumns])
                                    else if hasAggregationContext and not List.IsEmpty(aggregationKeys) then
                                        // DirectQuery scenario: Use aggregation context
                                        let
                                            derivedCols = List.Distinct(aggregationKeys & lastMetrics),
                                            _log = Diagnostics.LogValue("GetRows/SelectedColumns/FromAggContext", derivedCols)
                                        in
                                            derivedCols
                                    else
                                        // Fall back to all columns (navigation/preview)
                                        let
                                            allColNames = List.Transform(state[Metadata], each [ColumnName]),
                                            _log = Diagnostics.LogValue("GetRows/SelectedColumns/AllColumns", allColNames)
                                        in
                                            allColNames,

                                    // LAYER 1 FIX: Forced Aggregation Detection
                                    // When Power BI's Table.PrefixColumns bypasses our handlers, we still need
                                    // to ensure proper GROUP BY so each dimension combination has exactly ONE row.
                                    // This way, when Power BI applies List.Sum client-side, it sums one value = correct.
                                    selectedMetricNames = List.Select(selectedColumns, each List.Contains(allMetricNames, _)),
                                    selectedDimensionNames = List.Select(selectedColumns, each List.Contains(allDimensionNames, _)),
                                    hasSelectedMetrics = not List.IsEmpty(selectedMetricNames),
                                    hasSelectedDimensions = not List.IsEmpty(selectedDimensionNames),

                                    // Force GROUP BY if metrics are selected but OnGroup wasn't called
                                    // This ensures each dimension combination appears only once in results
                                    needsForcedGroupBy = hasSelectedMetrics and not hasAggregationContext,
                                    _logForcedGroupBy = Diagnostics.LogValue("GetRows/NeedsForcedGroupBy", needsForcedGroupBy),

                                    // Effective GROUP BY keys: use explicit keys if OnGroup was called,
                                    // otherwise derive from selected dimensions
                                    effectiveGroupByKeys = if hasAggregationContext then
                                        aggregationKeys
                                    else if needsForcedGroupBy and hasSelectedDimensions then
                                        selectedDimensionNames
                                    else
                                        {},
                                    _logEffectiveGroupBy = Diagnostics.LogValue("GetRows/EffectiveGroupByKeys", effectiveGroupByKeys),

                                    // ─────────────────────────────────────────────────────────
                                    // PREVIEW OPTIMIZATION: Inject high-cardinality filter for previews
                                    // ─────────────────────────────────────────────────────────
                                    // Preview mode = no explicit columns AND not grouped AND has LIMIT set
                                    // Import mode loads all data without LIMIT, so we only filter when LIMIT is present.
                                    // This filters on a high-cardinality dimension to prune data BEFORE aggregation,
                                    // reducing preview time from 4+ minutes to ~30 seconds for large semantic views.
                                    isPreviewMode = not hasExplicitColumns and not hasAggregationContext and state[Limit]? <> null,
                                    _logPreviewMode = Diagnostics.LogValue("GetRows/IsPreviewMode", [IsPreview = isPreviewMode, Limit = state[Limit]?]),

                                    // Generate preview filter from cached high-cardinality dimension info
                                    previewFilterConditions = if isPreviewMode and state[PreviewFilterInfo]? <> null then
                                        GeneratePreviewFilter(state[PreviewFilterInfo])
                                    else
                                        {},
                                    _logPreviewFilter = if not List.IsEmpty(previewFilterConditions) then
                                        Diagnostics.Trace(TraceLevel.Information, "GetRows/PreviewOptimization/Applied", [
                                            Column = state[PreviewFilterInfo][Column]?,
                                            Cardinality = state[PreviewFilterInfo][Cardinality]?,
                                            SampleValue = state[PreviewFilterInfo][SampleValue]?
                                        ], true)
                                    else true,

                                    // Combine existing filters with preview filter
                                    filterConditions = List.Combine({existingFilterConditions, previewFilterConditions}),

                                    // DIAGNOSTIC: Log FilterConditions state before query generation
                                    _traceFilters = Diagnostics.Trace(TraceLevel.Information, "GetRows/FilterConditions", [
                                        HasFilterConditions = not List.IsEmpty(filterConditions),
                                        FilterConditionsCount = List.Count(filterConditions),
                                        FilterConditions = filterConditions,
                                        IsPreviewMode = isPreviewMode,
                                        PreviewFilterApplied = not List.IsEmpty(previewFilterConditions)
                                    ], true),

                                    // Generate inner query with AGG() functions
                                    // LIMIT is pushed inside the query for efficiency
                                    // Note: Large semantic views (SF100+) require appropriate warehouse sizing
                                    innerSQL = GenerateSemanticViewQuery(
                                        state[QualifiedName],
                                        selectedColumns,
                                        state[Metadata],
                                        state[Limit]?,  // LIMIT inside query
                                        state[Skip]?,   // OFFSET for pagination
                                        state[OrderBy]?,
                                        state[AliasMap]?,
                                        state[DistinctCountMap]?,
                                        filterConditions,  // Combined: existing filters + preview filter
                                        state[StatisticalFuncMap]?,
                                        state[Distinct]?,
                                        state[RowCountMap]?,
                                        state[ComputedColumns]?  // Computed columns from OnAddColumn
                                    ),

                                    // Wrap in nested query for Power BI compatibility
                                    // LIMIT is already inside innerSQL, no need for outer LIMIT
                                    finalSQL = Diagnostics.LogValue("GetRows/FINAL_SQL", "SELECT * FROM (" & innerSQL & ") AS " & EscapeIdentifier("_")),

                                    // Execute SQL and get raw result
                                    rawResult = state[Context][ExecuteQueryInternal](finalSQL),

                                    // ADBC returns properly typed Arrow data directly
                                    // No manual type conversion needed

                                    // Phase 5.3: Transform complex types (VARIANT, OBJECT, ARRAY, STRUCT)
                                    // Converts JSON text to native M types (records/lists) for easy expansion
                                    transformedResult = TransformComplexColumns(rawResult),

                                    result = Diagnostics.LogValue("GetRows/ResultWithProperTypes", transformedResult)
                                in
                                    result,

                            // ─────────────────────────────────────────────────────────
                            // FOLDING HANDLERS
                            // ─────────────────────────────────────────────────────────

                            OnSelectColumns = (columns as list) as table =>
                                let
                                    tableName = state[QualifiedName],
                                    _logStart = Diagnostics.LogValue("OnSelectColumns/RequestedColumns", columns),

                                    // Separate REAL columns (exist in metadata) from ALIASES (like a0, a1)
                                    allColumnNames = List.Transform(state[Metadata], each [ColumnName]),
                                    allMetricNames = List.Transform(
                                        List.Select(state[Metadata], each [ColumnKind] = KIND_METRIC),
                                        each [ColumnName]
                                    ),

                                    realColumns = List.Select(columns, each List.Contains(allColumnNames, _)),
                                    aliasColumns = List.Select(columns, each not List.Contains(allColumnNames, _)),

                                    // Track which METRICS were selected (for OnGroup alias mapping)
                                    selectedMetrics = List.Select(realColumns, each List.Contains(allMetricNames, _)),
                                    _logMetrics = Diagnostics.LogValue("OnSelectColumns/SelectedMetrics", selectedMetrics),

                                    _logReal = Diagnostics.LogValue("OnSelectColumns/RealColumns", realColumns),
                                    _logAlias = Diagnostics.LogValue("OnSelectColumns/AliasColumns", aliasColumns),

                                    // Track metrics that were EVER selected (accumulate, don't replace)
                                    // This helps OnGroup map aliases to the correct metrics
                                    prevSelectedMetrics = state[SelectedMetrics]? ?? {},
                                    newSelectedMetrics = if List.IsEmpty(selectedMetrics) then
                                        prevSelectedMetrics  // Keep previous if none selected now
                                    else
                                        selectedMetrics,     // Update if new metrics selected

                                    // Track aliases for later resolution in OnGroup
                                    // These are Power BI's aggregate aliases (a0, a1, etc.)
                                    newStateWithCols = state & [
                                        SelectedColumns = realColumns,  // Only REAL columns
                                        PendingAliases = aliasColumns,  // Track aliases for OnGroup
                                        SelectedMetrics = newSelectedMetrics  // Track metrics for alias mapping
                                    ],
                                    newSQL = GenerateSemanticViewQuery(
                                        state[QualifiedName],
                                        realColumns,
                                        state[Metadata],
                                        state[Limit]?,
                                        state[Skip]?,
                                        state[OrderBy]?,
                                        state[AliasMap]?,
                                        state[DistinctCountMap]?,
                                        state[FilterConditions]?,
                                        state[StatisticalFuncMap]?,
                                        state[Distinct]?,
                                        state[RowCountMap]?,
                                        state[ComputedColumns]?),
                                    newState = newStateWithCols & [Query = newSQL]
                                in
                                    @View(newState),

                            // Use shared state update helpers - SQL is regenerated in GetRows
                            OnTake = (count as number) as table =>
                                let _ = Diagnostics.LogValue("OnTake/Count", count)
                                in @View(UpdateStateWithLimit(state, count)),

                            OnSkip = (count as number) as table =>
                                let _ = Diagnostics.LogValue("OnSkip/Count", count)
                                in @View(UpdateStateWithSkip(state, count)),

                            OnDistinct = (columns as list) as table =>
                                let _ = Diagnostics.LogValue("OnDistinct/Columns", columns)
                                in @View(UpdateStateWithDistinct(state)),

                            OnGroup = (keys as list, aggregates as list) as table =>
                                let
                                    tableName = state[QualifiedName],
                                    // Use LogValue which forces evaluation (Trace doesn't get executed due to lazy eval)
                                    keysLogged = Diagnostics.LogValue("OnGroup/Keys", keys),
                                    aggregatesLogged = Diagnostics.LogValue("OnGroup/RawAggregates", aggregates),

                                    // Get all metrics for column extraction (uses top-level StripTablePrefix)
                                    allMetricsForExtraction = List.Select(state[Metadata], each [ColumnKind] = KIND_METRIC),
                                    allMetricNamesForExtraction = List.Transform(allMetricsForExtraction, each [ColumnName]),

                                    // Strip prefixes from keys using shared helper
                                    cleanKeys = Diagnostics.LogValue("OnGroup/CleanKeys",
                                        List.Transform(keysLogged, each StripTablePrefix(_))),

                                    // Log aggregate fields - use aggregatesLogged to force logging
                                    aggregateFields = Diagnostics.LogValue("OnGroup/AggregateFields",
                                        List.Transform(aggregatesLogged, each try Record.FieldNames(_) otherwise {"NOT_A_RECORD"})),

                                    // Log first aggregate
                                    firstAgg = Diagnostics.LogValue("OnGroup/FirstAggregate",
                                        if List.Count(aggregatesLogged) > 0 then aggregatesLogged{0} else null),

                                    // Use shared ParseAggregateRecord for consistent parsing
                                    aggregateDetails = List.Transform(aggregatesLogged, (agg) =>
                                        ParseAggregateRecord(agg, allMetricNamesForExtraction)),
                                    _logDetails = Diagnostics.LogValue("OnGroup/AggregateDetails", aggregateDetails),

                                    // Get all metrics from metadata
                                    allMetrics = List.Select(state[Metadata], each [ColumnKind] = KIND_METRIC),
                                    allMetricNames = List.Transform(allMetrics, each [ColumnName]),
                                    _log4 = Diagnostics.LogValue("OnGroup/AllMetricNames", allMetricNames),

                                    // Get previously selected metrics - OnSelectColumns stores them in SelectedMetrics
                                    prevSelectedCols = state[SelectedColumns]? ?? {},
                                    _logPrevCols = Diagnostics.LogValue("OnGroup/PrevSelectedCols", prevSelectedCols),

                                    // FIX: Use state[SelectedMetrics] which OnSelectColumns explicitly tracks
                                    // Also try filtering SelectedColumns as fallback
                                    stateSelectedMetrics = state[SelectedMetrics]? ?? {},
                                    _logStateMetrics = Diagnostics.LogValue("OnGroup/StateSelectedMetrics", stateSelectedMetrics),

                                    selectedMetrics = if not List.IsEmpty(stateSelectedMetrics) then
                                        stateSelectedMetrics
                                    else
                                        List.Select(prevSelectedCols, each List.Contains(allMetricNames, _)),
                                    _logSelectedMetrics = Diagnostics.LogValue("OnGroup/SelectedMetrics", selectedMetrics),
                                    _logMetricsToUse = Diagnostics.LogValue("OnGroup/MetricsToUse", if List.IsEmpty(selectedMetrics) then allMetricNames else selectedMetrics),

                                    // For semantic views with pre-aggregated metrics, we map aliases to metrics
                                    // The Column field in aggregateDetails now contains the extracted column name
                                    // from either the direct Column field OR the Function expression
                                    aggregateAliases = List.Transform(aggregatesLogged, each Record.FieldOrDefault(_, "Name", "")),
                                    _logAliases = Diagnostics.LogValue("OnGroup/AggregateAliases", aggregateAliases),

                                    // Metrics for position-based fallback (only used when extraction fails)
                                    metricsToUse = if List.IsEmpty(selectedMetrics) then allMetricNames else selectedMetrics,
                                    numMetrics = List.Count(metricsToUse),

                                    allAggregatesMapped = List.Transform(
                                        List.Positions(aggregateDetails),
                                        (idx) =>
                                            let
                                                detail = aggregateDetails{idx},
                                                alias = detail[Name],
                                                // Column now comes from either direct field OR extracted from Function
                                                extractedColumn = detail[Column],
                                                // Check if extracted column is a valid metric
                                                isValidMetric = extractedColumn <> null and List.Contains(allMetricNames, extractedColumn),

                                                // FIX: Allow fallback even when OnSelectColumns wasn't called
                                                // Power BI may call OnGroup directly without OnSelectColumns for DirectQuery
                                                // In that case, use position-based mapping to all metrics
                                                metricIdx = if numMetrics > 0 then Number.Mod(idx, numMetrics) else 0,
                                                fallbackMetric = if numMetrics > 0 then
                                                    metricsToUse{metricIdx}
                                                else
                                                    null,

                                                // Priority: extracted column > fallback
                                                mappedMetric = if isValidMetric then extractedColumn else fallbackMetric
                                            in
                                                [
                                                    Alias = alias,
                                                    Column = if detail[IsRowCount] then null else mappedMetric,  // COUNTROWS has no column
                                                    ExtractedColumn = extractedColumn,  // For debugging
                                                    IsDistinctCount = detail[IsDistinctCount],
                                                    IsRowCount = detail[IsRowCount],
                                                    IsStatistical = detail[IsStatistical],
                                                    StatisticalSqlFunc = detail[StatisticalSqlFunc]
                                                ]
                                    ),
                                    _logMapped = Diagnostics.LogValue("OnGroup/MappedAggregates", allAggregatesMapped),

                                    // Valid aggregates: have Column OR are IsRowCount (COUNTROWS has no column but is valid)
                                    validAggregates = List.Select(allAggregatesMapped, each [Column] <> null or [IsRowCount]),

                                    // Use shared map builders for consistency
                                    aliasMap = BuildAliasMap(validAggregates),
                                    distinctCountMap = BuildDistinctCountMap(validAggregates),
                                    statisticalFuncMap = BuildStatisticalFuncMap(validAggregates),

                                    rowCountMap = BuildRowCountMap(validAggregates),

                                    _log5 = Diagnostics.LogValue("OnGroup/AliasMap", aliasMap),
                                    _logDC = Diagnostics.LogValue("OnGroup/DistinctCountMap", distinctCountMap),
                                    _logSF = Diagnostics.LogValue("OnGroup/StatisticalFuncMap", statisticalFuncMap),
                                    _logRC = Diagnostics.LogValue("OnGroup/RowCountMap", rowCountMap),

                                    // Include ALL valid aliases - Power BI expects all columns it requested
                                    // For pre-aggregated metrics, unmappable ops (COUNT) return same as SUM
                                    validAliasNames = List.Transform(validAggregates, each [Alias]),
                                    allColumns = List.Combine({cleanKeys, validAliasNames}),  // Use cleanKeys (stripped prefixes)
                                    _log6 = Diagnostics.LogValue("OnGroup/FinalColumns", allColumns),

                                    newState = state & [
                                        SelectedColumns = allColumns,
                                        AliasMap = aliasMap,
                                        DistinctCountMap = distinctCountMap,
                                        StatisticalFuncMap = statisticalFuncMap,
                                        RowCountMap = rowCountMap,
                                        IsGrouped = true,  // Track that OnGroup was called
                                        GroupByKeys = cleanKeys  // Store dimensions for GROUP BY (prefix-stripped)
                                    ]
                                in
                                    if List.IsEmpty(validAggregates) and not List.IsEmpty(aggregates) then error Error.Record(ERROR_EXPRESSION, "Cannot map aggregates - folding disabled") else @View(newState),

                            OnSort = (order as list) as table =>
                                let _ = Diagnostics.LogValue("OnSort/Order", order)
                                in @View(UpdateStateWithSort(state, order)),

                            // OnSelectRows - Push WHERE clauses to Snowflake
                            // Uses FilterParser.pqm module for parsing filter expressions
                            // NOTE: No type annotations for DirectQuery compatibility
                            // NOTE: Filter caching not needed - M engine handles lazy evaluation,
                            // and conditions accumulate in state[FilterConditions] across calls
                            OnSelectRows = (selector) =>
                                let
                                    // ================================================================================
                                    // DIAGNOSTIC: Log ENTRY to OnSelectRows - EASY TO FIND IN LOGS
                                    // ================================================================================
                                    _entryLog = Diagnostics.Trace(TraceLevel.Information,
                                        "================== ONSELECTROWS_CALLED ==================",
                                        [TableName = state[QualifiedName]?], true),

                                    // Use FilterParser module to parse the filter expression
                                    parseResult = FilterParser[ParseFilterExpression](selector, EscapeIdentifier, FormatSqlValue),

                                    // Extract results from parser
                                    realConditions = parseResult[Conditions],
                                    canFold = parseResult[CanFold],
                                    allIgnored = parseResult[AllIgnored],
                                    failedCount = parseResult[FailedCount],
                                    firstError = parseResult[ErrorCondition],
                                    hasHelpfulError = firstError <> null,
                                    exprAst = parseResult[RawAST],
                                    parsedConditions = parseResult[ParsedConditions],

                                    // ================================================================================
                                    // DIAGNOSTIC: Log RESULT of filter parsing
                                    // ================================================================================
                                    _resultLog = Diagnostics.Trace(TraceLevel.Information,
                                        "================== ONSELECTROWS_RESULT ==================",
                                        [
                                            CanFold = canFold,
                                            RealConditionsCount = List.Count(realConditions),
                                            IgnoredConditionsCount = parseResult[IgnoredCount],
                                            FailedCount = failedCount,
                                            AllIgnored = allIgnored,
                                            RealConditions = realConditions,
                                            ASTKind = exprAst[Kind]?,
                                            ASTOperator = exprAst[Operator]?
                                        ], true),

                                    result = if hasHelpfulError then
                                        // HELPFUL ERROR: User made a detectable mistake
                                        error Error.Record(
                                            firstError[ErrorType]? ?? ERROR_FILTER,
                                            firstError[Message]? ?? "Filter expression is invalid.",
                                            [
                                                TableName = state[QualifiedName]?,
                                                ErrorType = firstError[ErrorType]?,
                                                Suggestion = "Check the filter expression and correct the argument order."
                                            ]
                                        )
                                    else if canFold and not allIgnored then
                                        let
                                            existingConditions = if state[FilterConditions]? = null then {} else state[FilterConditions],
                                            allConditions = List.Combine({existingConditions, realConditions}),
                                            newState = state & [FilterConditions = allConditions]
                                        in
                                            @View(newState)
                                    else if canFold and allIgnored then
                                        // All conditions were ignored (Power BI internal filters)
                                        @View(state)
                                    else
                                        // Folding failed - build debug info
                                        let
                                            SafeToText = (val) =>
                                                if val = null then "null"
                                                else if val is function then "[function]"
                                                else if val is list then "[list:" & Text.From(List.Count(val)) & "]"
                                                else if val is record then "[record]"
                                                else if val is table then "[table]"
                                                else try Text.From(val) otherwise "[?]",

                                            astKind = if exprAst <> null then Text.From(exprAst[Kind]?) else "null",
                                            astOp = if exprAst <> null then Text.From(exprAst[Operator]?) else "null",
                                            orBranches = if astKind = "Binary" and astOp = "Or" then FilterParser[FlattenOr](exprAst) else {},
                                            branchCount = List.Count(orBranches),

                                            parsedDebug = try List.Transform(parsedConditions, each
                                                if _ = null then "FAILED"
                                                else if _[Ignore]? = true then "IGNORED"
                                                else SafeToText(_[Column]?) & " " & SafeToText(_[Operator]?) & " " & SafeToText(_[Value]?))
                                            otherwise {"[parse error]"},
                                            parsedStr = try Text.Combine(parsedDebug, " | ") otherwise "[combine error]",

                                            astDetails = try ("AST[Kind=" & astKind & ", Op=" & astOp &
                                                        "] OrBranches=" & Text.From(branchCount) &
                                                        " Parsed=[" & parsedStr & "]") otherwise "[debug error]",

                                            _debugLog = Diagnostics.Trace(TraceLevel.Error,
                                                "FILTER_FOLD_FAILURE_DEBUG",
                                                [FullAST = exprAst, ParsedConditions = parsedConditions], true),

                                            isStrictMode = state[StrictFoldingMode]? ?? false,
                                            strictErrorMsg = "Filter cannot be pushed to Snowflake. " &
                                                "This filter pattern is not supported for folding. " &
                                                "Details: " & astDetails
                                        in
                                            if isStrictMode then
                                                error Error.Record(ERROR_FOLDING, strictErrorMsg,
                                                    [TableName = state[QualifiedName]?, FilterAST = exprAst])
                                            else
                                                Table.ViewError([Reason = ERROR_EXPRESSION, Message = "OnSelectRows: " & astDetails])
                                in
                                    result,

                            // OnAddColumn - Fold computed columns to SQL
                            // Handles date extraction (YEAR, MONTH), text functions (UPPER), math (ROUND)
                            // Uses SqlGenerator.pqm function mappings
                            OnAddColumn = (tableName as text, columnName as text, columnGenerator as function) =>
                                let
                                    // Parse the column generator function to extract expression
                                    expr = try RowExpression.From(columnGenerator) otherwise null,
                                    _ = Diagnostics.LogValue("OnAddColumn/ColumnName", columnName),
                                    _expr = Diagnostics.LogValue("OnAddColumn/RowExpression", expr),

                                    // Helper: Strip table prefix from column name
                                    StripColPrefix = (colName) =>
                                        if colName = null then null
                                        else if Text.Contains(colName, ".") then
                                            List.Last(Text.Split(colName, "."))
                                        else colName,

                                    // Extract function name and source column from AST
                                    funcInfo = if expr <> null and expr[Kind]? = "Invocation" then
                                        let
                                            funcValue = expr[Function]?,
                                            // Get function name from metadata
                                            funcName = try Value.Metadata(funcValue[Value]?)[Name] otherwise null,
                                            args = expr[Arguments]?,
                                            firstArg = if args <> null and List.Count(args) > 0 then args{0} else null,
                                            // Get source column from first argument (FieldAccess)
                                            sourceCol = if firstArg <> null and firstArg[Kind]? = "FieldAccess" then
                                                StripColPrefix(firstArg[MemberName]?)
                                            else null,
                                            // Get additional arguments (for functions like Number.Round(col, 2))
                                            additionalArgs = if args <> null and List.Count(args) > 1 then
                                                List.Transform(List.Skip(args, 1), each
                                                    if _[Kind]? = "Constant" then _[Value] else null
                                                )
                                            else {}
                                        in
                                            [FunctionName = funcName, SourceColumn = sourceCol, Args = additionalArgs]
                                    else null,

                                    _funcInfo = Diagnostics.LogValue("OnAddColumn/FuncInfo", funcInfo),

                                    // Check if function is supported by SqlGenerator
                                    isSupported = funcInfo <> null and
                                                  funcInfo[FunctionName] <> null and
                                                  funcInfo[SourceColumn] <> null and
                                                  SqlGenerator[IsFunctionSupported](funcInfo[FunctionName]),

                                    _isSupported = Diagnostics.LogValue("OnAddColumn/IsSupported", isSupported),

                                    // Build result - if supported, add to ComputedColumns state
                                    result = if isSupported then
                                        let
                                            existingComputed = state[ComputedColumns]? ?? [],
                                            // Create new computed column record
                                            newComputedCol = [
                                                Name = columnName,
                                                Function = funcInfo[FunctionName],
                                                SourceColumn = funcInfo[SourceColumn],
                                                Args = funcInfo[Args]
                                            ],
                                            newComputed = List.Combine({existingComputed, {newComputedCol}}),
                                            newState = state & [ComputedColumns = newComputed]
                                        in
                                            @View(newState)
                                    else
                                        // Signal folding not possible - Power BI will compute client-side
                                        ...
                                in
                                    result,

                            // GetExpression - Return NotImplemented pattern for DirectQuery
                            // Signals to Power BI that SQL generation should be handled by GetRows
                            GetExpression = () =>
                                [
                                    Kind = "Invocation",
                                    Function = [Kind = "Constant", Value = Value.NativeQuery],
                                    Arguments = {
                                        [
                                            Kind = "Invocation",
                                            Function = [Kind = "Constant", Value = SnowflakeSemanticViews.Contents],
                                            Arguments = {
                                                [Kind = "Constant", Value = state[Context][Server]],
                                                [Kind = "Constant", Value = state[Context][Warehouse]]
                                            }
                                        ],
                                        [Kind = "NotImplemented"]
                                    }
                                ],

                            OnInvoke = (function, args, index) =>
                                if function = DirectQueryCapabilities.From then
                                    DirectQueryCapabilitiesTable
                                else
                                    ...
                        ]) & [ThrowFoldingFailures = false])  // ThrowFoldingFailures OUTSIDE WrapHandlers (it's not a function)
                    in
                        view
            in
                View(capturedState),  // Return View without extra metadata (SupportsDirectQuery is in Publish section)

        // ============================================================================
        // CUSTOM NAVIGATION (BuildCustomNavigation Pattern)
        // ============================================================================
        // Restored from v0.9.0-ADBC - builds custom navigation tree
        // Databases → Schemas → Tables/Views
        // ============================================================================

        BuildCustomNavigation = () as table =>
            let
                // Create execution context
                // Uses credentials from GetCredentials()
                // ALL auth types now use ADBC (unified execution path)
                // - KEYPAIR_ADBC: Uses auth_jwt with private key
                // - PAT: Uses auth_oauth with token
                // - OAUTH: Uses auth_oauth with token
                ExecuteQuery = (sql as text) =>
                    if actualTokenType = "KEYPAIR_ADBC" then
                        // KeyPair auth - use ADBC with JWT
                        ExecuteQueryViaADBC(
                            [
                                Server = actualServer,
                                Warehouse = actualWarehouse,
                                TokenType = "KEYPAIR_ADBC",
                                Username = actualUsername,
                                PrivateKey = credentials[PrivateKey],
                                Passphrase = credentials[Passphrase],
                                CommandTimeout = actualCommandTimeout,
                                ConnectionTimeout = actualConnectionTimeout
                            ],
                            sql
                        )
                    else if actualTokenType = "PAT" or actualTokenType = "OAUTH" then
                        // PAT uses auth_snowflake with username/password
                        // OAuth uses auth_oauth with access_token
                        ExecuteQueryViaADBC(
                            [
                                Server = actualServer,
                                Warehouse = actualWarehouse,
                                TokenType = actualTokenType,
                                Token = actualToken,
                                Username = actualUsername,  // Required for PAT auth_snowflake
                                CommandTimeout = actualCommandTimeout,
                                ConnectionTimeout = actualConnectionTimeout
                            ],
                            sql
                        )
                    else
                        // Unknown auth type - error (all known types use ADBC now)
                        error Error.Record(ERROR_DATA_SOURCE,
                            "Unsupported authentication type: " & actualTokenType & ". " &
                            "Supported types: KEYPAIR_ADBC, PAT, OAUTH"),

                ExecuteQueryInternal = ExecuteQuery,  // Internal query execution function

                context = [
                    ExecuteQuery = ExecuteQuery,
                    ExecuteQueryInternal = ExecuteQueryInternal,
                    // ExecuteMetadataQuery uses deterministic body/headers for Web.Contents caching
                    ExecuteMetadataQuery = (sql) => ExecuteMetadataQuery(@context, sql),
                    Server = actualServer,
                    Warehouse = actualWarehouse,
                    Role = actualRole,
                    Database = null,
                    Schema = null,
                    Token = actualToken,
                    TokenType = actualTokenType,
                    Username = actualUsername,
                    // KeyPair-specific fields (for ADBC auth)
                    PrivateKey = credentials[PrivateKey]?,
                    Passphrase = credentials[Passphrase]?,
                    // Timeout settings
                    ConnectionTimeout = actualConnectionTimeout,
                    CommandTimeout = actualCommandTimeout,
                    // Precision settings (Phase 2.3 and 2.4)
                    UseHighPrecision = actualUseHighPrecision,
                    DateTimePrecision = actualDateTimePrecision
                ],

                // Get databases - use ExecuteMetadataQuery for caching (deterministic body/headers)
                // Create a minimal context just for this query before full context is built
                metadataContext = [
                    Server = actualServer,
                    Warehouse = actualWarehouse,
                    Role = actualRole,
                    Token = actualToken,
                    TokenType = actualTokenType,
                    // KeyPair fields for ADBC routing
                    Username = actualUsername,
                    PrivateKey = credentials[PrivateKey]?,
                    Passphrase = credentials[Passphrase]?
                ],
                databasesQuery = "SHOW DATABASES",
                databasesAttempt = try ExecuteMetadataQuery(metadataContext, databasesQuery),
                databasesResult = if databasesAttempt[HasError] then
                    let
                        originalError = databasesAttempt[Error],
                        originalMessage = originalError[Message]? ?? "Unknown error",
                        _ = Diagnostics.Trace(TraceLevel.Error, "BuildCustomNavigation/GetDatabases/Failed",
                            [Query = databasesQuery, OriginalError = originalMessage], true)
                    in
                        error Error.Record(ERROR_DATA_SOURCE,
                            "SHOW DATABASES failed: " & originalMessage,
                            originalError)
                else
                    Table.Buffer(databasesAttempt[Value]),

                // Dynamically find the name column (handles different column names from SHOW commands)
                databases = let
                        columnNames = Table.ColumnNames(databasesResult),
                        nameColumn = if List.Contains(columnNames, "name") then
                                "name"
                            else if List.Contains(columnNames, "NAME") then
                                "NAME"
                            else if List.Count(columnNames) > 0 then
                                columnNames{1}  // Second column is usually the name
                            else
                                error Error.Record(ERROR_NO_COLUMNS, "No columns found in SHOW DATABASES result"),

                        // Rename to standardized "name" column
                        standardized = if nameColumn <> "name" then
                            Table.RenameColumns(databasesResult, {{nameColumn, "name"}})
                        else
                            databasesResult,

                        // Filter out INFORMATION_SCHEMA
                        filtered = Table.SelectRows(standardized, each [name] <> "INFORMATION_SCHEMA")
                    in
                        filtered,

                // Use "Database" for top level navigation
                withItemKind = Table.AddColumn(databases, "ItemKind", each ITEM_DATABASE, type text),
                withItemName = Table.AddColumn(withItemKind, "ItemName", each ITEM_DATABASE, type text),
                withIsLeaf = Table.AddColumn(withItemName, "IsLeaf", each false, type logical),

                // Build navigation tree
                databasesNav = Table.AddColumn(withIsLeaf, "Data", each
                    GetSchemasForDatabase(context, [name])),

                navTable = Table.ToNavigationTable(
                    databasesNav,
                    {"name"},
                    "name",
                    "Data",
                    "ItemKind",
                    "ItemName",
                    "IsLeaf"
                )
            in
                navTable,

        GetSchemasForDatabase = (context as record, database as text) as table =>
            let
                // ExecuteMetadataQuery uses deterministic body/headers for Web.Contents caching
                schemasQuery = "SHOW SCHEMAS IN " & EscapeIdentifier(database),
                schemasAttempt = try Table.Buffer(context[ExecuteMetadataQuery](schemasQuery)),
                schemasResult = if schemasAttempt[HasError] then
                    let
                        originalError = schemasAttempt[Error],
                        originalMessage = originalError[Message]? ?? "Unknown error",
                        _ = Diagnostics.Trace(TraceLevel.Error, "BuildCustomNavigation/GetSchemasForDatabase/Failed",
                            [Query = schemasQuery, OriginalError = originalMessage], true)
                    in
                        error Error.Record(ERROR_DATA_SOURCE,
                            "Database '" & database & "' not found or not accessible: " & originalMessage,
                            originalError)
                else
                    schemasAttempt[Value],

                // Dynamically find the name column
                schemas = let
                        columnNames = Table.ColumnNames(schemasResult),
                        nameColumn = if List.Contains(columnNames, "name") then
                                "name"
                            else if List.Contains(columnNames, "NAME") then
                                "NAME"
                            else if List.Count(columnNames) > 0 then
                                columnNames{1}  // Second column is usually the name
                            else
                                error Error.Record(ERROR_NO_COLUMNS, "No columns found in SHOW SCHEMAS result"),

                        // Rename to standardized "name" column
                        standardized = if nameColumn <> "name" then
                            Table.RenameColumns(schemasResult, {{nameColumn, "name"}})
                        else
                            schemasResult
                    in
                        standardized,

                // Use "Schema" for middle level
                withItemKind = Table.AddColumn(schemas, "ItemKind", each ITEM_SCHEMA, type text),
                withItemName = Table.AddColumn(withItemKind, "ItemName", each ITEM_SCHEMA, type text),
                withIsLeaf = Table.AddColumn(withItemName, "IsLeaf", each false, type logical),

                schemasNav = Table.AddColumn(withIsLeaf, "Data", each
                    GetTablesForSchema(context, database, [name])),

                navTable = Table.ToNavigationTable(
                    schemasNav,
                    {"name"},
                    "name",
                    "Data",
                    "ItemKind",
                    "ItemName",
                    "IsLeaf"
                )
            in
                navTable,

        // Get tables, views, and semantic views for a schema
        // Uses 2 queries: SHOW OBJECTS (all objects) + SHOW SEMANTIC VIEWS (to identify semantic views)
        GetTablesForSchema = (context as record, database as text, schema as text) as table =>
            let
                qualifiedSchema = EscapeIdentifier(database) & "." & EscapeIdentifier(schema),

                // Helper function to normalize name column
                NormalizeNameColumn = (tbl as table) as table =>
                    let
                        columnNames = Table.ColumnNames(tbl),
                        nameColumn = if List.Contains(columnNames, "name") then "name"
                            else if List.Contains(columnNames, "NAME") then "NAME"
                            else if List.Count(columnNames) > 0 then columnNames{1}
                            else error Error.Record(ERROR_NO_COLUMNS, "No name column found"),
                        standardized = if nameColumn <> "name" then
                            Table.RenameColumns(tbl, {{nameColumn, "name"}})
                        else tbl
                    in standardized,

                // Query 1: Get ALL objects (tables + views, including semantic views as "VIEW")
                // ExecuteMetadataQuery uses deterministic body/headers for Web.Contents caching
                objectsQuery = "SHOW OBJECTS IN SCHEMA " & qualifiedSchema,
                objectsAttempt = try Table.Buffer(context[ExecuteMetadataQuery](objectsQuery)),
                objectsRaw = if objectsAttempt[HasError] then
                    let
                        originalError = objectsAttempt[Error],
                        originalMessage = originalError[Message]? ?? "Unknown error",
                        _ = Diagnostics.Trace(TraceLevel.Error, "BuildCustomNavigation/GetTablesForSchema/ObjectsFailed",
                            [Query = objectsQuery, OriginalError = originalMessage], true)
                    in
                        error Error.Record(ERROR_DATA_SOURCE,
                            "Schema '" & database & "." & schema & "' not found or not accessible: " & originalMessage,
                            originalError)
                else
                    objectsAttempt[Value],
                objects = NormalizeNameColumn(objectsRaw),

                // Query 2: Get semantic view names only
                // ExecuteMetadataQuery uses deterministic body/headers for Web.Contents caching
                semanticQuery = "SHOW SEMANTIC VIEWS IN SCHEMA " & qualifiedSchema,
                semanticAttempt = try Table.Buffer(context[ExecuteMetadataQuery](semanticQuery)),
                semanticViewsRaw = if semanticAttempt[HasError] then
                    let
                        originalError = semanticAttempt[Error],
                        originalMessage = originalError[Message]? ?? "Unknown error",
                        _ = Diagnostics.Trace(TraceLevel.Error, "BuildCustomNavigation/GetTablesForSchema/SemanticViewsFailed",
                            [Query = semanticQuery, OriginalError = originalMessage], true)
                    in
                        error Error.Record(ERROR_DATA_SOURCE,
                            "Schema '" & database & "." & schema & "' not found or not accessible: " & originalMessage,
                            originalError)
                else
                    semanticAttempt[Value],
                semanticViews = NormalizeNameColumn(semanticViewsRaw),
                semanticNames = List.Transform(Table.ToRecords(semanticViews), each [name]),

                // Check if "kind" column exists in objects (SHOW OBJECTS returns it)
                hasKindColumn = List.Contains(Table.ColumnNames(objects), "kind"),

                // Filter by kind and cross-reference semantic names
                tables = if hasKindColumn then
                    Table.SelectRows(objects, each [kind] = "TABLE")
                else
                    #table({"name"}, {}),

                allViews = if hasKindColumn then
                    Table.SelectRows(objects, each [kind] = "VIEW")
                else
                    objects,

                // Separate regular views from semantic views using the semantic names list
                regularViews = Table.SelectRows(allViews, each not List.Contains(semanticNames, [name])),
                semanticViewsFiltered = Table.SelectRows(allViews, each List.Contains(semanticNames, [name])),

                // Combine all types with markers
                // ObjectType: Table, View, SemanticView (using constants)
                allObjectsCombined = Table.Combine({
                    Table.AddColumn(Table.AddColumn(tables, "IsSemantic", each false, type logical), "ObjectType", each OBJECT_TABLE, type text),
                    Table.AddColumn(Table.AddColumn(regularViews, "IsSemantic", each false, type logical), "ObjectType", each OBJECT_VIEW, type text),
                    Table.AddColumn(Table.AddColumn(semanticViewsFiltered, "IsSemantic", each true, type logical), "ObjectType", each OBJECT_SEMANTIC_VIEW, type text)
                }),

                // Differentiate with icons: SemanticView=CubeView icon, View=View icon, Table=Table icon
                withItemKind = Table.AddColumn(allObjectsCombined, "ItemKind", each
                    if [ObjectType] = OBJECT_TABLE then ITEM_TABLE
                    else if [ObjectType] = OBJECT_SEMANTIC_VIEW then ITEM_CUBE_VIEW
                    else ITEM_VIEW, type text),
                withItemName = Table.AddColumn(withItemKind, "ItemName", each
                    if [ObjectType] = OBJECT_TABLE then ITEM_TABLE
                    else if [ObjectType] = OBJECT_SEMANTIC_VIEW then ITEM_CUBE_VIEW
                    else ITEM_VIEW, type text),
                withIsLeaf = Table.AddColumn(withItemName, "IsLeaf", each true, type logical),

                // v3.0: Disable standard tables - only semantic views are supported
                withIsDisabled = Table.AddColumn(withIsLeaf, "IsDisabled", each
                    [ObjectType] <> OBJECT_SEMANTIC_VIEW, type logical),

                withReason = Table.AddColumn(withIsDisabled, "DisabledReason", each
                    if [IsDisabled] then
                        "Use the native Snowflake connector (Get Data → Snowflake) for standard tables"
                    else null, type text),

                // Return table directly from Data column, or error for disabled items
                tablesNav = Table.AddColumn(withReason, "Data", each
                    if [IsDisabled] = true then
                        error Error.Record("DataSource.Error",
                            "Standard tables are not supported. Use Power BI's native Snowflake connector for: " & [name])
                    else
                        GetTableData(context, database, schema, [name], [IsSemantic])),

                navTable = Table.ToNavigationTable(
                    tablesNav,
                    {"name"},
                    "name",
                    "Data",
                    "ItemKind",
                    "ItemName",
                    "IsLeaf"
                )
            in
                navTable,

        GetTableData = (context as record, database as text, schema as text, table as text, isSemantic as logical) as table =>
            let
                _ = Diagnostics.Trace(TraceLevel.Information,
                    "SemanticView/GetTableData/START",
                    [Database = database, Schema = schema, Table = table, IsSemantic = isSemantic]),

                qualifiedName = EscapeIdentifier(database) & "." & EscapeIdentifier(schema) & "." & EscapeIdentifier(table),

                result = if isSemantic then
                    // SEMANTIC VIEW: Use Table.View with handlers for DirectQuery
                    let
                        metadata = GetSemanticViewMetadata(context, qualifiedName),

                        // FIX: Pre-extract metric names for position-based mapping fallback
                        // When OnSelectColumns receives aliases (a0, a1), we need this for OnGroup
                        allMetricNames = List.Transform(
                            List.Select(metadata, each [ColumnKind] = KIND_METRIC),
                            each [ColumnName]
                        ),

                        // PREVIEW OPTIMIZATION: Cache high-cardinality dimension info for preview filtering
                        // This adds ~400ms one-time cost but saves 4+ minutes on large view previews
                        previewFilterInfo = GetPreviewFilterInfo(context, qualifiedName, metadata),

                        initialState = [
                            Context = context,
                            Database = database,
                            Schema = schema,
                            Table = table,
                            QualifiedName = qualifiedName,
                            Metadata = metadata,
                            SelectedColumns = null,  // null = all columns
                            Limit = null,
                            OrderBy = null,
                            IsGrouped = false,
                            // Initialize SelectedMetrics to empty - will be populated when user selects columns
                            // Position-based mapping will extract column from Function expression
                            SelectedMetrics = {},
                            // Strict folding mode - throw error on unsupported filters
                            StrictFoldingMode = STRICT_FOLDING_MODE,
                            // Preview optimization: cached high-cardinality dimension filter info
                            PreviewFilterInfo = previewFilterInfo
                        ],

                        _ = Diagnostics.Trace(TraceLevel.Information,
                            "SemanticView/GetTableData/CreatingDirectQueryView",
                            [QualifiedName = qualifiedName, MetadataCount = List.Count(metadata), PreviewColumn = previewFilterInfo[Column]?])
                    in
                        CreateDirectQueryView(initialState)
                else
                    // STANDARD TABLE/VIEW: Use Table.View (CreateRegularTableView)
                    // NOTE: Adbc.DataSource approach failed - causes connector load failure
                    let
                        descQuery = "DESCRIBE TABLE " & qualifiedName,
                        descResult = Table.Buffer(context[ExecuteQuery](descQuery)),

                        metadata = List.Transform(
                            Table.ToRecords(descResult),
                            (row) => [
                                ColumnName = row[name],
                                ColumnType = row[type],
                                ColumnKind = KIND_COLUMN
                            ]
                        ),

                        initialState = [
                            Context = context,
                            Database = database,
                            Schema = schema,
                            Table = table,
                            QualifiedName = qualifiedName,
                            Metadata = metadata,
                            SelectedColumns = null,
                            Limit = null,
                            OrderBy = null,
                            IsRegularTable = true,
                            StrictFoldingMode = STRICT_FOLDING_MODE,
                            FilterConditions = {},
                            GroupByKeys = {},
                            AliasMap = [],
                            DistinctCountMap = [],
                            StatisticalFuncMap = [],
                            RowCountMap = [],
                            IsGrouped = false,
                            Distinct = false
                        ],

                        _ = Diagnostics.Trace(TraceLevel.Information,
                            "RegularTable/GetTableData/CreatingDirectQueryView",
                            [QualifiedName = qualifiedName, MetadataCount = List.Count(metadata)])
                    in
                        CreateRegularTableView(initialState)
            in
                result,

        // v3.0: Standard tables are no longer supported via this connector
        // Users should use the native Snowflake connector (Get Data → Snowflake) for standard tables
        CreateRegularTableView = (initialState as record) as table =>
            error Error.Record("DataSource.Error",
                "Standard tables are not supported in v3.0. " &
                "Use the native Snowflake connector (Get Data → Snowflake) for: " &
                initialState[QualifiedName],
                [QualifiedName = initialState[QualifiedName]])
    in
        BuildCustomNavigation();

//
// Map Snowflake Type to M Type
//
MapSnowflakeType = (snowflakeType as text) as type =>
    let
        upperType = Text.Upper(Text.Trim(snowflakeType)),
        isNumericFamily = Text.StartsWith(upperType, "NUMBER") or Text.StartsWith(upperType, "DECIMAL") or Text.StartsWith(upperType, "NUMERIC"),
        // NUMBER/DECIMAL/NUMERIC with scale 0 (e.g. "NUMBER(4,0)", or a bare "NUMBER" which
        // defaults to NUMBER(38,0) in Snowflake) are true integers - map to Int64.Type so the
        // declared M type matches the integer Arrow value ADBC returns. Non-zero scale is a
        // genuine decimal - keep Decimal.Type. Mismatching these caused DISP_E_TYPEMISMATCH
        // errors in Power BI for narrow DISTINCT/TopN queries over integer dimensions.
        numericScale =
            if not isNumericFamily then
                null
            else
                let
                    openParen = Text.PositionOf(upperType, "("),
                    closeParen = Text.PositionOf(upperType, ")")
                in
                    if openParen = -1 or closeParen = -1 then
                        0
                    else
                        let
                            inside = Text.Range(upperType, openParen + 1, closeParen - openParen - 1),
                            parts = Text.Split(inside, ","),
                            scaleText = if List.Count(parts) >= 2 then Text.Trim(parts{1}) else "0"
                        in
                            try Number.From(scaleText) otherwise 0,
        m_type =
            // Numeric types
            if isNumericFamily and numericScale = 0 then
                Int64.Type
            else if isNumericFamily then
                Decimal.Type
            else if Text.StartsWith(upperType, "BIGINT") then
                Int64.Type  // Check BIGINT before INT
            else if Text.StartsWith(upperType, "INT") or Text.StartsWith(upperType, "SMALLINT") then
                Int32.Type
            else if Text.StartsWith(upperType, "FLOAT") or Text.StartsWith(upperType, "DOUBLE") or Text.StartsWith(upperType, "REAL") then
                Double.Type
            else if Text.StartsWith(upperType, "VARCHAR") or Text.StartsWith(upperType, "STRING") or Text.StartsWith(upperType, "TEXT") or Text.StartsWith(upperType, "CHAR") then
                type text
            else if Text.StartsWith(upperType, "TIMESTAMP") or Text.StartsWith(upperType, "DATETIME") then
                type datetime  // ALL timestamp types (TIMESTAMP_TZ, TIMESTAMP_NTZ, TIMESTAMP_LTZ) map to datetime
                               // Power BI TMDL has no datetimezone type - must match PBIT declaration
            else if Text.StartsWith(upperType, "DATE") then
                type date
            else if Text.StartsWith(upperType, "TIME") then
                type time
            else if Text.StartsWith(upperType, "BOOLEAN") then
                type logical
            else if Text.StartsWith(upperType, "BINARY") or Text.StartsWith(upperType, "VARBINARY") then
                type binary
            else if upperType = "VARIANT" or upperType = "OBJECT" or upperType = "ARRAY" then
                type text  // Semi-structured as JSON text
            else
                type any  // Default for unknown types
    in
        m_type;

//
// Transform Complex Columns (Phase 5.3)
// Converts VARIANT, OBJECT, ARRAY, STRUCT columns from JSON text to native M types
// Navigation table type for Power BI Navigator
// Wrapped in try/otherwise to gracefully handle tables without NativeTypeName metadata
//
TransformComplexColumns = (table as table) as table =>
    let
        // Safely attempt transformation - if anything fails, return original table
        Result = try
            let
                // Get table schema to identify complex columns
                Schema = Table.Schema(table),

                // Check if NativeTypeName column exists in schema
                HasNativeType = List.Contains(Table.ColumnNames(Schema), "NativeTypeName"),

                // Find columns with complex native types (only if NativeTypeName exists)
                ComplexColumns = if HasNativeType then
                    Table.SelectRows(Schema, (s) =>
                        s[NativeTypeName]? = "VARIANT" or
                        s[NativeTypeName]? = "OBJECT" or
                        s[NativeTypeName]? = "ARRAY" or
                        s[NativeTypeName]? = "STRUCT"
                    )
                else
                    #table({"Name", "NativeTypeName"}, {}),

                // Transform each complex column by parsing JSON
                TransformOperations = List.Accumulate(
                    Table.ToRecords(ComplexColumns),
                    table,
                    (state, column) =>
                        let
                            columnName = column[Name],
                            nativeType = column[NativeTypeName]?,

                            // Determine target type based on native type
                            targetType = if nativeType = "ARRAY" then type list else type any,

                            // Safe JSON parser that handles nulls and errors gracefully
                            ToNullableJson = (value) =>
                                if value = null then null
                                else if value = "" then null
                                else try Json.Document(value) otherwise value
                        in
                            try Table.TransformColumns(state, {{columnName, ToNullableJson, targetType}}) otherwise state
                )
            in
                TransformOperations
        otherwise
            table
    in
        Result;

//
// Escape Identifier
//
EscapeIdentifier = (identifier as text) as text => """" & Text.Replace(identifier, """", """""") & """";

// =========================================================================
// ONGROUP HELPER FUNCTIONS
// Extracted from OnGroup handler for reusability and testability
// =========================================================================

// Strip table prefix AND brackets from column name
// Power BI adds prefixes via Table.PrefixColumns when translating SQL
// e.g., "t1.REGION" -> "REGION", "[t0].[AVG_TAX]" -> "AVG_TAX"
StripTablePrefix = (colName as nullable text) as nullable text =>
    if colName = null then null
    else
        let
            // First strip square brackets: [Name] -> Name
            noBrackets = Text.Replace(Text.Replace(colName, "[", ""), "]", ""),
            // Then handle dot prefix: t1.REGION -> REGION
            result = if Text.Contains(noBrackets, ".") then
                let parts = Text.Split(noBrackets, ".")
                in List.Last(parts)
            else noBrackets
        in result;

// Recursively extract column name from RowExpression AST
// Handles: FieldAccess (direct column), Invocation (function call), Unary (operators)
ExtractColumnFromRowExpr = (expr as nullable record) as nullable text =>
    if expr = null then null
    else if expr[Kind]? = "FieldAccess" then
        // Direct field access - column name is in MemberName
        StripTablePrefix(expr[MemberName]?)
    else if expr[Kind]? = "Invocation" then
        // Function call (like List.Sum) - check Arguments
        let args = expr[Arguments]?
        in if args <> null and List.Count(args) > 0 then
            @ExtractColumnFromRowExpr(args{0})
        else null
    else if expr[Kind]? = "Unary" then
        // Unary operator (like negation) - check inner Expression
        @ExtractColumnFromRowExpr(expr[Expression]?)
    else null;

// Extract column name from aggregate Function expression using RowExpression.From()
// Power BI's SqlExpression.ToExpression pathway embeds column in Function: (row) => List.Sum(row[t0.TOTAL_REVENUE])
ExtractColumnFromFunction = (func as nullable function, metricNames as list) as nullable text =>
    if func = null then null
    else
        let
            // Convert function to expression AST
            rowExpr = try RowExpression.From(func) otherwise null,
            // Extract column name from AST
            extractedCol = ExtractColumnFromRowExpr(rowExpr),
            // Validate it's a known metric
            isValidMetric = extractedCol <> null and List.Contains(metricNames, extractedCol)
        in
            if isValidMetric then extractedCol else null;

// Parse a single aggregate record from Power BI's OnGroup callback
// Returns: [Name, Column, Function, IsDistinctCount, IsRowCount, IsStatistical, StatisticalSqlFunc]
ParseAggregateRecord = (agg as record, allMetricNames as list) as record =>
    let
        aggName = Record.FieldOrDefault(agg, "Name", ""),
        rawColumn = Record.FieldOrDefault(agg, "Column", null),
        aggColumn = StripTablePrefix(rawColumn),
        aggFunction = Record.FieldOrDefault(agg, "Function", null),
        aggArguments = Record.FieldOrDefault(agg, "Arguments", null),

        // Also check Expression field (some Power BI versions use this)
        rawExpression = Record.FieldOrDefault(agg, "Expression", null),
        aggExpression = StripTablePrefix(rawExpression),

        // Check for column in Arguments[0].Column (nested structure)
        argColumn = try StripTablePrefix(aggArguments{0}[Column]) otherwise null,

        // If Column is null, extract from Function expression
        functionExtractedColumn = if aggColumn = null then
            ExtractColumnFromFunction(aggFunction, allMetricNames)
        else null,

        // Priority: Column > Arguments > Expression > Function extraction
        finalColumn = if aggColumn <> null then aggColumn
            else if argColumn <> null then argColumn
            else if aggExpression <> null then aggExpression
            else functionExtractedColumn,

        // Detect DISTINCTCOUNT pattern: List.Count(List.Distinct([Column]))
        isDistinctCount = (aggFunction = List.Count) and
            (aggArguments <> null) and
            (List.Count(aggArguments) > 0) and
            (try Record.Field(aggArguments{0}, "Function") = List.Distinct otherwise false),

        // For DISTINCTCOUNT, get column from nested Arguments
        rawDistinctColumn = if isDistinctCount then
            try Record.Field(aggArguments{0}, "Column") otherwise null
        else null,
        distinctCountColumn = StripTablePrefix(rawDistinctColumn),

        // Detect statistical functions (STDEV, VAR, MEDIAN)
        funcName = try Value.Metadata(aggFunction)[Name] otherwise null,
        isStatistical = funcName <> null and Record.HasFields(StatisticalFunctionMapping, funcName),
        statisticalSqlFunc = if isStatistical then
            Record.Field(StatisticalFunctionMapping, funcName)
        else null,

        // Detect COUNTROWS pattern: Table.RowCount function.
        // Power Query's DirectQuery grouping negotiation doesn't always hand us the bare
        // Table.RowCount reference - for capability-negotiated folds (our declared
        // {"Table.RowCount", null} capability) it wraps it as a lambda, e.g.
        // "(t) => Table.RowCount(t)". Neither the reference check nor Value.Metadata catches
        // that wrapper, so probe: call the function against a zero-column, 3-row table. Only
        // a function that ignores columns entirely (i.e. actually counts rows) can succeed on
        // that table at all - any column-referencing aggregate (SUM/AVERAGE/etc.) errors out,
        // which try/otherwise turns into null, so this can't misidentify a real aggregate.
        rowCountProbeTable = #table({}, {{}, {}, {}}),
        probeResult = if aggFunction is function then try aggFunction(rowCountProbeTable) otherwise null else null,
        isRowCountByProbe = probeResult = 3,

        isRowCount = (aggFunction = Table.RowCount) or (funcName = "Table.RowCount") or isRowCountByProbe
    in
        [
            Name = aggName,
            Column = if isDistinctCount then distinctCountColumn else finalColumn,
            Function = aggFunction,
            IsDistinctCount = isDistinctCount,
            IsRowCount = isRowCount,
            IsStatistical = isStatistical,
            StatisticalSqlFunc = statisticalSqlFunc
        ];

// Build alias map from validated aggregates (maps column -> alias)
BuildAliasMap = (validAggregates as list) as record =>
    let
        aggregatesWithColumn = List.Select(validAggregates, each [Column] <> null),
        aliasMap = Record.FromList(
            List.Transform(aggregatesWithColumn, each [Column]),
            List.Transform(aggregatesWithColumn, each [Alias])
        )
    in aliasMap;

// Build distinct count map from validated aggregates (alias -> true for distinctcount)
BuildDistinctCountMap = (validAggregates as list) as record =>
    let
        distinctAggs = List.Select(validAggregates, each [IsDistinctCount]),
        distinctCountMap = Record.FromList(
            List.Transform(distinctAggs, each true),
            List.Transform(distinctAggs, each [Alias])
        )
    in distinctCountMap;

// Build statistical function map from validated aggregates (alias -> SQL function name)
BuildStatisticalFuncMap = (validAggregates as list) as record =>
    let
        statAggs = List.Select(validAggregates, each [IsStatistical]),
        statisticalFuncMap = Record.FromList(
            List.Transform(statAggs, each [StatisticalSqlFunc]),
            List.Transform(statAggs, each [Alias])
        )
    in statisticalFuncMap;

// Build row count map from validated aggregates (alias -> true for row count)
BuildRowCountMap = (validAggregates as list) as record =>
    let
        rowCountAggs = List.Select(validAggregates, each [IsRowCount]),
        rowCountMap = Record.FromList(
            List.Transform(rowCountAggs, each true),
            List.Transform(rowCountAggs, each [Alias])
        )
    in rowCountMap;

// =========================================================================
// SHARED STATE UPDATE FUNCTIONS
// Simple pure functions for updating view state - used by both view types
// =========================================================================

// Update state with LIMIT for OnTake handler
UpdateStateWithLimit = (state as record, count as number) as record =>
    state & [Limit = count];

// Update state with OFFSET for OnSkip handler
UpdateStateWithSkip = (state as record, count as number) as record =>
    state & [Skip = count];

// Update state with ORDER BY for OnSort handler
UpdateStateWithSort = (state as record, order as list) as record =>
    state & [OrderBy = order];

// Update state with DISTINCT for OnDistinct handler
UpdateStateWithDistinct = (state as record) as record =>
    state & [Distinct = true];

// Update state with selected columns for OnSelectColumns handler
UpdateStateWithSelectedColumns = (state as record, columns as list, metadata as list) as record =>
    let
        // Get metric names for tracking
        allMetricNames = List.Transform(
            List.Select(metadata, each [ColumnKind] = KIND_METRIC),
            each [ColumnName]
        ),
        // Track which selected columns are metrics
        selectedMetrics = List.Select(columns, each List.Contains(allMetricNames, _))
    in
        state & [SelectedColumns = columns, SelectedMetrics = selectedMetrics];

//
// Build Minimal Table Type (Type Number for Metrics)
// Returns type table with type number for METRICS - enables sigma icons in Power BI
//
BuildMinimalTableType = (metadata as list) as type =>
    let
        // Extract column names
        columnNames = List.Transform(metadata, each [ColumnName]),

        // Create record with null values
        sampleRecord = Record.FromList(
            List.Transform(columnNames, each null),
            columnNames
        ),

        // Create sample table
        sampleTable = Table.FromRecords({sampleRecord}),

        // Apply types to columns
        typedTable = List.Accumulate(
            metadata,
            sampleTable,
            (state, col) =>
                let
                    columnName = col[ColumnName],
                    columnKind = col[ColumnKind]? ?? "COLUMN",
                    snowflakeType = col[ColumnType]? ?? "TEXT",

                    // CRITICAL FIX: Use actual Snowflake types for dimensions
                    // Metrics always use type number for sigma icons
                    // ROW_COUNT (COUNTROWS) uses Int64.Type for proper OLE DB type mapping
                    // Dimensions and facts use their actual Snowflake type (DATE, VARCHAR, etc.)
                    mappedType = MapSnowflakeType(snowflakeType),

                    // Convert mapped type to nullable version
                    baseType = if columnKind = KIND_ROW_COUNT then
                        // COUNTROWS returns integer - use Int64.Type to avoid Double→Int64 conversion error
                        type nullable Int64.Type
                    else if columnKind = KIND_METRIC then
                        type nullable number  // Double - PBIT uses "double" with SummarizationSetBy annotation
                    else if mappedType = type date then
                        type nullable date
                    else if mappedType = type time then
                        type nullable time
                    else if mappedType = type datetime then
                        type nullable datetime  // TIMESTAMP_NTZ, TIMESTAMP_LTZ
                    else if mappedType = type datetimezone then
                        type nullable datetimezone  // TIMESTAMP_TZ only
                    else if mappedType = type number then
                        type nullable number
                    else if mappedType = Int64.Type then
                        type nullable Int64.Type
                    else if mappedType = type text then
                        type nullable text
                    else if mappedType = type logical then
                        type nullable logical
                    else if mappedType = type binary then
                        type nullable binary
                    else
                        type nullable any
                in
                    Table.TransformColumnTypes(state, {{columnName, baseType}})
        ),

        // Extract type
        minimalType = Value.Type(typedTable),

        _ = Diagnostics.Trace(TraceLevel.Information,
            "BuildMinimalTableType/TypeNumberStrategy",
            [
                Strategy = "Type number for metrics - enables sigma icons in Power BI",
                ColumnCount = List.Count(columnNames),
                MetricCount = List.Count(List.Select(metadata, each ([ColumnKind]? = "METRIC")))
            ])
    in
        minimalType;

//
// GetSemanticViewMetadata - Fetch column metadata for a semantic view
//
// Uses 3 separate SHOW queries (DIMENSIONS, METRICS, FACTS) instead of single DESC query.
// Trade-off: 3 round-trips vs 1, but SHOW queries return:
// - Clean, typed data per column kind
// - No post-filtering needed in M
// - Web.Contents caching helps with repeated calls
//
// Parameters:
//   context - Execution context with ExecuteMetadataQuery function
//   qualifiedName - Fully qualified semantic view name
//
// Returns: List of metadata records with ColumnName, ColumnType, ColumnKind, etc.
//
GetSemanticViewMetadata = (context as record, qualifiedName as text) as list =>
    let
        // Use ExecuteMetadataQuery for caching (deterministic body/headers)
        // SHOW SEMANTIC DIMENSIONS (Web.Contents caches identical requests)
        dimensionsQuery = "SHOW SEMANTIC DIMENSIONS IN " & qualifiedName,
        dimensionsRaw = try context[ExecuteMetadataQuery](dimensionsQuery) otherwise
            let _ = Diagnostics.Trace(TraceLevel.Warning, "GetSemanticViewMetadata/DIMENSIONS_FAILED",
                [Query = dimensionsQuery, View = qualifiedName])
            in #table({}, {}),
        dimensions = Table.Buffer(dimensionsRaw),
        dimensionRecords = Table.TransformRows(dimensions, (d) => [
            ColumnName = d[name]?,
            ColumnType = d[data_type]?,
            ColumnKind = KIND_DIMENSION,
            Description = d[comment]?,
            Expression = d[expression]?,
            NativeTypeName = d[data_type]?
        ]),

        // SHOW SEMANTIC METRICS (Web.Contents caches identical requests)
        metricsQuery = "SHOW SEMANTIC METRICS IN " & qualifiedName,
        metricsRaw = try context[ExecuteMetadataQuery](metricsQuery) otherwise
            let _ = Diagnostics.Trace(TraceLevel.Warning, "GetSemanticViewMetadata/METRICS_FAILED",
                [Query = metricsQuery, View = qualifiedName])
            in #table({}, {}),
        metrics = Table.Buffer(metricsRaw),
        metricRecords = Table.TransformRows(metrics, (m) => [
            ColumnName = m[name]?,
            ColumnType = m[data_type]?,
            ColumnKind = KIND_METRIC,
            Description = m[comment]?,
            Expression = m[expression]?,
            NativeTypeName = m[data_type]?
        ]),

        // SHOW SEMANTIC FACTS (Web.Contents caches identical requests)
        factsQuery = "SHOW SEMANTIC FACTS IN " & qualifiedName,
        factsRaw = try context[ExecuteMetadataQuery](factsQuery) otherwise
            let _ = Diagnostics.Trace(TraceLevel.Warning, "GetSemanticViewMetadata/FACTS_FAILED",
                [Query = factsQuery, View = qualifiedName])
            in #table({}, {}),
        facts = Table.Buffer(factsRaw),
        factRecords = Table.TransformRows(facts, (f) => [
            ColumnName = f[name]?,
            ColumnType = f[data_type]?,
            ColumnKind = KIND_FACT,
            Description = f[comment]?,
            Expression = f[expression]?,
            NativeTypeName = f[data_type]?
        ]),

        // Combine all metadata
        allMetadata = dimensionRecords & metricRecords & factRecords,

        // Resolve duplicate column names (adds _2, _3 suffixes and SourceColumn field)
        resolvedMetadata = ResolveDuplicateColumnNames(allMetadata)
    in
        resolvedMetadata;

//
// ResolveDuplicateColumnNames - Make column names unique by adding numeric suffixes
//
// When a semantic view has columns with the same name (e.g., multiple CATEGORY columns
// from different base tables), Power BI can't handle duplicate field names in records.
// This function adds _2, _3, etc. suffixes to make names unique.
//
// Parameters:
//   metadata - List of column metadata records with ColumnName field
//
// Returns: Updated metadata list with unique ColumnName values and SourceColumn field
//
ResolveDuplicateColumnNames = (metadata as list) as list =>
    let
        // Track name occurrences and build result list
        resolveNames = List.Accumulate(
            metadata,
            [Result = {}, Counts = []],
            (state, col) =>
                let
                    originalName = col[ColumnName],
                    currentCount = Record.FieldOrDefault(state[Counts], originalName, 0),
                    newCount = currentCount + 1,
                    // First occurrence keeps original name, subsequent get _2, _3, etc.
                    displayName = if newCount = 1 then originalName
                        else originalName & "_" & Text.From(newCount),
                    // Add SourceColumn field (original name for SQL queries)
                    updatedCol = col & [SourceColumn = originalName, ColumnName = displayName],
                    // Update counts record
                    newCounts = Record.AddField(
                        Record.RemoveFields(state[Counts], {originalName}, MissingField.Ignore),
                        originalName, newCount
                    )
                in
                    [Result = state[Result] & {updatedCol}, Counts = newCounts]
        )
    in
        resolveNames[Result];

// =============================================================================
// PREVIEW QUERY OPTIMIZATION
// =============================================================================
// Functions to optimize preview queries by filtering on high-cardinality dimensions.
// This reduces query time from 4+ minutes to ~30 seconds for large semantic views.

//
// GetHighCardinalityDimension - Find the dimension with highest cardinality
//
// Uses efficient SQL-side cardinality detection with CTE + UNION ALL pattern.
// Runs in ~300ms regardless of table size.
//
// Parameters:
//   context - Execution context with ExecuteQuery function
//   qualifiedName - Fully qualified semantic view name
//   dimensions - List of dimension column names
//
// Returns: Record with Column (name) and Cardinality (distinct count in 1000 sample)
//
GetHighCardinalityDimension = (context as record, qualifiedName as text, dimensions as list) as record =>
    let
        // Build comma-separated list of dimension columns
        dimColList = Text.Combine(List.Transform(dimensions, each EscapeIdentifier(_)), ", "),

        // Build UNION ALL for each dimension's COUNT(DISTINCT)
        unionParts = List.Transform(dimensions, (dim) =>
            "SELECT '" & dim & "' AS col, COUNT(DISTINCT " & EscapeIdentifier(dim) & ") AS distinct_in_1000 FROM sample_data"
        ),
        unionSql = Text.Combine(unionParts, " UNION ALL "),

        // Full cardinality detection query using CTE pattern
        cardinalityQuery = "WITH sample_data AS (SELECT " & dimColList &
            " FROM " & qualifiedName & " LIMIT 1000) " &
            unionSql & " ORDER BY distinct_in_1000 DESC LIMIT 1",

        _ = Diagnostics.Trace(TraceLevel.Information,
            "PreviewOptimization/GetHighCardinalityDimension",
            [Query = cardinalityQuery]),

        // Execute and get top result (highest cardinality dimension)
        result = context[ExecuteQuery](cardinalityQuery),
        topRow = Table.First(result),

        // Snowflake returns uppercase column names: COL, DISTINCT_IN_1000
        bestColumn = topRow[COL],
        bestCardinality = topRow[DISTINCT_IN_1000]
    in
        [Column = bestColumn, Cardinality = bestCardinality];

//
// GetPreviewFilterInfo - Get filter info for preview query optimization
//
// Combines cardinality detection with sample value fetching.
// Total time: ~400ms (300ms cardinality + 100ms sample value)
//
// Parameters:
//   context - Execution context with ExecuteQuery function
//   qualifiedName - Fully qualified semantic view name
//   metadata - List of metadata records with ColumnName, ColumnKind
//
// Returns: Record with Column, Cardinality, SampleValue (or null if no dimensions)
//
GetPreviewFilterInfo = (context as record, qualifiedName as text, metadata as list) as record =>
    let
        // Get dimension names only
        dimensions = List.Transform(
            List.Select(metadata, each [ColumnKind] = KIND_DIMENSION),
            each [ColumnName]
        ),

        // Skip if no dimensions (shouldn't happen for semantic views, but safety check)
        result = if List.IsEmpty(dimensions) then
            [Column = null, Cardinality = 0, SampleValue = null]
        else
            let
                // Step 1: Find highest cardinality dimension (~300ms)
                highCardDim = GetHighCardinalityDimension(context, qualifiedName, dimensions),

                // Step 2: Get a sample value from that column (~100ms)
                sampleQuery = "SELECT " & EscapeIdentifier(highCardDim[Column]) &
                    " FROM " & qualifiedName & " LIMIT 1",
                sampleResult = context[ExecuteQuery](sampleQuery),
                firstRow = Table.First(sampleResult),
                // Get the value from the first (and only) column
                sampleValue = Record.Field(firstRow, highCardDim[Column]),

                _ = Diagnostics.Trace(TraceLevel.Information,
                    "PreviewOptimization/GetPreviewFilterInfo",
                    [Column = highCardDim[Column], Cardinality = highCardDim[Cardinality], SampleValue = sampleValue])
            in
                highCardDim & [SampleValue = sampleValue]
    in
        result;

//
// GeneratePreviewFilter - Generate WHERE filter conditions for preview queries
//
// Uses BETWEEN range on high-cardinality dimension to prune data before aggregation.
// Only applies when cardinality is high enough to benefit from filtering.
//
// Parameters:
//   previewInfo - Record from GetPreviewFilterInfo with Column, Cardinality, SampleValue
//
// Returns: List of filter conditions for BuildWhereClause (empty if no filter needed)
//
GeneratePreviewFilter = (previewInfo as record) as list =>
    let
        // Skip filtering if:
        // - No valid column identified
        // - Low cardinality (filtering won't help much)
        // - Sample value is null
        filterConditions = if previewInfo[Column]? = null
                           or previewInfo[Cardinality]? = null
                           or previewInfo[Cardinality] < 100
                           or previewInfo[SampleValue]? = null then
            {}
        else if previewInfo[SampleValue] is number then
            // Numeric column: use BETWEEN with range ~10000 to ensure 200+ rows
            let
                startVal = previewInfo[SampleValue],
                endVal = previewInfo[SampleValue] + 10000
            in
                {[Column = previewInfo[Column],
                  Operator = "BETWEEN",
                  Value = [Start = startVal, End = endVal]]}
        else
            // Non-numeric column (text, date): use equality filter on sample value
            {[Column = previewInfo[Column],
              Operator = "=",
              Value = previewInfo[SampleValue]]}
    in
        filterConditions;

// =============================================================================
// SQL GENERATION HELPERS
// =============================================================================
// Helper functions for GenerateSemanticViewQuery - extracted for maintainability
// These functions handle specific aspects of SQL generation for semantic views

//
// ResolveColumnAliases - Resolve Power BI column aliases to source columns
//
// When Power BI does Table.Group, it creates aliases like "a0" for aggregated columns.
// This function maps aliases back to source column names and enriches metadata with
// aggregation information (DISTINCTCOUNT, COUNTROWS, statistical functions).
//
// Parameters:
//   colName - Column name (may be an alias like "a0")
//   metadataByName - Pre-indexed record of metadata by column name (O(1) lookup)
//   aliasMap - Record mapping aliases to source column names
//   distinctCountMap - Record tracking DISTINCTCOUNT operations
//   statisticalFuncMap - Record mapping columns to statistical SQL functions
//   rowCountMap - Record tracking COUNTROWS operations
//
// Returns: Metadata record with ColumnName, ColumnKind, aggregation flags, etc.
//
ResolveColumnAliases = (colName as text, metadataByName as record, optional aliasMap as record, optional distinctCountMap as record, optional statisticalFuncMap as record, optional rowCountMap as record) as record =>
    let
        // Check if this is a COUNTROWS column (no source column, just COUNT(*))
        isRowCount = rowCountMap <> null and Record.HasFields(rowCountMap, colName),

        // Check if this is an alias (e.g., "a0") that's in our map
        isAlias = aliasMap <> null and Record.HasFields(aliasMap, colName),
        sourceColumn = if isAlias then Record.Field(aliasMap, colName) else colName,

        // Check if this is a DISTINCTCOUNT column
        isDistinctCount = distinctCountMap <> null and Record.HasFields(distinctCountMap, colName),

        // Check if this is a statistical function (STDEV, VAR, MEDIAN)
        isStatistical = statisticalFuncMap <> null and Record.HasFields(statisticalFuncMap, colName),
        statisticalSqlFunc = if isStatistical then Record.Field(statisticalFuncMap, colName) else null,

        // For COUNTROWS, create special metadata (no source column lookup needed)
        result = if isRowCount then
            [ColumnName = null, ColumnType = "INT64", ColumnKind = KIND_ROW_COUNT, OutputAlias = colName, IsDistinctCount = false, IsRowCount = true, IsStatistical = false, StatisticalSqlFunc = null]
        else
            let
                // OPTIMIZED: O(1) lookup using pre-built record instead of O(n) List.Select
                baseMetadata = if Record.HasFields(metadataByName, sourceColumn) then
                    Record.Field(metadataByName, sourceColumn)
                else
                    // Column not found - create default entry
                    [ColumnName = sourceColumn, ColumnType = "TEXT", ColumnKind = KIND_DIMENSION],

                // If this is an alias, add alias information to metadata
                // Also track if this is a DISTINCTCOUNT or statistical operation
                resultMeta = if isAlias then
                    baseMetadata & [
                        OutputAlias = colName,
                        IsDistinctCount = isDistinctCount,
                        IsRowCount = false,
                        IsStatistical = isStatistical,
                        StatisticalSqlFunc = statisticalSqlFunc
                    ]
                else
                    baseMetadata & [IsDistinctCount = false, IsRowCount = false, IsStatistical = false, StatisticalSqlFunc = null]
            in
                resultMeta
    in
        result;

//
// BuildSelectExpression - Build SQL SELECT expression for a single column
//
// Generates the appropriate SQL expression based on column kind and aggregation type:
// - COUNTROWS → COUNT("dimensionOrFactColumn") - Snowflake Semantic Views reject bare
//   COUNT(*)/AGG(COUNT(*)) as an invalid metric expression; the documented ad-hoc-metric
//   pattern is COUNT() over an existing dimension/fact column instead (any non-null column
//   works, since it's just counting rows within the GROUP BY partition)
// - DISTINCTCOUNT → COUNT(DISTINCT "column")
// - Statistical → STDDEV_SAMP/VAR_SAMP/MEDIAN("column")
// - METRIC → AGG("column")
// - DIMENSION/FACT → "column"
//
// Parameters:
//   col - Column metadata record with ColumnName, ColumnKind, aggregation flags
//   rowCountColumn - optional dimension/fact column name to wrap in COUNT() for COUNTROWS
//
// Returns: SQL expression string with AS alias clause
//
BuildSelectExpression = (col as record, optional rowCountColumn as nullable text) as text =>
    let
        hasAlias = Record.HasFields(col, "OutputAlias"),
        outputName = if hasAlias then col[OutputAlias] else col[ColumnName],
        isRowCount = Record.FieldOrDefault(col, "IsRowCount", false),
        isDistinctCount = Record.FieldOrDefault(col, "IsDistinctCount", false),
        isStatistical = Record.FieldOrDefault(col, "IsStatistical", false),
        statisticalSqlFunc = Record.FieldOrDefault(col, "StatisticalSqlFunc", null),
        // Use SourceColumn for SQL (original name), fall back to ColumnName for non-duplicate columns
        sourceCol = Record.FieldOrDefault(col, "SourceColumn", col[ColumnName]),
        sourceExpr = if isRowCount then
            // COUNTROWS: COUNT(dimensionOrFactColumn) - see comment above BuildSelectExpression
            if rowCountColumn <> null then
                "COUNT(" & EscapeIdentifier(rowCountColumn) & ")"
            else
                "COUNT(*)"
        else if isDistinctCount then
            // DISTINCTCOUNT: COUNT(DISTINCT sourceColumn)
            "COUNT(DISTINCT " & EscapeIdentifier(sourceCol) & ")"
        else if isStatistical and statisticalSqlFunc <> null then
            // Statistical function: STDDEV_SAMP/VAR_SAMP/MEDIAN(sourceColumn)
            statisticalSqlFunc & "(" & EscapeIdentifier(sourceCol) & ")"
        else if col[ColumnKind] = KIND_METRIC then
            // Metrics: AGG(sourceColumn) - Snowflake Semantic Views specific
            // NOTE: AGG() wraps metrics for aggregation in Snowflake's semantic view engine
            "AGG(" & EscapeIdentifier(sourceCol) & ")"
        else
            // Dimensions and Facts: just sourceColumn
            EscapeIdentifier(sourceCol),
        // Always add AS clause if we have an alias
        fullExpr = sourceExpr & " AS " & EscapeIdentifier(outputName)
    in
        fullExpr;

//
// BuildComputedColumnExpression - Build SQL expression for computed column
//
// Translates M function calls (Date.Year, Text.Upper, etc.) to Snowflake SQL
// using the SqlGenerator module's function registry.
//
// Parameters:
//   cc - Computed column record with Name, Function, SourceColumn, Args
//
// Returns: SQL expression string with AS alias clause
//
BuildComputedColumnExpression = (cc as record) as text =>
    let
        // Use SqlGenerator to translate function to SQL
        sqlExpr = SqlGenerator[TranslateExpression]([
            Function = cc[Function],
            Column = cc[SourceColumn],
            Args = cc[Args]
        ]),
        // Add alias for the computed column
        fullExpr = sqlExpr & " AS " & EscapeIdentifier(cc[Name])
    in
        fullExpr;

//
// BuildGroupByClause - Build SQL GROUP BY clause based on column types
//
// Uses ORDINAL POSITIONS (1, 2, 3, ...) instead of column names to avoid
// ambiguity when there are duplicate source column names (e.g., multiple
// columns named "CATEGORY" from different base tables in a semantic view).
//
// Parameters:
//   dimensions - List of dimension column metadata
//   metrics - List of metric column metadata
//   facts - List of fact column metadata
//   allColumns - Full ordered list of all columns in SELECT (for position lookup)
//
// Returns: GROUP BY clause content (without "GROUP BY" prefix), or null if not needed
//
BuildGroupByClauseContent = (dimensions as list, metrics as list, facts as list, allColumns as list) as nullable text =>
    let
        // Get ordinal position (1-based) of a column in the SELECT list
        getOrdinal = (col as record) =>
            let
                pos = List.PositionOf(allColumns, col, Occurrence.First,
                    (a, b) => a[ColumnName] = b[ColumnName])
            in
                if pos >= 0 then Text.From(pos + 1) else null,

        // Get ordinals for dimensions and facts
        dimensionOrdinals = List.RemoveNulls(List.Transform(dimensions, each getOrdinal(_))),
        factOrdinals = List.RemoveNulls(List.Transform(facts, each getOrdinal(_))),

        // Build GROUP BY clause using ordinal positions
        // - Dimensions present: GROUP BY dimensions + facts
        // - Metrics only (no dimensions): GROUP BY facts only
        // - Facts only: No GROUP BY needed
        groupByCols = if not List.IsEmpty(dimensions) then
            // Have dimensions - always group by them (+ facts if metrics present)
            Text.Combine(dimensionOrdinals & factOrdinals, ", ")
        else if not List.IsEmpty(metrics) then
            // Metrics without dimensions - group by facts only
            if not List.IsEmpty(facts) then Text.Combine(factOrdinals, ", ") else null
        else
            // Facts only - no grouping needed
            null
    in
        groupByCols;

//
// BuildOrderByClause - Build SQL ORDER BY clause from sort specifications
//
// Snowflake semantic views reject ORDER BY over a dimension that isn't in the
// SELECT/GROUP BY list (error 002024 / 42601). Power BI can still hand us a sort
// key for a column it dropped from the projection (e.g. a dimension filtered to a
// single value, which the engine treats as provably constant) - see issue #7.
// So every sort key is resolved to its 1-based ordinal in the actual SELECT list
// instead of being quoted verbatim; terms that don't resolve to anything are
// dropped rather than emitted as a dangling/invalid ORDER BY term.
//
// Parameters:
//   orderBy - List of records with Name and Order fields
//   outputNames - Ordered list of column names/aliases as they appear in the SELECT list
//   aliasMap - Optional record mapping Power BI aliases (e.g. "a0") to source column names,
//              used in reverse to resolve a sort-by-metric-name to its output alias
//
// Returns: ORDER BY clause (with " ORDER BY " prefix), or empty string if no sorting
//          (or if every sort key was dropped because it isn't projected)
//
BuildOrderByClause = (orderBy as nullable list, outputNames as list, optional aliasMap as record) as text =>
    if orderBy <> null and not List.IsEmpty(orderBy) then
        let
            resolveOrdinal = (rawName as text) as nullable number =>
                let
                    // 1. Try the name verbatim (dimensions, dedup aliases like REGION_2, a0/a1)
                    posVerbatim = List.PositionOf(outputNames, rawName),
                    // 2. Try stripping a "t0."/"[t0].[X]" table-prefix Power BI may have added
                    stripped = StripTablePrefix(rawName),
                    posStripped = if stripped <> null then List.PositionOf(outputNames, stripped) else -1,
                    // 3. Reverse-lookup through aliasMap: metric name -> Power BI alias (e.g. a0)
                    reverseAlias = if aliasMap <> null then
                        let
                            aliasFieldNames = Record.FieldNames(aliasMap),
                            matchField = List.First(
                                List.Select(aliasFieldNames, each Record.Field(aliasMap, _) = rawName),
                                null
                            )
                        in
                            matchField
                    else null,
                    posViaAlias = if reverseAlias <> null then List.PositionOf(outputNames, reverseAlias) else -1,
                    pos = if posVerbatim >= 0 then posVerbatim
                        else if posStripped >= 0 then posStripped
                        else posViaAlias
                in
                    if pos >= 0 then pos + 1 else null,

            resolvedTerms = List.Transform(orderBy, each
                let
                    ordinal = resolveOrdinal([Name])
                in
                    if ordinal <> null then
                        Text.From(ordinal) & (if [Order] = Order.Descending then " DESC" else " ASC")
                    else
                        let
                            _ = Diagnostics.Trace(
                                TraceLevel.Warning,
                                "BuildOrderByClause/DroppedSortKey",
                                [Name = [Name], OutputNames = outputNames]
                            )
                        in
                            null
            ),
            validTerms = List.RemoveNulls(resolvedTerms)
        in
            if not List.IsEmpty(validTerms) then
                " ORDER BY " & Text.Combine(validTerms, ", ")
            else ""
    else "";

//
// BuildLimitOffsetClause - Build SQL LIMIT and OFFSET clauses
//
// Parameters:
//   limit - Maximum rows to return (null for no limit)
//   offset - Rows to skip (null or 0 for no offset)
//
// Returns: LIMIT/OFFSET clause string
//
BuildLimitOffsetClause = (optional limit as number, optional offset as number) as text =>
    (if limit <> null then " LIMIT " & Number.ToText(limit) else "") &
    (if offset <> null and offset > 0 then " OFFSET " & Number.ToText(offset) else "");

//
// GenerateSemanticViewQuery - Build complete SQL SELECT statement for semantic views
//
// Main SQL generation function that assembles a complete query for Snowflake semantic views.
// Uses helper functions for individual clause generation.
//
// Parameters:
//   qualifiedName - Fully qualified view name (database.schema.view)
//   selectedColumns - List of column names to include in SELECT
//   metadata - List of metadata records with ColumnName, ColumnType, ColumnKind
//   limit - Optional row limit (LIMIT clause)
//   offset - Optional row offset (OFFSET clause)
//   orderBy - Optional list of sort specifications [{Name, Order}]
//   aliasMap - Optional record mapping Power BI aliases to source columns
//   distinctCountMap - Optional record tracking DISTINCTCOUNT operations
//   filterConditions - Optional list of filter conditions for WHERE clause
//   statisticalFuncMap - Optional record mapping columns to statistical SQL functions
//   distinct - Optional flag to add DISTINCT keyword
//   rowCountMap - Optional record tracking COUNTROWS operations
//   computedColumns - Optional list of computed column definitions
//
// Returns: Complete SQL query string
//
// Example:
//   GenerateSemanticViewQuery("DB.SCHEMA.VIEW", {"REGION", "TOTAL_SALES"}, metadata, 1000)
//   => "SELECT "REGION", AGG("TOTAL_SALES") AS "TOTAL_SALES" FROM DB.SCHEMA.VIEW GROUP BY "REGION" LIMIT 1000"
//
GenerateSemanticViewQuery = (qualifiedName as text, selectedColumns as list, metadata as list, optional limit as number, optional offset as number, optional orderBy as list, optional aliasMap as record, optional distinctCountMap as record, optional filterConditions as list, optional statisticalFuncMap as record, optional distinct as logical, optional rowCountMap as record, optional computedColumns as list) as text =>
    let
        // OPTIMIZATION: Build pre-indexed lookup record for O(1) column lookups
        metadataByName = Record.FromList(
            metadata,
            List.Transform(metadata, each [ColumnName])
        ),

        // Resolve all column aliases and enrich metadata
        orderedMetadata = List.Transform(
            selectedColumns,
            (colName) => ResolveColumnAliases(colName, metadataByName, aliasMap, distinctCountMap, statisticalFuncMap, rowCountMap)
        ),

        // Get computed column names to exclude from regular column processing
        computedColNames = if computedColumns <> null then
            List.Transform(computedColumns, each [Name])
        else {},

        // Filter out computed columns from orderedMetadata - they'll be added separately
        filteredMetadata = List.Select(orderedMetadata, each
            not List.Contains(computedColNames, [ColumnName])
        ),

        // Partition columns by kind (preserving order)
        dimensions = List.Select(filteredMetadata, each [ColumnKind] = KIND_DIMENSION),
        metrics = List.Select(filteredMetadata, each [ColumnKind] = KIND_METRIC),
        facts = List.Select(filteredMetadata, each [ColumnKind] = KIND_FACT),

        // Pick a dimension/fact column to wrap in COUNT() for COUNTROWS aggregates - Snowflake
        // Semantic Views reject bare COUNT(*), so any non-null grouped column stands in for it
        rowCountColumn =
            if not List.IsEmpty(dimensions) then
                Record.FieldOrDefault(dimensions{0}, "SourceColumn", dimensions{0}[ColumnName])
            else if not List.IsEmpty(facts) then
                Record.FieldOrDefault(facts{0}, "SourceColumn", facts{0}[ColumnName])
            else
                null,

        // Build SELECT expressions
        selectColExpressions = List.Transform(filteredMetadata, each BuildSelectExpression(_, rowCountColumn)),
        computedColExpressions = if computedColumns <> null and not List.IsEmpty(computedColumns) then
            List.Transform(computedColumns, each BuildComputedColumnExpression(_))
        else {},
        allSelectExpressions = List.Combine({selectColExpressions, computedColExpressions}),
        selectCols = Text.Combine(allSelectExpressions, ", "),

        // Build GROUP BY clause - use ordinal positions to avoid duplicate column name ambiguity
        groupByCols = BuildGroupByClauseContent(dimensions, metrics, facts, filteredMetadata),

        // Partition filter conditions: METRIC filters go to outer query, DIMENSION/FACT to inner WHERE
        // Snowflake Semantic Views don't allow METRIC columns in WHERE clause
        partitionedFilters = if filterConditions <> null and not List.IsEmpty(filterConditions) then
            PartitionFilterConditions(filterConditions, metadataByName)
        else
            [WhereConditions = {}, MetricConditions = {}],

        whereConditions = partitionedFilters[WhereConditions],
        metricConditions = partitionedFilters[MetricConditions],
        hasMetricFilters = not List.IsEmpty(metricConditions),

        // Build WHERE clause with only DIMENSION/FACT conditions
        whereClause = if not List.IsEmpty(whereConditions) then
            BuildWhereClause(whereConditions)
        else "",

        // Add DISTINCT keyword when OnDistinct handler was called
        distinctKeyword = if distinct = true then "DISTINCT " else "",

        // CRITICAL: Never use SELECT * on semantic views - it fails because metrics need AGG() wrapper
        // When no columns selected, generate explicit column list from ALL metadata columns
        selectClause = if Text.Length(selectCols) > 0 then
            selectCols
        else
            // Generate explicit column list from all metadata columns with proper AGG() for metrics
            let
                allColExpressions = List.Transform(metadata, (colMeta) =>
                    let
                        // Use SourceColumn for SQL, ColumnName for alias
                        sourceCol = Record.FieldOrDefault(colMeta, "SourceColumn", colMeta[ColumnName]),
                        displayName = colMeta[ColumnName],
                        kind = colMeta[ColumnKind],
                        // Metrics need AGG() wrapper, dimensions/facts are bare column names
                        expr = if kind = KIND_METRIC then
                            "AGG(" & EscapeIdentifier(sourceCol) & ") AS " & EscapeIdentifier(displayName)
                        else
                            EscapeIdentifier(sourceCol) & " AS " & EscapeIdentifier(displayName)
                    in
                        expr
                ),
                allCols = Text.Combine(allColExpressions, ", ")
            in
                if Text.Length(allCols) > 0 then allCols else error "No columns available in semantic view metadata",

        // Track if we generated all columns from metadata (for GROUP BY logic)
        generatedAllColumns = Text.Length(selectCols) = 0 and Text.Length(selectClause) > 0,

        // Output names as they actually appear in the SELECT list, in order - used to resolve
        // ORDER BY sort keys to ordinal positions (see BuildOrderByClause, issue #7)
        outputNames = if generatedAllColumns then
            List.Transform(metadata, each [ColumnName])
        else
            List.Combine({
                List.Transform(filteredMetadata, each if Record.HasFields(_, "OutputAlias") then [OutputAlias] else [ColumnName]),
                computedColNames
            }),

        // When generating from full metadata, need to compute dimensions for GROUP BY
        // Use ordinal positions (1-based) to avoid duplicate column name ambiguity
        allDimensionsForGroupBy = if generatedAllColumns then
            List.RemoveNulls(
                List.Transform(
                    List.Positions(metadata),
                    (i) =>
                        if metadata{i}[ColumnKind] = KIND_DIMENSION or metadata{i}[ColumnKind] = KIND_FACT
                        then Text.From(i + 1)  // SQL ordinals are 1-based
                        else null
                )
            )
        else {},
        allMetricsExist = generatedAllColumns and
            List.Count(List.Select(metadata, each [ColumnKind] = KIND_METRIC)) > 0,

        // Determine if GROUP BY is needed - also needed when generating from full metadata with metrics
        needsGroupBy = (groupByCols <> null and Text.Length(groupByCols) > 0 and
            (not List.IsEmpty(metrics) or not List.IsEmpty(dimensions))) or
            (allMetricsExist and not List.IsEmpty(allDimensionsForGroupBy)),

        // Use computed GROUP BY columns when generating from full metadata
        effectiveGroupByCols = if generatedAllColumns and allMetricsExist then
            Text.Combine(allDimensionsForGroupBy, ", ")
        else
            groupByCols,

        // CRITICAL: Only apply metric filter subquery wrapper when columns are actually selected
        // SELECT * on semantic views can fail with computed metrics - don't wrap validation queries
        hasColumnsSelected = Text.Length(selectCols) > 0,
        shouldWrapInSubquery = hasMetricFilters and hasColumnsSelected,

        // Build inner query (without LIMIT/OFFSET if we're wrapping in subquery)
        innerSql = "SELECT " & distinctKeyword & selectClause & " FROM " & qualifiedName &
            whereClause &
            (if needsGroupBy then " GROUP BY " & effectiveGroupByCols else "") &
            BuildOrderByClause(orderBy, outputNames, aliasMap) &
            (if not shouldWrapInSubquery then BuildLimitOffsetClause(limit, offset) else ""),

        // If METRIC filters exist AND we have columns, wrap in subquery and apply filters on outer query
        metricWhereClause = if shouldWrapInSubquery then
            BuildWhereClause(metricConditions)
        else "",

        // Assemble final SQL - only wrap in subquery if we have columns AND metric filters
        baseSql = if shouldWrapInSubquery then
            "SELECT * FROM (" & innerSql & ") AS ""_""" &
            metricWhereClause &
            BuildLimitOffsetClause(limit, offset)
        else
            innerSql
    in
        baseSql;

//
// Filter Expression Helpers for SQL WHERE clauses
//

// Partition filter conditions by column kind (METRIC vs DIMENSION/FACT)
// METRIC filters cannot be in WHERE clause for Snowflake Semantic Views
// They must be applied after aggregation via subquery wrapper
// Returns record with [WhereConditions, MetricConditions]
PartitionFilterConditions = (conditions as list, metadataByName as record) as record =>
    let
        // Filter out malformed conditions (missing or empty Column field)
        validConditions = List.Select(conditions, each
            [Column]? <> null and Text.Length(Text.From([Column]? ?? "")) > 0
        ),

        classifyCondition = (cond) =>
            let
                colName = cond[Column],
                colMeta = Record.FieldOrDefault(metadataByName, colName, null),
                kind = if colMeta <> null then colMeta[ColumnKind]? else null
            in
                if kind = KIND_METRIC then "metric" else "where",

        whereConditions = List.Select(validConditions, each classifyCondition(_) = "where"),
        metricConditions = List.Select(validConditions, each classifyCondition(_) = "metric")
    in
        [WhereConditions = whereConditions, MetricConditions = metricConditions];

// Format a value for SQL based on its type
FormatSqlValue = (value as any) as text =>
    if value = null then "NULL"
    else if value is text then "'" & Text.Replace(value, "'", "''") & "'"
    else if value is number then Number.ToText(value)
    else if value is logical then (if value then "TRUE" else "FALSE")
    else if value is date then "'" & Date.ToText(value, "yyyy-MM-dd") & "'"
    else if value is datetime then "'" & DateTime.ToText(value, "yyyy-MM-dd HH:mm:ss") & "'"
    else if value is datetimezone then "'" & DateTimeZone.ToText(value, "yyyy-MM-dd HH:mm:ss") & "'"
    else if value is time then "'" & Time.ToText(value, "HH:mm:ss") & "'"
    else Text.From(value);

// Build WHERE clause from conditions list
BuildWhereClause = (conditions as list) as text =>
    let
        // Format a single condition - handles comparisons, IN clauses, IS NULL, BETWEEN, column-to-column, and SQL expressions
        FormatCondition = (cond) =>
            let
                // Use SqlExpression if present (for text transform functions), otherwise use escaped Column
                leftSide = if cond[SqlExpression]? <> null then cond[SqlExpression]
                    else EscapeIdentifier(cond[Column]),
                op = cond[Operator],
                val = cond[Value]
            in
                // IS NULL / IS NOT NULL - no value needed
                if op = "IS NULL" or op = "IS NOT NULL" then
                    leftSide & " " & op
                // BETWEEN clause - Value is a record with Start and End fields
                else if op = "BETWEEN" then
                    leftSide & " BETWEEN " & FormatSqlValue(val[Start]) & " AND " & FormatSqlValue(val[End])
                // Column-to-column comparison - Value is a record with ColumnRef field
                else if val is record and val[ColumnRef]? <> null then
                    leftSide & " " & op & " " & EscapeIdentifier(val[ColumnRef])
                // IN or NOT IN clause - Value is a list of values
                else if op = "IN" or op = "NOT IN" then
                    leftSide & " " & op & " (" & Text.Combine(List.Transform(val, each FormatSqlValue(_)), ", ") & ")"
                // LIKE or NOT LIKE clause - add ESCAPE clause for proper pattern handling
                else if op = "LIKE" or op = "NOT LIKE" then
                    leftSide & " " & op & " " & FormatSqlValue(val) & " ESCAPE '\\'"
                // Simple comparison
                else
                    leftSide & " " & op & " " & FormatSqlValue(val),

        whereParts = List.Transform(conditions, each FormatCondition(_)),
        whereClause = if List.IsEmpty(whereParts) then ""
            else " WHERE " & Text.Combine(whereParts, " AND ")
    in
        whereClause;

//
// Helper: Table.ToNavigationTable
//
Table.ToNavigationTable = (
    table as table,
    keyColumns as list,
    nameColumn as text,
    dataColumn as text,
    itemKindColumn as text,
    itemNameColumn as text,
    isLeafColumn as text
) as table =>
    let
        tableType = Value.Type(table),
        newTableType = Type.AddTableKey(tableType, keyColumns, true) meta [
            NavigationTable.NameColumn = nameColumn,
            NavigationTable.DataColumn = dataColumn,
            NavigationTable.ItemKindColumn = itemKindColumn,
            Preview.DelayColumn = itemNameColumn,
            NavigationTable.IsLeafColumn = isLeafColumn
        ],
        navigationTable = Value.ReplaceType(table, newTableType)
    in
        navigationTable;

//
// Data Source Kind Definition
//
SnowflakeSemanticViews = [
    TestConnection = (dataSourcePath) =>
        let
            json = Json.Document(dataSourcePath),
            server = json[server]?,
            warehouse = json[warehouse]?
        in
            {"SnowflakeSemanticViews.Contents", server, warehouse},
    Authentication = [
        // Snowflake (UsernamePassword) - PAT token authentication
        UsernamePassword = [
            Name = "Snowflake",
            Label = "Snowflake",
            UsernameLabel = "Username",
            PasswordLabel = "Password"
        ],
        // Microsoft Account (Azure AD / Entra ID) - OAuth authentication
        Aad = [
            Label = "Microsoft Account",
            AuthorizationUri = "https://login.microsoftonline.com/common/oauth2/authorize",
            Resource = "https://analysis.windows.net/powerbi/connector/Snowflake"
        ],
        // KeyPair - JWT authentication with private key
        KeyPair = [
            Properties = type function (
                Username as text,
                privatekey as (Certificate.Type meta [Documentation.FieldCaption = "Private Key"]),
                optional passphrase as (Password.Type meta [Documentation.FieldCaption = "Passphrase"])
            ) as any
        ]
    ],
Label = "Snowflake Semantic Views"
];

//
// TEST HELPER FUNCTIONS (for PQTest SQL generation testing)
// These functions expose internal SQL generation for unit testing
//
shared SnowflakeSemanticViews.TestGenerateSQL = (
    qualifiedName as text,
    selectedColumns as list,
    metadata as list,
    optional limit as number,
    optional offset as number,
    optional orderBy as list,
    optional aliasMap as record,
    optional distinctCountMap as record,
    optional filterConditions as list,
    optional statisticalFuncMap as record,
    optional distinct as logical,
    optional rowCountMap as record,
    optional computedColumns as list
) as text =>
    GenerateSemanticViewQuery(
        qualifiedName,
        selectedColumns,
        metadata,
        limit,
        offset,
        orderBy,
        aliasMap,
        distinctCountMap,
        filterConditions,
        statisticalFuncMap,
        distinct,
        rowCountMap,
        computedColumns
    );

// Expose ParseSnowflakeServer for PQTest / RunUnitTests coverage of
// PrivateLink, legacy-locator, and account-name host formats (issues #1, #2).
shared SnowflakeSemanticViews.TestParseServer = (server as text) as record =>
    ParseSnowflakeServer(server);

// Lightweight self-test harness. Run via PQTest or the Power Query SDK
// evaluation pane: SnowflakeSemanticViews.RunUnitTests()
// Returns a table of {TestName, Expected, Actual, Pass} so failures are
// easy to spot without a full DAX Studio / Power BI Desktop round trip.
shared SnowflakeSemanticViews.RunUnitTests = () as table =>
    let
        makeCase = (name as text, expected as any, actual as any) as record =>
            [
                TestName = name,
                Expected = Text.From(expected),
                Actual = Text.From(actual),
                Pass = expected = actual
            ],

        // --- ParseSnowflakeServer: account-name format (no region) ---
        pAccount = ParseSnowflakeServer("myaccount.snowflakecomputing.com"),

        // --- ParseSnowflakeServer: legacy locator + region format ---
        pLegacy = ParseSnowflakeServer("xy12345.eu-west-1.snowflakecomputing.com"),

        // --- ParseSnowflakeServer: PrivateLink, org-account style (no region segment) ---
        pPrivateLinkOrg = ParseSnowflakeServer("myorg-myaccount.privatelink.snowflakecomputing.com"),

        // --- ParseSnowflakeServer: PrivateLink, legacy locator + region ---
        pPrivateLinkLocator = ParseSnowflakeServer("xy12345.eu-west-1.privatelink.snowflakecomputing.com"),

        // --- ParseSnowflakeServer: mixed-case account name must be preserved (case-sensitive TLS/SNI) ---
        pMixedCase = ParseSnowflakeServer("MyOrg-MyAccount.snowflakecomputing.com"),

        // --- ParseSnowflakeServer: bare multi-segment identifier keeps its region via full Host ---
        pBareMulti = ParseSnowflakeServer("cs83279.eu-west-2.aws"),

        // --- ParseSnowflakeServer: bare single-segment identifier lets the driver build the host ---
        pBareSingle = ParseSnowflakeServer("myaccount"),

        // --- ResolveDuplicateColumnNames: suffixes duplicate display names but keeps SourceColumn ---
        dupInput = {
            [ColumnName = "REGION"],
            [ColumnName = "REGION"],
            [ColumnName = "REGION"],
            [ColumnName = "CUSTOMER_NAME"]
        },
        dupResult = ResolveDuplicateColumnNames(dupInput),

        // --- BuildOrderByClause / GenerateSemanticViewQuery: issue #7 ordinal-based ORDER BY ---
        obMetadata = {
            [ColumnName = "REGION_NAME", ColumnType = "TEXT", ColumnKind = KIND_DIMENSION],
            [ColumnName = "ORDER_YEAR", ColumnType = "INT64", ColumnKind = KIND_DIMENSION],
            [ColumnName = "NET_REVENUE", ColumnType = "FLOAT", ColumnKind = KIND_METRIC]
        },
        obView = "TPCH_RICH_DB.TPCH_RICH_SVS.SV_SALES_ANALYSIS",

        // Sort on a projected dimension -> ordinal 1
        obSqlProjected = GenerateSemanticViewQuery(obView, {"REGION_NAME"}, obMetadata, null, null,
            {[Name = "REGION_NAME", Order = Order.Ascending]}),

        // Sort on a dimension NOT in selectedColumns, filtered to a single value (issue #7 regression):
        // the column is dropped from the projection, so the sort key must be dropped too, not emitted
        // as a dangling ORDER BY on an unprojected column
        obSqlDroppedFilter = GenerateSemanticViewQuery(obView, {"REGION_NAME"}, obMetadata, null, null,
            {[Name = "ORDER_YEAR", Order = Order.Ascending]}, null, null,
            {[Column = "ORDER_YEAR", Operator = "=", Value = 1998]}),

        // Sort by a metric's source name while the projection carries a Power BI alias (a0) ->
        // resolved via the reverse aliasMap lookup
        obSqlAlias = GenerateSemanticViewQuery(obView, {"REGION_NAME", "a0"}, obMetadata, null, null,
            {[Name = "NET_REVENUE", Order = Order.Ascending]}, [a0 = "NET_REVENUE"]),

        // Sort key with a "t0." table prefix Power BI adds -> resolved via StripTablePrefix
        obSqlPrefixed = GenerateSemanticViewQuery(obView, {"REGION_NAME"}, obMetadata, null, null,
            {[Name = "t0.REGION_NAME", Order = Order.Ascending]}),

        // Sort descending on the second projected column
        obSqlDesc = GenerateSemanticViewQuery(obView, {"REGION_NAME", "NET_REVENUE"}, obMetadata, null, null,
            {[Name = "NET_REVENUE", Order = Order.Descending]}),

        // Sort + limit -> "ORDER BY n DESC LIMIT k" in that order
        obSqlSortLimit = GenerateSemanticViewQuery(obView, {"REGION_NAME", "NET_REVENUE"}, obMetadata, 10, null,
            {[Name = "NET_REVENUE", Order = Order.Descending]}),

        // --- MapSnowflakeType: zero-scale NUMBER/DECIMAL/NUMERIC must map to Int64.Type, not
        // Decimal.Type, so integer dimensions (e.g. ORDER_YEAR NUMBER(4,0)) match the integer
        // Arrow value ADBC returns. A Double-declared integer column caused DISP_E_TYPEMISMATCH
        // in Power BI for DISTINCT/TopN queries over the raw dimension value.
        mtOrderYear = MapSnowflakeType("NUMBER(4,0)"),
        mtDecimal = MapSnowflakeType("NUMBER(10,2)"),
        mtBareNumber = MapSnowflakeType("NUMBER"),
        mtDecimal38_0 = MapSnowflakeType("DECIMAL(38,0)"),

        // --- BuildMinimalTableType: the Int64.Type branch must be wired up, or an integer
        // dimension falls through to "type nullable any" instead of "type nullable Int64.Type"
        tmMetadata = {[ColumnName = "ORDER_YEAR", ColumnType = "NUMBER(4,0)", ColumnKind = KIND_DIMENSION]},
        tmType = BuildMinimalTableType(tmMetadata),
        tmOrderYearType = Type.RecordFields(Type.TableRow(tmType))[ORDER_YEAR][Type],

        // --- ParseAggregateRecord: Power BI's Basic-filtering list-of-items query folds
        // COUNTROWS via Table.Group's own capability negotiation, which hands OnGroup a
        // lambda wrapper - e.g. "(t) => Table.RowCount(t)" - rather than the bare
        // Table.RowCount reference. Confirmed from a live mashup trace
        // (SqlExpressionTranslator/Translate) showing exactly this shape. Undetected, this
        // fell through to the position-based metric fallback and wrapped an unrelated metric
        // in AGG() against the grouped dimension, tripping Snowflake's semantic-view
        // granularity check with an unrelated "higher level of granularity" error.
        parWrappedRowCount = ParseAggregateRecord([Name = "a0", Function = (t) => Table.RowCount(t)], {"NET_REVENUE", "CUSTOMER_COUNT"}),
        parBareRowCount = ParseAggregateRecord([Name = "a0", Function = Table.RowCount], {"NET_REVENUE", "CUSTOMER_COUNT"}),
        parRealAggregateNotMisdetected = ParseAggregateRecord([Name = "a0", Column = "NET_REVENUE", Function = (t) => List.Sum(t[NET_REVENUE])], {"NET_REVENUE", "CUSTOMER_COUNT"}),

        // --- GenerateSemanticViewQuery: COUNTROWS must render as COUNT("dimension"), not
        // COUNT(*) - Snowflake Semantic Views reject bare COUNT(*)/AGG(COUNT(*)) as an invalid
        // metric expression (confirmed live). Live-verified: COUNT("ORDER_YEAR") over this
        // semantic view returns correct per-year row counts.
        rcMetadata = {[ColumnName = "ORDER_YEAR", ColumnType = "NUMBER(4,0)", ColumnKind = KIND_DIMENSION]},
        rcRowCountMap = [a0 = true],
        rcSql = GenerateSemanticViewQuery(obView, {"ORDER_YEAR", "a0"}, rcMetadata, 1000001, null, null, null, null, null, null, null, rcRowCountMap),

        tests = {
            makeCase("ParseServer_AccountName_Account", "myaccount", pAccount[Account]),
            makeCase("ParseServer_AccountName_UrlFormat", "AccountName", pAccount[UrlFormat]),
            makeCase("ParseServer_AccountName_IsPrivateLink", false, pAccount[IsPrivateLink]),

            makeCase("ParseServer_LegacyLocator_Account", "xy12345", pLegacy[Account]),
            makeCase("ParseServer_LegacyLocator_Region", "eu-west-1", pLegacy[Region]),
            makeCase("ParseServer_LegacyLocator_UrlFormat", "LegacyLocator", pLegacy[UrlFormat]),
            makeCase("ParseServer_LegacyLocator_Host", "xy12345.eu-west-1.snowflakecomputing.com", pLegacy[Host]),

            makeCase("ParseServer_PrivateLinkOrg_Account", "myorg-myaccount", pPrivateLinkOrg[Account]),
            makeCase("ParseServer_PrivateLinkOrg_IsPrivateLink", true, pPrivateLinkOrg[IsPrivateLink]),
            makeCase("ParseServer_PrivateLinkOrg_UrlFormat", "PrivateLink", pPrivateLinkOrg[UrlFormat]),
            makeCase(
                "ParseServer_PrivateLinkOrg_Host",
                "myorg-myaccount.privatelink.snowflakecomputing.com",
                pPrivateLinkOrg[Host]
            ),

            makeCase("ParseServer_PrivateLinkLocator_Account", "xy12345", pPrivateLinkLocator[Account]),
            makeCase("ParseServer_PrivateLinkLocator_Region", "eu-west-1", pPrivateLinkLocator[Region]),
            makeCase("ParseServer_PrivateLinkLocator_IsPrivateLink", true, pPrivateLinkLocator[IsPrivateLink]),

            makeCase("ParseServer_MixedCase_AccountPreservesCase", "MyOrg-MyAccount", pMixedCase[Account]),

            makeCase("ParseServer_BareMulti_Account", "cs83279", pBareMulti[Account]),
            makeCase("ParseServer_BareMulti_Region", "eu-west-2", pBareMulti[Region]),
            makeCase("ParseServer_BareMulti_Host", "cs83279.eu-west-2.aws.snowflakecomputing.com", pBareMulti[Host]),
            makeCase("ParseServer_BareMulti_UrlFormat", "LegacyLocator", pBareMulti[UrlFormat]),

            makeCase("ParseServer_BareSingle_Account", "myaccount", pBareSingle[Account]),
            makeCase("ParseServer_BareSingle_Host", null, pBareSingle[Host]),
            makeCase("ParseServer_BareSingle_UrlFormat", "AccountName", pBareSingle[UrlFormat]),

            makeCase("ResolveDuplicates_Count", 4, List.Count(dupResult)),
            makeCase("ResolveDuplicates_First_ColumnName", "REGION", dupResult{0}[ColumnName]),
            makeCase("ResolveDuplicates_First_SourceColumn", "REGION", dupResult{0}[SourceColumn]),
            makeCase("ResolveDuplicates_Second_ColumnName", "REGION_2", dupResult{1}[ColumnName]),
            makeCase("ResolveDuplicates_Second_SourceColumn", "REGION", dupResult{1}[SourceColumn]),
            makeCase("ResolveDuplicates_Third_ColumnName", "REGION_3", dupResult{2}[ColumnName]),
            makeCase("ResolveDuplicates_Unique_ColumnName", "CUSTOMER_NAME", dupResult{3}[ColumnName]),

            makeCase("OrderBy_ProjectedDimension_UsesOrdinal", true, Text.Contains(obSqlProjected, "ORDER BY 1 ASC")),
            makeCase("OrderBy_UnprojectedFilteredDimension_Dropped", false, Text.Contains(obSqlDroppedFilter, "ORDER BY")),
            makeCase("OrderBy_MetricViaAliasMap_UsesOrdinal", true, Text.Contains(obSqlAlias, "ORDER BY 2 ASC")),
            makeCase("OrderBy_TablePrefixedName_ResolvedViaStrip", true, Text.Contains(obSqlPrefixed, "ORDER BY 1 ASC")),
            makeCase("OrderBy_SecondColumn_Descending", true, Text.Contains(obSqlDesc, "ORDER BY 2 DESC")),
            makeCase("OrderBy_SortThenLimit_CorrectOrder", true, Text.Contains(obSqlSortLimit, "ORDER BY 2 DESC LIMIT 10")),

            makeCase("MapType_IntegerScale_NUMBER4_0_IsInt64", true, mtOrderYear = Int64.Type),
            makeCase("MapType_DecimalScale_NUMBER10_2_IsDecimal", true, mtDecimal = Decimal.Type),
            makeCase("MapType_BareNUMBER_DefaultsToInt64", true, mtBareNumber = Int64.Type),
            makeCase("MapType_DECIMAL38_0_IsInt64", true, mtDecimal38_0 = Int64.Type),
            makeCase("BuildMinimalTableType_IntegerDimension_UsesInt64", true, tmOrderYearType = type nullable Int64.Type),

            makeCase("ParseAggregateRecord_WrappedRowCount_IsRowCountDetected", true, parWrappedRowCount[IsRowCount]),
            makeCase("ParseAggregateRecord_WrappedRowCount_ColumnIsNull", null, parWrappedRowCount[Column]),
            makeCase("ParseAggregateRecord_BareRowCount_IsRowCountDetected", true, parBareRowCount[IsRowCount]),
            makeCase("ParseAggregateRecord_RealAggregate_NotMisdetectedAsRowCount", false, parRealAggregateNotMisdetected[IsRowCount]),

            makeCase("GenerateSemanticViewQuery_RowCount_UsesCountDimension_NotCountStar", true, Text.Contains(rcSql, "COUNT(""ORDER_YEAR"")")),
            makeCase("GenerateSemanticViewQuery_RowCount_DoesNotEmitCountStar", false, Text.Contains(rcSql, "COUNT(*)"))
        }
    in
        Table.FromRecords(tests, {"TestName", "Expected", "Actual", "Pass"});

//
// Data Source UI Publishing Definition
//
SnowflakeSemanticViews.Publish = [
    Beta = true,
    Category = "Database",
        ButtonText = {"Snowflake Semantic Views", "Connect to Snowflake Semantic Views. Authored By Alex Ross, Principal Solution Engineer at Snowflake. V3.3.2"},
    LearnMoreUrl = "https://docs.snowflake.com/en/user-guide/views-semantic",
    SupportsDirectQuery = true,
    SourceImage = SnowflakeSemanticViews.Icons,
    SourceTypeImage = SnowflakeSemanticViews.Icons
];

SnowflakeSemanticViews.Icons = [
    Icon16 = {
        Extension.Contents("Snowflake16.png"),
        Extension.Contents("Snowflake20.png"),
        Extension.Contents("Snowflake24.png"),
        Extension.Contents("Snowflake32.png")
    },
    Icon32 = {
        Extension.Contents("Snowflake32.png"),
        Extension.Contents("Snowflake40.png"),
        Extension.Contents("Snowflake48.png"),
        Extension.Contents("Snowflake64.png")
    }
];

//
// NORMALIZE PEM FORMAT
// Converts private key to proper PEM format for ADBC driver
// Handles both binary (from file picker) and text inputs
//
NormalizePEM = (privateKeyRaw as any) as nullable text =>
    if privateKeyRaw = null then
        null
    else
        let
            // Convert binary to text if needed (Certificate.Type returns binary)
            privateKeyText = if Value.Is(privateKeyRaw, type binary) then
                Text.FromBinary(privateKeyRaw, TextEncoding.Utf8)
            else if Value.Is(privateKeyRaw, type text) then
                privateKeyRaw
            else
                error Error.Record(ERROR_DATA_SOURCE,
                    "Private key must be binary or text"),

            // Normalize line endings (Windows CRLF -> Unix LF)
            normalizedEndings = Text.Replace(privateKeyText, "#(cr)#(lf)", "#(lf)"),

            // Remove any extra whitespace at start/end
            trimmed = Text.Trim(normalizedEndings)
        in
            trimmed;

//
// EXECUTE QUERY VIA ADBC (for KeyPair authentication)
// Uses the Snowflake ADBC driver which handles JWT generation internally from private key
// Execute query via ADBC driver for KeyPair authentication
//
// =============================================================================
// ADBC QUERY EXECUTION (Unified for all auth types)
// =============================================================================

// Build ADBC auth configuration based on token type
// Returns a record with auth-specific connection string fields
GetAdbcAuthConfig = (tokenType as text, credentials as record) as record =>
    if tokenType = "KEYPAIR_ADBC" then
        let
            username = credentials[Username],
            privateKeyRaw = credentials[PrivateKey],
            passphraseRaw = credentials[Passphrase],

            // Validate required fields
            _validateKey = if privateKeyRaw = null then
                error Error.Record(ERROR_DATA_SOURCE,
                    "Private key not provided. Please select a .pem or .p8 file in the Key Pair authentication dialog.")
            else null,

            // Normalize PEM format
            privateKey = NormalizePEM(privateKeyRaw),

            // KeyPair auth uses auth_jwt with private key
            authConfig = [
                #"adbc.snowflake.sql.auth_type" = CredentialProperty("auth_jwt"),
                username = CredentialProperty(username),
                #"adbc.snowflake.sql.client_option.jwt_private_key_pkcs8_value" = CredentialProperty(privateKey)
            ] & (if passphraseRaw <> null then
                [#"adbc.snowflake.sql.client_option.jwt_private_key_pkcs8_password" = CredentialProperty(passphraseRaw)]
            else [])
        in
            authConfig
    else if tokenType = "PAT" then
        // PAT (UsernamePassword) uses auth_snowflake with username/password
        let
            username = credentials[Username],
            password = credentials[Token]  // PAT token passed as password
        in
            [
                #"adbc.snowflake.sql.auth_type" = CredentialProperty("auth_snowflake"),
                username = CredentialProperty(username),
                password = CredentialProperty(password)
            ]
    else if tokenType = "OAUTH" then
        // OAuth uses auth_oauth with access_token
        let
            token = credentials[Token]
        in
            [
                #"adbc.snowflake.sql.auth_type" = CredentialProperty("auth_oauth"),
                #"adbc.snowflake.sql.client_option.auth_token" = CredentialProperty(token)
            ]
    else
        error Error.Record(ERROR_DATA_SOURCE,
            "Unsupported authentication type: " & tokenType & ". Supported types: KEYPAIR_ADBC, PAT, OAUTH");

// Generate OpenTelemetry trace parent ID for distributed tracing
// Format: {version}-{trace-id}-{parent-id}-{trace-flags}
// Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
MakeTraceParentId = (activityId as text) as text =>
    let
        TraceVersion = "00",
        Sampled = "01",
        // Remove hyphens from activity ID to get 32-char trace ID
        CleanedActivityId = Text.Replace(activityId, "-", ""),
        // Generate random 8-byte (16 hex char) parent span ID
        GenerateByte = () => Number.RoundDown(Number.RandomBetween(0, 255)),
        RandomBytes = List.Generate(() => 0, each _ < 8, each _ + 1, each GenerateByte()),
        ParentSpanId = Text.Combine(List.Transform(RandomBytes, each
            Text.PadStart(Number.ToText(_, "X"), 2, "0")
        ))
    in
        Text.Combine({TraceVersion, CleanedActivityId, ParentSpanId, Sampled}, "-");

// Build query tag JSON for Snowflake tracking
BuildQueryTag = (sql as text) as text =>
    let
        upperSql = Text.Upper(Text.Start(sql, 50)),
        queryType =
            if Text.StartsWith(upperSql, "SHOW DATABASE") or Text.StartsWith(upperSql, "SHOW SCHEMA")
               or Text.StartsWith(upperSql, "SHOW TABLE") or Text.StartsWith(upperSql, "SHOW VIEW")
               or Text.StartsWith(upperSql, "SHOW SEMANTIC VIEW") then "Navigation"
            else if Text.StartsWith(upperSql, "DESCRIBE") or Text.StartsWith(upperSql, "SHOW SEMANTIC DIM")
               or Text.StartsWith(upperSql, "SHOW SEMANTIC MET") or Text.StartsWith(upperSql, "SHOW SEMANTIC FAC") then "Metadata"
            else if Text.Contains(upperSql, "AGG(") then "SemanticView"
            else "Table",
        activityId = try Diagnostics.ActivityId() otherwise null
    in
        Text.FromBinary(Json.FromValue([
            Connector = "SnowflakeSemanticViews",
            Version = "3.0",
            QueryType = queryType,
            ActivityId = activityId,
            Transport = "ADBC"
        ]));

// =============================================================================
// SNOWFLAKE SERVER URL PARSER (v3.2.0)
// =============================================================================
// Parses Snowflake server URLs into components for ADBC connection
// Supports all URL formats:
//   - Account name: orgname-account.snowflakecomputing.com
//   - Legacy locator: xy12345.us-east-1.aws.snowflakecomputing.com
//   - PrivateLink (org): orgname-account.privatelink.snowflakecomputing.com
//   - PrivateLink (legacy): xy12345.eu-west-1.privatelink.snowflakecomputing.com
//   - Bare identifier: myaccount or orgname-account (driver builds the host)
//   - Bare multi-segment: xy12345.eu-west-2.aws (suffix appended to preserve region)
//
// Returns record with:
//   Account - Account identifier for ADBC
//   Host - Full hostname (for PrivateLink, null otherwise)
//   Region - Region identifier (if present)
//   IsPrivateLink - Boolean flag
//   UrlFormat - "AccountName", "LegacyLocator", or "PrivateLink"
//
ParseSnowflakeServer = (server as text) as record =>
    let
        lowerServer = Text.Lower(server),
        parts = Text.Split(server, "."),
        numParts = List.Count(parts),

        // Detect PrivateLink (contains ".privatelink." segment)
        isPrivateLink = Text.Contains(lowerServer, ".privatelink."),

        result = if isPrivateLink then
            let
                // PrivateLink format: account[.region].privatelink.snowflakecomputing.com
                // Extract account: everything before ".privatelink."
                beforePrivateLink = Text.BeforeDelimiter(server, ".privatelink."),
                accountParts = Text.Split(beforePrivateLink, "."),
                // Account is always the first part (preserve original case for TLS compatibility)
                account = accountParts{0},
                // Region is second part if exists (for legacy format like xy12345.eu-west-1.privatelink...)
                region = if List.Count(accountParts) > 1 then accountParts{1} else null
            in
                [
                    Account = account,
                    Host = server,  // Full host required for PrivateLink (ADBC uri.host override)
                    Region = region,
                    IsPrivateLink = true,
                    UrlFormat = "PrivateLink"
                ]
        else
            let
                // Standard or legacy format
                firstPart = parts{0},
                endsWithSfc = Text.EndsWith(lowerServer, ".snowflakecomputing.com"),
                // Check if this is legacy format with region (xy12345.region.cloud.snowflakecomputing.com)
                // Legacy format has: account.region.cloud.snowflakecomputing.com (5 parts)
                // Or: account.region.snowflakecomputing.com (4 parts with region)
                hasRegion = numParts >= 4 and
                    not Text.StartsWith(Text.Lower(parts{1}), "snowflake") and
                    endsWithSfc,
                // Bare multi-segment identifier (e.g. "xy12345.eu-west-2.aws"): no
                // snowflakecomputing.com suffix but dotted segments carrying a region.
                // Passing just parts{0} to the driver would drop the region, so build
                // the full host ourselves by appending the standard suffix.
                isBareMultiSegment = (not endsWithSfc) and numParts >= 2,
                region = if hasRegion or isBareMultiSegment then parts{1} else null
            in
                [
                    Account = firstPart,
                    // Set Host for legacy locator so ADBC uses uri.host override
                    // (without this, ADBC constructs URL from account alone, dropping the region)
                    Host = if hasRegion then server
                        else if isBareMultiSegment then server & ".snowflakecomputing.com"
                        else null,
                    Region = region,
                    IsPrivateLink = false,
                    UrlFormat = if hasRegion or isBareMultiSegment then "LegacyLocator" else "AccountName"
                ]
    in
        result;

// Build ADBC connection string (shared by both connection modes)
// v3.2.0: Added PrivateLink support via ParseSnowflakeServer
BuildAdbcConnectionString = (context as record) as record =>
    let
        server = context[Server],
        warehouse = context[Warehouse],
        tokenType = context[TokenType],

        // v3.2.0: Parse server URL (handles PrivateLink, legacy locator, account name formats)
        serverInfo = ParseSnowflakeServer(server),
        account = serverInfo[Account],

        // Get timeout values (with defaults)
        commandTimeout = context[CommandTimeout]? ?? DEFAULT_COMMAND_TIMEOUT,
        connectionTimeout = context[ConnectionTimeout]? ?? DEFAULT_CONNECTION_TIMEOUT,
        commandTimeoutStr = Number.ToText(commandTimeout) & "s",
        connectionTimeoutStr = Number.ToText(connectionTimeout) & "s",

        // Build auth config based on token type
        authConfig = GetAdbcAuthConfig(tokenType, context),

        // Build full connection string
        // NOTE: ADBC timeout options only control HTTP client behavior, NOT query execution time!
        // Server-side query timeout is controlled via STATEMENT_TIMEOUT_IN_SECONDS in pre-SQL
        // Application name for Snowflake tracking
        // Must start with "[ADBC]" or driver prepends unwanted text
        appName = "[ADBC] SnowflakeSemanticViews v3.3.2",

        // Base connection string options
        baseConnectionString = [
            server = server meta [Is.Pii="server"],
            #"adbc.snowflake.sql.account" = account,
            #"adbc.snowflake.sql.warehouse" = warehouse,
            #"adbc.snowflake.sql.client_option.client_timeout" = commandTimeoutStr,
            #"adbc.snowflake.sql.client_option.request_timeout" = commandTimeoutStr,
            #"adbc.snowflake.sql.client_option.login_timeout" = connectionTimeoutStr,
            // Use low precision mode (Double) to avoid decimal overflow with large NUMBER types
            #"adbc.snowflake.sql.client_option.use_high_precision" = "false",
            // Application name for Snowflake query history tracking
            #"adbc.snowflake.sql.client_option.app_name" = appName,
            // Datetime precision - "nanoseconds" for full precision
            #"adbc.snowflake.sql.client_option.max_timestamp_precision" = "nanoseconds"
            // Note: Role (adbc.snowflake.sql.role) not implemented - would require UI parameter
        ],

        // v3.2.0: Set uri.host for any format where the hostname is more than account.snowflakecomputing.com
        // This ensures the ADBC Go driver uses the full hostname (with region/privatelink) instead of
        // constructing it from account alone (which would drop region segments and cause 404 errors)
        hostOptions = if serverInfo[Host] <> null then
            [#"adbc.snowflake.sql.uri.host" = serverInfo[Host]]
        else [],

        // Combine all options
        connectionString = baseConnectionString & hostOptions & authConfig
    in
        connectionString;

// Generic ADBC query executor using Adbc.Connection for session-aware queries
// Uses ExecuteQueryWithContext to ensure timeout settings and query run in same session
// context must contain: Server, Warehouse, TokenType, and auth-specific credentials
ExecuteQueryViaADBC = (context as record, sql as text) as table =>
    let
        server = context[Server],
        tokenType = context[TokenType],
        account = ParseSnowflakeServer(server)[Account],

        _trace = Diagnostics.Trace(TraceLevel.Information, "ExecuteQueryViaADBC",
            [Account = account, TokenType = tokenType, SQL = Text.Start(sql, 50)]),

        // Build connection string
        connectionString = BuildAdbcConnectionString(context),

        // Get command timeout for session setting
        commandTimeout = context[CommandTimeout]? ?? DEFAULT_COMMAND_TIMEOUT,

        // Build timeout SQL to run BEFORE each query (in same session)
        timeoutSql = "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = " & Number.ToText(commandTimeout),

        // Statement options with query tag and OpenTelemetry trace parent
        queryTagJson = BuildQueryTag(sql),
        activityId = try Diagnostics.ActivityId() otherwise "00000000-0000-0000-0000-000000000000",
        traceParentId = MakeTraceParentId(activityId),
        statementProperties = [
            #"adbc.snowflake.statement.query_tag" = queryTagJson,
            #"adbc.telemetry.trace_parent" = traceParentId
        ],

        // ADBC driver specification
        Driver = [
            Name = "SnowflakeAdbc",
            Folder = "Snowflake",
            File = "libadbc_driver_snowflake.dll",
            DriverType = "Unmanaged",
            EntryPoint = "AdbcDriverSnowflakeInit"
        ],

        // Try using Adbc.Connection with ExecuteQueryWithContext (session-aware)
        // Falls back to Adbc.Query if Adbc.Connection is not available
        useConnection = try
            let
                // Create managed connection with pooling (ConnectionPoolType=2)
                connection = Adbc.Connection(Driver, connectionString, [], [ConnectionPoolType=2]),

                // Execute with timeout pre-SQL and main query in SAME session
                // ExecuteQueryWithContext(preSql, mainSql, postSql, options)
                queryResult = connection[ExecuteQueryWithContext](
                    timeoutSql,
                    sql,
                    null,
                    [StatementProperties = statementProperties]
                )
            in
                queryResult
        otherwise
            // Fallback: Use Adbc.Query (may not guarantee same session for timeout)
            let
                _trace2 = Diagnostics.Trace(TraceLevel.Warning, "ExecuteQueryViaADBC",
                    "Adbc.Connection not available, falling back to Adbc.Query (timeout may not work correctly)"),

                // Try to set timeout (may be on different connection due to pooling)
                _setTimeout = try Adbc.Query("SnowflakeAdbc", connectionString, timeoutSql,
                    [ClientConnectionPooling = true, StatementProperties = statementProperties])
                otherwise null,

                // Execute the actual query
                queryResult = Adbc.Query("SnowflakeAdbc", connectionString, sql,
                    [ClientConnectionPooling = true, StatementProperties = statementProperties])
            in
                queryResult
    in
        useConnection;

// Legacy wrapper for KeyPair auth (backward compatibility)
// Converts old context format to new unified format
ExecuteQueryViaADBC_KeyPair = (context as record, sql as text) as table =>
    let
        // Convert to unified context format
        unifiedContext = [
            Server = context[Server],
            Warehouse = context[Warehouse],
            TokenType = "KEYPAIR_ADBC",
            Username = context[Username],
            PrivateKey = context[PrivateKey],
            Passphrase = context[Passphrase],
            CommandTimeout = context[CommandTimeout]? ?? DEFAULT_COMMAND_TIMEOUT,
            ConnectionTimeout = context[ConnectionTimeout]? ?? DEFAULT_CONNECTION_TIMEOUT
        ]
    in
        ExecuteQueryViaADBC(unifiedContext, sql);

// Execute metadata queries via ADBC (unified for all auth types)
// Note: Previously used REST API with Web.Contents caching for PAT/OAuth,
// but migrated to ADBC for consistency and simpler codebase
ExecuteMetadataQuery = (context as record, sql as text) as table =>
    let
        tokenType = context[TokenType]? ?? "KEYPAIR_ADBC",

        _trace = Diagnostics.Trace(TraceLevel.Information, "ExecuteMetadataQuery",
            [TokenType = tokenType, SQL = Text.Start(sql, 50)]),

        // Build unified context for ADBC execution
        adbcContext = if tokenType = "KEYPAIR_ADBC" then
            [
                Server = context[Server],
                Warehouse = context[Warehouse],
                TokenType = "KEYPAIR_ADBC",
                Username = context[Username],
                PrivateKey = context[PrivateKey],
                Passphrase = context[Passphrase],
                CommandTimeout = context[CommandTimeout]? ?? DEFAULT_COMMAND_TIMEOUT,
                ConnectionTimeout = context[ConnectionTimeout]? ?? DEFAULT_CONNECTION_TIMEOUT
            ]
        else
            // PAT or OAuth
            [
                Server = context[Server],
                Warehouse = context[Warehouse],
                TokenType = tokenType,
                Token = context[Token],
                Username = context[Username],  // Required for PAT auth_snowflake
                CommandTimeout = context[CommandTimeout]? ?? DEFAULT_COMMAND_TIMEOUT,
                ConnectionTimeout = context[ConnectionTimeout]? ?? DEFAULT_CONNECTION_TIMEOUT
            ],

        // Execute via ADBC
        tableResult = ExecuteQueryViaADBC(adbcContext, sql)
    in
        tableResult;


//
// ADBC Functions from #shared (Global Environment)
// Required for ADBC driver integration with Snowflake
//
Adbc.Query = try #shared[Adbc.Query]
    otherwise (driver, connectionString, sql, options) =>
        error Error.Record(ERROR_EXPRESSION, "Adbc.Query is not available in this environment. ADBC requires Power BI Desktop.");

// Adbc.Connection - Creates managed connection with ExecuteQueryWithContext for session-aware queries
// Used to ensure timeout settings and queries run on same session (unlike Adbc.Query which may use different pooled connections)
Adbc.Connection = try #shared[Adbc.Connection]
    otherwise (driver, databaseProperties, connectionProperties, options) =>
        error Error.Record(ERROR_EXPRESSION, "Adbc.Connection is not available in this environment. ADBC requires Power BI Desktop.");

// Adbc.DataSource - DISABLED (causes connector load failure when accessed)
// TODO: Investigate why accessing #shared[Adbc.DataSource] fails
// Adbc.DataSource = try #shared[Adbc.DataSource]
//     otherwise (driver, connectionString, options) =>
//         error Error.Record(ERROR_EXPRESSION, "Adbc.DataSource is not available in this environment.");

// Helper to mark credential properties for ADBC connection strings
CredentialProperty = (p as any) as any => p meta [Credential.Property = true];
