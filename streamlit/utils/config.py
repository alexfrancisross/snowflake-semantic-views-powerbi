_S='#DC3545'
_R='critical'
_Q='medium'
_P='COLUMN'
_O='METRIC'
_N='DIMENSION'
_M='native'
_L='DirectQuery'
_K='#34C759'
_J='#FF9F36'
_I='VIEW'
_H='SEMANTIC_VIEW'
_G='many'
_F='one'
_E='symbol'
_D='to'
_C='from'
_B='TABLE'
_A=True
from dataclasses import dataclass,field
from typing import Literal
@dataclass(frozen=_A)
class AppConfig:APP_NAME:str='Power BI Semantic Model Generator';APP_VERSION:str='3.0.0';APP_ICON:str='snowflake';CACHE_TTL_DATABASE:int=300;CACHE_TTL_METADATA:int=60;CACHE_TTL_SESSION:int=3600;PBIT_VERSION:str='1.28';PBIT_THEME_NAME:str='CY25SU11';MAX_TREE_DEPTH:int=3;DEFAULT_PAGE_SIZE:int=1000;SIDEBAR_WIDTH:int=300;WIZARD_STEP_REVIEW:int=0;WIZARD_STEP_MODEL:int=1;WIZARD_STEP_SEMANTIC:int=2;WIZARD_STEP_GENERATE:int=3;WIZARD_TOTAL_STEPS:int=4;MAX_IDENTIFIER_LENGTH:int=255;DEFAULT_PBI_MODE:str=_L;SUPPORTED_PBI_MODES:tuple=(_L,'Import');MAX_PBIT_SIZE_MB:int=100
CONFIG=AppConfig()
@dataclass(frozen=_A)
class WizardStep:index:int;name:str;short_name:str;description:str;icon:str
WIZARD_STEPS=WizardStep(index=0,name='Review Selected Objects',short_name='Review',description='Review selected objects and their metadata',icon='verified'),WizardStep(index=1,name='Design Data Model',short_name='Model',description='Configure relationships and data model settings',icon='data_engineering'),WizardStep(index=2,name='Download PBI Workbook',short_name='Download',description='Generate and download your Power BI workbook',icon='download')
def get_wizard_step_by_index(index):
	for A in WIZARD_STEPS:
		if A.index==index:return A
ObjectTypeLiteral=Literal[_H,_I,_B]
@dataclass(frozen=_A)
class ObjectTypeConfig:name:str;display_name:str;icon_key:str;color_primary:str;color_background:str;connector_type:str
OBJECT_TYPES={_H:ObjectTypeConfig(name=_H,display_name='Semantic View',icon_key='cube',color_primary='#7254A3',color_background='#F0EBF8',connector_type='custom'),_B:ObjectTypeConfig(name=_B,display_name='Table',icon_key='table',color_primary='#75CDD7',color_background='#E8F6F7',connector_type=_M),_I:ObjectTypeConfig(name=_I,display_name='View',icon_key='view',color_primary=_J,color_background='#FFF5E6',connector_type=_M)}
def get_object_type_config(object_type):return OBJECT_TYPES.get(object_type,OBJECT_TYPES[_B])
SNOWFLAKE_AGGREGATIONS='SUM','AVG','COUNT','MIN','MAX','COUNT_DISTINCT','MEDIAN','STDDEV','VARIANCE'
DEFAULT_AGGREGATION='SUM'
@dataclass(frozen=_A)
class ColumnKindConfig:name:str;display_name:str;description:str;color:str;can_aggregate:bool
COLUMN_KINDS={_N:ColumnKindConfig(name=_N,display_name='Dimension',description='Categorical attribute for grouping/filtering',color='#29B5E8',can_aggregate=False),_O:ColumnKindConfig(name=_O,display_name='Metric',description='Pre-aggregated numeric measure',color=_K,can_aggregate=_A),'FACT':ColumnKindConfig(name='FACT',display_name='Fact',description='Raw numeric value at detail level',color=_J,can_aggregate=_A),_P:ColumnKindConfig(name=_P,display_name='Column',description='Regular table/view column',color='#8A8A8A',can_aggregate=_A)}
CARDINALITY_TYPES={'one-to-one':{_C:_F,_D:_F,_E:'1:1'},'one-to-many':{_C:_F,_D:_G,_E:'1:N'},'many-to-one':{_C:_G,_D:_F,_E:'N:1'},'many-to-many':{_C:_G,_D:_G,_E:'M:N'}}
@dataclass(frozen=_A)
class RiskLevelConfig:name:str;display_name:str;color:str;description:str
RISK_LEVELS={'none':RiskLevelConfig(name='none',display_name='None',color=_K,description='No fan-out risk detected'),'low':RiskLevelConfig(name='low',display_name='Low',color=_K,description='Minimal risk of measure inflation'),_Q:RiskLevelConfig(name=_Q,display_name='Medium',color=_J,description='Moderate risk - review relationship direction'),'high':RiskLevelConfig(name='high',display_name='High',color=_S,description='High risk of incorrect aggregations'),_R:RiskLevelConfig(name=_R,display_name='Critical',color=_S,description='Significant measure inflation expected')}