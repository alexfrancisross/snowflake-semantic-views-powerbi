_J='TIMESTAMP_TZ'
_I='TIMESTAMP_NTZ'
_H='TIMESTAMP_LTZ'
_G='TIMESTAMP'
_F='DATETIME'
_E='decimal'
_D='double'
_C='int64'
_B='dateTime'
_A='string'
SNOWFLAKE_TO_PBI_TYPE={'VARCHAR':_A,'CHAR':_A,'CHARACTER':_A,'STRING':_A,'TEXT':_A,'BINARY':_A,'VARBINARY':_A,'INT':_C,'INTEGER':_C,'BIGINT':_C,'SMALLINT':_C,'TINYINT':_C,'BYTEINT':_C,'NUMBER':_E,'DECIMAL':_E,'NUMERIC':_E,'FLOAT':_D,'FLOAT4':_D,'FLOAT8':_D,'DOUBLE':_D,'DOUBLE PRECISION':_D,'REAL':_D,'BOOLEAN':'boolean','DATE':_B,_F:_B,'TIME':_B,_G:_B,_H:_B,_I:_B,_J:_B,'VARIANT':_A,'OBJECT':_A,'ARRAY':_A,'GEOGRAPHY':_A,'GEOMETRY':_A,'VECTOR':_A,'INTERVAL':_A}
DEFAULT_PBI_TYPE=_A
def snowflake_to_pbi_type(snowflake_type):
	A=snowflake_type
	if not A:return DEFAULT_PBI_TYPE
	B=A.upper().split('(')[0].strip();return SNOWFLAKE_TO_PBI_TYPE.get(B,DEFAULT_PBI_TYPE)
def get_pbi_format_string(snowflake_type):
	B=snowflake_type;A=B.upper().split('(')[0].strip()if B else''
	if A=='DATE':return'yyyy-MM-dd'
	elif A in(_F,_G,_H,_I,_J):return'yyyy-MM-dd HH:mm:ss'
	elif A=='TIME':return'HH:mm:ss'