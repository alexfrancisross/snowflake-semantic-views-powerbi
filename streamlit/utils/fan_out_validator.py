_I='medium'
_H='critical'
_G='many_to_many'
_F='one'
_E='fan_out'
_D='many'
_C=False
_B=None
_A='none'
from dataclasses import dataclass
from typing import Literal
from.metadata_fetcher import RelationshipMetadata,SemanticViewMetadata,CardinalityInfo,FanOutRisk
@dataclass
class BlockedCombination:measure_table:str;measure_column:str;grouping_table:str;reason:str;inflation_factor:float|_B=_B
@dataclass
class RelationshipIssue:issue_type:Literal[_E,_G,_A];relationship:RelationshipMetadata;reason:str;solutions:list[str];affected_measures:list[str]|_B=_B;inflation_factor:float|_B=_B
@dataclass
class ValidationResult:
	is_valid:bool;warnings:list[str];errors:list[str];blocked_combinations:list[BlockedCombination];fan_out_risks:list[FanOutRisk]
	@property
	def has_issues(self):return len(self.warnings)>0 or len(self.errors)>0
def validate_measure_dimension_combinations(relationships,tables_metadata,strict_mode=_C):
	C=[];D=[];F=[];G=[];H={A.view:A for A in tables_metadata}
	for B in relationships:
		if not B.fan_out_risk:continue
		A=B.fan_out_risk;G.append(A)
		if A.risk_level==_A:continue
		I=H.get(B.from_table);J=H.get(B.to_table)
		if not I or not J:continue
		E=_format_risk_message(B,A,I,J)
		if A.risk_level in(_H,'high'):
			if strict_mode:D.append(E)
			else:C.append(E)
			for K in A.affected_measures:F.append(BlockedCombination(measure_table=B.to_table,measure_column=K,grouping_table=B.from_table,reason=A.reason,inflation_factor=A.inflation_factor))
		elif A.risk_level==_I:C.append(E)
	L=len(D)==0;return ValidationResult(is_valid=L,warnings=C,errors=D,blocked_combinations=F,fan_out_risks=G)
def _format_risk_message(rel,risk,from_table,to_table):
	A=risk;D=f" (~{A.inflation_factor:.1f}x)"if A.inflation_factor else''
	if A.risk_level==_H:B='CRITICAL'
	elif A.risk_level=='high':B='HIGH RISK'
	elif A.risk_level==_I:B='WARNING'
	else:B='INFO'
	C=', '.join(A.affected_measures[:3])
	if len(A.affected_measures)>3:C+=f" (+{len(A.affected_measures)-3} more)"
	return f"[{B}] {rel.from_table} -> {rel.to_table}: Aggregating {C}{D} may be inflated when grouped by {from_table.view} columns. {A.recommendation}"
def get_safe_aggregations(table_name,column_name,relationships,tables_metadata):
	G='DISTINCTCOUNT';F='MAX';E='MIN';D='COUNT';C='AVG';B='SUM';A=True;H=[A for A in relationships if A.to_table==table_name and A.cardinality and A.cardinality.to_cardinality==_F and A.cardinality.from_cardinality==_D]
	if not H:return{B:A,C:A,D:A,E:A,F:A,G:A}
	I=any(A.fan_out_risk and column_name in A.fan_out_risk.affected_measures for A in H)
	if not I:return{B:A,C:A,D:A,E:A,F:A,G:A}
	return{B:_C,C:_C,D:_C,E:A,F:A,G:A}
def suggest_fix_for_fan_out(relationship,from_table_metadata,to_table_metadata):
	E=from_table_metadata;D=relationship;B=to_table_metadata;A=[]
	if not D.fan_out_risk:return A
	C=D.fan_out_risk
	if C.risk_level==_A:return A
	A.append(f"Use DISTINCTCOUNT({B.view}_KEY) instead of COUNT(*) when counting {B.view} records")
	if C.affected_measures:F=', '.join(C.affected_measures[:2]);A.append(f"Create a bridge table that pre-aggregates {F} at the {B.view} level before joining")
	A.append(f"Configure the relationship to filter from {B.view} to {E.view} (single direction)");A.append(f"Group by {B.view} attributes first, then join to {E.view} for additional details");return A
def calculate_expected_inflation(relationships,grouping_columns,measure_columns):
	D=measure_columns;A={};F={A for(A,B)in grouping_columns};I={A for(A,B)in D}
	for(E,G)in D:
		C=f"{E}.{G}"
		for B in relationships:
			if B.to_table==E and B.from_table in F:
				if B.cardinality and B.cardinality.avg_rows_per_key:H=A.get(C,1.);A[C]=H*B.cardinality.avg_rows_per_key
		if C not in A:A[C]=1.
	return A
def detect_relationship_issue_type(relationship,from_table_metadata,to_table_metadata):
	E=from_table_metadata;D='semantic_view';C=to_table_metadata;A=relationship;B=A.cardinality
	if not B:
		if A.fan_out_risk and A.fan_out_risk.risk_level!=_A:return RelationshipIssue(issue_type=_E,relationship=A,reason='Potential fan-out risk detected (cardinality unknown)',solutions=[D],affected_measures=A.fan_out_risk.affected_measures,inflation_factor=A.fan_out_risk.inflation_factor)
		return RelationshipIssue(issue_type=_A,relationship=A,reason='Cardinality unknown - no issue detected',solutions=[])
	if B.from_cardinality==_D and B.to_cardinality==_D:return RelationshipIssue(issue_type=_G,relationship=A,reason=f"Many-to-many relationship: {E.view} (*) ↔ (*) {C.view}",solutions=['bridge_table'])
	if B.from_cardinality==_D and B.to_cardinality==_F:
		F=_find_potential_measures(C)
		if not F:return RelationshipIssue(issue_type=_A,relationship=A,reason="No numeric measures found on 'one' side - no fan-out risk",solutions=[])
		G=_B
		if A.fan_out_risk:G=A.fan_out_risk.inflation_factor
		return RelationshipIssue(issue_type=_E,relationship=A,reason=f"Fan-out risk: Aggregating from {C.view} while grouping by {E.view}",solutions=[D],affected_measures=F,inflation_factor=G or B.avg_rows_per_key)
	if B.from_cardinality==_F and B.to_cardinality==_D:
		if A.fan_out_risk and A.fan_out_risk.risk_level!=_A:return RelationshipIssue(issue_type=_E,relationship=A,reason=A.fan_out_risk.reason,solutions=[D],affected_measures=A.fan_out_risk.affected_measures,inflation_factor=A.fan_out_risk.inflation_factor)
	return RelationshipIssue(issue_type=_A,relationship=A,reason='No fan-out risk for this cardinality',solutions=[])
def _find_potential_measures(table_metadata):
	D='KEY';E={'NUMBER','DECIMAL','NUMERIC','INT','INTEGER','BIGINT','SMALLINT','FLOAT','DOUBLE','REAL','FLOAT4','FLOAT8','DOUBLE PRECISION'};C=[]
	for B in table_metadata.columns:
		F=B.data_type.upper().split('(')[0].strip()
		if F not in E:continue
		A=B.name.upper();G=B.is_primary_key or getattr(B,'is_foreign_key',_C)or A.endswith('_ID')or A.endswith('_KEY')or A.endswith(D)or A.startswith('FK_')or A.startswith('PK_')or D in A and len(A)<20
		if not G:C.append(B.name)
	return C