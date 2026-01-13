#!/usr/bin/env python3
_N='\n*** DRY RUN MODE - No changes will be made ***\n'
_M='network_rule'
_L='deploy_config.yaml'
_K='app_name'
_J='external_access_integration'
_I='compute_pool'
_H='warehouse'
_G='stage'
_F='schema'
_E='='
_D='database'
_C=False
_B=True
_A='resources'
import argparse,os,sys
from pathlib import Path
from typing import Optional
import toml,yaml
class DeploymentError(Exception):0
class SnowflakeDeployer:
	def __init__(A,config_path=_L,dry_run=_C):A.config_path=config_path;A.dry_run=dry_run;A.config=A._load_config();A.script_dir=Path(__file__).parent.resolve();A.session=None
	def _load_config(A):
		B=Path(A.config_path)
		if not B.exists():raise DeploymentError(f"Config file not found: {A.config_path}")
		with open(B,'r')as C:return yaml.safe_load(C)
	def _load_connection_config(A):
		F='snowflake';E=A.config.get(F,{}).get('connection_file','deploy_connections.toml');B=A.config.get(F,{}).get('connection_name','default');C=A.script_dir/E
		if not C.exists():raise DeploymentError(f"Connection file not found: {C}\nCopy deploy_connections.toml.example to deploy_connections.toml and fill in your credentials.")
		D=toml.load(C)
		if B not in D:G=list(D.keys());raise DeploymentError(f"Connection '{B}' not found in {E}. Available connections: {G}")
		return D[B]
	def _create_session(K):
		J='private_key_path';I='role';H='user';G='account';E='password';from snowflake.snowpark import Session as L;A=K._load_connection_config();B={G:A[G],H:A[H],_H:A.get(_H),I:A.get(I),_D:A.get(_D)};B={B:A for(B,A)in B.items()if A is not None}
		if J in A:
			from cryptography.hazmat.backends import default_backend as M;from cryptography.hazmat.primitives import serialization as C;D=Path(A[J]).expanduser()
			if not D.exists():raise DeploymentError(f"Private key file not found: {D}")
			with open(D,'rb')as N:F=A.get('private_key_passphrase');O=C.load_pem_private_key(N.read(),password=F.encode()if F else None,backend=M())
			P=O.private_bytes(encoding=C.Encoding.DER,format=C.PrivateFormat.PKCS8,encryption_algorithm=C.NoEncryption());B['private_key']=P
		elif E in A:B[E]=A[E]
		else:raise DeploymentError("No authentication method configured. Provide either 'password' or 'private_key_path' in deploy_connections.toml")
		return L.builder.configs(B).create()
	def _run_sql(B,sql,description=''):
		C=description;A=sql
		if C:print(f"  {C}...")
		if B.dry_run:print(f"  [DRY-RUN] Would execute:\n    {A[:200]}{'...'if len(A)>200 else''}");return _B,''
		try:D=B.session.sql(A).collect();E='\n'.join(str(A)for A in D)if D else'';return _B,E
		except Exception as F:return _C,str(F)
	def validate_prerequisites(A):
		print('\n[1/8] Validating prerequisites...')
		if A.dry_run:print('  [DRY-RUN] Would test Snowpark connection');return _B
		try:
			A.session=A._create_session();B=A.session.sql('SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()').collect()
			if B:C,D,E=B[0][0],B[0][1],B[0][2];print(f"  Connected as: {C}");print(f"  Role: {D}");print(f"  Warehouse: {E}")
			print('  Prerequisites OK');return _B
		except Exception as F:print(f"  ERROR: Could not connect to Snowflake: {F}");return _C
	def create_database(B):
		print('\n[2/8] Creating database...');A=B.config[_A][_D];C,D=B._run_sql(f"CREATE DATABASE IF NOT EXISTS {A}",f"Creating database {A}")
		if not C:print(f"  ERROR: {D}");return _C
		print(f"  Database {A} ready");return _B
	def create_schema(A):
		print('\n[3/8] Creating schema...');B=A.config[_A][_D];C=A.config[_A][_F];D,E=A._run_sql(f"CREATE SCHEMA IF NOT EXISTS {B}.{C}",f"Creating schema {B}.{C}")
		if not D:print(f"  ERROR: {E}");return _C
		print(f"  Schema {B}.{C} ready");return _B
	def create_stage(A):
		print('\n[4/8] Creating stage...');C=A.config[_A][_D];D=A.config[_A][_F];E=A.config[_A][_G];B=f"{C}.{D}.{E}";A._run_sql(f"DROP STAGE IF EXISTS {B}",'Dropping existing stage');F,G=A._run_sql(f"CREATE STAGE {B}\n                DIRECTORY = (ENABLE = TRUE)\n                ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')",f"Creating stage {B}")
		if not F:print(f"  ERROR: {G}");return _C
		print(f"  Stage {B} ready");return _B
	def upload_files(A):
		print('\n[5/8] Uploading files to stage...');O=A.config[_A][_D];P=A.config[_A][_F];Q=A.config[_A][_G];D=f"@{O}.{P}.{Q}";I=A.config.get('exclude_patterns',[])
		if A.dry_run:print(f"  [DRY-RUN] Would upload files from {A.script_dir} to {D}");print(f"  [DRY-RUN] Excluding: {I}");return _B
		E=[]
		for F in A.script_dir.rglob('*'):
			if F.is_file():
				B=F.relative_to(A.script_dir);J=_C
				for K in I:
					if K in str(B)or B.match(K):J=_B;break
				if not J:E.append(F)
		print(f"  Found {len(E)} files to upload");G=0;H=0
		for L in E:
			B=L.relative_to(A.script_dir);M=str(B.parent).replace(os.sep,'/')
			if M=='.':N=D
			else:N=f"{D}/{M}"
			R=str(L).replace(os.sep,'/');S=f"file://{R}";T=f"PUT '{S}' '{N}/' AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
			try:A.session.sql(T).collect();G+=1
			except Exception as U:
				C=str(U)
				if len(C)>100:C=C[:100]+'...'
				print(f"    Warning: Failed to upload {B}: {C}");H+=1
		print(f"  Uploaded {G} files ({H} failed)");return H==0 or G>0
	def create_compute_pool(B):
		print('\n[6/8] Creating compute pool...');A=B.config[_A][_I];C=B.config.get('compute_pool_config',{});F=C.get('instance_family','CPU_X64_XS');G=C.get('min_nodes',1);H=C.get('max_nodes',1);I=C.get('auto_suspend_secs',300);D,E=B._run_sql(f"SHOW COMPUTE POOLS LIKE '{A}'",f"Checking if compute pool {A} exists")
		if D and A.upper()in E.upper():print(f"  Compute pool {A} already exists");return _B
		D,E=B._run_sql(f"CREATE COMPUTE POOL IF NOT EXISTS {A}\n                MIN_NODES = {G}\n                MAX_NODES = {H}\n                INSTANCE_FAMILY = {F}\n                AUTO_SUSPEND_SECS = {I}",f"Creating compute pool {A}")
		if not D:print(f"  ERROR: {E}");print('  Note: Compute pool creation requires ACCOUNTADMIN or similar privileges');return _C
		print(f"  Compute pool {A} ready");return _B
	def create_network_rule_and_eai(A):
		print('\n[7/8] Creating network rule and external access integration...');G=A.config[_A][_D];H=A.config[_A][_F];B=A.config[_A][_M];C=A.config[_A][_J];F=f"{G}.{H}.{B}";D,E=A._run_sql(f"CREATE OR REPLACE NETWORK RULE {F}\n                MODE = EGRESS\n                TYPE = HOST_PORT\n                VALUE_LIST = ('pypi.org:443', 'files.pythonhosted.org:443')",f"Creating network rule {B}")
		if not D:print(f"  ERROR creating network rule: {E}");return _C
		D,E=A._run_sql(f"CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION {C}\n                ALLOWED_NETWORK_RULES = ({F})\n                ENABLED = TRUE",f"Creating external access integration {C}")
		if not D:print(f"  ERROR creating EAI: {E}");return _C
		print(f"  Network rule {B} and EAI {C} ready");return _B
	def create_streamlit_app(A):
		C='app';print('\n[8/8] Creating Streamlit app...');D=A.config[_A][_D];E=A.config[_A][_F];G=A.config[_A][_G];F=A.config[_A][_K];H=A.config[_A][_H];I=A.config[_A][_I];J=A.config[_A][_J];K=A.config[C]['title'];L=A.config[C]['main_file'];M=A.config[C]['runtime'];B=f"{D}.{E}.{F}";N=f"@{D}.{E}.{G}";A._run_sql(f"DROP STREAMLIT IF EXISTS {B}",'Dropping existing app');O=f"""CREATE STREAMLIT {B}
            FROM '{N}'
            MAIN_FILE = '{L}'
            QUERY_WAREHOUSE = {H}
            TITLE = '{K}'
            RUNTIME_NAME = '{M}'
            COMPUTE_POOL = {I}
            EXTERNAL_ACCESS_INTEGRATIONS = ({J})""";P,Q=A._run_sql(O,f"Creating Streamlit app {F}")
		if not P:print(f"  ERROR: {Q}");return _C
		print(f"  Streamlit app {B} created successfully!");return _B
	def get_app_url(A):
		if A.dry_run:return'[DRY-RUN] URL would be displayed here'
		D=A.config[_A][_D];E=A.config[_A][_F];F=A.config[_A][_K];C=f"{D}.{E}.{F}"
		try:
			B=A.session.sql('SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()').collect()
			if B:G=B[0][0].lower();H=B[0][1].lower();return f"https://app.snowflake.com/{G}/{H}/#/streamlit-apps/{C}"
			return f"App deployed. View in Snowsight under {C}"
		except Exception:return
	def deploy(A):
		print(_E*60);print('Snowflake Streamlit Deployment');print(_E*60)
		if A.dry_run:print(_N)
		D=[A.validate_prerequisites,A.create_database,A.create_schema,A.create_stage,A.upload_files,A.create_compute_pool,A.create_network_rule_and_eai,A.create_streamlit_app]
		for B in D:
			if not B():print(f"\n*** Deployment failed at step: {B.__name__} ***");return _C
		print('\n'+_E*60);print('DEPLOYMENT SUCCESSFUL!');print(_E*60);C=A.get_app_url()
		if C:print(f"\nApp URL: {C}")
		print('\nNote: First load may take 1-2 minutes as compute pool starts.')
		if A.session:A.session.close()
		return _B
	def teardown(A,confirm=_B):
		F=confirm;print(_E*60);print('Snowflake Streamlit Teardown');print(_E*60)
		if A.dry_run:print(_N)
		if not A.dry_run and not A.session:
			if not A.validate_prerequisites():return _C
		B=A.config[_A][_D];C=A.config[_A][_F];K=A.config[_A][_G];L=A.config[_A][_K];D=A.config[_A][_I];G=A.config[_A][_J];M=A.config[_A][_M];H=f"{B}.{C}.{L}";I=f"{B}.{C}.{K}";J=f"{B}.{C}.{M}"
		if F and not A.dry_run:
			print(f"\nThis will remove:");print(f"  - Streamlit app: {H}");print(f"  - External access integration: {G}");print(f"  - Network rule: {J}");print(f"  - Stage: {I}");print(f"  - Schema: {B}.{C}");print(f"  - Database: {B}");print(f"  - Compute pool: {D} (optional)");E=input('\nProceed? [y/N]: ').strip().lower()
			if E!='y':print('Teardown cancelled.');return _C
		print('\n[1/7] Dropping Streamlit app...');A._run_sql(f"DROP STREAMLIT IF EXISTS {H}");print('[2/7] Dropping external access integration...');A._run_sql(f"DROP INTEGRATION IF EXISTS {G}");print('[3/7] Dropping network rule...');A._run_sql(f"DROP NETWORK RULE IF EXISTS {J}");print('[4/7] Dropping stage...');A._run_sql(f"DROP STAGE IF EXISTS {I}");print('[5/7] Dropping schema...');A._run_sql(f"DROP SCHEMA IF EXISTS {B}.{C}");print('[6/7] Dropping database...');A._run_sql(f"DROP DATABASE IF EXISTS {B}")
		if F and not A.dry_run:
			E=input(f"\nDrop compute pool {D}? (shared resource) [y/N]: ").strip().lower()
			if E=='y':print('[7/7] Dropping compute pool...');A._run_sql(f"DROP COMPUTE POOL IF EXISTS {D}")
		else:print('[7/7] Skipping compute pool (shared resource)')
		print('\n'+_E*60);print('TEARDOWN COMPLETE');print(_E*60)
		if A.session:A.session.close()
		return _B
def main():
	C='store_true';A=argparse.ArgumentParser(description='Deploy Streamlit app to Snowflake (no CLI required)',formatter_class=argparse.RawDescriptionHelpFormatter,epilog='\nExamples:\n  python deploy.py                    # Deploy app\n  python deploy.py --dry-run          # Show what would be done\n  python deploy.py --teardown         # Remove all resources\n  python deploy.py --config my.yaml   # Use custom config\n\nConfiguration:\n  1. Copy deploy_connections.toml.example to deploy_connections.toml\n  2. Fill in your Snowflake credentials (password or key-pair)\n  3. Run deploy.py\n        ');A.add_argument('--config','-c',default=_L,help='Path to config file (default: deploy_config.yaml)');A.add_argument('--teardown','-t',action=C,help='Remove all deployed resources');A.add_argument('--dry-run','-n',action=C,help='Show what would be done without making changes');A.add_argument('--yes','-y',action=C,help='Skip confirmation prompts');B=A.parse_args()
	try:
		D=SnowflakeDeployer(config_path=B.config,dry_run=B.dry_run)
		if B.teardown:E=D.teardown(confirm=not B.yes)
		else:E=D.deploy()
		sys.exit(0 if E else 1)
	except DeploymentError as F:print(f"ERROR: {F}");sys.exit(1)
	except KeyboardInterrupt:print('\n\nDeployment cancelled by user.');sys.exit(1)
if __name__=='__main__':main()