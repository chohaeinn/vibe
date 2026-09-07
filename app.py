import streamlit as st
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "users.db"

st.set_page_config(
    page_title="행사장 디자이너",
    page_icon="🎪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Database / authentication
# -----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def create_user(username: str, password: str):
    username = username.strip()
    if not username or not password:
        return False, "아이디와 비밀번호를 입력해주세요."
    if len(username) < 3:
        return False, "아이디는 3자 이상 입력해주세요."
    if len(password) < 6:
        return False, "비밀번호는 6자 이상 입력해주세요."

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, hash_password(password), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return True, "회원가입이 완료되었습니다."
    except sqlite3.IntegrityError:
        return False, "이미 존재하는 아이디입니다."
    finally:
        conn.close()

def authenticate(username: str, password: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    conn.close()
    return bool(row and row[0] == hash_password(password))

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# -----------------------------
# Recommendation engine
# -----------------------------
def recommend_design(event_type, people, duration, age_group, mood, fee, place):
    if people <= 50:
        scale = "소규모"
        area = f"약 {max(60, people * 2)}~{max(90, people * 3)}㎡"
    elif people <= 200:
        scale = "중규모"
        area = f"약 {people * 1.5:.0f}~{people * 2.2:.0f}㎡"
    else:
        scale = "대규모"
        area = f"약 {people * 1.2:.0f}~{people * 1.8:.0f}㎡"

    if duration <= 2:
        flow = "입장 → 핵심 프로그램 → 자유 관람 → 퇴장"
    elif duration <= 5:
        flow = "입장 → 오프닝 → 메인 프로그램 → 휴식/체험 → 클로징"
    else:
        flow = "입장 → 오프닝 → 세션/체험 → 식음/휴식 → 메인 프로그램 → 클로징"

    if place == "실내":
        venue = "천장고와 기둥 위치를 먼저 확인하고, 무대·객석·체험존을 중앙 동선 기준으로 배치합니다."
        weather = "실내이므로 우천 대응 부담이 낮고, 조명·음향 연출에 집중하기 좋습니다."
    else:
        venue = "그늘·휴식존·화장실·전기·우천 대피 동선을 입구와 가까운 위치에 우선 배치합니다."
        weather = "야외 행사이므로 우천 및 폭염/한파 대비 플랜 B 공간을 반드시 확보합니다."

    if "가족" in age_group or "어린이" in age_group:
        safety = "유아·어린이 이동을 고려해 모서리 없는 가구, 넓은 통로, 보호자 대기존을 확보합니다."
    elif "청소년" in age_group:
        safety = "친구 단위 이동이 많으므로 포토존·체험존을 분산하고 혼잡 구간을 넓게 잡습니다."
    elif "중장년" in age_group:
        safety = "좌석 비중과 휴식 공간을 늘리고, 안내 표지와 화장실 접근성을 높입니다."
    else:
        safety = "참가자 체류 시간을 고려해 휴식·대기·포토존을 적절히 분산합니다."

    mood_map = {
        "세련되고 모던한": "화이트/그레이 계열 베이스에 간접조명과 미니멀 사인물을 사용합니다.",
        "활기차고 축제 같은": "강한 포인트 컬러, 스트링 조명, 대형 포토월과 참여형 체험존을 활용합니다.",
        "따뜻하고 감성적인": "우드 소재, 웜톤 조명, 패브릭 장식과 작은 휴식 공간을 배치합니다.",
        "고급스럽고 프리미엄한": "여백을 넓게 두고 메탈·블랙·뉴트럴 소재와 집중 조명을 사용합니다.",
        "자연스럽고 편안한": "식물, 우드, 자연 소재와 낮은 조도의 편안한 휴식존을 구성합니다.",
    }

    budget_note = (
        "입장료가 낮은 편이므로 체험형 시설은 최소화하고 공간 연출과 동선 효율에 집중합니다."
        if fee < 10000 else
        "입장료가 중간 수준이므로 핵심 체험 1~2개와 포토존을 결합하는 구성이 적합합니다."
        if fee < 30000 else
        "입장료가 높은 편이므로 프리미엄 웰컴존, 예약형 프로그램, 굿즈/라운지 등을 추가하기 좋습니다."
    )

    zones = [
        ("① 웰컴존", "입구", "등록/티켓 확인, 행사 안내, 첫인상 연출"),
        ("② 메인존", "중앙", f"{event_type}의 핵심 프로그램 진행"),
        ("③ 체험/콘텐츠존", "메인존 주변", "참가자의 체류시간을 늘리는 참여형 콘텐츠"),
        ("④ 휴식존", "동선 가장자리", "대기·휴식·음료·소셜 공간"),
        ("⑤ 포토존", "입구 또는 메인존 인근", "행사 분위기를 시각적으로 보여주는 SNS 콘텐츠 공간"),
        ("⑥ 운영존", "후면/측면", "스태프·장비·물품 관리"),
    ]

    if people > 500:
        crowd = "500명 이상이므로 입·퇴장 동선을 분리하고, 병목이 생기기 쉬운 구간에 안내 인력을 배치하세요."
    elif people > 200:
        crowd = "200명 이상이므로 메인존 앞 대기열과 체험존별 대기 공간을 별도로 확보하세요."
    else:
        crowd = "참가자 규모가 비교적 작아 핵심 공간을 서로 가깝게 묶어 몰입감 있는 구성이 가능합니다."

    return {
        "scale": scale,
        "area": area,
        "flow": flow,
        "venue": venue,
        "weather": weather,
        "safety": safety,
        "mood": mood_map.get(mood, "행사 목적에 맞는 통일감 있는 색상과 사인 시스템을 사용합니다."),
        "budget": budget_note,
        "crowd": crowd,
        "zones": zones,
    }

# -----------------------------
# Session state
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# -----------------------------
# Login / Signup screen
# -----------------------------
if not st.session_state.logged_in:
    st.title("🎪 행사장 디자이너")
    st.caption("사용자의 행사 조건을 바탕으로 공간 구성과 운영 아이디어를 제안합니다.")

    login_tab, signup_tab = st.tabs(["로그인", "회원가입"])

    with login_tab:
        st.subheader("로그인")
        with st.form("login_form"):
            username = st.text_input("아이디")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인", use_container_width=True)

        if submitted:
            if authenticate(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username.strip()
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    with signup_tab:
        st.subheader("회원가입")
        with st.form("signup_form"):
            new_username = st.text_input("새 아이디")
            new_password = st.text_input("새 비밀번호", type="password")
            new_password2 = st.text_input("비밀번호 확인", type="password")
            submitted = st.form_submit_button("회원가입", use_container_width=True)

        if submitted:
            if new_password != new_password2:
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                ok, message = create_user(new_username, new_password)
                (st.success if ok else st.error)(message)

    st.info("💡 대회/프로토타입용으로 바로 실행할 수 있는 기본 회원가입 기능입니다.")
    st.stop()

# -----------------------------
# Venue simulation helpers
# -----------------------------
import numpy as np
import pandas as pd
import plotly.graph_objects as go


VENUE_ZONES = {
    "① 웰컴존": {"x": 7, "y": 73, "w": 22, "h": 16, "capacity": 70, "fill": "rgba(76, 175, 239, 0.34)"},
    "② 메인존": {"x": 35, "y": 31, "w": 36, "h": 34, "capacity": 230, "fill": "rgba(255, 193, 7, 0.30)"},
    "③ 체험/콘텐츠존": {"x": 7, "y": 42, "w": 22, "h": 22, "capacity": 100, "fill": "rgba(76, 200, 140, 0.30)"},
    "④ 휴식존": {"x": 7, "y": 10, "w": 26, "h": 20, "capacity": 110, "fill": "rgba(115, 170, 255, 0.28)"},
    "⑤ 포토존": {"x": 76, "y": 72, "w": 18, "h": 17, "capacity": 90, "fill": "rgba(190, 120, 230, 0.30)"},
    "⑥ 운영존": {"x": 76, "y": 10, "w": 18, "h": 20, "capacity": 60, "fill": "rgba(180, 180, 180, 0.24)"},
    "푸드존": {"x": 76, "y": 37, "w": 18, "h": 25, "capacity": 100, "fill": "rgba(255, 130, 70, 0.28)"},
}

ZONE_CENTER = {
    name: (z["x"] + z["w"] / 2, z["y"] + z["h"] / 2)
    for name, z in VENUE_ZONES.items()
}


def _weighted_choice(rng, choices, weights):
    weights = np.array(weights, dtype=float)
    weights = np.clip(weights, 0, None)
    weights = weights / weights.sum()
    return rng.choice(choices, p=weights)


def target_zone(event_type, age_group, u, minute, weights, rng, participant_id):
    """교육/기획용으로 단순화한 참가자 이동 모델."""
    # 입장 직후에는 웰컴존을 중심으로 분포
    if minute <= 20:
        if u < 0.70:
            return "① 웰컴존"
        if u < 0.84:
            return "⑤ 포토존"
        return "푸드존"

    # 공연/핵심 프로그램 집중 시간
    if minute <= 120:
        if event_type in ["콘서트", "페스티벌"]:
            choices = ["② 메인존", "⑤ 포토존", "④ 휴식존", "푸드존"]
            probs = [0.72, 0.10, 0.09, 0.09]
        else:
            choices = ["② 메인존", "③ 체험/콘텐츠존", "④ 휴식존", "⑤ 포토존", "푸드존"]
            probs = [0.48, 0.23, 0.12, 0.07, 0.10]

        # 사용자가 조정한 공간 활성도를 반영
        adjusted = []
        for zone, p in zip(choices, probs):
            adjusted.append(p * weights.get(zone, 1.0))
        return _weighted_choice(rng, choices, adjusted)

    # 중후반에는 프로그램에 따라 분산
    phase = int((minute - 120) // 20) % 4
    if phase == 0:
        choices = ["② 메인존", "③ 체험/콘텐츠존", "④ 휴식존", "⑤ 포토존", "푸드존"]
        probs = [0.42, 0.18, 0.13, 0.12, 0.15]
    elif phase == 1:
        choices = ["② 메인존", "③ 체험/콘텐츠존", "④ 휴식존", "⑤ 포토존", "푸드존"]
        probs = [0.30, 0.22, 0.20, 0.12, 0.16]
    elif phase == 2:
        choices = ["② 메인존", "③ 체험/콘텐츠존", "④ 휴식존", "⑤ 포토존", "푸드존"]
        probs = [0.34, 0.14, 0.12, 0.24, 0.12]
    else:
        choices = ["② 메인존", "③ 체험/콘텐츠존", "④ 휴식존", "⑤ 포토존", "푸드존"]
        probs = [0.26, 0.18, 0.15, 0.16, 0.25]

    adjusted = [p * weights.get(zone, 1.0) for zone, p in zip(choices, probs)]
    return _weighted_choice(rng, choices, adjusted)


def simulate_agents(participant_count, current_minute, event_type, age_group, weights):
    # 고정 시드라서 슬라이더를 움직여도 결과가 지나치게 흔들리지 않음
    rng = np.random.default_rng(20260907)
    u = rng.random(participant_count)
    personal = rng.random(participant_count)

    prev_minute = max(0, current_minute - 15)
    positions = np.zeros((participant_count, 2), dtype=float)
    destinations = []

    for i in range(participant_count):
        now_zone = target_zone(
            event_type, age_group, u[i], current_minute, weights, rng, i
        )
        prev_zone = target_zone(
            event_type, age_group, u[i], prev_minute, weights, rng, i + 10000
        )
        destinations.append(now_zone)

        start = np.array(ZONE_CENTER[prev_zone], dtype=float)
        end = np.array(ZONE_CENTER[now_zone], dtype=float)

        # 이동 중인 사람과 도착한 사람을 혼합
        phase = (current_minute - prev_minute) / 15.0
        phase = np.clip(phase, 0.0, 1.0)
        travel_start = 0.18 + personal[i] * 0.20
        t = np.clip((phase - travel_start) / (1 - travel_start), 0.0, 1.0)
        t = t * t * (3 - 2 * t)

        pos = start * (1 - t) + end * t

        # 구역 내부 분산
        jitter_scale = 1.4
        pos += rng.normal(0, jitter_scale, 2)

        # 행사장 밖으로 나가지 않게 제한
        pos[0] = np.clip(pos[0], 2, 98)
        pos[1] = np.clip(pos[1], 2, 98)
        positions[i] = pos

    return positions, np.array(destinations)


def make_density_grid(points, grid_size=65, sigma=4.8):
    xs = np.linspace(0, 100, grid_size)
    ys = np.linspace(0, 100, grid_size)
    X, Y = np.meshgrid(xs, ys)
    heat = np.zeros_like(X, dtype=float)

    # 메모리 사용량을 줄이기 위해 배치 계산
    for start in range(0, len(points), 250):
        batch = points[start:start + 250]
        dx = X[:, :, None] - batch[:, 0][None, None, :]
        dy = Y[:, :, None] - batch[:, 1][None, None, :]
        heat += np.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma)).sum(axis=2)

    return xs, ys, heat


def zone_occupancy(points):
    result = {}
    for zone_name, zone in VENUE_ZONES.items():
        cx, cy = ZONE_CENTER[zone_name]
        # 각 존 중심 주변의 간단한 영향 반경으로 예상 체류 인원 계산
        radius = max(7.5, min(zone["w"], zone["h"]) * 0.55)
        dist = np.sqrt((points[:, 0] - cx) ** 2 + (points[:, 1] - cy) ** 2)
        result[zone_name] = int((dist <= radius).sum())
    return result


def build_floorplan(
    positions,
    occupancy,
    event_type,
    show_people=True,
    show_heatmap=True,
    show_paths=True,
):
    xs, ys, heat = make_density_grid(positions)

    fig = go.Figure()

    if show_heatmap:
        fig.add_trace(
            go.Heatmap(
                x=xs,
                y=ys,
                z=heat,
                colorscale=[
                    [0.00, "rgb(30, 80, 170)"],
                    [0.25, "rgb(55, 160, 220)"],
                    [0.50, "rgb(95, 200, 125)"],
                    [0.72, "rgb(245, 220, 70)"],
                    [0.88, "rgb(245, 140, 40)"],
                    [1.00, "rgb(215, 45, 35)"],
                ],
                opacity=0.48,
                colorbar=dict(title="밀집도"),
                hoverinfo="skip",
                name="혼잡도",
            )
        )

    if show_paths:
        path_pairs = [
            ("① 웰컴존", "② 메인존"),
            ("② 메인존", "⑤ 포토존"),
            ("② 메인존", "④ 휴식존"),
            ("④ 휴식존", "푸드존"),
            ("② 메인존", "③ 체험/콘텐츠존"),
        ]
        for a, b in path_pairs:
            ax, ay = ZONE_CENTER[a]
            bx, by = ZONE_CENTER[b]
            fig.add_annotation(
                x=bx,
                y=by,
                ax=ax,
                ay=ay,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="rgba(255,255,255,0.62)",
            )

    for zone_name, zone in VENUE_ZONES.items():
        fig.add_shape(
            type="rect",
            x0=zone["x"],
            y0=zone["y"],
            x1=zone["x"] + zone["w"],
            y1=zone["y"] + zone["h"],
            line=dict(color="white", width=2),
            fillcolor=zone["fill"],
        )

        count = occupancy.get(zone_name, 0)
        capacity = zone["capacity"]
        percent = count / capacity * 100 if capacity else 0
        label = f"<b>{zone_name}</b><br>{count}명 / {capacity}명<br>{percent:.0f}%"

        fig.add_annotation(
            x=zone["x"] + zone["w"] / 2,
            y=zone["y"] + zone["h"] / 2,
            text=label,
            showarrow=False,
            font=dict(size=12, color="white"),
            align="center",
        )

    if show_people:
        fig.add_trace(
            go.Scatter(
                x=positions[:, 0],
                y=positions[:, 1],
                mode="markers",
                marker=dict(
                    size=5,
                    color="white",
                    opacity=0.68,
                    line=dict(width=0.5, color="rgba(0,0,0,0.25)"),
                ),
                name="참가자",
                hovertemplate="참가자 위치<br>x=%{x:.1f}, y=%{y:.1f}<extra></extra>",
            )
        )

    # 무대 표시
    if event_type in ["콘서트", "페스티벌"]:
        fig.add_shape(
            type="rect",
            x0=45,
            y0=55,
            x1=61,
            y1=61,
            line=dict(color="white", width=2),
            fillcolor="rgba(20,20,20,0.55)",
        )
        fig.add_annotation(
            x=53,
            y=58,
            text="<b>MAIN STAGE 🎤</b>",
            showarrow=False,
            font=dict(size=12, color="white"),
        )

    fig.update_layout(
        height=650,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,20,27,1)",
        xaxis=dict(range=[0, 100], visible=False, fixedrange=True),
        yaxis=dict(
            range=[0, 100],
            visible=False,
            fixedrange=True,
            scaleanchor="x",
            scaleratio=1,
        ),
        showlegend=False,
    )
    return fig


# -----------------------------
# Main app
# -----------------------------
with st.sidebar:
    st.success(f"👤 {st.session_state.username}님")
    if st.button("로그아웃", use_container_width=True):
        logout()

st.title("🎪 행사장 설계 AI")
st.write("행사 정보를 입력하면 **행사 콘셉트, 공간 구성, 동선, 운영 포인트**를 제안하고, 아래에서 실제 평면도와 참가자 흐름을 시뮬레이션합니다.")

st.markdown("---")

left, right = st.columns([1, 1])

with left:
    st.subheader("1. 행사 기본 정보")
    event_type = st.selectbox(
        "행사장의 유형",
        ["콘서트", "페스티벌", "전시회", "박람회", "기업 행사", "네트워킹 행사", "플리마켓", "팝업스토어", "세미나/컨퍼런스", "기타"],
    )
    people = st.number_input(
        "예상 인원수", min_value=10, max_value=10000, value=200, step=10
    )
    duration = st.number_input(
        "진행 시간 (시간)", min_value=0.5, max_value=24.0, value=4.0, step=0.5
    )
    age_group = st.selectbox(
        "예상 연령대",
        ["어린이 중심", "청소년 중심", "20~30대 중심", "30~40대 중심", "40~60대 중심", "전 연령대 / 가족", "혼합 연령대"],
    )

with right:
    st.subheader("2. 원하는 공간 방향")
    mood = st.selectbox(
        "원하는 분위기",
        ["세련되고 모던한", "활기차고 축제 같은", "따뜻하고 감성적인", "고급스럽고 프리미엄한", "자연스럽고 편안한"],
    )
    fee = st.number_input(
        "예상 입장료 (원)", min_value=0, max_value=1000000, value=15000, step=1000
    )
    place = st.radio("행사 장소", ["실내", "실외"], horizontal=True)

    st.markdown("### 3. 설계하기")
    generate = st.button(
        "✨ 행사장 설계안 만들기",
        type="primary",
        use_container_width=True,
    )

# 결과를 세션에 저장해서 다른 시각화 컨트롤을 움직여도 설계안이 유지되도록 함
if generate:
    st.session_state.design_result = recommend_design(
        event_type, int(people), float(duration), age_group, mood, int(fee), place
    )
    st.session_state.design_inputs = {
        "event_type": event_type,
        "people": int(people),
        "duration": float(duration),
        "age_group": age_group,
        "mood": mood,
        "fee": int(fee),
        "place": place,
    }

if "design_result" not in st.session_state:
    st.markdown(
        """
        ### 👋 이렇게 사용하세요
        1. 행사 유형과 예상 인원을 입력합니다.
        2. 원하는 분위기와 입장료를 선택합니다.
        3. 실내/실외를 선택합니다.
        4. **행사장 설계안 만들기** 버튼을 누르면 공간 구성이 생성됩니다.
        5. 생성 후 **시뮬레이션** 탭에서 참가자 이동과 혼잡도를 확인합니다.
        """
    )
    st.info("💡 이제 결과를 글로만 보는 대신, 실제 2D 행사장 평면도에서 참가자 흐름과 히트맵을 확인할 수 있습니다.")
    st.stop()

result = st.session_state.design_result
saved = st.session_state.design_inputs

# -----------------------------
# AI 기획 결과
# -----------------------------
st.markdown("---")
st.header("🎯 추천 행사장 설계안")

c1, c2, c3 = st.columns(3)
c1.metric("행사 규모", result["scale"])
c2.metric("권장 공간 규모", result["area"])
c3.metric("예상 입장료", f'{saved["fee"]:,}원')

st.subheader("💡 행사 콘셉트")
st.info(
    f'**{saved["mood"]} {saved["event_type"]}**를 콘셉트로, '
    f'{saved["people"]:,}명의 참가자가 {saved["duration"]:g}시간 동안 '
    "자연스럽게 이동하고 머무를 수 있는 공간을 제안합니다."
)

st.subheader("🗺️ 기존 기획 공간")
zone_cols = st.columns(3)
for idx, (name, position, desc) in enumerate(result["zones"]):
    with zone_cols[idx % 3]:
        st.markdown(f"**{name}**")
        st.caption(f"위치: {position}")
        st.write(desc)

st.subheader("🚶 추천 동선")
st.success(result["flow"])

st.subheader("🎨 분위기 연출")
st.write(result["mood"])

# -----------------------------
# Interactive simulator
# -----------------------------
st.markdown("---")
st.header("🧭 행사장 시뮬레이션")
st.caption("아래 화면은 기획 단계에서 공간 배치와 혼잡도를 비교하기 위한 간단한 2D 시뮬레이션입니다.")

sim_left, sim_right = st.columns([3.2, 1])

with sim_right:
    st.subheader("🎛️ 시뮬레이션 설정")

    sim_people = st.slider(
        "시뮬레이션 참가자 수",
        min_value=50,
        max_value=1000,
        value=min(saved["people"], 300),
        step=10,
    )

    event_total_minutes = max(60, int(saved["duration"] * 60))
    current_minute = st.slider(
        "행사 진행 시간(분)",
        min_value=0,
        max_value=event_total_minutes,
        value=min(90, event_total_minutes),
        step=5,
    )

    st.markdown("**공간 활성도 조절**")
    main_weight = st.slider("메인존", 0.5, 2.0, 1.0, 0.1)
    content_weight = st.slider("체험/콘텐츠존", 0.5, 2.0, 1.0, 0.1)
    rest_weight = st.slider("휴식존", 0.5, 2.0, 1.0, 0.1)
    photo_weight = st.slider("포토존", 0.5, 2.0, 1.0, 0.1)
    food_weight = st.slider("푸드존", 0.5, 2.0, 1.0, 0.1)

    st.markdown("**표시 옵션**")
    show_heatmap = st.checkbox("혼잡도 히트맵", value=True)
    show_people = st.checkbox("참가자 위치", value=True)
    show_paths = st.checkbox("추천 동선 화살표", value=True)

weights = {
    "② 메인존": main_weight,
    "③ 체험/콘텐츠존": content_weight,
    "④ 휴식존": rest_weight,
    "⑤ 포토존": photo_weight,
    "푸드존": food_weight,
    "① 웰컴존": 1.0,
}

positions, destinations = simulate_agents(
    sim_people,
    current_minute,
    saved["event_type"],
    saved["age_group"],
    weights,
)
occupancy = zone_occupancy(positions)

peak_zone = max(occupancy, key=occupancy.get)
peak_count = occupancy[peak_zone]
peak_capacity = VENUE_ZONES[peak_zone]["capacity"]
peak_pct = peak_count / peak_capacity * 100

corridor_scores = {
    "웰컴존 → 메인존": occupancy["① 웰컴존"] * 0.45 + occupancy["② 메인존"] * 0.35,
    "메인존 → 포토존": occupancy["② 메인존"] * 0.40 + occupancy["⑤ 포토존"] * 0.60,
    "메인존 → 휴식존": occupancy["② 메인존"] * 0.45 + occupancy["④ 휴식존"] * 0.55,
    "메인존 → 체험존": occupancy["② 메인존"] * 0.45 + occupancy["③ 체험/콘텐츠존"] * 0.55,
}
bottleneck = max(corridor_scores, key=corridor_scores.get)

with sim_left:
    fig = build_floorplan(
        positions=positions,
        occupancy=occupancy,
        event_type=saved["event_type"],
        show_people=show_people,
        show_heatmap=show_heatmap,
        show_paths=show_paths,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("현재 인원", f"{sim_people:,}명")
    k2.metric("최대 혼잡 구역", peak_zone.replace("① ", "").replace("② ", "").replace("③ ", "").replace("④ ", "").replace("⑤ ", "").replace("⑥ ", ""))
    k3.metric("점유율", f"{peak_pct:.0f}%")
    k4.metric("주의 동선", bottleneck)

st.subheader("📊 공간별 예상 체류 인원")
rows = []
for zone_name, zone in VENUE_ZONES.items():
    count = occupancy[zone_name]
    capacity = zone["capacity"]
    pct = count / capacity * 100
    status = "🔴 혼잡" if pct >= 85 else "🟠 주의" if pct >= 65 else "🟢 여유"
    rows.append(
        {
            "공간": zone_name,
            "예상 인원": count,
            "수용 가능": capacity,
            "점유율": f"{pct:.0f}%",
            "상태": status,
        }
    )

st.dataframe(
    pd.DataFrame(rows).sort_values("예상 인원", ascending=False),
    hide_index=True,
    use_container_width=True,
)

st.subheader("⏱️ 시간대별 혼잡도")

trend_times = np.arange(
    0,
    event_total_minutes + 1,
    max(10, event_total_minutes // 12),
)
trend_rows = []

# 그래프는 계산량을 줄이기 위해 최대 13개 시점으로 샘플링
for t in trend_times:
    p, _ = simulate_agents(
        sim_people,
        int(t),
        saved["event_type"],
        saved["age_group"],
        weights,
    )
    occ = zone_occupancy(p)
    for zone_name, count in occ.items():
        trend_rows.append(
            {"시간": int(t), "공간": zone_name, "인원": count}
        )

trend_df = pd.DataFrame(trend_rows)
trend_fig = go.Figure()

for zone_name in VENUE_ZONES:
    part = trend_df[trend_df["공간"] == zone_name]
    trend_fig.add_trace(
        go.Scatter(
            x=part["시간"],
            y=part["인원"],
            mode="lines+markers",
            name=zone_name,
        )
    )

trend_fig.update_layout(
    height=380,
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="행사 진행 시간(분)",
    yaxis_title="예상 체류 인원",
    legend=dict(orientation="h", y=1.12),
)
st.plotly_chart(trend_fig, use_container_width=True, config={"displaylogo": False})

st.subheader("🧠 시뮬레이션 해석")
warnings = []

if peak_pct >= 100:
    warnings.append(
        f"{peak_zone}의 예상 인원이 수용 규모를 넘어섭니다. 공간을 넓히거나 인근 공간으로 참가자를 분산하는 방안을 검토하세요."
    )
elif peak_pct >= 85:
    warnings.append(
        f"{peak_zone}이 혼잡해질 가능성이 큽니다. 입구·통로 폭을 넓히거나 체류형 콘텐츠를 분산하는 것이 좋습니다."
    )

if occupancy["⑤ 포토존"] > VENUE_ZONES["⑤ 포토존"]["capacity"] * 0.8:
    warnings.append("포토존 주변에 대기열이 형성될 가능성이 있으므로 대기 공간을 따로 확보하세요.")

if occupancy["④ 휴식존"] < 15:
    warnings.append("휴식존 이용률이 낮습니다. 메인존과의 연결성을 높이거나 위치를 메인 동선 쪽으로 이동해 볼 수 있습니다.")

if occupancy["③ 체험/콘텐츠존"] > VENUE_ZONES["③ 체험/콘텐츠존"]["capacity"] * 0.8:
    warnings.append("체험/콘텐츠존이 혼잡합니다. 프로그램을 여러 위치로 분산하거나 회차를 나누는 방법을 고려하세요.")

if not warnings:
    warnings.append("현재 설정에서는 특정 구역에 과도한 집중이 나타나지 않습니다. 시간대별 그래프를 함께 확인해 보세요.")

for warning in warnings:
    st.write("• " + warning)

st.markdown("---")
st.subheader("👥 인원 및 안전 운영")
st.write(result["crowd"])
st.write(result["safety"])

st.subheader("🏠 장소 조건")
st.write(result["venue"])
st.write(result["weather"])

st.subheader("💰 입장료 기반 운영 전략")
st.write(result["budget"])

st.markdown("---")
st.caption(
    "※ 히트맵과 이동 결과는 행사 기획용의 단순화된 시뮬레이션입니다. "
    "실제 행사에서는 현장 평면도, 출입구 수, 통로 폭, 비상 동선, 시설/소방 기준 등을 별도로 검토해야 합니다."
)
