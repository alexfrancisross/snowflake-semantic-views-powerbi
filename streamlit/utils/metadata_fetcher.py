_Y='NUMBER'
_X='fk_column_name'
_W='fk_name'
_V='critical'
_U='data_analysis'
_T='permission'
_S='VARCHAR'
_R='column_name'
_Q='medium'
_P='low'
_O='pk_fk'
_N='VIEW'
_M='connection'
_L='timeout'
_K='comment'
_J='TABLE'
_I='None'
_H='unknown'
_G='warning'
_F='many'
_E='one'
_D=False
_C='SEMANTIC_VIEW'
_B='name'
_A=None
from typing import Any,Literal
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor,as_completed,TimeoutError as FuturesTimeoutError
import streamlit as st
from.logging_config import get_logger
logger=get_logger(__name__)
CACHE_TTL_SECONDS=1800
DEFAULT_QUERY_TIMEOUT_SECONDS=30
CARDINALITY_QUERY_TIMEOUT_SECONDS=60
PERMISSION_ERROR_PATTERNS=['access denied','insufficient privileges','not authorized','permission denied','does not exist or not authorized']
NO_DATA_ERROR_PATTERNS=['does not exist','object does not exist','cannot be found','no results']
def classify_snowflake_error(error):
	E='error';D=error;A=str(D).lower();B=type(D).__name__
	for C in PERMISSION_ERROR_PATTERNS:
		if C in A:return _T,_G
	for C in NO_DATA_ERROR_PATTERNS:
		if C in A:return'not_found','debug'
	if _L in A or'timed out'in A:return _L,_G
	if any(B in A for B in[_M,'network','refused','reset']):return _M,E
	if'ProgrammingError'in B:return'sql_error',_G
	if'DatabaseError'in B or'OperationalError'in B:return'database_error',E
	return _H,_G
def log_snowflake_error(error,operation,context='',suppress=True):
	D=context;C=error;B,E=classify_snowflake_error(C);F=f" for {D}"if D else'';A=f"{operation}{F}: {C}"
	if B==_T:A=f"[Permission Error] {A}"
	elif B==_L:A=f"[Timeout] {A}"
	elif B==_M:A=f"[Connection Error] {A}"
	if E=='debug':logger.debug(A)
	elif E==_G:logger.warning(A)
	else:logger.error(A,exc_info=True)
	if not suppress:raise
def execute_with_timeout(session,query,timeout_seconds=DEFAULT_QUERY_TIMEOUT_SECONDS,description='query'):
	C=description;B=timeout_seconds;A=query
	def D():return session.sql(A).collect()
	with ThreadPoolExecutor(max_workers=1)as E:
		F=E.submit(D)
		try:return F.result(timeout=B)
		except FuturesTimeoutError:logger.warning(f"Query timeout ({B}s) for {C}: {A[:100]}...");return[]
		except Exception as G:logger.warning(f"Query error for {C}: {G}");return[]
ObjectType=Literal[_C,_N,_J]
def get_session_cache_key(session):
	C=session;A='_snowflake_user_cache_key'
	if A in st.session_state:return st.session_state[A]
	try:
		B=C.sql('SELECT CURRENT_USER() as user, CURRENT_ROLE() as role').collect()
		if B:F=B[0]['USER'];G=B[0]['ROLE'];D=f"{F}_{G}";st.session_state[A]=D;return D
	except Exception as H:log_snowflake_error(H,operation='Getting user info for cache key')
	E=f"session_{id(C)}";st.session_state[A]=E;return E
@dataclass
class ColumnMetadata:name:str;data_type:str;kind:str;description:str|_A=_A;expression:str|_A=_A;is_nullable:bool=True;is_primary_key:bool=_D;source_column:str|_A=_A;is_hidden:bool=_D;data_category:str|_A=_A;format_string:str|_A=_A
@dataclass
class TableMetadata:comment:str|_A=_A;row_count:int|_A=_A
@dataclass
class ConstraintMetadata:constraint_name:str;constraint_type:str;table_name:str;columns:list[str]
@dataclass
class CardinalityInfo:from_cardinality:Literal[_E,_F];to_cardinality:Literal[_E,_F];detected_by:Literal[_O,_U,'user_override'];confidence:float;avg_rows_per_key:float|_A=_A
@dataclass
class FanOutRisk:risk_level:Literal['none',_P,_Q,'high',_V];reason:str;affected_measures:list[str];inflation_factor:float|_A=_A;recommendation:str=''
@dataclass
class RelationshipMetadata:
	name:str|_A;from_table:str;from_columns:str|list[str];to_table:str;to_columns:str|list[str];from_database:str|_A=_A;from_schema:str|_A=_A;to_database:str|_A=_A;to_schema:str|_A=_A;cardinality:CardinalityInfo|_A=_A;fan_out_risk:FanOutRisk|_A=_A
	def __post_init__(A):
		if isinstance(A.from_columns,str):object.__setattr__(A,'from_columns',[A.from_columns])
		if isinstance(A.to_columns,str):object.__setattr__(A,'to_columns',[A.to_columns])
	@property
	def from_column(self):A=self;B=A.from_columns if isinstance(A.from_columns,list)else[A.from_columns];return B[0]if B else''
	@property
	def to_column(self):A=self;B=A.to_columns if isinstance(A.to_columns,list)else[A.to_columns];return B[0]if B else''
	@property
	def is_composite(self):A=self;B=A.from_columns if isinstance(A.from_columns,list)else[A.from_columns];C=A.to_columns if isinstance(A.to_columns,list)else[A.to_columns];return len(B)>1 or len(C)>1
	@property
	def relationship_id(self):A=self;B=A.from_columns if isinstance(A.from_columns,list)else[A.from_columns];C=A.to_columns if isinstance(A.to_columns,list)else[A.to_columns];D='_'.join(B);E='_'.join(C);return f"{A.from_table}_{D}_{A.to_table}_{E}"
@dataclass
class SemanticViewMetadata:
	database:str;schema:str;view:str;columns:list[ColumnMetadata];object_type:ObjectType=_C;table_metadata:TableMetadata|_A=_A;constraints:list[ConstraintMetadata]|_A=_A;relationships:list[RelationshipMetadata]|_A=_A
	@property
	def full_name(self):A=self;return f"{A.database}.{A.schema}.{A.view}"
	@property
	def is_semantic_view(self):return self.object_type==_C
@st.cache_data(ttl=CACHE_TTL_SECONDS,show_spinner=_D)
def _get_databases_cached(_session,user_cache_key):A=_session.sql('SHOW DATABASES').collect();return[A[_B]for A in A]
def get_databases(session):A=session;B=get_session_cache_key(A);return _get_databases_cached(A,B)
@st.cache_data(ttl=CACHE_TTL_SECONDS,show_spinner=_D)
def _get_schemas_cached(_session,database,user_cache_key):A=_session.sql(f'SHOW SCHEMAS IN DATABASE "{database}"').collect();return[A[_B]for A in A if A[_B]!='INFORMATION_SCHEMA']
def get_schemas(session,database):A=session;B=get_session_cache_key(A);return _get_schemas_cached(A,database,B)
@st.cache_data(ttl=CACHE_TTL_SECONDS,show_spinner=_D)
def _get_semantic_views_cached(_session,database,schema,user_cache_key):
	B=schema;A=database
	try:C=_session.sql(f'SHOW SEMANTIC VIEWS IN SCHEMA "{A}"."{B}"').collect();return[A[_B]for A in C]
	except Exception as D:log_snowflake_error(D,operation='Fetching semantic views',context=f"{A}.{B}");return[]
def get_semantic_views(session,database,schema):A=session;B=get_session_cache_key(A);return _get_semantic_views_cached(A,database,schema,B)
@st.cache_data(ttl=CACHE_TTL_SECONDS,show_spinner=_D)
def _get_views_cached(_session,database,schema,user_cache_key):
	B=schema;A=database
	try:C=_session.sql(f'SHOW VIEWS IN SCHEMA "{A}"."{B}"').collect();return[A[_B]for A in C]
	except Exception as D:log_snowflake_error(D,operation='Fetching views',context=f"{A}.{B}");return[]
def get_views(session,database,schema):A=session;B=get_session_cache_key(A);return _get_views_cached(A,database,schema,B)
@st.cache_data(ttl=CACHE_TTL_SECONDS,show_spinner=_D)
def _get_tables_cached(_session,database,schema,user_cache_key):
	B=schema;A=database
	try:C=_session.sql(f'SHOW TABLES IN SCHEMA "{A}"."{B}"').collect();return[A[_B]for A in C]
	except Exception as D:log_snowflake_error(D,operation='Fetching tables',context=f"{A}.{B}");return[]
def get_tables(session,database,schema):A=session;B=get_session_cache_key(A);return _get_tables_cached(A,database,schema,B)
def get_objects_by_type(session,database,schema,object_type):
	D=object_type;C=schema;B=database;A=session
	if D==_C:return get_semantic_views(A,B,C)
	elif D==_N:return get_views(A,B,C)
	elif D==_J:return get_tables(A,B,C)
	else:return[]
@dataclass
class ObjectInfo:name:str;object_type:ObjectType
def get_all_objects(session,database,schema):
	F=schema;E=database;D=session;C=[];B=set()
	for A in get_semantic_views(D,E,F):
		if A not in B:C.append(ObjectInfo(name=A,object_type=_C));B.add(A)
	for A in get_tables(D,E,F):
		if A not in B:C.append(ObjectInfo(name=A,object_type=_J));B.add(A)
	for A in get_views(D,E,F):
		if A not in B:C.append(ObjectInfo(name=A,object_type=_N));B.add(A)
	C.sort(key=lambda x:x.name);return C
def _row_to_dict(row):
	A=row
	if hasattr(A,'as_dict'):return A.as_dict()
	if hasattr(A,'asDict'):return A.asDict()
	if isinstance(A,dict):return A
	try:return dict(A)
	except Exception as B:logger.debug(f"Failed to convert row to dict: {type(A).__name__} - {B}");return{}
def _get_row_value(row_dict,key,default=_A):
	B=key;A=row_dict
	if B in A:return A[B]
	if B.upper()in A:return A[B.upper()]
	if B.lower()in A:return A[B.lower()]
	return default
def _escape_sql_string(value):
	A=value
	if A is _A:return''
	return A.replace("'","''")
def get_table_comment(session,database,schema,table_name):
	E=table_name;D=schema;C=database
	try:
		F=_escape_sql_string(D);G=_escape_sql_string(E);B=session.sql(f"""
            SELECT comment
            FROM \"{C}\".INFORMATION_SCHEMA.TABLES
            WHERE table_schema = '{F}'
              AND table_name = '{G}'
        """).collect()
		if B and len(B)>0:
			H=_row_to_dict(B[0]);A=_get_row_value(H,_K)
			if A and A!=_I and A.strip():return A
	except Exception as I:log_snowflake_error(I,operation='Fetching table comment',context=f"{C}.{D}.{E}")
def get_semantic_view_comment(session,database,schema,view_name):
	E=view_name;D=schema;C=database
	try:
		F=_escape_sql_string(E);B=session.sql(f'SHOW SEMANTIC VIEWS LIKE \'{F}\' IN SCHEMA "{C}"."{D}"').collect()
		if B and len(B)>0:
			G=_row_to_dict(B[0]);A=_get_row_value(G,_K)
			if A and A!=_I and A.strip():return A
	except Exception as H:log_snowflake_error(H,operation='Fetching semantic view comment',context=f"{C}.{D}.{E}")
def get_table_constraints(session,database,schema,table_name):
	D=session;C=schema;B=database;A=table_name;E=[]
	try:
		H=_escape_sql_string(C);I=_escape_sql_string(A);J=D.sql(f"""
            SELECT
                tc.constraint_name,
                tc.constraint_type,
                tc.table_name
            FROM \"{B}\".INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            WHERE tc.table_schema = '{H}'
              AND tc.table_name = '{I}'
            ORDER BY tc.constraint_type, tc.constraint_name
        """).collect()
		for K in J:F=_row_to_dict(K);G=_get_row_value(F,'constraint_name','');L=_get_row_value(F,'constraint_type','');M=get_constraint_columns(D,B,C,A,G);E.append(ConstraintMetadata(constraint_name=G,constraint_type=L,table_name=A,columns=M))
	except Exception as N:log_snowflake_error(N,operation='Fetching constraints',context=f"{B}.{C}.{A}")
	return E
def get_constraint_columns(session,database,schema,table_name,constraint_name):
	J=schema;I=database;H=session;D=table_name;B=constraint_name;E=[]
	try:
		if'PK_'in B or'PRIMARY'in B.upper():
			F=H.sql(f'SHOW PRIMARY KEYS IN TABLE "{I}"."{J}"."{D}"').collect()
			for G in F:
				C=_row_to_dict(G);A=_get_row_value(C,_R,'')
				if A:E.append(A)
		else:
			F=H.sql(f'SHOW IMPORTED KEYS IN TABLE "{I}"."{J}"."{D}"').collect()
			for G in F:
				C=_row_to_dict(G);K=_get_row_value(C,_W,'')
				if K==B:
					A=_get_row_value(C,_X,'')
					if A:E.append(A)
	except Exception as L:log_snowflake_error(L,operation='Fetching constraint columns',context=f"{D}.{B}")
	return E
def get_table_relationships(session,database,schema,table_name):
	G=table_name;D=schema;C=database;J=[]
	try:
		P=session.sql(f'SHOW IMPORTED KEYS IN TABLE "{C}"."{D}"."{G}"').collect();E={}
		for Q in P:
			A=_row_to_dict(Q);B=_get_row_value(A,_W,'')
			if B:
				if B not in E:E[B]=[]
				E[B].append(A)
		for(B,K)in E.items():
			K.sort(key=lambda r:int(_get_row_value(r,'key_sequence','1')));H=[];I=[];F='';L=D;M=C
			for A in K:
				N=_get_row_value(A,_X,'');O=_get_row_value(A,'pk_column_name','')
				if N and O:H.append(N);I.append(O)
				if not F:F=_get_row_value(A,'pk_table_name','');L=_get_row_value(A,'pk_schema_name',D);M=_get_row_value(A,'pk_database_name',C)
			if H and I and F:J.append(RelationshipMetadata(name=B,from_table=G,from_columns=H,to_table=F,to_columns=I,from_database=C,from_schema=D,to_database=M,to_schema=L))
	except Exception as R:log_snowflake_error(R,operation='Fetching relationships',context=f"{C}.{D}.{G}")
	return J
def _get_description_with_fallback(description,expression):
	B=expression;A=description
	if A and A!=_I and A.strip():return A
	if B and B!=_I and B.strip():return f"[Expression: {B}]"
def _resolve_duplicate_column_names(columns):
	E=columns;B={}
	for C in E:F=C.get(_B,'');B[F]=B.get(F,0)+1
	G={};H=[]
	for C in E:
		A=C.get(_B,'');J=A
		if B[A]>1:D=G.get(A,1);G[A]=D+1;I=A if D==1 else f"{A}_{D}"
		else:I=A
		H.append((I,J))
	return H
@st.cache_data(ttl=CACHE_TTL_SECONDS,show_spinner=_D)
def get_semantic_view_metadata(_session,database,schema,view):
	R='description';Q='kind';K='data_type';J='expression';F=view;E=schema;D=database;L=_session;B=f'"{D}"."{E}"."{F}"';A=[];M=get_semantic_view_comment(L,D,E,F);S=TableMetadata(comment=M)if M else _A
	def G(query,kind,default_type):
		C=kind;D=[]
		try:
			F=execute_with_timeout(L,query,timeout_seconds=DEFAULT_QUERY_TIMEOUT_SECONDS,description=f"SHOW SEMANTIC {C}S")
			for G in F:A=_row_to_dict(G);H=_get_row_value(A,_K);E=_get_row_value(A,J);I=_get_row_value(A,_B,'');D.append({_B:I,K:_get_row_value(A,K,default_type),Q:C,R:_get_description_with_fallback(H,E),J:E})
		except Exception as M:log_snowflake_error(M,operation=f"Fetching semantic {C.lower()}s",context=B)
		return D
	with ThreadPoolExecutor(max_workers=3)as H:T=H.submit(G,f"SHOW SEMANTIC DIMENSIONS IN {B}",'DIMENSION',_S);U=H.submit(G,f"SHOW SEMANTIC METRICS IN {B}",'METRIC',_Y);V=H.submit(G,f"SHOW SEMANTIC FACTS IN {B}",'FACT',_S);A.extend(T.result());A.extend(U.result());A.extend(V.result())
	W=_resolve_duplicate_column_names(A);N=[]
	for(X,C)in enumerate(A):Y,Z=W[X];N.append(ColumnMetadata(name=Y,data_type=C[K],kind=C[Q],description=C[R],expression=C[J],source_column=Z))
	O=set();P=[]
	for I in N:
		if I.name not in O:O.add(I.name);P.append(I)
	return SemanticViewMetadata(database=D,schema=E,view=F,columns=P,object_type=_C,table_metadata=S)
@st.cache_data(ttl=CACHE_TTL_SECONDS,show_spinner=_D)
def get_table_or_view_metadata(_session,database,schema,object_name,object_type):
	H='Y';G=object_type;C=object_name;B=schema;A=database;F=_session;N=f'"{A}"."{B}"."{C}"';I=[];J=get_table_comment(F,A,B,C);O=TableMetadata(comment=J)if J else _A
	try:
		P=F.sql(f"DESCRIBE TABLE {N}").collect()
		for Q in P:
			D=_row_to_dict(Q);K=_get_row_value(D,_B,'');R=_get_row_value(D,'type',_S);E=_get_row_value(D,_K,_A);S=_get_row_value(D,'null?',H);T=_get_row_value(D,'primary key','N')
			if K.startswith('$'):continue
			if E and(E==_I or not E.strip()):E=_A
			I.append(ColumnMetadata(name=K,data_type=R,kind='COLUMN',description=E,expression=_A,is_nullable=S==H,is_primary_key=T==H))
	except Exception as U:log_snowflake_error(U,operation=f"Describing {G.lower()}",context=f"{A}.{B}.{C}")
	L=_A;M=_A
	if G==_J:L=get_table_constraints(F,A,B,C);M=get_table_relationships(F,A,B,C)
	return SemanticViewMetadata(database=A,schema=B,view=C,columns=I,object_type=G,table_metadata=O,constraints=L,relationships=M)
def get_view_metadata(session,database,schema,view,object_type=_C):
	D=object_type;C=schema;B=database;A=session
	if D==_C:return get_semantic_view_metadata(A,B,C,view)
	else:return get_table_or_view_metadata(A,B,C,view,D)
def get_multiple_views_metadata(session,database,schema,views,object_type=_C):return[get_view_metadata(session,database,schema,A,object_type)for A in views]
def get_metadata_batch_parallel(session,objects,max_workers=8):
	E=session;A=objects
	if not A:return[]
	if len(A)<=2:return[get_view_metadata(E,A,B,C,D)for(A,B,C,D)in A]
	C={};D={}
	def J(index,db,schema,name,obj_type):
		A=index
		try:return A,get_view_metadata(E,db,schema,name,obj_type),_A
		except Exception as B:return A,_A,str(B)
	with ThreadPoolExecutor(max_workers=min(max_workers,len(A)))as K:
		L={K.submit(J,A,B,C,D,E):A for(A,(B,C,D,E))in enumerate(A)}
		for M in as_completed(L):
			F,G,H=M.result()
			if G:C[F]=G
			elif H:D[F]=H
	I=[]
	for B in range(len(A)):
		if B in C:I.append(C[B])
		elif B in D:N,O,P,Q=A[B];st.warning(f"Failed to load metadata for {N}.{O}.{P}: {D[B]}")
	return I
def get_connection_info(session):A=session;B=A.sql('SELECT CURRENT_ACCOUNT()').collect();C=A.sql('SELECT CURRENT_WAREHOUSE()').collect();D=B[0][0]if B else _H;E=C[0][0]if C else'XSMALL';F=f"{D}.snowflakecomputing.com";return{'server':F,'warehouse':E,'account':D}
def detect_cardinality_from_constraints(session,database,schema,from_table,from_column,to_table,to_column):
	E=to_table;D=from_table;C=schema;B=database;A=session
	try:
		H=A.sql(f'SHOW PRIMARY KEYS IN TABLE "{B}"."{C}"."{E}"').collect();I=any(_get_row_value(_row_to_dict(A),_R,'').upper()==to_column.upper()for A in H);J=A.sql(f'SHOW PRIMARY KEYS IN TABLE "{B}"."{C}"."{D}"').collect();F=[_get_row_value(_row_to_dict(A),_R,'').upper()for A in J];G=len(F)==1 and from_column.upper()in F
		if I:K=_E if G else _F;return CardinalityInfo(from_cardinality=K,to_cardinality=_E,detected_by=_O,confidence=.95 if G else .9)
		return
	except Exception as L:log_snowflake_error(L,operation='Detecting cardinality from constraints',context=f"{D}->{E}");return
def analyze_cardinality_from_data(session,database,schema,from_table,from_column,to_table,to_column,sample_size=100000):
	I=schema;H=database;G=sample_size;F=to_table;E=from_column;D=from_table;A=to_column
	try:
		K=f'''
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT f."{E}") as distinct_from,
                COUNT(DISTINCT t."{A}") as distinct_to,
                COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT t."{A}"), 0) as avg_rows_per_to
            FROM (SELECT "{E}" FROM "{H}"."{I}"."{D}" LIMIT {G}) f
            JOIN (SELECT "{A}" FROM "{H}"."{I}"."{F}" LIMIT {G}) t
                ON f."{E}" = t."{A}"
        ''';J=execute_with_timeout(session,K,timeout_seconds=CARDINALITY_QUERY_TIMEOUT_SECONDS,description=f"cardinality analysis {D}->{F}")
		if not J:return
		B=_row_to_dict(J[0]);C=_get_row_value(B,'total_rows',0)or 0;L=_get_row_value(B,'distinct_from',0)or 0;M=_get_row_value(B,'distinct_to',0)or 0;N=_get_row_value(B,'avg_rows_per_to',1.)or 1.
		if C==0:return
		O=C/max(L,1);P=C/max(M,1);Q=_E if O<1.2 else _F;R=_E if P<1.2 else _F;S=min(.8,.5+C/G*.3);return CardinalityInfo(from_cardinality=Q,to_cardinality=R,detected_by=_U,confidence=S,avg_rows_per_key=float(N))
	except Exception as T:log_snowflake_error(T,operation='Analyzing cardinality from data',context=f"{D}->{F}");return
def _calculate_avg_rows_per_key(session,database,schema,from_table,from_column,to_table,to_column,sample_size=100000):
	G=sample_size;F=from_column;E=schema;D=database;C=to_column;B=to_table;A=from_table
	try:
		J=f'''
            SELECT
                COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT t."{C}"), 0) as avg_rows_per_key
            FROM (SELECT "{F}" FROM "{D}"."{E}"."{A}" LIMIT {G}) f
            JOIN (SELECT "{C}" FROM "{D}"."{E}"."{B}" LIMIT {G}) t
                ON f."{F}" = t."{C}"
        ''';H=execute_with_timeout(session,J,timeout_seconds=CARDINALITY_QUERY_TIMEOUT_SECONDS,description=f"avg_rows_per_key {A}->{B}")
		if H:
			K=_row_to_dict(H[0]);I=_get_row_value(K,'avg_rows_per_key',_A)
			if I is not _A:return float(I)
		return
	except Exception as L:log_snowflake_error(L,operation='Calculating avg_rows_per_key',context=f"{A}->{B}");return
def detect_cardinality(session,database,schema,from_table,from_column,to_table,to_column):
	H=to_column;G=to_table;F=from_column;E=from_table;D=schema;C=database;B=session;A=detect_cardinality_from_constraints(B,C,D,E,F,G,H)
	if A:I=_calculate_avg_rows_per_key(B,C,D,E,F,G,H);return CardinalityInfo(from_cardinality=A.from_cardinality,to_cardinality=A.to_cardinality,detected_by=A.detected_by,confidence=A.confidence,avg_rows_per_key=I)
	A=analyze_cardinality_from_data(B,C,D,E,F,G,H)
	if A:return A
	return CardinalityInfo(from_cardinality=_F,to_cardinality=_E,detected_by=_O,confidence=.5)
def assess_fan_out_risk(relationship,from_table_metadata,to_table_metadata):
	H='KEY';D=to_table_metadata;E=relationship.cardinality
	if not E:return FanOutRisk(risk_level=_Q,reason='Cardinality unknown - potential fan-out risk',affected_measures=[],recommendation='Configure cardinality to assess fan-out risk')
	if E.from_cardinality!=_F or E.to_cardinality!=_E:return FanOutRisk(risk_level='none',reason='No fan-out risk for this cardinality',affected_measures=[],recommendation='')
	I={_Y,'DECIMAL','NUMERIC','INT','INTEGER','BIGINT','SMALLINT','FLOAT','DOUBLE','REAL'};A=[]
	for F in D.columns:
		J=F.data_type.upper().split('(')[0]
		if J in I:
			B=F.name.upper();K=F.is_primary_key or B.endswith('_ID')or B.endswith('ID')or B.endswith('_KEY')or B.endswith(H)or H in B
			if not K:A.append(F.name)
	if not A:return FanOutRisk(risk_level=_P,reason="Many-to-one relationship but no obvious measures on 'one' side",affected_measures=[],recommendation='No action needed unless aggregating numeric columns from '+f"{D.view}")
	C=E.avg_rows_per_key or 1.
	if C>3.:G=_V
	elif C>2.:G='high'
	elif C>1.5:G=_Q
	else:G=_P
	return FanOutRisk(risk_level=G,reason=f"Aggregating {', '.join(A[:3])}{'...'if len(A)>3 else''} from {D.view} grouped by {from_table_metadata.view} attributes may inflate values by ~{C:.1f}x",affected_measures=A,inflation_factor=C,recommendation=f"Use Snowflake Semantic View to define metrics at {D.view} level")
def enrich_relationship_with_cardinality(session,relationship,from_table_metadata,to_table_metadata):B=from_table_metadata;A=relationship;C=A.from_database or B.database;D=A.from_schema or B.schema;E=detect_cardinality(session,C,D,A.from_table,A.from_column,A.to_table,A.to_column);A.cardinality=E;F=assess_fan_out_risk(A,B,to_table_metadata);A.fan_out_risk=F;return A
def get_primary_key_columns(metadata):return[A.name for A in metadata.columns if A.is_primary_key]
def has_composite_primary_key(metadata):A=get_primary_key_columns(metadata);return len(A)>1
SchemaType=Literal['star','chain',_H]
def detect_all_relationships(session,tables):
	E=session;C=tables;D=[];G={A.view.upper()for A in C}
	for A in C:
		H=get_table_relationships(E,A.database,A.schema,A.view)
		for B in H:
			if B.to_table.upper()in G:
				F=next((A for A in C if A.view.upper()==B.to_table.upper()),_A)
				if F:I=enrich_relationship_with_cardinality(E,B,A,F);D.append(I)
				else:D.append(B)
	return D
def detect_schema_type(tables,relationships):
	D=relationships;C=tables
	if not D or len(C)<2:return _H
	A={};B={}
	for E in C:A[E.view.upper()]=0;B[E.view.upper()]=0
	for F in D:
		G=F.from_table.upper();H=F.to_table.upper()
		if G in A:A[G]+=1
		if H in B:B[H]+=1
	I=max(A.values())if A else 0;J=max(B.values())if B else 0;K=all(A<=1 for A in A.values())and all(A<=1 for A in B.values())
	if I>=2 or J>=2:return'star'
	elif K and len(D)==len(C)-1:return'chain'
	else:return _H
def identify_base_table(tables,relationships):
	A=tables
	if not A:return
	if len(A)==1:return A[0]
	D={A.view.upper():0 for A in A}
	for H in relationships:
		G=H.from_table.upper()
		if G in D:D[G]+=1
	C={}
	for E in A:
		F=E.view.upper();B=.0;B+=D.get(F,0)*10
		if has_composite_primary_key(E):B+=5
		B+=len(E.columns)*.1
		if any(A in F for A in['FACT','LINEITEM','SALES','ORDER_ITEMS','TRANSACTIONS']):B+=3
		C[F]=B
	if not C:return A[0]
	I=max(C,key=lambda k:C[k]);return next((A for A in A if A.view.upper()==I),A[0])
def get_tables_by_granularity(base_table,tables,relationships):
	A={};C=base_table.view.upper()
	for D in tables:
		B=D.view.upper()
		if B==C:A[B]='base'
		else:A[B]='dimension'
	return A
def can_have_metrics(table,base_table,tables,relationships):return table.view.upper()==base_table.view.upper()
def can_have_facts(table,base_table,tables,relationships):return table.view.upper()==base_table.view.upper()
def detect_indirect_connections(base_table,tables,relationships):
	H=tables;G=base_table;from collections import defaultdict as N,deque;E=N(set)
	for B in relationships:E[B.from_table].add(B.to_table);E[B.to_table].add(B.from_table)
	O={A.view for A in H};I={}
	for A in H:
		if A.view.upper()==G.upper():continue
		J={A.view};F=deque([(A.view,[A.view])]);C=_A
		while F:
			K,L=F.popleft()
			if K.upper()==G.upper():C=L;break
			for D in E.get(K,set()):
				if D not in J:J.add(D);F.append((D,L+[D]))
		if C and len(C)>2:
			M=[A for A in C[1:-1]if A in O]
			if M:I[A.view]=M
	return I
def detect_multi_path_conflicts(tables,relationships,base_table):
	H=relationships;G=tables;from collections import defaultdict as Q;D=Q(set)
	for A in H:I=A.from_table.upper();J=A.to_table.upper();D[I].add(J);D[J].add(I)
	K=base_table.upper();L=[]
	def R(start,end,max_depth=10):
		A=start
		def C(current,path,depth):
			F=depth;E=current;A=path
			if F>max_depth:return[]
			if E==end:return[A]
			G=[]
			for B in D.get(E,set()):
				if B not in A:G.extend(C(B,A+[B],F+1))
			return G
		return C(A,[A],0)
	S={A.view.upper()for A in G}
	for M in G:
		N=M.view.upper()
		if N==K:continue
		T=R(K,N);E=[A for A in T if all(A in S for A in A)]
		if len(E)>1:
			F=[]
			for A in H:
				O=A.from_table.upper();P=A.to_table.upper()
				for B in E:
					for C in range(len(B)-1):
						if B[C]==O and B[C+1]==P or B[C]==P and B[C+1]==O:
							if A not in F:F.append(A)
			L.append({'target_table':M.view,'paths':E,'conflicting_relationships':F})
	return L