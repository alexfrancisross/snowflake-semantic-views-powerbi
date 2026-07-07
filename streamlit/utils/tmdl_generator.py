"""
TMDL (Tabular Model Definition Language) generator for Power BI.
Generates PBIP-compatible project files from Snowflake objects:
- Semantic Views (uses custom SnowflakeSemanticViews connector)
- Views (uses native Snowflake connector)
- Tables (uses native Snowflake connector)

Updated to match Power BI Desktop's actual TMDL format.
"""

import uuid
import json
from datetime import datetime
from typing import Any

from .metadata_fetcher import SemanticViewMetadata, ColumnMetadata, ObjectType
from .type_mappings import snowflake_to_pbi_type


def generate_lineage_tag() -> str:
    """Generate a unique lineage tag (UUID format)."""
    return str(uuid.uuid4())


def escape_m_string(value: str | None) -> str:
    """Escape a string for use in M (Power Query) expressions."""
    return (value or "").replace('"', '""')


def get_source_provider_type(snowflake_type: str, pbi_type: str) -> str | None:
    """
    Get the sourceProviderType for Power BI based on Snowflake type.

    Args:
        snowflake_type: Original Snowflake data type
        pbi_type: Mapped Power BI data type

    Returns:
        Source provider type string, or None if not applicable
    """
    base_type = snowflake_type.upper().split("(")[0].strip() if snowflake_type else ""

    # Semi-structured types do NOT have sourceProviderType in Power BI
    if base_type in ("VARIANT", "OBJECT", "ARRAY"):
        return None

    # Geo types do NOT have sourceProviderType in Power BI
    if base_type in ("GEOGRAPHY", "GEOMETRY"):
        return None

    # Date types
    if base_type == "DATE":
        return "date"
    elif base_type == "TIME":
        return "time"
    elif base_type == "TIMESTAMP_TZ":
        return "datetimeoffset"
    elif base_type in ("DATETIME", "TIMESTAMP", "TIMESTAMP_LTZ", "TIMESTAMP_NTZ"):
        return "datetime2"

    # Numeric types - Power BI uses double for most Snowflake numbers
    if pbi_type == "double" or pbi_type == "decimal":
        return "double"
    elif pbi_type == "int64":
        return "bigint"

    # String types
    if pbi_type == "string":
        return "nvarchar(max)"

    # Boolean
    if pbi_type == "boolean":
        return "bit"

    return "nvarchar(max)"


def get_format_string(snowflake_type: str, pbi_type: str) -> str | None:
    """
    Get the formatString for Power BI display.

    Args:
        snowflake_type: Original Snowflake data type
        pbi_type: Mapped Power BI data type

    Returns:
        Format string or None
    """
    base_type = snowflake_type.upper().split("(")[0].strip() if snowflake_type else ""

    # DATE uses "Long Date"
    if base_type == "DATE":
        return "Long Date"

    # TIME uses "Long Time"
    if base_type == "TIME":
        return "Long Time"

    # TIMESTAMP/DATETIME uses "General Date"
    if base_type in ("DATETIME", "TIMESTAMP", "TIMESTAMP_LTZ", "TIMESTAMP_NTZ", "TIMESTAMP_TZ"):
        return "General Date"

    # BOOLEAN uses special TRUE/FALSE format
    if base_type == "BOOLEAN" or pbi_type == "boolean":
        return '"""TRUE"";""TRUE"";""FALSE"""'

    return None


def get_summarize_by(column_kind: str, pbi_type: str, column_name: str = "") -> str:
    """
    Get the summarizeBy setting based on column type.
    Power BI defaults all numeric columns to sum, non-numeric to none.

    Args:
        column_kind: DIMENSION, METRIC, or FACT (used for context)
        pbi_type: Power BI data type
        column_name: Column name (for ID detection)

    Returns:
        Summarize setting (sum, count, or none)
    """
    # ID columns typically use count
    if column_name.upper() in ("ID", "KEY", "PK") or column_name.upper().endswith("_ID"):
        if pbi_type in ("double", "int64"):
            return "count"

    # All numeric columns get sum by default in Power BI
    if pbi_type in ("double", "int64"):
        return "sum"

    # Non-numeric columns (string, date, boolean) get none
    return "none"


def generate_column_tmdl(col: ColumnMetadata) -> str:
    """
    Generate TMDL for a single column matching Power BI's format.

    Args:
        col: Column metadata

    Returns:
        TMDL string for the column
    """
    pbi_type = snowflake_to_pbi_type(col.data_type)
    lineage_tag = generate_lineage_tag()
    source_provider_type = get_source_provider_type(col.data_type, pbi_type)
    format_string = get_format_string(col.data_type, pbi_type)
    summarize_by = get_summarize_by(col.kind, pbi_type, col.name)

    lines = [f'\t\tcolumn {col.name}']

    # Property order matches Power BI: dataType, formatString, sourceProviderType, lineageTag, summarizeBy, sourceColumn
    lines.append(f'\t\t\tdataType: {pbi_type}')

    if format_string:
        lines.append(f'\t\t\tformatString: {format_string}')

    # Only include sourceProviderType if it's not None (semi-structured/geo types don't have it)
    if source_provider_type:
        lines.append(f'\t\t\tsourceProviderType: {source_provider_type}')

    lines.append(f'\t\t\tlineageTag: {lineage_tag}')
    lines.append(f'\t\t\tsummarizeBy: {summarize_by}')
    source_col = col.source_column or col.name  # Use original name for DirectQuery
    lines.append(f'\t\t\tsourceColumn: {source_col}')

    # Annotations
    lines.append('')
    lines.append('\t\t\tannotation SummarizationSetBy = Automatic')

    # Add format hint for numeric types
    if pbi_type in ("double", "int64") and not format_string:
        lines.append('')
        lines.append('\t\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}')

    # Add underlying date type annotation for DATE and TIME
    base_type = col.data_type.upper().split("(")[0].strip() if col.data_type else ""
    if base_type == "DATE":
        lines.append('')
        lines.append('\t\t\tannotation UnderlyingDateTimeDataType = Date')
    elif base_type == "TIME":
        lines.append('')
        lines.append('\t\t\tannotation UnderlyingDateTimeDataType = Time')
    # Note: TIMESTAMP types do NOT get UnderlyingDateTimeDataType annotation in Power BI

    return '\n'.join(lines)


def generate_partition_tmdl(
    view_name: str,
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str,
    mode: str = "directQuery"
) -> str:
    """
    Generate TMDL for the partition (M expression).
    Uses appropriate connector based on object type.

    Args:
        view_name: Name of the object
        metadata: Object metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name
        mode: Storage mode ("directQuery" or "import")

    Returns:
        TMDL string for the partition
    """
    # Use appropriate M expression based on object type
    if metadata.object_type == "SEMANTIC_VIEW":
        m_expression = generate_semantic_view_m_expression(metadata, server, warehouse)
    else:
        m_expression = generate_standard_m_expression(metadata, server, warehouse)

    partition_tmdl = f'''\t\tpartition {view_name} = m
\t\t\tmode: {mode}
\t\t\tsource =
\t\t\t\t\t{m_expression.replace(chr(10), chr(10) + chr(9) + chr(9) + chr(9) + chr(9) + chr(9))}'''

    return partition_tmdl


def generate_column_tmdl_no_indent(col: ColumnMetadata) -> str:
    """
    Generate TMDL for a single column matching Power BI's format (no extra indent).

    Args:
        col: Column metadata

    Returns:
        TMDL string for the column
    """
    pbi_type = snowflake_to_pbi_type(col.data_type)
    lineage_tag = generate_lineage_tag()
    source_provider_type = get_source_provider_type(col.data_type, pbi_type)
    format_string = get_format_string(col.data_type, pbi_type)
    summarize_by = get_summarize_by(col.kind, pbi_type, col.name)

    lines = [f'\tcolumn {col.name}']

    # Property order matches Power BI: dataType, formatString, sourceProviderType, lineageTag, summarizeBy, sourceColumn
    lines.append(f'\t\tdataType: {pbi_type}')

    if format_string:
        lines.append(f'\t\tformatString: {format_string}')

    # Only include sourceProviderType if it's not None (semi-structured/geo types don't have it)
    if source_provider_type:
        lines.append(f'\t\tsourceProviderType: {source_provider_type}')

    lines.append(f'\t\tlineageTag: {lineage_tag}')
    lines.append(f'\t\tsummarizeBy: {summarize_by}')
    source_col = col.source_column or col.name  # Use original name for DirectQuery
    lines.append(f'\t\tsourceColumn: {source_col}')

    # Annotations
    lines.append('')
    lines.append('\t\tannotation SummarizationSetBy = Automatic')

    # Add format hint for numeric types
    if pbi_type in ("double", "int64") and not format_string:
        lines.append('')
        lines.append('\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}')

    # Add underlying date type annotation for DATE and TIME
    base_type = col.data_type.upper().split("(")[0].strip() if col.data_type else ""
    if base_type == "DATE":
        lines.append('')
        lines.append('\t\tannotation UnderlyingDateTimeDataType = Date')
    elif base_type == "TIME":
        lines.append('')
        lines.append('\t\tannotation UnderlyingDateTimeDataType = Time')

    return '\n'.join(lines)


def generate_semantic_view_m_expression(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str
) -> str:
    """
    Generate M expression for semantic views using custom connector.

    Args:
        metadata: Semantic view metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name

    Returns:
        M expression string
    """
    database = escape_m_string(metadata.database)
    schema = escape_m_string(metadata.schema)
    escaped_view = escape_m_string(metadata.view)

    return f'''let
    Source = SnowflakeSemanticViews.Contents("{escape_m_string(server)}", "{escape_m_string(warehouse)}", null, null, null, null, null),
    {database}_DB = Source{{[name="{database}"]}}[Data],
    {schema}_Schema = {database}_DB{{[name="{schema}"]}}[Data],
    {escaped_view}1 = {schema}_Schema{{[name="{escaped_view}"]}}[Data]
in
    {escaped_view}1'''


def generate_standard_m_expression(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str
) -> str:
    """
    Generate M expression for regular views/tables using native Snowflake connector.

    v3.0: Uses Snowflake.Databases() for standard tables and views.
    The custom connector now only supports semantic views.

    Args:
        metadata: View/table metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name

    Returns:
        M expression string
    """
    database = escape_m_string(metadata.database)
    schema = escape_m_string(metadata.schema)
    object_name = escape_m_string(metadata.view)

    # v3.0: Use native Snowflake connector for standard tables/views
    # Uses Kind="Database", Kind="Schema", Kind="Table" navigation
    return f'''let
    Source = Snowflake.Databases("{escape_m_string(server)}", "{escape_m_string(warehouse)}"),
    {database}_Database = Source{{[Name="{database}", Kind="Database"]}}[Data],
    {schema}_Schema = {database}_Database{{[Name="{schema}", Kind="Schema"]}}[Data],
    {object_name}_Table = {schema}_Schema{{[Name="{object_name}", Kind="Table"]}}[Data]
in
    {object_name}_Table'''


def generate_partition_tmdl_no_indent(
    view_name: str,
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str,
    mode: str = "directQuery"
) -> str:
    """
    Generate TMDL for the partition (M expression) without extra indentation.

    Args:
        view_name: Name of the object
        metadata: Object metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name
        mode: Storage mode ("directQuery" or "import")

    Returns:
        TMDL string for the partition
    """
    # Use appropriate M expression based on object type
    if metadata.object_type == "SEMANTIC_VIEW":
        m_expression = generate_semantic_view_m_expression(metadata, server, warehouse)
    else:
        m_expression = generate_standard_m_expression(metadata, server, warehouse)

    # Indent each line of the M expression for proper TMDL format
    m_lines = m_expression.split('\n')
    indented_m = '\n\t\t\t\t'.join(m_lines)

    partition_tmdl = f'''\tpartition {view_name} = m
\t\tmode: {mode}
\t\tsource =
\t\t\t\t{indented_m}'''

    return partition_tmdl


def generate_table_tmdl(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str,
    include_create_or_replace: bool = False,
    include_columns: bool = True,
    mode: str = "directQuery"
) -> str:
    """
    Generate TMDL for a semantic view table matching Power BI's format.

    Args:
        metadata: Semantic view metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name
        include_create_or_replace: Whether to include createOrReplace header
        include_columns: Whether to include column definitions (default True).
                        Power BI Desktop includes columns in TMDL files.
        mode: Storage mode ("directQuery" or "import")

    Returns:
        Complete TMDL string for the table
    """
    view_name = metadata.view
    lineage_tag = generate_lineage_tag()

    # Generate partition (without leading tabs - will be added inline)
    partition_tmdl = generate_partition_tmdl_no_indent(view_name, metadata, server, warehouse, mode=mode)

    # Build table TMDL - matching Power BI Desktop format (no leading tabs)
    header = "createOrReplace\n\n" if include_create_or_replace else ""

    if include_columns and metadata.columns:
        # Deduplicate columns to prevent TMDL errors
        seen_columns = set()
        unique_columns = []
        for col in metadata.columns:
            if col.name in seen_columns:
                continue
            seen_columns.add(col.name)
            unique_columns.append(col)

        # Generate columns (before partition in Power BI format)
        columns_tmdl = '\n\n'.join(
            generate_column_tmdl_no_indent(col) for col in unique_columns
        )
        table_tmdl = f'''{header}table {view_name}
\tlineageTag: {lineage_tag}

{columns_tmdl}

{partition_tmdl}

\tannotation PBI_ResultType = Table
'''
    else:
        # Minimal format - Power BI discovers columns at runtime
        table_tmdl = f'''{header}table {view_name}
\tlineageTag: {lineage_tag}

{partition_tmdl}

\tannotation PBI_ResultType = Table
'''

    return table_tmdl


def generate_model_tmdl(
    views_metadata: list[SemanticViewMetadata],
    model_name: str = "SnowflakeSemanticViews"
) -> str:
    """
    Generate the model.tmdl file content matching Power BI Desktop format.

    Uses 'ref table' syntax instead of inline definitions.

    Args:
        views_metadata: List of semantic view metadata
        model_name: Name for the model

    Returns:
        TMDL string for model.tmdl
    """
    culture = "en-US"

    # Build ref table lines
    ref_tables = '\n\n'.join(f'ref table {m.view}' for m in views_metadata)

    model_tmdl = f'''model Model
\tculture: {culture}
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: {culture}
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 1

annotation PBI_QueryOrder = {json.dumps([m.view for m in views_metadata])}

annotation PBI_ProTooling = ["DevMode"]

{ref_tables}

ref cultureInfo {culture}

'''

    return model_tmdl


def generate_culture_tmdl(culture: str = "en-US") -> str:
    """
    Generate culture TMDL file (e.g., en-US.tmdl).

    Args:
        culture: Culture code

    Returns:
        TMDL string for culture file
    """
    return f'''cultureInfo {culture}

'''


def generate_database_tmdl(model_name: str = "SnowflakeSemanticViews") -> str:
    """
    Generate the database.tmdl file content.

    Based on actual Power BI Desktop output - database has no name,
    just uses compatibilityLevel: 1550.

    Args:
        model_name: Name for the database/model (unused - PBI uses anonymous database)

    Returns:
        TMDL string for database.tmdl
    """
    # Power BI Desktop generates database without a name
    database_tmdl = '''database
\tcompatibilityLevel: 1550
'''

    return database_tmdl


def generate_model_bim(
    views_metadata: list[SemanticViewMetadata],
    server: str,
    warehouse: str,
    model_name: str = "SnowflakeSemanticViews",
    mode: str = "directQuery"
) -> str:
    """
    Generate model.bim file (JSON format) for Power BI.

    This is the standard format that works without Developer Mode enabled.
    v3.0: Supports dual connectors - custom for semantic views, native for tables.

    Args:
        views_metadata: List of semantic view metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name
        model_name: Name for the model
        mode: Storage mode ("directQuery" or "import")

    Returns:
        JSON string for model.bim
    """
    tables = []

    for metadata in views_metadata:
        view_name = metadata.view
        database = escape_m_string(metadata.database)
        schema = escape_m_string(metadata.schema)
        object_name = escape_m_string(metadata.view)

        # v3.0: Use appropriate connector based on object type
        use_native = metadata.object_type in ("TABLE", "VIEW")

        if use_native:
            # Native Snowflake connector: Snowflake.Databases()
            m_expression = [
                "let",
                f'    Source = Snowflake.Databases("{escape_m_string(server)}", "{escape_m_string(warehouse)}"),',
                f'    {database}_Database = Source{{[Name="{database}", Kind="Database"]}}[Data],',
                f'    {schema}_Schema = {database}_Database{{[Name="{schema}", Kind="Schema"]}}[Data],',
                f'    {object_name}_Table = {schema}_Schema{{[Name="{object_name}", Kind="Table"]}}[Data]',
                "in",
                f"    {object_name}_Table"
            ]
        else:
            # Custom semantic views connector: SnowflakeSemanticViews.Contents()
            m_expression = [
                "let",
                f'    Source = SnowflakeSemanticViews.Contents("{escape_m_string(server)}", "{escape_m_string(warehouse)}", null, null, null, null, null),',
                f'    {database}_DB = Source{{[name="{database}"]}}[Data],',
                f'    {schema}_Schema = {database}_DB{{[name="{schema}"]}}[Data],',
                f'    {object_name}1 = {schema}_Schema{{[name="{object_name}"]}}[Data]',
                "in",
                f"    {object_name}1"
            ]

        table = {
            "name": view_name,
            "lineageTag": generate_lineage_tag(),
            "partitions": [
                {
                    "name": view_name,
                    "mode": mode,
                    "source": {
                        "type": "m",
                        "expression": m_expression
                    }
                }
            ],
            "annotations": [
                {
                    "name": "PBI_ResultType",
                    "value": "Table"
                }
            ]
        }
        tables.append(table)

    model_bim = {
        "name": model_name,
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "annotations": [
                {
                    "name": "PBI_QueryOrder",
                    "value": json.dumps([m.view for m in views_metadata])
                },
                {
                    "name": "__PBI_TimeIntelligenceEnabled",
                    "value": "0"
                },
                {
                    "name": "PBIDesktopVersion",
                    "value": "2.136.1202.0"
                },
                {
                    "name": "PBI_ProTooling",
                    "value": "[\"DevMode\"]"
                }
            ]
        }
    }

    return json.dumps(model_bim, indent=2)


def generate_definition_pbism() -> str:
    """
    Generate the definition.pbism manifest file.

    Based on actual Power BI Desktop output format (version 4.2 for TMDL).

    Returns:
        JSON string for definition.pbism
    """
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {}
    }
    return json.dumps(manifest, indent=2)


def generate_pbip_file(project_name: str) -> str:
    """
    Generate the .pbip project file content.

    Args:
        project_name: Name of the project

    Returns:
        JSON string for the .pbip file
    """
    pbip = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [
            {
                "report": {
                    "path": f"{project_name}.Report"
                }
            }
        ],
        "settings": {
            "enableAutoRecovery": True
        }
    }
    return json.dumps(pbip, indent=2)


def generate_page_id() -> str:
    """Generate a random page ID (20 hex characters)."""
    return uuid.uuid4().hex[:20]


def generate_report_json() -> str:
    """
    Generate report.json file matching Power BI Desktop format.

    Returns:
        JSON string for report.json
    """
    report = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY25SU11",
                "reportVersionAtImport": {
                    "visual": "2.4.0",
                    "report": "3.0.0",
                    "page": "2.3.0"
                },
                "type": "SharedResources"
            }
        },
        "objects": {
            "section": [
                {
                    "properties": {
                        "verticalAlignment": {
                            "expr": {
                                "Literal": {
                                    "Value": "'Top'"
                                }
                            }
                        }
                    }
                }
            ]
        },
        "resourcePackages": [
            {
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [
                    {
                        "name": "CY25SU11",
                        "path": "BaseThemes/CY25SU11.json",
                        "type": "BaseTheme"
                    }
                ]
            }
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True
        }
    }
    return json.dumps(report, indent=2)


def generate_pages_json(page_id: str) -> str:
    """
    Generate pages.json file with page order.

    Args:
        page_id: The ID of the first page

    Returns:
        JSON string for pages.json
    """
    pages = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [page_id],
        "activePageName": page_id
    }
    return json.dumps(pages, indent=2)


def generate_page_json(page_id: str, display_name: str = "Page 1") -> str:
    """
    Generate page.json file for a single page.

    Args:
        page_id: The page ID
        display_name: Display name for the page

    Returns:
        JSON string for page.json
    """
    page = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280
    }
    return json.dumps(page, indent=2)


def generate_version_json() -> str:
    """
    Generate version.json file.

    Returns:
        JSON string for version.json
    """
    version = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"
    }
    return json.dumps(version, indent=2)


def generate_multi_view_tmdl_project(
    views_metadata: list[SemanticViewMetadata],
    server: str,
    warehouse: str,
    project_name: str = "SnowflakeSemanticViews",
    mode: str = "directQuery"
) -> dict[str, str]:
    """
    Generate a complete TMDL project with multiple semantic views.

    Args:
        views_metadata: List of semantic view metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name
        project_name: Name for the project
        mode: Storage mode ("directQuery" or "import")

    Returns:
        Dictionary mapping file paths to file contents
    """
    files = {}

    # Root level files
    files[f"{project_name}.pbip"] = generate_pbip_file(project_name)

    # Semantic model folder
    model_folder = f"{project_name}.SemanticModel"
    files[f"{model_folder}/definition.pbism"] = generate_definition_pbism()
    files[f"{model_folder}/definition/database.tmdl"] = generate_database_tmdl(project_name)
    files[f"{model_folder}/definition/model.tmdl"] = generate_model_tmdl(views_metadata, project_name)

    # Generate table TMDL for each semantic view
    for metadata in views_metadata:
        table_tmdl = generate_table_tmdl(metadata, server, warehouse, mode=mode)
        files[f"{model_folder}/definition/tables/{metadata.view}.tmdl"] = table_tmdl

    # Generate cultures folder (required by Power BI)
    files[f"{model_folder}/definition/cultures/en-US.tmdl"] = generate_culture_tmdl("en-US")

    # Report folder with proper page structure
    report_folder = f"{project_name}.Report"
    page_id = generate_page_id()

    # Report definition
    files[f"{report_folder}/definition.pbir"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {
            "byPath": {
                "path": f"../{model_folder}"
            }
        }
    }, indent=2)

    # Report definition folder
    files[f"{report_folder}/definition/report.json"] = generate_report_json()
    files[f"{report_folder}/definition/version.json"] = generate_version_json()

    # Pages structure
    files[f"{report_folder}/definition/pages/pages.json"] = generate_pages_json(page_id)
    files[f"{report_folder}/definition/pages/{page_id}/page.json"] = generate_page_json(page_id, "Page 1")

    return files


def generate_single_view_tmdl_project(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str,
    mode: str = "directQuery"
) -> dict[str, str]:
    """
    Generate a TMDL project for a single semantic view.

    Args:
        metadata: Semantic view metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name
        mode: Storage mode ("directQuery" or "import")

    Returns:
        Dictionary mapping file paths to file contents
    """
    return generate_multi_view_tmdl_project(
        [metadata],
        server,
        warehouse,
        project_name=metadata.view,
        mode=mode
    )


def generate_multi_view_bim_project(
    views_metadata: list[SemanticViewMetadata],
    server: str,
    warehouse: str,
    project_name: str = "SnowflakeSemanticViews",
    mode: str = "directQuery"
) -> dict[str, str]:
    """
    Generate a PBIP project with model.bim format (works without Developer Mode).

    This format uses a single model.bim JSON file instead of TMDL files.
    It works with standard Power BI Desktop without any special settings.

    Args:
        views_metadata: List of semantic view metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name
        project_name: Name for the project
        mode: Storage mode ("directQuery" or "import")

    Returns:
        Dictionary mapping file paths to file contents
    """
    files = {}

    # Root level files
    files[f"{project_name}.pbip"] = generate_pbip_file(project_name)

    # Semantic model folder with model.bim (not TMDL)
    model_folder = f"{project_name}.SemanticModel"
    files[f"{model_folder}/definition.pbism"] = generate_definition_pbism()
    files[f"{model_folder}/model.bim"] = generate_model_bim(
        views_metadata, server, warehouse, project_name, mode=mode
    )

    # Report folder with proper page structure
    report_folder = f"{project_name}.Report"
    page_id = generate_page_id()

    # Report definition
    files[f"{report_folder}/definition.pbir"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {
            "byPath": {
                "path": f"../{model_folder}"
            }
        }
    }, indent=2)

    # Report definition folder
    files[f"{report_folder}/definition/report.json"] = generate_report_json()
    files[f"{report_folder}/definition/version.json"] = generate_version_json()

    # Pages structure
    files[f"{report_folder}/definition/pages/pages.json"] = generate_pages_json(page_id)
    files[f"{report_folder}/definition/pages/{page_id}/page.json"] = generate_page_json(page_id, "Page 1")

    return files


def generate_single_view_bim_project(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str
) -> dict[str, str]:
    """
    Generate a PBIP project with model.bim format for a single semantic view.

    Args:
        metadata: Semantic view metadata
        server: Snowflake server URL
        warehouse: Snowflake warehouse name

    Returns:
        Dictionary mapping file paths to file contents
    """
    return generate_multi_view_bim_project(
        [metadata],
        server,
        warehouse,
        project_name=metadata.view
    )
