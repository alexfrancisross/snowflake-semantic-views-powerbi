"""
Single authority for building / normalizing Snowflake server hostnames.

Mirrors the Power BI M connector's `ParseSnowflakeServer` semantics so the
Streamlit app and the connector agree on how a "server" value used in
generated M expressions is derived. This fixes issues #1 and #2 on the
app side: the app used to build `{account}.snowflakecomputing.com` in
several places with no region or PrivateLink handling, which drops the
region for legacy locator accounts and mangles PrivateLink hosts.

Supported forms (all case-preserving - PrivateLink TLS certs are
case-sensitive):
  - Org account name:        {org}-{account}.snowflakecomputing.com
  - Legacy locator + region: {locator}.{region}[.{cloud}].snowflakecomputing.com
  - PrivateLink (any form):  ...privatelink.snowflakecomputing.com
  - Anything already containing ".snowflakecomputing.com": passed through
    unchanged (covers PrivateLink and any pre-qualified host).
"""


def is_full_host(value: str | None) -> bool:
    """Return True if `value` already looks like a fully-qualified Snowflake host."""
    return bool(value) and ".snowflakecomputing.com" in value.lower()


def build_snowflake_host(account_identifier: str | None, region: str | None = None) -> str:
    """
    Build a fully-qualified Snowflake host from an account identifier.

    Args:
        account_identifier: Account locator, org-account name, or an
            already-fully-qualified host (including PrivateLink forms).
            Case is always preserved.
        region: Optional region (e.g. from CURRENT_REGION()). Only used
            when account_identifier is a bare locator that isn't already
            a full host - required so legacy locator accounts don't lose
            their region segment (issue #2).

    Returns:
        A fully-qualified *.snowflakecomputing.com hostname, or the
        original value unchanged if it's empty or already fully qualified.
    """
    if not account_identifier:
        return account_identifier or ""

    if is_full_host(account_identifier):
        # Already a full host (org-account, legacy+region, or PrivateLink) -
        # pass through unchanged so we never mangle a working host.
        return account_identifier

    if region and "." not in account_identifier:
        # Only inject the region for single-segment locators; multi-segment
        # identifiers (e.g. "xy12345.eu-west-2.aws") already carry their
        # region, and injecting it again would build a double-region host.
        return f"{account_identifier}.{region}.snowflakecomputing.com"

    return f"{account_identifier}.snowflakecomputing.com"


def resolve_server_host(
    org_account_name: str | None = None,
    connections_toml_account: str | None = None,
    current_account: str | None = None,
    current_region: str | None = None,
    override: str | None = None,
) -> str:
    """
    Resolve the Snowflake server host to embed in generated M code, in
    priority order:

    1. Explicit user override (e.g. "Server host override" field in the UI)
    2. Org-account name from CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME()
       (already a full, region-free identifier for org-account accounts)
    3. Account value read from connections.toml (may already be a full host,
       incl. PrivateLink - passed through unchanged if so)
    4. CURRENT_ACCOUNT() + CURRENT_REGION() fallback (legacy locator accounts)

    Returns "unknown" if none of the inputs are usable.
    """
    if override:
        return build_snowflake_host(override)

    if org_account_name and org_account_name != "-":
        return build_snowflake_host(org_account_name)

    if connections_toml_account:
        return build_snowflake_host(connections_toml_account, region=current_region)

    if current_account:
        return build_snowflake_host(current_account, region=current_region)

    return "unknown"
