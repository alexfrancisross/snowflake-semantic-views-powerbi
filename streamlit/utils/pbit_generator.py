_AA='SnowflakeNativeSource'
_A9='["DevMode"]'
_A8='PBI_ProTooling'
_A7='PBI_QueryOrder'
_A6='PBIDesktopVersion'
_A5='__PBI_TimeIntelligenceEnabled'
_A4='powerBI_V3'
_A3='returnErrorValuesAsNull'
_A2='legacyRedirects'
_A1='tables'
_A0='sourceQueryCulture'
_z='defaultPowerBIDataSourceVersion'
_y='dataAccessOptions'
_x='culture'
_w='model'
_v='lastSchemaUpdate'
_u='lastUpdate'
_t='createdTimestamp'
_s='compatibilityLevel'
_r='milliseconds'
_q='SemanticModel'
_p='source'
_o='mode'
_n='partitions'
_m='columns'
_l='formatString'
_k='dataCategory'
_j='isHidden'
_i='{"isGeneralNumber":true}'
_h='PBI_FormatHint'
_g='User'
_f='SummarizationSetBy'
_e='none'
_d='sum'
_c='isKey'
_b='sourceProviderType'
_a='sourceColumn'
_Z='dataType'
_Y='METRIC'
_X='ordinal'
_W='directQuery'
_V='int64'
_U='version'
_T='2.149.178.0'
_S='Table'
_R='PBI_ResultType'
_Q='expression'
_P='in'
_O='let'
_N='Version'
_M='en-US'
_L='summarizeBy'
_K='description'
_J='lineageTag'
_I='type'
_H='double'
_G='decimal'
_F=False
_E='annotations'
_D='value'
_C=None
_B=True
_A='name'
import io,json,logging,uuid,zipfile
from datetime import datetime
from typing import Any
logger=logging.getLogger(__name__)
from.metadata_fetcher import SemanticViewMetadata,ColumnMetadata,RelationshipMetadata,TableMetadata,CardinalityInfo,has_composite_primary_key
from.type_mappings import snowflake_to_pbi_type
PBIT_VERSION='1.28'
def generate_lineage_tag():return str(uuid.uuid4())
def generate_page_id():return uuid.uuid4().hex[:20]
def escape_m_string(value):return value.replace('"','""')
def escape_m_identifier(name):
	A=name;import re
	if not A or re.search('[^a-zA-Z0-9_]',A)or A[0].isdigit():B=A.replace('"','""');return f'#"{B}"'
	return A
def generate_version():return PBIT_VERSION
def generate_content_types_xml():return'<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="json" ContentType=""/><Override PartName="/Version" ContentType=""/><Override PartName="/DataModelSchema" ContentType=""/><Override PartName="/DiagramLayout" ContentType=""/><Override PartName="/Report/Layout" ContentType=""/><Override PartName="/Settings" ContentType="application/json"/><Override PartName="/Metadata" ContentType="application/json"/><Override PartName="/SecurityBindings" ContentType=""/></Types>'
def generate_settings():A={_N:4,'ReportSettings':{},'QueriesSettings':{'TypeDetectionEnabled':_B,'RelationshipImportEnabled':_B,_N:_T}};return json.dumps(A)
def generate_metadata(description=''):
	A=description;B={_N:5,'AutoCreatedRelationships':[],'CreatedFrom':'Cloud','CreatedFromRelease':'2025.01'}
	if A:B['FileDescription']=A
	return json.dumps(B)
def generate_connections():A={_N:3,'RemoteArtifacts':[]};return json.dumps(A)
def _remove_overlaps(positions,node_width,node_height,padding=2e1):
	K=padding;G=positions
	if len(G)<2:return G
	A=dict(G);F=list(A.keys());H=_B;L=100
	while H and L>0:
		H=_F;L-=1
		for M in range(len(F)):
			P=F[M];N,O=A[P]
			for Q in range(M+1,len(F)):
				D=F[Q];B,C=A[D];I=node_width+K-abs(N-B);J=node_height+K-abs(O-C)
				if I>0 and J>0:
					if I<J:
						E=I+1
						if B>=N:A[D]=B+E,C
						else:A[D]=B-E,C
					else:
						E=J+1
						if C>=O:A[D]=B,C+E
						else:A[D]=B,C-E
					H=_B
	return A
def generate_diagram_layout(table_names,relationships=_C,role_playing_dims=_C):
	q='zoomValue';p='nodes';o='scrollPosition';n='1.1.0';m='defaultDiagram';l='selectedDiagram';k='diagrams';d=role_playing_dims;c=relationships;b='y';a='x';H='All tables';B=table_names
	if not B:return json.dumps({_U:n,k:[{_X:0,o:{a:0,b:0},p:[],_A:H,q:100}],l:H,m:H})
	S=234;T=200;e=50;r=30;I=S+e;J=T+r;from collections import defaultdict as U;N=U(set)
	if c:
		for G in c:
			if G.from_table in B and G.to_table in B:N[G.from_table].add(G.to_table);N[G.to_table].add(G.from_table)
	O={}
	if d:
		for(s,t)in d.items():
			for f in t:
				C=f"{f}_{s}"
				if C in B:O[C]=f
	u={A:len(N.get(A,set()))for A in B};V=[A for A in B if A not in O]
	if V:P=max(V,key=lambda t:u.get(t,0))
	else:P=B[0]
	A={};Q=set();D=U(list);from collections import deque;W=deque([(P,0)]);Q.add(P);D[0].append(P)
	while W:
		v,F=W.popleft()
		for K in N.get(v,set()):
			if K not in Q and K not in O:Q.add(K);D[F+1].append(K);W.append((K,F+1))
	for L in V:
		if L not in Q:X=max(D.keys())if D else 0;D[X+1].append(L)
	X=max(D.keys())if D else 0;Y=(X+1)*I
	for(F,g)in D.items():
		if F==0:M=Y
		elif F%2==1:M=Y+(F+1)//2*I
		else:M=Y-F//2*I
		w=len(g)*J;x=-w//2+J//2
		for(E,y)in enumerate(g):Z=x+E*J;A[y]=float(M),float(Z)
	h=U(list)
	for(C,R)in O.items():h[R].append(C)
	for(R,i)in h.items():
		if R in A:
			z,A0=A[R]
			for(E,C)in enumerate(i):A1=A0+(E+1)*J;A[C]=z,A1
		else:
			A2=max(A[0]for A in A.values())if A else 0
			for(E,C)in enumerate(i):A[C]=A2+I,float(E*J)
	A=_remove_overlaps(A,S,T,padding=e)
	if A:A3=min(A[0]for A in A.values());A4=min(A[1]for A in A.values());A={A:(B-A3+50,C-A4+50)for(A,(B,C))in A.items()}
	j=[]
	for(E,L)in enumerate(B):M,Z=A.get(L,(E*I+50,50));j.append({'location':{a:float(M),b:float(Z)},'nodeIndex':L,'size':{'height':T,'width':S},'zIndex':E})
	A5={_U:n,k:[{_X:0,o:{a:0,b:0},p:j,_A:H,q:100,'pinKeyFieldsToTop':_F,'showExtraHeaderInfo':_F,'hideKeyFieldsWhenCollapsed':_F}],l:H,m:H};return json.dumps(A5)
def generate_report_layout(page_name='Page 1'):B='config';A='CY25SU11';C=generate_page_id();D={_U:'5.68','themeCollection':{'baseTheme':{_A:A,_U:{'visual':'2.4.0','report':'3.0.0','page':'2.3.0'},_I:2}},'activeSectionIndex':0,'defaultDrillFilterOtherVisuals':_B,'settings':{'useNewFilterPaneExperience':_B,'allowChangeFilterTypes':_B,'useStylableVisualContainerHeader':_B,'queryLimitOption':6,'exportDataMode':1,'useDefaultAggregateDisplayName':_B,'useEnhancedTooltips':_B},'objects':{'section':[{'properties':{'verticalAlignment':{'expr':{'Literal':{'Value':"'Top'"}}}}}]}};E={'id':0,'resourcePackages':[{'resourcePackage':{_A:'SharedResources',_I:2,'items':[{_I:202,'path':'BaseThemes/CY25SU11.json',_A:A}],'disabled':_F}}],'sections':[{'id':0,_A:C,'displayName':page_name,'filters':'[]',_X:0,'visualContainers':[],B:'{}','displayOption':1,'width':1280,'height':720}],B:json.dumps(D),'layoutOptimization':0};return json.dumps(E)
def load_theme_file():
	B='CY25SU11.json';import os as A;D=[A.path.join(A.path.dirname(__file__),B),B,A.path.join(A.path.dirname(A.path.abspath(__file__)),B)]
	for C in D:
		if A.path.exists(C):
			with open(C,'rb')as E:return E.read()
	return b'{"name":"CY25SU11","dataColors":["#118DFF","#12239E"]}'
def is_self_referential(rel):return rel.from_table==rel.to_table
def collect_all_relationships(views_metadata,session=_C):
	D=session;B=views_metadata;from.metadata_fetcher import enrich_relationship_with_cardinality as J;E={A.view for A in B};K={A.view:A for A in B};F=[];G=set()
	for C in B:
		if C.relationships:
			for A in C.relationships:
				if A.from_table in E and A.to_table in E:
					H=A.relationship_id
					if H not in G:
						if D and not A.cardinality:
							I=K.get(A.to_table)
							if I:
								try:A=J(D,A,C,I)
								except Exception as L:logger.warning(f"Cardinality enrichment failed for {A.from_table}->{A.to_table}: {L}")
						F.append(A);G.add(H)
	return F
def detect_ambiguous_paths(relationships,user_active_choices=_C):
	K=user_active_choices;C=relationships
	if not C:return[],[]
	from collections import defaultdict as L;M=L(list);I=set()
	for A in C:M[A.from_table].append((A.to_table,A));I.add(A.from_table);I.add(A.to_table)
	W=10;X=100
	def N(start,end,visited=_C,depth=0):
		D=depth;B=start;A=visited
		if A is _C:A=set()
		if D>W:return[]
		if B==end:return[[]]
		if B in A:return[]
		A=A|{B};C=[]
		for(E,F)in M[B]:
			for G in N(E,end,A,D+1):
				C.append([F]+G)
				if len(C)>=X:return C
		return C
	O=L(int)
	for A in C:O[A.to_table]+=1
	P={A for(A,B)in O.items()if B>1};B=set()
	for E in P:
		Q={}
		for F in I:
			if F!=E:
				D=N(F,E)
				if D:Q[F]=D
		for(F,D)in Q.items():
			if len(D)>1:
				R=sorted(D,key=len);Y={A.relationship_id for A in R[0]}
				for Z in R[1:]:
					for A in Z:
						if A.relationship_id not in Y:B.add(A.relationship_id)
	S=0
	for E in P:
		J=[A for A in C if A.to_table==E]
		if len(J)>1:
			T=J[0]
			for G in J[1:]:
				a=f"conflict_{S}";H=_C
				if K:H=K.get(a)
				if H:
					if H==T.relationship_id:B.add(G.relationship_id)
					elif H==G.relationship_id:B.add(T.relationship_id)
					else:B.add(G.relationship_id)
				else:B.add(G.relationship_id)
				S+=1
	U=[];V=[]
	for A in C:
		if A.relationship_id in B:V.append(A)
		else:U.append(A)
	return U,V
def detect_conflict_pairs(relationships):
	C=relationships
	if not C:return[]
	from collections import defaultdict as E;J=E(list);F=set()
	for A in C:J[A.from_table].append((A.to_table,A));F.add(A.from_table);F.add(A.to_table)
	W=10;X=100
	def K(start,end,visited=_C,depth=0):
		D=depth;B=start;A=visited
		if A is _C:A=set()
		if D>W:return[]
		if B==end:return[[]]
		if B in A:return[]
		A=A|{B};C=[]
		for(E,F)in J[B]:
			for G in K(E,end,A,D+1):
				C.append([F]+G)
				if len(C)>=X:return C
		return C
	L=E(int)
	for A in C:L[A.to_table]+=1
	Y={A for(A,B)in L.items()if B>1};G=[];D=set()
	for H in Y:
		for M in F:
			if M!=H:
				N=K(M,H)
				if len(N)>1:
					O=sorted(N,key=len);P=O[0]
					if P:
						Q=P[0]
						for R in O[1:]:
							if R:
								S=R[0];B=tuple(sorted([Q.relationship_id,S.relationship_id]))
								if B not in D:D.add(B);G.append((Q,S,H))
	T=E(list)
	for A in C:T[A.to_table].append(A)
	for(Z,I)in T.items():
		if len(I)>=2:
			U=I[0]
			for V in I[1:]:
				B=tuple(sorted([U.relationship_id,V.relationship_id]))
				if B not in D:D.add(B);G.append((U,V,Z))
	return G
def detect_role_playing_dimensions(relationships):
	from collections import defaultdict as C;A=C(list)
	for B in relationships:A[B.to_table].append(B.from_table)
	return{B:A for(B,A)in A.items()if len(A)>1}
def create_role_playing_table(original_metadata,role_prefix,original_table_name):
	B=role_prefix;A=original_metadata;E=f"{B}_{A.view}";C=_C
	if A.table_metadata:D=A.table_metadata.comment or'';C=TableMetadata(comment=f"{B}'s {A.view}"+(f" - {D}"if D else''),row_count=A.table_metadata.row_count)
	F=SemanticViewMetadata(database=A.database,schema=A.schema,view=E,columns=A.columns,object_type=A.object_type,table_metadata=C,constraints=A.constraints,relationships=[]);return F,original_table_name
def generate_pbi_relationships(relationships,inactive_relationships=_C):
	H='isActive';G='crossFilteringBehavior';D=inactive_relationships;C='many';E=set()
	if D:E={A.relationship_id for A in D}
	F=[]
	for A in relationships:
		if A.from_table==A.to_table:continue
		I=A.name or f"{A.from_table}_{A.from_column}_{A.to_table}";B={_A:I,'fromTable':A.from_table,'fromColumn':A.from_column,'toTable':A.to_table,'toColumn':A.to_column,G:'oneDirection'}
		if A.cardinality and A.cardinality.to_cardinality==C:B['fromCardinality']=C;B['toCardinality']=C;B[G]='bothDirections'
		if A.relationship_id in E:B[H]=_F
		else:B[H]=_B
		F.append(B)
	return F
def _generate_m_expression(metadata,server,warehouse):A=metadata;B=escape_m_string(A.database);C=escape_m_string(A.schema);D=escape_m_string(A.view);E=escape_m_identifier(f"{B}_DB");F=escape_m_identifier(f"{C}_Schema");G=escape_m_identifier(f"{D}1");return[_O,f'    Source = SnowflakeSemanticViews.Contents("{escape_m_string(server)}", "{escape_m_string(warehouse)}", null, null, null, null, null),',f'    {E} = Source{{[name="{B}"]}}[Data],',f'    {F} = {E}{{[name="{C}"]}}[Data],',f'    {G} = {F}{{[name="{D}"]}}[Data]',_P,f"    {G}"]
def _generate_native_m_expression(metadata,server,warehouse,source_name=_AA):A=metadata;B=escape_m_string(A.database);C=escape_m_string(A.schema);D=escape_m_string(A.view);E=escape_m_identifier(f"{B}_Database");F=escape_m_identifier(f"{C}_Schema");G=escape_m_identifier(f"{D}_Table");return[_O,f'    Source = #"{source_name}",',f'    {E} = Source{{[Name="{B}", Kind="Database"]}}[Data],',f'    {F} = {E}{{[Name="{C}", Kind="Schema"]}}[Data],',f'    {G} = {F}{{[Name="{D}", Kind="Table"]}}[Data]',_P,f"    {G}"]
def generate_dual_source_expressions(server,warehouse,has_semantic_views,has_standard_tables):
	F='Navigation';E='PBI_NavigationStepName';D='kind';C=warehouse;B=server;A=[]
	if has_semantic_views:A.append({_A:'SnowflakeSemanticViewsSource',D:'m',_Q:f'SnowflakeSemanticViews.Contents("{escape_m_string(B)}", "{escape_m_string(C)}", null, null, null, null, null)',_E:[{_A:E,_D:F},{_A:_R,_D:_S}]})
	if has_standard_tables:A.append({_A:_AA,D:'m',_Q:f'Snowflake.Databases("{escape_m_string(B)}", "{escape_m_string(C)}")',_E:[{_A:E,_D:F},{_A:_R,_D:_S}]})
	return A
def _generate_empty_table_expression(metadata):
	J='binary';I='time';H='date';E=metadata;D='number';F=set();B=[];C=[]
	for A in E.columns:
		if A.name in F:C.append(A.name);continue
		F.add(A.name);B.append(A)
	if C:logger.warning(f"Duplicate columns dropped from {E.view}: {C}. This may indicate data modeling issues in the source.")
	G=[]
	for A in B:K=snowflake_to_pbi_type(A.data_type);L={'string':'text',_V:D,_H:D,_G:D,'boolean':'logical','dateTime':'datetime',H:H,I:I,J:J};M=L.get(K,'any');G.append(f'{{"{A.name}", type {M}}}')
	N=', '.join(G);return[_O,f"    Source = #table(type table [{', '.join(f'[{A.name}]'for A in B)}], {{}})",_P,'    Source']
def _generate_table_definition(metadata,server,warehouse):
	C=metadata;G=C.view;L=generate_lineage_tag();M=_generate_m_expression(C,server,warehouse);H=_F;I=set();E=[];J=[]
	for A in C.columns:
		if A.name in I:E.append(A.name);continue
		I.add(A.name);D=snowflake_to_pbi_type(A.data_type);N=generate_lineage_tag();F=A.kind==_Y
		if F and D==_G:D=_H
		B={_A:A.name,_Z:D,_a:A.source_column or A.name,_J:N}
		if F:B[_b]=_G
		if A.description:B[_K]=A.description
		if A.is_primary_key and not H:B[_c]=_B;H=_B
		if D in(_H,_V,_G):B[_L]=_d
		else:B[_L]=_e
		if F:B[_E]=[{_A:_f,_D:_g},{_A:_h,_D:_i}]
		if A.is_hidden:B[_j]=_B
		if A.data_category:B[_k]=A.data_category
		if A.format_string:B[_l]=A.format_string
		J.append(B)
	if E:logger.warning(f"Duplicate columns dropped from {C.view}: {E}. This may indicate data modeling issues in the source.")
	K={_A:G,_J:L,_m:J,_n:[{_A:G,_o:_W,_p:{_I:'m',_Q:M}}],_E:[{_A:_R,_D:_S}]}
	if C.table_metadata and C.table_metadata.comment:K[_K]=C.table_metadata.comment
	return K
def generate_data_model_schema(views_metadata,server,warehouse,model_name=_q):B=views_metadata;C=[_generate_table_definition(A,server,warehouse)for A in B];A=datetime.utcnow().isoformat(timespec=_r);D={_A:str(uuid.uuid4()),_s:1567,_t:A,_u:A,_v:A,_w:{_x:_M,_y:{_A2:_B,_A3:_B},_z:_A4,_A0:_M,_A1:C,_E:[{_A:_A5,_D:'0'},{_A:_A6,_D:_T},{_A:_A7,_D:json.dumps([A.view for A in B])},{_A:_A8,_D:_A9}]}};return json.dumps(D,indent=2)
def create_pbit_file(views_metadata,server,warehouse,project_name,page_name='Page 1',description='',selected_relationships=_C,duplicate_role_playing_dims=_C,mode=_W,user_active_choices=_C):
	F=duplicate_role_playing_dims;E=selected_relationships;D=views_metadata;B='utf-16-le'
	if E is not _C:G=E
	else:G=collect_all_relationships(D)
	C=detect_role_playing_dimensions(G)
	if F is not _C:C={A:B for(A,B)in C.items()if F.get(A,_B)}
	H=[]
	for J in D:
		if J.view in C:continue
		H.append(J.view)
	for(K,L)in C.items():
		for M in L:H.append(f"{M}_{K}")
	I=io.BytesIO()
	with zipfile.ZipFile(I,'w',zipfile.ZIP_DEFLATED)as A:A.writestr(_N,generate_version().encode(B));A.writestr('[Content_Types].xml',generate_content_types_xml().encode('utf-8'));N=generate_data_model_schema_directquery(D,server,warehouse,project_name,selected_relationships=E,duplicate_role_playing_dims=F,mode=mode,user_active_choices=user_active_choices);A.writestr('DataModelSchema',N.encode(B));O=generate_report_layout(page_name);A.writestr('Report/Layout',O.encode(B));P=load_theme_file();A.writestr('Report/StaticResources/SharedResources/BaseThemes/CY25SU11.json',P);A.writestr('Settings',generate_settings().encode(B));A.writestr('Metadata',generate_metadata(description).encode(B));Q=generate_diagram_layout(H,relationships=G,role_playing_dims=C);A.writestr('DiagramLayout',Q.encode(B));A.writestr('SecurityBindings',b'')
	I.seek(0);return I.getvalue()
def create_single_view_pbit(metadata,server,warehouse):A=metadata;return create_pbit_file([A],server,warehouse,A.view)
def _generate_table_definition_for_imagesave(metadata,server,warehouse):
	C=metadata;G=C.view;L=generate_lineage_tag();M=_generate_m_expression(C,server,warehouse);H=_F;I=set();E=[];J=[]
	for A in C.columns:
		if A.name in I:E.append(A.name);continue
		I.add(A.name);D=snowflake_to_pbi_type(A.data_type);N=generate_lineage_tag();F=A.kind==_Y
		if F and D==_G:D=_H
		B={_A:A.name,_Z:D,_a:A.source_column or A.name,_J:N}
		if F:B[_b]=_G
		if A.description:B[_K]=A.description
		if A.is_primary_key and not H:B[_c]=_B;H=_B
		if D in(_H,_V,_G):B[_L]=_d
		else:B[_L]=_e
		if F:B[_E]=[{_A:_f,_D:_g},{_A:_h,_D:_i}]
		if A.is_hidden:B[_j]=_B
		if A.data_category:B[_k]=A.data_category
		if A.format_string:B[_l]=A.format_string
		J.append(B)
	if E:logger.warning(f"Duplicate columns dropped from {C.view}: {E}. This may indicate data modeling issues in the source.")
	K={_A:G,_J:L,_m:J,_n:[{_A:G,_o:'import',_p:{_I:'m',_Q:M}}],_E:[{_A:_R,_D:_S}]}
	if C.table_metadata and C.table_metadata.comment:K[_K]=C.table_metadata.comment
	return K
def _generate_table_definition_directquery(metadata,server,warehouse,source_table_name=_C,use_native=_F,mode=_W):
	C=metadata;K=C.view;U=source_table_name or C.view;V=generate_lineage_tag();L=_F;M=set();H=[];N=[]
	for A in C.columns:
		if A.name in M:H.append(A.name);continue
		M.add(A.name);D=snowflake_to_pbi_type(A.data_type);W=generate_lineage_tag();I=A.kind==_Y
		if I and D==_G:D=_H
		B={_A:A.name,_Z:D,_a:A.source_column or A.name,_J:W}
		if I:B[_b]=_G
		if A.description:B[_K]=A.description
		if A.is_primary_key and not L:B[_c]=_B;L=_B
		if D in(_H,_V,_G):B[_L]=_d
		else:B[_L]=_e
		if I:B[_E]=[{_A:_f,_D:_g},{_A:_h,_D:_i}]
		if A.is_hidden:B[_j]=_B
		if A.data_category:B[_k]=A.data_category
		if A.format_string:B[_l]=A.format_string
		N.append(B)
	if H:logger.warning(f"Duplicate columns dropped from {C.view}: {H}. This may indicate data modeling issues in the source.")
	E=escape_m_string(C.database);J=escape_m_string(C.schema);F=escape_m_string(U);O=escape_m_identifier(f"{E}_Database");P=escape_m_identifier(f"{E}_DB");G=escape_m_identifier(f"{J}_Schema");Q=escape_m_identifier(f"{F}_Table");R=escape_m_identifier(f"{F}1")
	if use_native:S=[_O,f'    Source = #"SnowflakeNativeSource",',f'    {O} = Source{{[Name="{E}", Kind="Database"]}}[Data],',f'    {G} = {O}{{[Name="{J}", Kind="Schema"]}}[Data],',f'    {Q} = {G}{{[Name="{F}", Kind="Table"]}}[Data]',_P,f"    {Q}"]
	else:S=[_O,f'    Source = #"SnowflakeSemanticViewsSource",',f'    {P} = Source{{[name="{E}"]}}[Data],',f'    {G} = {P}{{[name="{J}"]}}[Data],',f'    {R} = {G}{{[name="{F}"]}}[Data]',_P,f"    {R}"]
	T={_A:K,_J:V,_m:N,_n:[{_A:K,_o:mode,_p:{_I:'m',_Q:S}}],_E:[{_A:_R,_D:_S}]}
	if C.table_metadata and C.table_metadata.comment:T[_K]=C.table_metadata.comment
	return T
def generate_data_model_schema_for_imagesave(views_metadata,server,warehouse,model_name=_q):B=views_metadata;C=[_generate_table_definition_for_imagesave(A,server,warehouse)for A in B];A=datetime.utcnow().isoformat(timespec=_r);D={_A:str(uuid.uuid4()),_s:1567,_t:A,_u:A,_v:A,_w:{_x:_M,_y:{_A2:_B,_A3:_B},_z:_A4,_A0:_M,_A1:C,_E:[{_A:_A5,_D:'0'},{_A:_A6,_D:_T},{_A:_A7,_D:json.dumps([A.view for A in B])},{_A:_A8,_D:_A9}]}};return json.dumps(D,indent=2)
def generate_data_model_schema_directquery(views_metadata,server,warehouse,model_name=_q,selected_relationships=_C,duplicate_role_playing_dims=_C,mode=_W,user_active_choices=_C):
	U=duplicate_role_playing_dims;T=selected_relationships;S=warehouse;R=server;Q='VIEW';P='TABLE';F=views_metadata
	if T is not _C:G=T
	else:G=collect_all_relationships(F)
	B=detect_role_playing_dimensions(G)
	if U is not _C:B={A:B for(A,B)in B.items()if U.get(A,_B)}
	V=[];H={}
	for(I,b)in B.items():
		W=next((A for A in F if A.view==I),_C)
		if not W:continue
		for D in b:X,J=create_role_playing_table(W,D,I);V.append((X,J));H[D,I]=X.view
	C=[]
	for K in F:
		if K.view in B:continue
		L=K.object_type in(P,Q);C.append((K,_C,L))
	for(Y,J)in V:L=Y.object_type in(P,Q);C.append((Y,J,L))
	c=[_generate_table_definition_directquery(A,R,S,B,use_native=C,mode=mode)for(A,B,C)in C];d=any(A.object_type=='SEMANTIC_VIEW'for(A,B,B)in C);e=any(A.object_type in(P,Q)for(A,B,B)in C);f=generate_dual_source_expressions(R,S,d,e);E=[]
	for A in G:
		if A.from_table in B:
			for D in B[A.from_table]:g=f"{D}_{A.from_table}";M=H.get((A.from_table,A.to_table),A.to_table);N=RelationshipMetadata(name=f"{D}_{A.name}"if A.name else _C,from_table=g,from_columns=A.from_column,to_table=M,to_columns=A.to_column);E.append(N)
		else:M=H.get((A.from_table,A.to_table),A.to_table);N=RelationshipMetadata(name=A.name,from_table=A.from_table,from_columns=A.from_column,to_table=M,to_columns=A.to_column);E.append(N)
	j,h=detect_ambiguous_paths(E,user_active_choices=user_active_choices);Z=generate_pbi_relationships(E,h);O=datetime.utcnow().isoformat(timespec=_r);a={_x:_M,_y:{_A2:_B,_A3:_B},_z:_A4,_A0:_M,_A1:c,'expressions':f,_E:[{_A:_A5,_D:'0'},{_A:_A6,_D:_T},{_A:_A7,_D:json.dumps([A.view for(A,B,B)in C])},{_A:_A8,_D:_A9}]}
	if Z:a['relationships']=Z
	i={_A:str(uuid.uuid4()),_s:1567,_t:O,_u:O,_v:O,_w:a};return json.dumps(i,indent=2)