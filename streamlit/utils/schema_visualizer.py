_Q='strokeWidth'
_P='stroke'
_O='medium'
_N='critical'
_M='#FF9F36'
_L='#75CDD7'
_K='#7254A3'
_J='none'
_I='header'
_H='SEMANTIC_VIEW'
_G='object_type'
_F='background'
_E='border'
_D='TABLE'
_C=False
_B=True
_A=None
import streamlit as st
from typing import Optional
try:from streamlit_flow import streamlit_flow;from streamlit_flow.elements import StreamlitFlowNode,StreamlitFlowEdge;from streamlit_flow.state import StreamlitFlowState;from streamlit_flow.layouts import LayeredLayout,ManualLayout;FLOW_AVAILABLE=_B
except ImportError:FLOW_AVAILABLE=_C
NODE_STYLES={_H:{_F:'#F0EBF8',_E:_K,_I:_K},_D:{_F:'#E8F6F7',_E:_L,_I:_L},'VIEW':{_F:'#FFF5E6',_E:_M,_I:_M}}
EDGE_COLOR_NORMAL='#8A8A8A'
EDGE_COLOR_RISKY='#DC3545'
def create_node_style(obj_type,is_selected=_C):A=is_selected;B=NODE_STYLES.get(obj_type,NODE_STYLES[_D]);return{'backgroundColor':B[_F],_E:f"{'3px'if A else'2px'} solid {B[_E]}",'borderRadius':'6px','padding':'8px 12px','minWidth':'140px','boxShadow':'0 2px 4px rgba(0,0,0,0.1)'if A else _J}
def create_node_content(table_name,col_count,obj_type,columns=_A):
	D=table_name;C='kind';B=columns
	if obj_type==_H and B:
		E=sum(1 for A in B if getattr(A,C,_A)=='DIMENSION');F=sum(1 for A in B if getattr(A,C,_A)=='METRIC');G=sum(1 for A in B if getattr(A,C,_A)=='FACT');A=[]
		if E:A.append(f"D:{E}")
		if F:A.append(f"M:{F}")
		if G:A.append(f"F:{G}")
		if A:return f"{D}\n{' '.join(A)}"
	return f"{D}\n({col_count} cols)"
def get_cardinality_label(rel):
	D='one';A=rel
	if not hasattr(A,'cardinality')or not A.cardinality:return''
	B=getattr(A.cardinality,'from_cardinality',_A);C=getattr(A.cardinality,'to_cardinality',_A)
	if not B or not C:return''
	E='1'if B==D else'*';F='1'if C==D else'*';return f"{E}:{F}"
def get_edge_style(risk_level):A=risk_level in[_N,'high',_O];B=EDGE_COLOR_RISKY if A else EDGE_COLOR_NORMAL;return{_P:B,_Q:3 if A else 2}
def _remove_overlaps(positions,node_width,node_height,padding=2e1):
	K=padding;G=positions
	if len(G)<2:return G
	A=dict(G);F=list(A.keys());H=_B;L=100
	while H and L>0:
		H=_C;L-=1
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
def calculate_node_positions(tables,relationships,role_playing_dims=_A):
	e=role_playing_dims;d=relationships;S=tables;from collections import defaultdict as T,deque;f=200;g=55;h=100;o=10;G=f+h;H=g+o;p=120;A={}
	if not S:return A
	U={A.view for A in S};I=T(set)
	if d:
		for J in d:
			if J.from_table in U and J.to_table in U:I[J.from_table].add(J.to_table);I[J.to_table].add(J.from_table)
	N={}
	if e:
		for(q,r)in e.items():
			for i in r:
				D=f"{i}_{q}"
				if D in U:N[D]=i
	O=[];K=[]
	for B in S:
		L=B.view
		if L in N:continue
		if L in I and I[L]:O.append(B)
		else:K.append(B)
	if O:
		j={A.view:len(I.get(A.view,set()))for A in O};V=max(j,key=j.get);E=T(list);P=set();W=deque([(V,0)]);P.add(V);E[0].append(V)
		while W:
			s,F=W.popleft()
			for M in I.get(s,set()):
				if M not in P and M not in N:P.add(M);E[F+1].append(M);W.append((M,F+1))
		for B in O:
			if B.view not in P:X=max(E.keys())if E else 0;E[X+1].append(B.view)
		X=max(E.keys())if E else 0;Y=(X+1)*G
		for(F,k)in E.items():
			if F==0:Z=Y
			elif F%2==1:Z=Y+(F+1)//2*G
			else:Z=Y-F//2*G
			t=len(k)*H;u=50-t//2+H//2
			for(C,L)in enumerate(k):v=u+C*H;A[L]=float(Z),float(v)
		l=T(list)
		for(D,Q)in N.items():l[Q].append(D)
		for(Q,m)in l.items():
			if Q in A:
				w,x=A[Q]
				for(C,D)in enumerate(m):y=x+(C+1)*H;A[D]=w,y
			else:
				z=max(A[0]for A in A.values())if A else 0
				for(C,D)in enumerate(m):A[D]=z+G,float(C*H+50)
		A=_remove_overlaps(A,f,g,padding=h)
	if K:
		if A:R=max(A for(B,A)in A.values())+p;A0=min(A for(A,B)in A.values());A1=max(A for(A,B)in A.values());n=(A0+A1)/2
		else:R=50;n=G*1.5
		A2=[A for A in K if getattr(A,_G,'')==_H];A3=[A for A in K if getattr(A,_G,'')=='VIEW'];A4=[A for A in K if getattr(A,_G,_D)==_D];a=G;b=H;A5=a*2;c=n-A5/2
		for(C,B)in enumerate(A4):A[B.view]=c,R+C*b
		for(C,B)in enumerate(A3):A[B.view]=c+a,R+C*b
		for(C,B)in enumerate(A2):A[B.view]=c+a*2,R+C*b
	if A:A6=min(A[0]for A in A.values());A7=min(A[1]for A in A.values());A={A:(B-A6+50,C-A7+50)for(A,(B,C))in A.items()}
	return A
def create_flow_nodes(tables,relationships=_A,selected_table=_A,role_playing_dims=_A):
	D=selected_table;C=tables;E=[];H=calculate_node_positions(C,relationships or[],role_playing_dims)
	for A in C:B=A.view;F=getattr(A,_G,_D);G=A.columns if hasattr(A,'columns')else[];I=len(G);J=D and B.upper()==D.upper();K=StreamlitFlowNode(id=B,pos=H.get(B,(0,0)),data={'content':create_node_content(B,I,F,G)},node_type='default',style=create_node_style(F,J),source_position='right',target_position='left',draggable=_B);E.append(K)
	return E
def create_flow_edges(relationships,tables):
	C=[];D={A.view for A in tables}
	for(G,A)in enumerate(relationships):
		if A.from_table not in D or A.to_table not in D:continue
		E=A.from_table==A.to_table;B=_J
		if hasattr(A,'fan_out_risk')and A.fan_out_risk:B=getattr(A.fan_out_risk,'risk_level',_J)
		if E:F={_P:'#FFA500',_Q:2,'strokeDasharray':'5,5'}
		else:F=get_edge_style(B)
		H=StreamlitFlowEdge(id=f"e{G}_{A.from_table}_{A.to_table}",source=A.from_table,target=A.to_table,edge_type='smoothstep',style=F,label='',animated=B in[_N,'high',_O]and not E);C.append(H)
	return C
def render_schema_visualizer(tables,relationships,selected_table=_A,key='schema_flow',role_playing_dims=_A):
	C=relationships;A=tables
	if not FLOW_AVAILABLE:st.warning('Schema visualizer requires streamlit-flow-component. Install with: pip install streamlit-flow-component');return
	if not A:st.info('No tables to visualize');return
	B=create_flow_nodes(A,C,selected_table,role_playing_dims);D=create_flow_edges(C,A)
	if not B:st.info('No data to display in graph');return
	E=len(B);F=min(700,max(450,E*60));G=StreamlitFlowState(B,D);H=ManualLayout()
	@st.fragment
	def I():streamlit_flow(key=key,state=G,height=F,fit_view=_B,show_controls=_B,show_minimap=_C,allow_zoom=_B,pan_on_drag=_B,layout=H,get_node_on_click=_C,hide_watermark=_B)
	try:I();return
	except Exception as J:st.error(f"Error rendering schema diagram: {J}");return
def show_graph_legend():st.markdown('\n    <style>\n        @keyframes legendDash {\n            0% { background-position: 0 0; }\n            100% { background-position: 20px 0; }\n        }\n    </style>\n    <div style="display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 12px; background: #F5F5F5; border-radius: 8px; border-left: 4px solid #29B5E8; margin-top: 8px; align-items: center;">\n        <div style="display: flex; align-items: center; gap: 6px;">\n            <div style="width: 16px; height: 16px; background: #E8F6F7; border: 2px solid #75CDD7; border-radius: 4px;"></div>\n            <span style="font-size: 12px; color: #5B5B5B;">Table</span>\n        </div>\n        <div style="display: flex; align-items: center; gap: 6px;">\n            <div style="width: 16px; height: 16px; background: #FFF5E6; border: 2px solid #FF9F36; border-radius: 4px;"></div>\n            <span style="font-size: 12px; color: #5B5B5B;">View</span>\n        </div>\n        <div style="display: flex; align-items: center; gap: 6px;">\n            <div style="width: 16px; height: 16px; background: #F0EBF8; border: 2px solid #7254A3; border-radius: 4px;"></div>\n            <span style="font-size: 12px; color: #5B5B5B;">Semantic View</span>\n        </div>\n        <div style="width: 1px; height: 16px; background: #E5E5E5;"></div>\n        <div style="display: flex; align-items: center; gap: 6px;">\n            <div style="width: 20px; height: 3px; background: repeating-linear-gradient(90deg, #DC3545 0px, #DC3545 4px, transparent 4px, transparent 8px); background-size: 8px 3px; animation: legendDash 0.5s linear infinite;"></div>\n            <span style="font-size: 12px; color: #5B5B5B;">Fan-out risk</span>\n        </div>\n        <div style="display: flex; align-items: center; gap: 6px;">\n            <div style="width: 20px; height: 2px; background: repeating-linear-gradient(90deg, #FFA500 0px, #FFA500 4px, transparent 4px, transparent 8px);"></div>\n            <span style="font-size: 12px; color: #5B5B5B;">Self-ref</span>\n        </div>\n        <div style="display: flex; align-items: center; gap: 6px;">\n            <div style="width: 20px; height: 2px; background: #8A8A8A;"></div>\n            <span style="font-size: 12px; color: #5B5B5B;">Normal</span>\n        </div>\n        <div style="width: 1px; height: 16px; background: #E5E5E5;"></div>\n        <div style="display: flex; align-items: center; gap: 6px;">\n            <span style="font-size: 11px; color: #5B5B5B; font-style: italic;">D=Dimension M=Metric F=Fact</span>\n        </div>\n    </div>\n    ',unsafe_allow_html=_B)