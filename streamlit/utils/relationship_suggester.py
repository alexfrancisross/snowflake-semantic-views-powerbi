_D='manual'
_C='many'
_B='one'
_A=None
from dataclasses import dataclass,field
from enum import Enum
from typing import TYPE_CHECKING,Literal
if TYPE_CHECKING:from.metadata_fetcher import RelationshipMetadata,CardinalityInfo
class SuggestionSource(Enum):FK_CONSTRAINT='fk_constraint';MANUAL=_D
@dataclass
class SuggestedRelationship:
	from_table:str;from_columns:str|list[str];to_table:str;to_columns:str|list[str];confidence:float;source:SuggestionSource;match_reason:str='';name:str|_A=_A;from_database:str|_A=_A;from_schema:str|_A=_A;to_database:str|_A=_A;to_schema:str|_A=_A;from_cardinality:Literal[_B,_C]|_A=_A;to_cardinality:Literal[_B,_C]|_A=_A
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
	def to_relationship_metadata(A):
		from.metadata_fetcher import RelationshipMetadata as C,CardinalityInfo as D;B=_A
		if A.from_cardinality and A.to_cardinality:B=D(from_cardinality=A.from_cardinality,to_cardinality=A.to_cardinality,detected_by=_D,confidence=1.)
		return C(name=A.name,from_table=A.from_table,from_columns=A.from_columns,to_table=A.to_table,to_columns=A.to_columns,from_database=A.from_database,from_schema=A.from_schema,to_database=A.to_database,to_schema=A.to_schema,cardinality=B)
def create_manual_relationship(from_table,from_columns,to_table,to_columns,from_database=_A,from_schema=_A,to_database=_A,to_schema=_A,from_cardinality=_C,to_cardinality=_B):B=to_columns;A=from_columns;C=[A]if isinstance(A,str)else list(A);D=[B]if isinstance(B,str)else list(B);return SuggestedRelationship(from_table=from_table,from_columns=C,to_table=to_table,to_columns=D,confidence=1.,source=SuggestionSource.MANUAL,match_reason='Manually created by user',from_database=from_database,from_schema=from_schema,to_database=to_database,to_schema=to_schema,from_cardinality=from_cardinality,to_cardinality=to_cardinality)