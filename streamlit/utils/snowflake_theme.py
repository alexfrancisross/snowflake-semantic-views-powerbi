_A7='shadow_lg'
_A6='shadow_md'
_A5='shadow_sm'
_A4='radius_full'
_A3='radius_xl'
_A2='radius_lg'
_A1='radius_md'
_A0='radius_sm'
_z='font_bold'
_y='font_semibold'
_x='font_medium'
_w='font_normal'
_v='text_4xl'
_u='text_3xl'
_t='text_2xl'
_s='text_xl'
_r='text_lg'
_q='text_base'
_p='text_sm'
_o='text_xs'
_n='font_mono'
_m='font_primary'
_l='#E5E5E5'
_k='#29B5E8'
_j='disabled'
_i='active'
_h='info_light'
_g='error_light'
_f='warning_light'
_e='warning'
_d='success_light'
_c='success'
_b='purple_moon'
_a='first_light'
_Z='valencia_orange'
_Y='star_blue'
_X='blue_light'
_W='blue_rgb'
_V='1rem'
_U='0.75rem'
_T='border'
_S='background'
_R='primary'
_Q='border_color'
_P='text_tertiary'
_O='text_secondary'
_N='text_primary'
_M='bg_tertiary'
_L='bg_secondary'
_K='bg_primary'
_J='#7254A3'
_I='white'
_H='gray_lighter'
_G='gray_medium'
_F='gray_dark'
_E='midnight'
_D='blue_dark'
_C='#FF9F36'
_B='#75CDD7'
_A='gray_light'
COLORS={'blue':_k,_W:'41, 181, 232',_X:_B,_D:'#11567F',_E:'#000000',_F:'#5B5B5B',_G:'#8A8A8A',_A:_l,_H:'#F5F5F5',_I:'#FFFFFF',_Y:_B,_Z:_C,_a:'#D45B90',_b:_J,_c:'#34C759',_d:'#D4EDDA',_e:_C,_f:'#FFF3CD','error':'#DC3545',_g:'#F8D7DA','info':_k,_h:'#D1ECF1','hover':'rgba(41, 181, 232, 0.1)',_i:'rgba(41, 181, 232, 0.2)','focus':'rgba(41, 181, 232, 0.4)',_j:_l}
DARK_COLORS={_K:'#0D1117',_L:'#161B22',_M:'#21262D',_N:'#F0F6FC',_O:'#8B949E',_P:'#6E7681',_Q:'#30363D','border_color_dark':'#484F58'}
OBJECT_TYPE_COLORS={'SEMANTIC_VIEW':{_R:_J,_S:'#F0EBF8',_T:_J},'TABLE':{_R:_B,_S:'#E8F6F7',_T:_B},'VIEW':{_R:_C,_S:'#FFF5E6',_T:_C}}
TYPOGRAPHY={_m:"'Arial', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",_n:"'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace",_o:_U,_p:'0.875rem',_q:_V,_r:'1.125rem',_s:'1.25rem',_t:'1.5rem',_u:'1.875rem',_v:'2.25rem','text_5xl':'3rem',_w:400,_x:500,_y:600,_z:700,'leading_tight':1.25,'leading_normal':1.5,'leading_relaxed':1.75}
SPACING={'space_1':'0.25rem','space_2':'0.5rem','space_3':_U,'space_4':_V,'space_5':'1.25rem','space_6':'1.5rem','space_8':'2rem','space_10':'2.5rem','space_12':'3rem'}
BORDERS={_A0:'0.25rem',_A1:'0.5rem',_A2:_U,_A3:_V,_A4:'9999px'}
SHADOWS={_A5:'0 1px 2px 0 rgba(0, 0, 0, 0.05)',_A6:'0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',_A7:'0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)','shadow_xl':'0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'}
def get_css_variables(dark_mode=False):
	A=f"""
    :root {{
        /* Primary Colors */
        --sf-blue: {COLORS["blue"]};
        --sf-blue-rgb: {COLORS[_W]};
        --sf-blue-light: {COLORS[_X]};
        --sf-blue-dark: {COLORS[_D]};
        --sf-mid-blue: {COLORS[_D]};
        --sf-midnight: {COLORS[_E]};

        /* Grays */
        --sf-gray-dark: {COLORS[_F]};
        --sf-gray-medium: {COLORS[_G]};
        --sf-gray-light: {COLORS[_A]};
        --sf-gray-lighter: {COLORS[_H]};
        --sf-white: {COLORS[_I]};

        /* Secondary Colors */
        --sf-star-blue: {COLORS[_Y]};
        --sf-valencia-orange: {COLORS[_Z]};
        --sf-first-light: {COLORS[_a]};
        --sf-purple-moon: {COLORS[_b]};

        /* Semantic Colors */
        --sf-success: {COLORS[_c]};
        --sf-success-light: {COLORS[_d]};
        --sf-warning: {COLORS[_e]};
        --sf-warning-light: {COLORS[_f]};
        --sf-error: {COLORS["error"]};
        --sf-error-light: {COLORS[_g]};
        --sf-info: {COLORS["info"]};
        --sf-info-light: {COLORS[_h]};

        /* Interactive States */
        --sf-hover: {COLORS["hover"]};
        --sf-active: {COLORS[_i]};
        --sf-focus: {COLORS["focus"]};
        --sf-disabled: {COLORS[_j]};

        /* Typography */
        --sf-font-primary: {TYPOGRAPHY[_m]};
        --sf-font-mono: {TYPOGRAPHY[_n]};
        --sf-text-xs: {TYPOGRAPHY[_o]};
        --sf-text-sm: {TYPOGRAPHY[_p]};
        --sf-text-base: {TYPOGRAPHY[_q]};
        --sf-text-lg: {TYPOGRAPHY[_r]};
        --sf-text-xl: {TYPOGRAPHY[_s]};
        --sf-text-2xl: {TYPOGRAPHY[_t]};
        --sf-text-3xl: {TYPOGRAPHY[_u]};
        --sf-text-4xl: {TYPOGRAPHY[_v]};
        --sf-font-normal: {TYPOGRAPHY[_w]};
        --sf-font-medium: {TYPOGRAPHY[_x]};
        --sf-font-semibold: {TYPOGRAPHY[_y]};
        --sf-font-bold: {TYPOGRAPHY[_z]};

        /* Spacing */
        --sf-space-1: {SPACING["space_1"]};
        --sf-space-2: {SPACING["space_2"]};
        --sf-space-3: {SPACING["space_3"]};
        --sf-space-4: {SPACING["space_4"]};
        --sf-space-6: {SPACING["space_6"]};
        --sf-space-8: {SPACING["space_8"]};

        /* Borders & Radius */
        --sf-radius-sm: {BORDERS[_A0]};
        --sf-radius-md: {BORDERS[_A1]};
        --sf-radius-lg: {BORDERS[_A2]};
        --sf-radius-xl: {BORDERS[_A3]};
        --sf-radius-full: {BORDERS[_A4]};

        /* Shadows */
        --sf-shadow-sm: {SHADOWS[_A5]};
        --sf-shadow-md: {SHADOWS[_A6]};
        --sf-shadow-lg: {SHADOWS[_A7]};

        /* Theme-dependent (Light Mode Default) */
        --sf-bg-primary: {COLORS[_I]};
        --sf-bg-secondary: {COLORS[_H]};
        --sf-bg-tertiary: {COLORS[_A]};
        --sf-text-primary: {COLORS[_E]};
        --sf-text-secondary: {COLORS[_F]};
        --sf-text-tertiary: {COLORS[_G]};
        --sf-border-color: {COLORS[_A]};
    }}
    """
	if dark_mode:A+=f"""
        :root {{
            --sf-bg-primary: {DARK_COLORS[_K]};
            --sf-bg-secondary: {DARK_COLORS[_L]};
            --sf-bg-tertiary: {DARK_COLORS[_M]};
            --sf-text-primary: {DARK_COLORS[_N]};
            --sf-text-secondary: {DARK_COLORS[_O]};
            --sf-text-tertiary: {DARK_COLORS[_P]};
            --sf-border-color: {DARK_COLORS[_Q]};
        }}
        """
	return A
def get_component_css():return'\n    /* Typography - Strict Snowflake Compliance */\n    /* Exclude Material Icons (data-testid="stIconMaterial") from font override */\n    body, .stApp, .stMarkdown, p, div {\n        font-family: var(--sf-font-primary) !important;\n    }\n\n    /* Apply font to spans but NOT icon spans */\n    span:not([data-testid="stIconMaterial"]):not([class*="material"]):not(.material-icons) {\n        font-family: var(--sf-font-primary) !important;\n    }\n\n    code, pre, .stCode {\n        font-family: var(--sf-font-mono) !important;\n    }\n\n    h1 {\n        font-size: var(--sf-text-4xl) !important;\n        font-weight: var(--sf-font-bold) !important;\n        color: var(--sf-midnight) !important;\n    }\n\n    h2 {\n        font-size: var(--sf-text-3xl) !important;\n        font-weight: var(--sf-font-bold) !important;\n        color: var(--sf-midnight) !important;\n    }\n\n    h3 {\n        font-size: var(--sf-text-2xl) !important;\n        font-weight: var(--sf-font-semibold) !important;\n        color: var(--sf-midnight) !important;\n    }\n\n    h4 {\n        font-size: var(--sf-text-xl) !important;\n        font-weight: var(--sf-font-semibold) !important;\n        color: var(--sf-text-primary) !important;\n    }\n\n    /* Buttons - Full Snowflake Replacement */\n    .stButton > button[kind="primary"],\n    .stDownloadButton > button {\n        background-color: var(--sf-blue) !important;\n        color: var(--sf-white) !important;\n        border: 2px solid var(--sf-blue) !important;\n        border-radius: var(--sf-radius-md) !important;\n        font-weight: var(--sf-font-bold) !important;\n        text-transform: uppercase !important;\n        letter-spacing: 0.02em !important;\n        padding: var(--sf-space-2) var(--sf-space-4) !important;\n        transition: all 0.2s ease !important;\n    }\n\n    .stButton > button[kind="primary"]:hover,\n    .stDownloadButton > button:hover {\n        background-color: var(--sf-mid-blue) !important;\n        border-color: var(--sf-mid-blue) !important;\n        box-shadow: var(--sf-shadow-md) !important;\n    }\n\n    .stButton > button[kind="secondary"] {\n        background-color: transparent !important;\n        color: var(--sf-blue) !important;\n        border: 2px solid var(--sf-blue) !important;\n        border-radius: var(--sf-radius-md) !important;\n        font-weight: var(--sf-font-bold) !important;\n    }\n\n    .stButton > button[kind="secondary"]:hover {\n        background-color: var(--sf-hover) !important;\n    }\n\n    /* Cards/Expanders - Snowflake Accent Border */\n    .stExpander {\n        background-color: var(--sf-bg-primary) !important;\n        border: 1px solid var(--sf-border-color) !important;\n        border-left: 4px solid var(--sf-blue) !important;\n        border-radius: var(--sf-radius-lg) !important;\n        box-shadow: var(--sf-shadow-sm) !important;\n    }\n\n    .stExpander:hover {\n        box-shadow: var(--sf-shadow-md) !important;\n    }\n\n    .stExpander [data-testid="stExpanderToggleIcon"] {\n        color: var(--sf-blue) !important;\n    }\n\n    /* Alerts - Full Snowflake Style */\n    div[data-testid="stAlert"] {\n        border-radius: var(--sf-radius-md) !important;\n        border-left-width: 4px !important;\n        border-left-style: solid !important;\n    }\n\n    div[data-testid="stAlert"][data-baseweb*="info"],\n    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-info"]) {\n        background-color: var(--sf-info-light) !important;\n        border-left-color: var(--sf-info) !important;\n    }\n\n    div[data-testid="stAlert"][data-baseweb*="success"],\n    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-success"]) {\n        background-color: var(--sf-success-light) !important;\n        border-left-color: var(--sf-success) !important;\n    }\n\n    div[data-testid="stAlert"][data-baseweb*="warning"],\n    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-warning"]) {\n        background-color: var(--sf-warning-light) !important;\n        border-left-color: var(--sf-warning) !important;\n    }\n\n    div[data-testid="stAlert"][data-baseweb*="error"],\n    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-error"]) {\n        background-color: var(--sf-error-light) !important;\n        border-left-color: var(--sf-error) !important;\n    }\n\n    /* Progress Steps - Snowflake Colors */\n    .step-complete {\n        background: var(--sf-success-light);\n        border-left: 4px solid var(--sf-success);\n        padding: var(--sf-space-2) var(--sf-space-4);\n        border-radius: var(--sf-radius-sm);\n        margin: var(--sf-space-1) 0;\n    }\n\n    .step-current {\n        background: var(--sf-info-light);\n        border-left: 4px solid var(--sf-blue);\n        padding: var(--sf-space-2) var(--sf-space-4);\n        border-radius: var(--sf-radius-sm);\n        margin: var(--sf-space-1) 0;\n        font-weight: var(--sf-font-medium);\n    }\n\n    .step-pending {\n        background: var(--sf-bg-secondary);\n        border-left: 4px solid var(--sf-gray-light);\n        padding: var(--sf-space-2) var(--sf-space-4);\n        border-radius: var(--sf-radius-sm);\n        margin: var(--sf-space-1) 0;\n        color: var(--sf-text-secondary);\n    }\n\n    /* Scrollable tabs */\n    .stTabs [data-baseweb="tab-list"] {\n        overflow-x: auto;\n        overflow-y: hidden;\n        flex-wrap: nowrap;\n        scrollbar-width: thin;\n        scrollbar-color: var(--sf-blue) var(--sf-bg-secondary);\n        padding-bottom: 4px;\n    }\n\n    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {\n        height: 6px;\n    }\n\n    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-track {\n        background: var(--sf-bg-secondary);\n        border-radius: 3px;\n    }\n\n    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb {\n        background: var(--sf-blue);\n        border-radius: 3px;\n    }\n\n    .stTabs [data-baseweb="tab"] {\n        white-space: nowrap;\n        flex-shrink: 0;\n    }\n\n    /* Select boxes and inputs */\n    .stSelectbox [data-baseweb="select"] > div {\n        border-color: var(--sf-border-color) !important;\n        border-radius: var(--sf-radius-md) !important;\n    }\n\n    .stSelectbox [data-baseweb="select"] > div:focus-within {\n        border-color: var(--sf-blue) !important;\n        box-shadow: 0 0 0 1px var(--sf-blue) !important;\n    }\n\n    /* Multiselect tags - Snowflake Blue */\n    .stMultiSelect [data-baseweb="tag"] {\n        background-color: var(--sf-blue) !important;\n        border-radius: var(--sf-radius-md) !important;\n    }\n\n    .stMultiSelect [data-baseweb="tag"] span {\n        color: var(--sf-white) !important;\n    }\n\n    .stMultiSelect [data-baseweb="tag"] [data-baseweb="tag-action"] {\n        color: var(--sf-white) !important;\n    }\n\n    .stMultiSelect [data-baseweb="tag"]:hover {\n        background-color: var(--sf-mid-blue) !important;\n    }\n\n    /* Sidebar styling */\n    section[data-testid="stSidebar"] {\n        background-color: var(--sf-bg-secondary) !important;\n        min-width: 24rem !important;\n    }\n\n    section[data-testid="stSidebar"] .stMarkdown {\n        color: var(--sf-text-primary) !important;\n    }\n    '
def get_dark_mode_css():return f'''
    /* Dark Mode Overrides */
    [data-theme="dark"] {{
        --sf-bg-primary: {DARK_COLORS[_K]};
        --sf-bg-secondary: {DARK_COLORS[_L]};
        --sf-bg-tertiary: {DARK_COLORS[_M]};
        --sf-text-primary: {DARK_COLORS[_N]};
        --sf-text-secondary: {DARK_COLORS[_O]};
        --sf-text-tertiary: {DARK_COLORS[_P]};
        --sf-border-color: {DARK_COLORS[_Q]};
    }}

    [data-theme="dark"] body,
    [data-theme="dark"] .stApp {{
        background-color: var(--sf-bg-primary) !important;
        color: var(--sf-text-primary) !important;
    }}

    [data-theme="dark"] h1,
    [data-theme="dark"] h2,
    [data-theme="dark"] h3,
    [data-theme="dark"] h4 {{
        color: var(--sf-text-primary) !important;
    }}

    [data-theme="dark"] .stExpander {{
        background-color: var(--sf-bg-secondary) !important;
        border-color: var(--sf-border-color) !important;
    }}

    [data-theme="dark"] section[data-testid="stSidebar"] {{
        background-color: var(--sf-bg-secondary) !important;
    }}

    [data-theme="dark"] .stSelectbox [data-baseweb="select"] > div {{
        background-color: var(--sf-bg-tertiary) !important;
        border-color: var(--sf-border-color) !important;
        color: var(--sf-text-primary) !important;
    }}
    '''
def get_full_theme_css(dark_mode=False):return get_css_variables(dark_mode)+get_component_css()+get_dark_mode_css()
from pathlib import Path
import re
ICONS={'connected':'connected.svg','analytics':'analytics.svg','verified':'verified.svg','data_engineering':'migration_tools.svg','cloud':'icon_database_013.png','rocket':'rocket.svg','code':'code.svg','docs':'docs.svg','copy':'copy_icon.svg','cube':'cube.svg','table':'table.svg','view':'view.svg','snowflake':'snowflake.svg','select':'select.svg','download':'download.svg','lock':'lock.svg','checkmark':'checkmark.svg','plus':'plus.svg','database':'database.svg','schema':'schema.svg'}
def get_svg_icon(icon_name,size=24,color=None):
	J='<svg ';F=color;E=icon_name;D='utf-8';B=size;import base64 as G
	if E not in ICONS:return''
	K=Path(__file__).parent.parent/'img';C=K/ICONS[E]
	if not C.exists():return''
	try:
		if C.suffix.lower()=='.png':L=C.read_bytes();M=G.b64encode(L).decode(D);return f'<img src="data:image/png;base64,{M}" width="{B}" height="{B}" style="vertical-align: middle; display: inline-block;" />'
		A=C.read_text(encoding=D);A=re.sub('<svg\\s+',J,A);H='width="'in A;I='height="'in A
		if H:A=re.sub('width="[^"]*"',f'width="{B}"',A)
		if I:A=re.sub('height="[^"]*"',f'height="{B}"',A)
		if not H or not I:A=re.sub(J,f'<svg width="{B}" height="{B}" ',A)
		if F:A=re.sub('fill="#[0-9A-Fa-f]{6}"',f'fill="{F}"',A)
		N=A.encode(D);O=G.b64encode(N).decode(D);return f'<img src="data:image/svg+xml;base64,{O}" width="{B}" height="{B}" style="vertical-align: middle; display: inline-block;" />'
	except Exception as P:return''
def icon_header(icon_name,text,size=28,color=None):A=get_svg_icon(icon_name,size,color);return f"{A} {text}"
def icon_button_label(icon_name,text,size=18,color=None):A=get_svg_icon(icon_name,size,color);return f"{A} {text}"