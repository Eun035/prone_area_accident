import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import platform
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm # 폰트 매니저

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="교통사고 다발지역 분석 대시보드",
    page_icon="🚦",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. 한글 폰트 설정 (깨짐 방지)
# -----------------------------------------------------------------------------
def init_korean_font():
    """
    OS 환경에 따라 적절한 한글 폰트를 설정합니다.
    Streamlit Cloud(Linux)에서는 'packages.txt'로 설치한 나눔글꼴을 사용합니다.
    """
    system_name = platform.system()
    
    if system_name == 'Windows':
        # 윈도우: 맑은 고딕
        plt.rc('font', family='Malgun Gothic')
        font_family = "Malgun Gothic"
    elif system_name == 'Darwin':
        # 맥: 애플고딕
        plt.rc('font', family='AppleGothic')
        font_family = "AppleGothic"
    else:
        # 리눅스 (Streamlit Cloud): 나눔글꼴 설치 확인 후 적용
        # packages.txt에 'fonts-nanum' 추가 필수
        font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
        try:
            font_prop = fm.FontProperties(fname=font_path)
            plt.rc('font', family=font_prop.get_name())
            font_family = "NanumGothic" # Plotly용
        except:
            # 폰트가 없을 경우 경고 메시지 대신 기본값 사용
            plt.rc('font', family='DejaVu Sans')
            font_family = "sans-serif"

    # 마이너스 기호 깨짐 방지
    plt.rc('axes', unicode_minus=False)
    
    return font_family

# 폰트 초기화 실행 및 Plotly용 폰트명 받기
plotly_font = init_korean_font()

st.title("🚦 전국 교통사고 다발지역 분석 및 사고 감소 예측")

# -----------------------------------------------------------------------------
# 3. 데이터 로드 및 전처리
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    file_path = '전국교통사고다발지역표준데이터.csv'
    try:
        df = pd.read_csv(file_path, encoding='cp949')
    except:
        try:
            df = pd.read_csv(file_path, encoding='euc-kr')
        except:
            df = pd.read_csv(file_path, encoding='utf-8')
    return df

try:
    raw_df = load_data()
except FileNotFoundError:
    st.error("데이터 파일을 찾을 수 없습니다. 폴더에 '전국교통사고다발지역표준데이터.csv'가 있는지 확인해주세요.")
    st.stop()

def preprocess_and_analyze(df):
    data = df.copy()
    
    # 지역명 정제
    def clean_region(text):
        if isinstance(text, str):
            return re.sub(r'\d+$', '', text)
        return text
    
    data['region_clean'] = data['사고다발지역시도시군구'].apply(clean_region)
    data['시도'] = data['region_clean'].apply(lambda x: x.split()[0])
    
    # 전략 매핑
    strategy_map = {
        '스쿨존어린이': {'strategy': '스쿨존 과속단속/시인성 강화', 'rate': 0.30},
        '보행어린이': {'strategy': '보행로 펜스 및 안전교육', 'rate': 0.25},
        '보행노인': {'strategy': '노인보호구역 및 횡단보도 개선', 'rate': 0.20},
        '자전거': {'strategy': '자전거 전용도로 및 교차로 개선', 'rate': 0.25}
    }
    
    def apply_strategy(row):
        st_info = strategy_map.get(row['사고유형구분'], {'strategy': '일반 안전 점검', 'rate': 0.10})
        return pd.Series([st_info['strategy'], st_info['rate']])

    data[['proposed_strategy', 'reduction_rate']] = data.apply(apply_strategy, axis=1)
    data['predicted_reduction'] = data['사고건수'] * data['reduction_rate']
    data['predicted_remaining'] = data['사고건수'] - data['predicted_reduction']
    
    return data

df = preprocess_and_analyze(raw_df)

# -----------------------------------------------------------------------------
# 4. 사이드바 및 필터
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 필터 설정")
sido_list = sorted(df['시도'].unique())
selected_sido = st.sidebar.selectbox("광역시/도 선택", ["전체"] + sido_list)

if selected_sido != "전체":
    filtered_df = df[df['시도'] == selected_sido]
else:
    filtered_df = df

type_list = sorted(filtered_df['사고유형구분'].unique())
selected_types = st.sidebar.multiselect("사고 유형 선택", type_list, default=type_list)

if selected_types:
    filtered_df = filtered_df[filtered_df['사고유형구분'].isin(selected_types)]

# -----------------------------------------------------------------------------
# 5. KPI 및 시각화
# -----------------------------------------------------------------------------
total_accidents = filtered_df['사고건수'].sum()
total_reduction = filtered_df['predicted_reduction'].sum()
reduction_pct = (total_reduction / total_accidents * 100) if total_accidents > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("총 사고 건수", f"{total_accidents:,.0f}건")
col2.metric("예상 감소 건수", f"{total_reduction:,.0f}건", delta=f"-{total_reduction:,.0f}건")
col3.metric("예상 감소율", f"{reduction_pct:.1f}%", delta="안전성 향상")

st.divider()

tab1, tab2, tab3 = st.tabs(["🗺️ 지도 분석", "📊 차트 분석", "📋 상세 데이터"])

# 공통 레이아웃 설정 (폰트 적용)
def update_layout_font(fig):
    fig.update_layout(
        font=dict(family=f"{plotly_font}, sans-serif")
    )
    return fig

with tab1:
    st.subheader(f"📍 {selected_sido if selected_sido != '전체' else '전국'} 사고 다발 지역 위치")
    map_df = filtered_df[['위도', '경도', '사고지역위치명', '사고건수', '사고유형구분']].dropna()
    
    fig_map = px.scatter_mapbox(
        map_df, lat="위도", lon="경도", color="사고유형구분", size="사고건수",
        hover_name="사고지역위치명", hover_data={"위도": False, "경도": False, "사고건수": True},
        zoom=10 if selected_sido != "전체" else 6,
        mapbox_style="carto-positron",
        title="사고 다발지역 분포"
    )
    fig_map = update_layout_font(fig_map)
    fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, height=600)
    st.plotly_chart(fig_map, use_container_width=True)

with tab2:
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("사고 유형별 비중")
        type_counts = filtered_df.groupby('사고유형구분')['사고건수'].sum().reset_index()
        fig_pie = px.pie(type_counts, values='사고건수', names='사고유형구분', hole=0.4,
                         color_discrete_sequence=px.colors.sequential.RdBu)
        fig_pie = update_layout_font(fig_pie)
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_chart2:
        st.subheader("사고 유형별 예측 감소 효과")
        type_red = filtered_df.groupby('사고유형구분')[['predicted_reduction', 'predicted_remaining']].sum().reset_index()
        fig_bar = go.Figure(data=[
            go.Bar(name='감소 후 잔여 사고', x=type_red['사고유형구분'], y=type_red['predicted_remaining'], marker_color='lightgray'),
            go.Bar(name='예상 감소 사고', x=type_red['사고유형구분'], y=type_red['predicted_reduction'], marker_color='salmon')
        ])
        fig_bar.update_layout(barmode='stack', title="유형별 사고 감소 시뮬레이션")
        fig_bar = update_layout_font(fig_bar)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("🚨 사고 최다 발생 지역 Top 10")
    top_regions = filtered_df.groupby('region_clean')[['사고건수', 'predicted_reduction', 'predicted_remaining']].sum().reset_index()
    top_regions = top_regions.sort_values('사고건수', ascending=True).tail(10)
    
    fig_top = go.Figure(data=[
        go.Bar(name='감소 후 잔여', y=top_regions['region_clean'], x=top_regions['predicted_remaining'], orientation='h', marker_color='lightgray'),
        go.Bar(name='예상 감소량', y=top_regions['region_clean'], x=top_regions['predicted_reduction'], orientation='h', marker_color='red')
    ])
    fig_top.update_layout(barmode='stack', title="상위 10개 지역 예측 감소량", height=500)
    fig_top = update_layout_font(fig_top)
    st.plotly_chart(fig_top, use_container_width=True)

with tab3:
    st.subheader("📋 상세 데이터")
    view_df = filtered_df[['사고다발지역시도시군구', '사고지역위치명', '사고유형구분', '사고건수', 'proposed_strategy', 'predicted_reduction']].copy()
    view_df.columns = ['지역', '위치', '유형', '사고건수', '제안 개선안', '예상 감소수']
    view_df['예상 감소수'] = view_df['예상 감소수'].round(1)
    
    st.dataframe(view_df, use_container_width=True)
    csv = view_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 분석 결과 다운로드 (CSV)", data=csv, file_name='traffic_accident_analysis.csv', mime='text/csv')