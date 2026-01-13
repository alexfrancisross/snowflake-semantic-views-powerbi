_C=True
_B=False
_A=None
import re
from dataclasses import dataclass
from typing import Optional
from.config import CONFIG
@dataclass
class ValidationResult:
	is_valid:bool;error_message:Optional[str]=_A;sanitized_value:Optional[str]=_A
	@staticmethod
	def success(value=_A):return ValidationResult(is_valid=_C,sanitized_value=value)
	@staticmethod
	def failure(message):return ValidationResult(is_valid=_B,error_message=message)
UNQUOTED_IDENTIFIER_PATTERN=re.compile('^[A-Za-z_][A-Za-z0-9_$]*$')
QUOTED_IDENTIFIER_PATTERN=re.compile('^[^"]+$')
SNOWFLAKE_RESERVED_WORDS=frozenset({'SELECT','FROM','WHERE','AND','OR','NOT','NULL','TRUE','FALSE','ORDER','BY','GROUP','HAVING','LIMIT','OFFSET','JOIN','LEFT','RIGHT','INNER','OUTER','FULL','CROSS','ON','AS','IN','IS','BETWEEN','LIKE','CASE','WHEN','THEN','ELSE','END','CREATE','ALTER','DROP','TABLE','VIEW','DATABASE','SCHEMA','INSERT','UPDATE','DELETE','GRANT','REVOKE','ALL','ANY','SOME','EXISTS','UNION','INTERSECT','EXCEPT','DISTINCT','ASC','DESC','NULLS','FIRST','LAST','FETCH','NEXT','ROWS','ONLY','PERCENT','WITH'})
def validate_identifier(value,allow_empty=_B,max_length=_A,allow_reserved=_B):
	B=allow_empty;A=value;C=max_length or CONFIG.MAX_IDENTIFIER_LENGTH
	if A is _A:
		if B:return ValidationResult.success('')
		return ValidationResult.failure('Identifier cannot be None')
	A=A.strip()
	if not A:
		if B:return ValidationResult.success('')
		return ValidationResult.failure('Identifier cannot be empty')
	if len(A)>C:return ValidationResult.failure(f"Identifier cannot exceed {C} characters (got {len(A)})")
	if not UNQUOTED_IDENTIFIER_PATTERN.match(A):
		if A[0].isdigit():return ValidationResult.failure('Identifier cannot start with a digit')
		if' 'in A:return ValidationResult.failure('Identifier cannot contain spaces (use underscores instead)')
		if any(B in A for B in"!@#%^&*()-+=[]{}|;:',.<>?/\\"):return ValidationResult.failure('Identifier contains invalid characters. Use only letters, digits, underscores, and dollar signs.')
		return ValidationResult.failure('Identifier must start with a letter or underscore and contain only letters, digits, underscores, or dollar signs')
	if not allow_reserved and A.upper()in SNOWFLAKE_RESERVED_WORDS:return ValidationResult.failure(f"'{A}' is a reserved word and cannot be used as an identifier")
	return ValidationResult.success(A)
def validate_semantic_view_name(name):
	A=validate_identifier(name,allow_empty=_B,allow_reserved=_B)
	if not A.is_valid:return A
	if name.upper().startswith('SYS_'):return ValidationResult.failure("Semantic view names cannot start with 'SYS_' (reserved prefix)")
	return A
def validate_qualified_name(database,schema,name):
	B=schema;A=database;C=validate_identifier(A,allow_empty=_B)
	if not C.is_valid:return ValidationResult.failure(f"Database name: {C.error_message}")
	D=validate_identifier(B,allow_empty=_B)
	if not D.is_valid:return ValidationResult.failure(f"Schema name: {D.error_message}")
	E=validate_identifier(name,allow_empty=_B)
	if not E.is_valid:return ValidationResult.failure(f"Object name: {E.error_message}")
	F=f"{A}.{B}.{name}";return ValidationResult.success(F)
def validate_limit_value(value):
	try:
		A=int(value)
		if A<0:return ValidationResult.failure('LIMIT cannot be negative')
		if A>1000000000:return ValidationResult.failure('LIMIT exceeds maximum allowed value')
		return ValidationResult.success(str(A))
	except(ValueError,TypeError):return ValidationResult.failure('LIMIT must be a valid integer')
def validate_aggregation(aggregation):
	A=aggregation;from config import SNOWFLAKE_AGGREGATIONS as B
	if not A:return ValidationResult.failure('Aggregation cannot be empty')
	C=A.strip().upper()
	if C not in B:D=', '.join(B);return ValidationResult.failure(f"'{A}' is not a valid aggregation. Supported: {D}")
	return ValidationResult.success(C)
def sanitize_for_display(value,max_length=100):
	B=max_length;A=value
	if A is _A:return''
	A=str(A).strip();A=re.sub('[\\x00-\\x1f\\x7f-\\x9f]','',A)
	if len(A)>B:A=A[:B-3]+'...'
	return A
def escape_sql_string(value):
	A=value
	if A is _A:return''
	return str(A).replace("'","''")
def escape_identifier(value):
	A=value
	if A is _A:return'""'
	B=str(A).replace('"','""');return f'"{B}"'
def build_qualified_name(database,schema,name):return f"{escape_identifier(database)}.{escape_identifier(schema)}.{escape_identifier(name)}"
def validate_and_show_error(value,validator_func,field_name='Value',**B):
	import streamlit as C;A=validator_func(value,**B)
	if not A.is_valid:C.error(f"**{field_name}:** {A.error_message}");return _B,_A
	return _C,A.sanitized_value
def create_identifier_input(label,key,default_value='',help_text=_A,validate_on_change=_C):
	import streamlit as B;A=B.text_input(label,value=default_value,key=key,help=help_text or'Must start with letter/underscore, alphanumeric only')
	if validate_on_change and A:
		C=validate_identifier(A)
		if not C.is_valid:B.caption(f":red[{C.error_message}]");return A,_B
	return A,_C