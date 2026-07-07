"""
Type mappings between Snowflake and Power BI data types.
Used by the TMDL generator to create proper column definitions.
"""

# Snowflake type to Power BI TMDL dataType mapping
# Based on native Snowflake connector patterns from:
# connector_code/PowerBIExtensions/PowerBIExtensions.Snowflake/SqlGenerator.pqm
SNOWFLAKE_TO_PBI_TYPE = {
    # String types
    "VARCHAR": "string",
    "CHAR": "string",
    "CHARACTER": "string",
    "STRING": "string",
    "TEXT": "string",
    "BINARY": "string",
    "VARBINARY": "string",

    # Numeric types - aligned with connector's MapSnowflakeType function
    # Integer types -> int64 (TMDL has no int32, all map to int64)
    "INT": "int64",
    "INTEGER": "int64",
    "BIGINT": "int64",
    "SMALLINT": "int64",
    "TINYINT": "int64",
    "BYTEINT": "int64",

    # Decimal types -> decimal (for NUMBER, DECIMAL, NUMERIC with precision)
    "NUMBER": "decimal",
    "DECIMAL": "decimal",
    "NUMERIC": "decimal",

    # Float types -> double
    "FLOAT": "double",
    "FLOAT4": "double",
    "FLOAT8": "double",
    "DOUBLE": "double",
    "DOUBLE PRECISION": "double",
    "REAL": "double",

    # Boolean
    "BOOLEAN": "boolean",

    # Date/Time types
    "DATE": "dateTime",
    "DATETIME": "dateTime",
    "TIME": "dateTime",
    "TIMESTAMP": "dateTime",
    "TIMESTAMP_LTZ": "dateTime",
    "TIMESTAMP_NTZ": "dateTime",
    "TIMESTAMP_TZ": "dateTime",

    # Semi-structured types (stored as string in Power BI)
    "VARIANT": "string",
    "OBJECT": "string",
    "ARRAY": "string",

    # Geospatial types (stored as string - GeoJSON/WKT representation)
    "GEOGRAPHY": "string",
    "GEOMETRY": "string",

    # Vector/AI types (stored as string)
    "VECTOR": "string",

    # Time interval types (stored as string)
    "INTERVAL": "string",
}

# Default type for unknown Snowflake types
DEFAULT_PBI_TYPE = "string"


def snowflake_to_pbi_type(snowflake_type: str) -> str:
    """
    Convert a Snowflake data type to a Power BI TMDL dataType.

    Args:
        snowflake_type: The Snowflake data type (e.g., "VARCHAR", "NUMBER(10,2)")

    Returns:
        The corresponding Power BI TMDL dataType (e.g., "string", "decimal")
    """
    if not snowflake_type:
        return DEFAULT_PBI_TYPE

    # Normalize: uppercase and remove precision/scale info
    # e.g., "NUMBER(10,2)" -> "NUMBER", "VARCHAR(100)" -> "VARCHAR"
    base_type = snowflake_type.upper().split("(")[0].strip()

    return SNOWFLAKE_TO_PBI_TYPE.get(base_type, DEFAULT_PBI_TYPE)


def get_pbi_format_string(snowflake_type: str) -> str | None:
    """
    Get the Power BI format string for a given Snowflake type.
    Returns None if no special formatting is needed.

    Args:
        snowflake_type: The Snowflake data type

    Returns:
        Format string or None
    """
    base_type = snowflake_type.upper().split("(")[0].strip() if snowflake_type else ""

    # Date formatting
    if base_type == "DATE":
        return "yyyy-MM-dd"
    elif base_type in ("DATETIME", "TIMESTAMP", "TIMESTAMP_LTZ", "TIMESTAMP_NTZ", "TIMESTAMP_TZ"):
        return "yyyy-MM-dd HH:mm:ss"
    elif base_type == "TIME":
        return "HH:mm:ss"

    return None
