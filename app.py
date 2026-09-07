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
# Main app
# -----------------------------
with st.sidebar:
    st.success(f"👤 {st.session_state.username}님")
    if st.button("로그아웃", use_container_width=True):
        logout()

st.title("🎪 행사장 설계 AI")
st.write("행사 정보를 입력하면 **행사장 콘셉트, 공간 구성, 동선, 운영 포인트**를 한 번에 제안합니다.")

st.markdown("---")

left, right = st.columns([1, 1])

with left:
    st.subheader("1. 행사 기본 정보")
    event_type = st.selectbox(
        "행사장의 유형",
        ["콘서트", "페스티벌", "전시회", "박람회", "기업 행사", "네트워킹 행사", "플리마켓", "팝업스토어", "세미나/컨퍼런스", "기타"],
    )
    people = st.number_input("예상 인원수", min_value=10, max_value=10000, value=200, step=10)
    duration = st.number_input("진행 시간 (시간)", min_value=0.5, max_value=24.0, value=4.0, step=0.5)

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
    fee = st.number_input("예상 입장료 (원)", min_value=0, max_value=1000000, value=15000, step=1000)
    place = st.radio("행사 장소", ["실내", "실외"], horizontal=True)

    st.markdown("### 3. 설계하기")
    generate = st.button("✨ 행사장 설계안 만들기", type="primary", use_container_width=True)

if generate:
    result = recommend_design(event_type, int(people), float(duration), age_group, mood, int(fee), place)

    st.markdown("---")
    st.header("🎯 추천 행사장 설계안")

    c1, c2, c3 = st.columns(3)
    c1.metric("행사 규모", result["scale"])
    c2.metric("권장 공간 규모", result["area"])
    c3.metric("예상 입장료", f"{fee:,}원")

    st.subheader("💡 행사 콘셉트")
    st.info(
        f"**{mood} {event_type}**를 콘셉트로, {people:,}명의 참가자가 "
        f"{duration:g}시간 동안 자연스럽게 이동하고 머무를 수 있는 공간을 제안합니다."
    )

    st.subheader("🗺️ 공간 배치")
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

    st.subheader("👥 인원 및 안전 운영")
    st.write(result["crowd"])
    st.write(result["safety"])

    st.subheader("🏠 장소 조건")
    st.write(result["venue"])
    st.write(result["weather"])

    st.subheader("💰 입장료 기반 운영 전략")
    st.write(result["budget"])

    st.markdown("---")
    st.caption("※ 본 결과는 입력값을 기반으로 한 기획 초안입니다. 실제 행사에서는 소방·전기·시설·안전 관련 법규와 현장 조건을 별도로 검토해야 합니다.")
else:
    st.markdown(
        """
        ### 👋 이렇게 사용하세요
        1. 행사 유형과 예상 인원을 입력합니다.
        2. 원하는 분위기와 입장료를 선택합니다.
        3. 실내/실외를 선택합니다.
        4. **행사장 설계안 만들기** 버튼을 누르면 공간 구성이 생성됩니다.
        """
    )
