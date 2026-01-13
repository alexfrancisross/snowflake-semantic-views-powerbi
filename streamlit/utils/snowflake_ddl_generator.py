_Z='RELATIONSHIPS ('
_Y='COUNT_DISTINCT'
_X='SEMANTIC_VIEW'
_W='FACTS ('
_V='TABLES ('
_U='TARGET'
_T='SOURCE'
_S='PARENT'
_R='EMPLOYEE'
_Q='MAX'
_P='MIN'
_O='AVG'
_N='METRICS ('
_M='DIMENSIONS ('
_L='MANAGER'
_K='COUNT'
_J=', '
_I='FACT'
_H='METRIC'
_G='\n'
_F=False
_E='DIMENSION'
_D='SUM'
_C=',\n'
_B=')'
_A=None
from dataclasses import dataclass,field
from typing import Literal
from.logging_config import get_logger
from.metadata_fetcher import RelationshipMetadata,SemanticViewMetadata,detect_multi_path_conflicts
logger=get_logger(__name__)
SNOWFLAKE_AGGREGATIONS=[_D,_O,_K,_P,_Q,_Y,'MEDIAN','STDDEV','VARIANCE']
def format_metric_expression(aggregation,column):
	A=column;B=aggregation.upper()
	if B==_Y:return f"COUNT(DISTINCT {A})"
	else:return f"{B}({A})"
@dataclass
class SemanticColumnConfig:source_column:str;semantic_name:str;kind:Literal[_E,_H,_I];data_type:str;aggregation:str|_A=_A;description:str|_A=_A;table_alias:str|_A=_A;requires_coalesce:bool=_F;coalesce_default:str|_A=_A
@dataclass
class DDLResult:ddl:str;object_name:str;object_type:str;description:str
ALIAS_ROLE_MAPPINGS={'MGR':_L,_L:_L,'EMP':_R,_R:_R,_S:_S,'CHILD':'CHILD','SRC':_T,_T:_T,'TGT':_U,_U:_U,'DIM':'',_I:''}
def detect_duplicate_dimensions(configs):
	A={}
	for(D,B)in enumerate(configs):
		if B.kind==_E:
			C=B.semantic_name.upper()
			if C not in A:A[C]=[]
			A[C].append((D,B))
	return{B:A for(B,A)in A.items()if len(A)>1}
def resolve_duplicate_dimension_names(configs,relationships=_A):
	P='_FACT';O='_DIM';H=relationships;E=configs;I=detect_duplicate_dimensions(E);F=[]
	if not I:return E,F
	G=[]
	for(V,Q)in I.items():
		for(R,(W,C))in enumerate(Q):
			A=(C.table_alias or'').upper();B=_A
			if A in ALIAS_ROLE_MAPPINGS:B=ALIAS_ROLE_MAPPINGS[A]
			else:
				for(S,J)in ALIAS_ROLE_MAPPINGS.items():
					if S in A and J:B=J;break
			if not B and H:
				for K in H:
					L=K.relationship_name.upper()if hasattr(K,'relationship_name')else''
					if f"TO_{A}"in L or f"{A}_TO"in L:B=A.replace(O,'').replace(P,'');break
			if B:
				M=C.source_column.upper()
				for N in['_NAME','_ID','_DATE','_CODE']:
					if M.endswith(N):D=f"{B}{N}";break
				else:D=f"{B}_{M}"
			elif A:T=A.replace(O,'').replace(P,'');D=f"{T}_{C.source_column.upper()}"
			else:D=f"{C.semantic_name.upper()}_{R+1}"
			U=C.semantic_name;C.semantic_name=D;G.append((U,D,A))
	if G:F.append(f"Duplicate dimension names detected and auto-renamed for self-referential table support:\n"+_G.join(f"  - {A} (alias: {C}) -> {B}"for(A,B,C)in G))
	return E,F
def detect_self_referential_joins(tables,relationships,table_aliases):
	I=tables;D=table_aliases;J={};B={}
	for C in I:
		Q=D.get(C.view,f"{C.view}_FACT");E=C.view.upper()
		if E not in B:B[E]=[]
		B[E].append((Q,C))
	for A in relationships:
		F=A.from_table.upper();K=A.to_table.upper()
		if F==K:
			L=next((A for A in I if A.view.upper()==F),_A)
			if not L:continue
			G=[]
			for M in A.from_columns:
				N=next((A for A in L.columns if A.name.upper()==M.upper()),_A)
				if N and N.is_nullable:G.append(M)
			if G:
				O=D.get(A.from_table,f"{A.from_table}_FACT");H=D.get(A.to_table,f"{A.to_table}_DIM")
				if O==H:
					P=B.get(F,[])
					if len(P)>=2:H=P[1][0]
				J[H]={'base_table':K,'from_alias':O,'nullable_fk_columns':G,'to_columns':list(A.to_columns)}
	return J
def get_coalesce_default_for_type(data_type,column_name=_A,custom_defaults=_A):
	F="'(No Value)'";E=data_type;D=custom_defaults;C=column_name
	if D and C:
		A=C.upper()
		if A in D:return D[A]
	B=E.upper().split('(')[0].strip()if E else''
	if B in('VARCHAR','CHAR','CHARACTER','STRING','TEXT'):
		if C:
			A=C.upper()
			if _L in A or'MGR'in A:return"'(No Manager)'"
			elif _S in A:return"'(No Parent)'"
			elif'SUPERVISOR'in A:return"'(No Supervisor)'"
			elif'_NAME'in A:return"'(No Name)'"
		return F
	if B in('NUMBER','DECIMAL','NUMERIC','INT','INTEGER','BIGINT','SMALLINT','TINYINT','FLOAT','DOUBLE','REAL'):return'0'
	if B=='DATE':return"'1900-01-01'::DATE"
	if B in('DATETIME','TIMESTAMP','TIMESTAMP_LTZ','TIMESTAMP_NTZ','TIMESTAMP_TZ'):return"'1900-01-01 00:00:00'::TIMESTAMP"
	if B=='TIME':return"'00:00:00'::TIME"
	if B=='BOOLEAN':return'FALSE'
	return F
def apply_coalesce_for_self_referential(configs,self_ref_info,custom_defaults=_A):
	C=configs;D=[];B=[]
	for A in C:
		E=(A.table_alias or'').upper()
		if E in self_ref_info:
			if A.kind==_E:A.requires_coalesce=True;A.coalesce_default=get_coalesce_default_for_type(A.data_type,A.semantic_name,custom_defaults);B.append(f"  - {E}.{A.semantic_name} -> COALESCE(..., {A.coalesce_default})")
	if B:D.append('Auto-wrapping columns in COALESCE for nullable FK in self-referential join:\n'+_G.join(B))
	return C,D
def detect_role_playing_dimensions(relationships):
	A={}
	for B in relationships:
		C=B.from_table.upper(),B.to_table.upper()
		if C not in A:A[C]=[]
		A[C].append(B)
	return{B:A for(B,A)in A.items()if len(A)>=2}
def detect_circular_relationships(relationships,base_table):
	B={}
	for C in relationships:
		A=C.from_table.upper();D=C.to_table.upper()
		if A==D:continue
		if A not in B:B[A]=[]
		B[A].append(D)
	E=[];F=base_table.upper()
	def G(node,path,visited):
		D=visited;C=path;A=node
		if A in D:
			if A in C:F=C.index(A);H=C[F:]+[A];E.append(H)
			return
		D.add(A);C.append(A)
		for I in B.get(A,[]):G(I,C.copy(),D.copy())
	if F in B:G(F,[],set())
	return E
def generate_semantic_view_ddl(base_table,measures,aggregations,view_name,database,schema,column_configs=_A):
	P=column_configs;O=schema;N=database;F=base_table;Q=f"{N}.{O}.{view_name}";R=f"{N}.{O}.{F.view}";B=F.view[0].lower();S=[A for A in F.columns if A.is_primary_key];G=S[0].name if S else _A;A=[f"CREATE OR REPLACE SEMANTIC VIEW {Q}",_V]
	if G:A.append(f"    {B} AS {R} PRIMARY KEY ({G})")
	else:A.append(f"    {B} AS {R}")
	A.append(_B)
	if P:
		C=[];E=[];I=[]
		for D in P:
			J=D.semantic_name.lower();K=D.source_column;H=''
			if D.description:V=D.description.replace("'","''");H=f"\n        COMMENT = '{V}'"
			if D.kind==_E:C.append(f"    {B}.{J} AS {B}.{K}{H}")
			elif D.kind==_H:W=D.aggregation or _D;X=format_metric_expression(W,K);E.append(f"    {B}.{J} AS {X}{H}")
			elif D.kind==_I:I.append(f"    {B}.{J} AS {B}.{K}{H}")
		if C:A.append(_M);A.append(_C.join(C));A.append(_B)
		if E:A.append(_N);A.append(_C.join(E));A.append(_B)
		if I:A.append(_W);A.append(_C.join(I));A.append(_B)
	else:
		C=[]
		if G:L=G.lower();C.append(f"    {B}.{L} AS {B}.{G}")
		Y=[A for A in F.columns if not A.is_primary_key and A.kind in(_E,'COLUMN')and'KEY'in A.name.upper()][:3]
		for T in Y:L=T.name.lower();C.append(f"    {B}.{L} AS {B}.{T.name}")
		if C:A.append(_M);A.append(_C.join(C));A.append(_B)
		E=[]
		for M in measures:U=aggregations.get(M,[_D]);Z=U[0]if U else _D;a=M.lower();E.append(f"    {B}.{a} AS {Z}({M})")
		if E:A.append(_N);A.append(_C.join(E));A.append(_B)
	A.append(';');b=_G.join(A);return DDLResult(ddl=b,object_name=Q,object_type=_X,description=f"Semantic view for {F.view} with pre-defined metrics")
class GranularityConstraintError(ValueError):0
class MultiPathConflictError(ValueError):
	def __init__(A,message,conflicts):B=message;A.message=B;A.conflicts=conflicts;super().__init__(B)
def _validate_granularity_constraints(from_table_configs,to_table_configs,from_table_name,to_table_name):
	D=to_table_name;C=from_table_name;B=to_table_configs;A=from_table_configs;E=any(A.kind==_E for A in A or[]);F=any(A.kind==_H for A in B or[])
	if E and F:G=[A.semantic_name for A in B if A.kind==_H];H=[A.semantic_name for A in A if A.kind==_E];raise GranularityConstraintError(f"""Granularity constraint violation: Cannot have metrics from '{D}' (dimension table) when there are dimensions from '{C}' (fact table).

Problematic metrics on dimension table: {G}
Dimensions on fact table: {H}

Power BI queries ALL columns together, which triggers this Snowflake error.

Solutions:
1. Remove metrics from '{D}' tab (recommended)
2. OR remove dimensions from '{C}' tab""")
def generate_multi_table_semantic_view_ddl(from_table,to_table,relationship,view_name,database,schema,from_table_configs=_A,to_table_configs=_A):
	L=to_table_configs;K=from_table_configs;J=relationship;D=to_table;C=from_table;_validate_granularity_constraints(from_table_configs=K,to_table_configs=L,from_table_name=C.view,to_table_name=D.view);T=f"{database}.{schema}.{view_name}";U=f"{C.database}.{C.schema}.{C.view}";V=f"{D.database}.{D.schema}.{D.view}";G=f"{C.view}_FACT";H=f"{D.view}_DIM";W=[A for A in C.columns if A.is_primary_key];X=[A for A in D.columns if A.is_primary_key];Y=','.join(A.name for A in W)if W else _A;Z=','.join(A.name for A in X)if X else _A;B=[f"CREATE OR REPLACE SEMANTIC VIEW {T}",_V];I=[]
	if Z:I.append(f"    {H} as {V} primary key ({Z})")
	else:I.append(f"    {H} as {V}")
	if Y:I.append(f"    {G} as {U} primary key ({Y})")
	else:I.append(f"    {G} as {U}")
	B.append(_C.join(I));B.append(_B);b=f"{C.view.lower()}_to_{D.view.lower()}";c=_J.join(J.from_columns);d=_J.join(J.to_columns);B.append(_Z);B.append(f"    {b} as {G}({c}) references {H}({d})");B.append(_B)
	def e(desc):
		if desc:A=desc.replace("'","''");return f" comment='{A}'"
		return''
	E=[]
	if L:
		for A in L:
			if not A.table_alias:A.table_alias=H
			E.append(A)
	if K:
		for A in K:
			if not A.table_alias:A.table_alias=G
			E.append(A)
	E,k=resolve_duplicate_dimension_names(E,[J]);f={C.view:G,D.view:H};g=[C,D];a=detect_self_referential_joins(g,[J],f)
	if a:E,l=apply_coalesce_for_self_referential(E,a)
	M=[];N=[];O=[]
	for A in E:
		F=A.table_alias or'';P=A.semantic_name.lower();Q=A.source_column;R=e(A.description)
		if A.kind==_E:
			S=f"{F.lower()}.{Q.lower()}"
			if A.requires_coalesce and A.coalesce_default:S=f"COALESCE({S}, {A.coalesce_default})"
			M.append(f"    {F}.{P} as {S}{R}")
		elif A.kind==_H:h=A.aggregation or _D;i=format_metric_expression(h,f"{F.lower()}.{Q.lower()}");N.append(f"    {F}.{P} as {i}{R}")
		elif A.kind==_I:O.append(f"    {F}.{P} as {F.lower()}.{Q.lower()}{R}")
	if O:B.append(_W);B.append(_C.join(O));B.append(_B)
	if M:B.append(_M);B.append(_C.join(M));B.append(_B)
	if N:B.append(_N);B.append(_C.join(N));B.append(_B)
	B.append(';');j=_G.join(B);return DDLResult(ddl=j,object_name=T,object_type=_X,description=f"Multi-table semantic view joining {C.view} and {D.view}")
def _validate_n_table_granularity_constraints(tables,table_configs,base_table):
	A=base_table;F=A.view.upper()
	for B in tables:
		G=B.view.upper();C=table_configs.get(B.view,[])
		if G!=F:
			D=[A.semantic_name for A in C if A.kind==_H];E=[A.semantic_name for A in C if A.kind==_I]
			if D:raise GranularityConstraintError(f"""Granularity constraint violation: Cannot have metrics on dimension table '{B.view}'.

Problematic metrics: {D}

Metrics can only be defined on the base table '{A.view}' (fact table).

Solution: Move these metrics to the '{A.view}' tab, or remove them.""")
			if E:raise GranularityConstraintError(f"""Granularity constraint violation: Cannot have facts on dimension table '{B.view}'.

Problematic facts: {E}

Facts can only be defined on the base table '{A.view}' (fact table).

Solution: Move these facts to the '{A.view}' tab, or remove them.""")
def generate_n_table_semantic_view_ddl(tables,relationships,table_configs,base_table,view_name,database,schema):
	T=table_configs;J=base_table;I=relationships;F=tables;_validate_n_table_granularity_constraints(F,T,J);K=detect_multi_path_conflicts(F,I,J.view)
	if K:
		U=[]
		for V in K:c=_G.join(f"      Path {A+1}: {' -> '.join(B)}"for(A,B)in enumerate(V['paths']));U.append(f"  - {V['target_table']} is reachable via multiple paths:\n{c}")
		raise MultiPathConflictError(message=f"""Multi-path relationships detected!

Snowflake semantic views require unambiguous relationship paths.
The following tables have multiple paths from '{J.view}':

"""+_G.join(U)+f"\n\nSolution: Remove one of the conflicting relationships to create an unambiguous path.\nFor example, if both direct (A->B) and indirect (A->C->B) paths exist, remove one.",conflicts=K)
	W=f"{database}.{schema}.{view_name}";d=J.view.upper();G={}
	for C in F:
		if C.view.upper()==d:G[C.view]=f"{C.view}_FACT"
		else:G[C.view]=f"{C.view}_DIM"
	def e(desc):
		if desc:A=desc.replace("'","''");return f" comment='{A}'"
		return''
	A=[f"CREATE OR REPLACE SEMANTIC VIEW {W}",_V];L=[]
	for C in F:
		D=G[C.view];X=f"{C.database}.{C.schema}.{C.view}";Y=[A for A in C.columns if A.is_primary_key];Z=','.join(A.name for A in Y)if Y else _A
		if Z:L.append(f"    {D} as {X} primary key ({Z})")
		else:L.append(f"    {D} as {X}")
	A.append(_C.join(L));A.append(_B)
	if I:
		A.append(_Z);a=[]
		for E in I:f=G.get(E.from_table,f"{E.from_table}_FACT");g=G.get(E.to_table,f"{E.to_table}_DIM");h=f"{E.from_table.lower()}_to_{E.to_table.lower()}";i=_J.join(E.from_columns);j=_J.join(E.to_columns);a.append(f"    {h} as {f}({i}) references {g}({j})")
		A.append(_C.join(a));A.append(_B)
	H=[]
	for C in F:
		D=G[C.view];k=T.get(C.view,[])
		for B in k:
			if not B.table_alias:B.table_alias=D
			H.append(B)
	H,p=resolve_duplicate_dimension_names(H,I);b=detect_self_referential_joins(F,I,G)
	if b:H,q=apply_coalesce_for_self_referential(H,b)
	M=[];N=[];O=[]
	for B in H:
		D=B.table_alias or'';P=B.semantic_name.lower();Q=B.source_column;R=e(B.description)
		if B.kind==_E:
			S=f"{D.lower()}.{Q.lower()}"
			if B.requires_coalesce and B.coalesce_default:S=f"COALESCE({S}, {B.coalesce_default})"
			M.append(f"    {D}.{P} as {S}{R}")
		elif B.kind==_H:l=B.aggregation or _D;m=format_metric_expression(l,f"{D.lower()}.{Q.lower()}");N.append(f"    {D}.{P} as {m}{R}")
		elif B.kind==_I:O.append(f"    {D}.{P} as {D.lower()}.{Q.lower()}{R}")
	if O:A.append(_W);A.append(_C.join(O));A.append(_B)
	if M:A.append(_M);A.append(_C.join(M));A.append(_B)
	if N:A.append(_N);A.append(_C.join(N));A.append(_B)
	A.append(';');n=_G.join(A);o=_J.join(A.view for A in F);return DDLResult(ddl=n,object_name=W,object_type=_X,description=f"Multi-table semantic view joining {o}")
def generate_dax_measure(measure_name,source_table,measure_column,pk_column,aggregation=_D):
	I='SUMX';H=measure_column;F=pk_column;E=measure_name;C=source_table;A=aggregation
	if A.upper()==_D:D=_D;B=I
	elif A.upper()==_O:D='AVERAGE';B='AVERAGEX'
	elif A.upper()==_K:D=_K;B='COUNTX'
	elif A.upper()==_P:D=_P;B='MINX'
	elif A.upper()==_Q:D=_Q;B='MAXX'
	else:D=_D;B=I
	if A.upper()==_D:G=f"{E} (Correct) =\n{B}(\n    VALUES({C}[{F}]),\n    CALCULATE(MAX({C}[{H}]))\n)"
	elif A.upper()==_O:G=f"{E} (Correct) =\n{B}(\n    VALUES({C}[{F}]),\n    CALCULATE(MAX({C}[{H}]))\n)"
	elif A.upper()==_K:G=f"{E} (Correct) =\nCOUNTROWS(\n    VALUES({C}[{F}])\n)"
	else:G=f"{E} (Correct) =\n{B}(\n    VALUES({C}[{F}]),\n    CALCULATE(MAX({C}[{H}]))\n)"
	return G
def execute_ddl(session,ddl):
	U='SQL compilation error';T='090';S='002';R='001';Q='Statement executed successfully';P='VIEW';M='TABLE';L='SEMANTIC VIEW';G=session;import re;F=[]
	for A in ddl.split(';'):
		A=A.strip()
		if not A:continue
		V=[A.strip()for A in A.split(_G)if A.strip()and not A.strip().startswith('--')]
		if V:F.append(A)
	if not F:return _F,'No valid SQL statements found'
	def W(stmt):
		B='CREATE\\s+(?:OR\\s+REPLACE\\s+)?(?:SEMANTIC\\s+VIEW|TABLE|VIEW)\\s+([^\\s(]+)';A=re.search(B,stmt,re.IGNORECASE)
		if A:return A.group(1)
	def X(obj_name,obj_type):
		C=obj_type;A=obj_name
		try:
			if C==L:B=f"DESC SEMANTIC VIEW {A}"
			elif C==M:B=f"DESC TABLE {A}"
			else:B=f"DESC VIEW {A}"
			D=G.sql(B).collect();return len(D)>0
		except Exception as E:logger.debug(f"Object verification failed for {A}: {E}");return _F
	try:
		C=[]
		for A in F:
			H=A.upper()
			if L in H:D=L
			elif M in H:D=M
			elif P in H:D=P
			else:D=_A
			N=W(A);I=_A;J=_A
			try:
				K=G.connection.cursor();K.execute(A);E=K.fetchone();K.close()
				if E:C.append(str(E[0])if E[0]else'OK')
				else:C.append(Q)
				continue
			except AttributeError:pass
			except Exception as Y:
				B=str(Y)
				if any(A in B for A in[R,S,T,U]):return _F,f"Snowflake error: {B}"
			try:
				E=G.sql(A).collect()
				if E:C.append(str(E[0][0])if E[0]else'OK')
				else:C.append(Q)
				continue
			except Exception as O:
				B=str(O)
				if any(A in B for A in[R,S,T,U]):J=B
				else:I=O
			if J:return _F,f"Snowflake error: {J}"
			if I:
				B=str(I);Z='alias'in B.lower()or'1301'in B
				if N and D:
					if X(N,D):C.append(f"{D} created successfully");continue
					else:return _F,f"DDL failed - {D} not created. Please run this SQL manually in Snowflake to see the actual error:\n\n{A}"
				elif Z:C.append('Statement executed (unverified)');continue
				else:return _F,B
		if len(F)==1:return True,C[0]
		else:return True,f"Executed {len(F)} statements successfully"
	except Exception as a:return _F,str(a)
def get_default_semantic_view_name(table_name):return f"{table_name}_METRICS"