import streamlit as st
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from PIL import Image, ImageDraw

try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_OK = True
except ImportError:
    CANVAS_OK = False


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="행사장 설계 AI",
    page_icon="🎪",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = Path(__file__).parent / "users.db"

CANVAS_W = 900
CANVAS_H = 600


# =========================================================
# 기본 행사장 구역
# =========================================================

DEFAULT_ZONES = {
    "① 웰컴존": {
        "x": 7,
        "y": 76,
        "w": 22,
        "h": 14,
        "capacity": 70,
        "kind": "welcome",
    },

    "② 메인존": {
        "x": 34,
        "y": 35,
        "w": 38,
        "h": 30,
        "capacity": 230,
        "kind": "main",
    },

    "③ 체험/콘텐츠존": {
        "x": 7,
        "y": 44,
        "w": 23,
        "h": 22,
        "capacity": 100,
        "kind": "content",
    },

    "④ 휴식존": {
        "x": 7,
        "y": 10,
        "w": 26,
        "h": 22,
        "capacity": 110,
        "kind": "rest",
    },

    "⑤ 포토존": {
        "x": 76,
        "y": 73,
        "w": 18,
        "h": 16,
        "capacity": 90,
        "kind": "photo",
    },

    "⑥ 운영존": {
        "x": 76,
        "y": 10,
        "w": 18,
        "h": 18,
        "capacity": 60,
        "kind": "ops",
    },

    "⑦ 푸드존": {
        "x": 76,
        "y": 36,
        "w": 18,
        "h": 26,
        "capacity": 100,
        "kind": "food",
    },

    "♿ 접근성 휴식/지원": {
        "x": 35,
        "y": 12,
        "w": 18,
        "h": 14,
        "capacity": 45,
        "kind": "access",
    },
}


ZONE_COLORS = {
    "welcome": (70, 160, 235),
    "main": (245, 180, 55),
    "content": (75, 195, 135),
    "rest": (95, 155, 235),
    "photo": (180, 115, 215),
    "ops": (145, 145, 145),
    "food": (245, 125, 70),
    "access": (50, 190, 175),
}


# =========================================================
# 로그인 / 회원가입
# =========================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()

    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


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
            """
            INSERT INTO users
            (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (
                username,
                hash_password(password),
                datetime.now().isoformat(
                    timespec="seconds"
                ),
            ),
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
        """
        SELECT password_hash
        FROM users
        WHERE username = ?
        """,
        (username.strip(),),
    ).fetchone()

    conn.close()

    return bool(
        row
        and row[0] == hash_password(password)
    )


def logout():

    st.session_state.logged_in = False
    st.session_state.username = ""

    st.rerun()


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""


# =========================================================
# 행사 기획 추천
# =========================================================

def recommend_design(
    event_type,
    people,
    duration,
    age_group,
    mood,
    fee,
    place,
):

    # 행사 규모
    if people <= 50:

        scale = "소규모"

        area = (
            f"약 {max(60, people * 2)}"
            f"~{max(90, people * 3)}㎡"
        )

    elif people <= 200:

        scale = "중규모"

        area = (
            f"약 {people * 1.5:.0f}"
            f"~{people * 2.2:.0f}㎡"
        )

    else:

        scale = "대규모"

        area = (
            f"약 {people * 1.2:.0f}"
            f"~{people * 1.8:.0f}㎡"
        )

    # 동선
    if duration <= 2:

        flow = (
            "입장 → 핵심 프로그램 → "
            "자유 관람 → 퇴장"
        )

    elif duration <= 5:

        flow = (
            "입장 → 오프닝 → 메인 프로그램 → "
            "휴식/체험 → 클로징"
        )

    else:

        flow = (
            "입장 → 오프닝 → 세션/체험 → "
            "식음/휴식 → 메인 프로그램 → 클로징"
        )

    # 장소
    if place == "실내":

        venue = (
            "천장고·기둥·출입구 위치를 먼저 확인하고 "
            "무대·객석·체험존을 중앙 동선 기준으로 배치합니다."
        )

        weather = (
            "실내이므로 우천 대응 부담이 낮고 "
            "조명·음향 연출에 집중하기 좋습니다."
        )

    else:

        venue = (
            "그늘·휴식존·화장실·전기·우천 대피 동선을 "
            "입구와 가까운 위치에 우선 배치합니다."
        )

        weather = (
            "야외 행사이므로 우천 및 폭염/한파 대비 "
            "플랜 B를 확보합니다."
        )

    # 안전
    if (
        "가족" in age_group
        or "어린이" in age_group
    ):

        safety = (
            "보호자 대기존, 넓은 통로, "
            "안전한 가구 배치를 우선합니다."
        )

    elif "청소년" in age_group:

        safety = (
            "친구 단위 이동이 많으므로 "
            "포토존·체험존을 분산합니다."
        )

    elif (
        "중장년" in age_group
        or "40~60" in age_group
    ):

        safety = (
            "좌석·휴식 공간과 안내 표지, "
            "화장실 접근성을 높입니다."
        )

    else:

        safety = (
            "휴식·대기·포토존을 "
            "주 동선과 적절히 분산합니다."
        )

    mood_map = {

        "세련되고 모던한":
            "미니멀 사인·간접조명·뉴트럴 컬러를 사용합니다.",

        "활기차고 축제 같은":
            "포인트 컬러·스트링 조명·대형 포토월을 활용합니다.",

        "따뜻하고 감성적인":
            "우드·웜톤 조명·패브릭 장식을 사용합니다.",

        "고급스럽고 프리미엄한":
            "넓은 여백·메탈·블랙·집중 조명을 사용합니다.",

        "자연스럽고 편안한":
            "식물·우드·자연 소재와 편안한 휴식 공간을 구성합니다.",
    }

    budget = (

        "저비용 참여 콘텐츠와 동선 효율에 집중합니다."

        if fee < 10000

        else

        "핵심 체험 1~2개와 포토존을 결합하기 좋습니다."

        if fee < 30000

        else

        "프리미엄 웰컴존·예약형 프로그램·라운지 등을 추가하기 좋습니다."
    )

    zones = [

        (
            "① 웰컴존",
            "입구",
            "등록·티켓 확인·행사 안내",
        ),

        (
            "② 메인존",
            "중앙",
            f"{event_type} 핵심 프로그램",
        ),

        (
            "③ 체험/콘텐츠존",
            "메인존 주변",
            "참가형 콘텐츠",
        ),

        (
            "④ 휴식존",
            "동선 가장자리",
            "대기·휴식·음료",
        ),

        (
            "⑤ 포토존",
            "입구 또는 메인존 인근",
            "사진·SNS 콘텐츠",
        ),

        (
            "⑥ 운영존",
            "후면/측면",
            "스태프·장비 관리",
        ),
    ]

    if people > 500:

        crowd = (
            "대규모 행사이므로 입·퇴장 동선을 분리하고 "
            "병목 구간에 안내 인력을 배치하세요."
        )

    elif people > 200:

        crowd = (
            "메인존 앞 대기열과 체험존별 대기 공간을 "
            "별도로 확보하세요."
        )

    else:

        crowd = (
            "핵심 공간을 서로 가깝게 묶어 "
            "몰입감 있는 구성이 가능합니다."
        )

    return {

        "scale": scale,

        "area": area,

        "flow": flow,

        "venue": venue,

        "weather": weather,

        "safety": safety,

        "mood": mood_map.get(
            mood,
            "행사 목적에 맞는 통일감 있는 공간을 구성합니다.",
        ),

        "budget": budget,

        "crowd": crowd,

        "zones": zones,
    }


# =========================================================
# 공통 유틸
# =========================================================

def clean_zones(zones):

    if not isinstance(zones, dict):
        zones = {}

    result = {}

    for name, default in DEFAULT_ZONES.items():

        z = zones.get(name, {})

        result[name] = {

            "x": float(
                z.get("x", default["x"])
            ),

            "y": float(
                z.get("y", default["y"])
            ),

            "w": float(
                z.get("w", default["w"])
            ),

            "h": float(
                z.get("h", default["h"])
            ),

            "capacity": int(
                z.get(
                    "capacity",
                    default["capacity"],
                )
            ),

            "kind": z.get(
                "kind",
                default["kind"],
            ),
        }

    return result


def centers(zones):

    return {

        name: (
            z["x"] + z["w"] / 2,
            z["y"] + z["h"] / 2,
        )

        for name, z in zones.items()
    }


def weighted_choice(
    rng,
    choices,
    weights,
):

    p = np.asarray(
        weights,
        dtype=float,
    )

    p = np.clip(
        p,
        0.001,
        None,
    )

    p /= p.sum()

    return rng.choice(
        choices,
        p=p,
    )


# =========================================================
# 참가자 이동 시뮬레이션
# =========================================================

def target_zone(
    event_type,
    u,
    minute,
    weights,
    needs,
    rng,
):

    # 입장
    if minute <= 20:

        choices = [

            "① 웰컴존",

            "⑤ 포토존",

            "⑦ 푸드존",

            "♿ 접근성 휴식/지원",
        ]

        probs = [
            0.68,
            0.14,
            0.12,
            0.06,
        ]

        return weighted_choice(
            rng,
            choices,
            probs,
        )

    # 초반 주요 프로그램
    if minute <= 120:

        if event_type in [
            "콘서트",
            "페스티벌",
        ]:

            choices = [

                "② 메인존",

                "⑤ 포토존",

                "④ 휴식존",

                "⑦ 푸드존",

                "♿ 접근성 휴식/지원",
            ]

            probs = [
                0.68,
                0.10,
                0.08,
                0.08,
                0.06,
            ]

        else:

            choices = [

                "② 메인존",

                "③ 체험/콘텐츠존",

                "④ 휴식존",

                "⑤ 포토존",

                "⑦ 푸드존",

                "♿ 접근성 휴식/지원",
            ]

            probs = [
                0.43,
                0.23,
                0.12,
                0.08,
                0.09,
                0.05,
            ]

    # 중후반
    else:

        phase = int(
            (minute - 120) // 20
        ) % 4

        choices = [

            "② 메인존",

            "③ 체험/콘텐츠존",

            "④ 휴식존",

            "⑤ 포토존",

            "⑦ 푸드존",

            "♿ 접근성 휴식/지원",
        ]

        phases = [

            [
                0.40,
                0.18,
                0.12,
                0.11,
                0.14,
                0.05,
            ],

            [
                0.30,
                0.21,
                0.18,
                0.12,
                0.14,
                0.05,
            ],

            [
                0.33,
                0.13,
                0.12,
                0.25,
                0.12,
                0.05,
            ],

            [
                0.27,
                0.17,
                0.14,
                0.14,
                0.23,
                0.05,
            ],
        ]

        probs = phases[phase]

    adjusted = []

    for zone, p in zip(
        choices,
        probs,
    ):

        modifier = weights.get(
            zone,
            1.0,
        )

        if (
            zone
            in [
                "④ 휴식존",
                "♿ 접근성 휴식/지원",
            ]
            and needs
        ):
            modifier *= 1.20

        adjusted.append(
            p * modifier
        )

    return weighted_choice(
        rng,
        choices,
        adjusted,
    )


def simulate_agents(
    count,
    minute,
    event_type,
    zones,
    weights,
    needs,
):

    rng = np.random.default_rng(
        20260907
    )

    u = rng.random(count)

    personal = rng.random(count)

    c = centers(zones)

    prev_minute = max(
        0,
        minute - 15,
    )

    positions = np.zeros(
        (count, 2)
    )

    for i in range(count):

        now = target_zone(
            event_type,
            u[i],
            minute,
            weights,
            needs,
            rng,
        )

        prev = target_zone(
            event_type,
            u[i],
            prev_minute,
            weights,
            needs,
            rng,
        )

        start = np.array(
            c[prev],
            dtype=float,
        )

        end = np.array(
            c[now],
            dtype=float,
        )

        t = np.clip(
            (minute - prev_minute)
            / 15.0,
            0,
            1,
        )

        t = np.clip(
            (
                t
                - 0.18
                - personal[i] * 0.18
            )
            / 0.64,
            0,
            1,
        )

        t = (
            t
            * t
            * (3 - 2 * t)
        )

        pos = (
            start * (1 - t)
            + end * t
        )

        pos += rng.normal(
            0,
            1.7,
            2,
        )

        pos[0] = np.clip(
            pos[0],
            1,
            99,
        )

        pos[1] = np.clip(
            pos[1],
            1,
            99,
        )

        positions[i] = pos

    return positions


# =========================================================
# 밀집도
# =========================================================

def zone_occupancy(
    points,
    zones,
):

    result = {}

    for name, z in zones.items():

        cx = (
            z["x"]
            + z["w"] / 2
        )

        cy = (
            z["y"]
            + z["h"] / 2
        )

        rx = max(
            5,
            z["w"] * 0.52,
        )

        ry = max(
            5,
            z["h"] * 0.52,
        )

        distance = (

            (
                points[:, 0] - cx
            ) / rx

        ) ** 2 + (

            (
                points[:, 1] - cy
            ) / ry

        ) ** 2

        result[name] = int(
            (
                distance <= 1
            ).sum()
        )

    return result


def heatmap(
    points,
    grid=75,
    sigma=4.5,
):

    xs = np.linspace(
        0,
        100,
        grid,
    )

    ys = np.linspace(
        0,
        100,
        grid,
    )

    X, Y = np.meshgrid(
        xs,
        ys,
    )

    H = np.zeros_like(X)

    for start in range(
        0,
        len(points),
        250,
    ):

        batch = points[
            start : start + 250
        ]

        dx = (
            X[:, :, None]
            - batch[:, 0]
            [None, None, :]
        )

        dy = (
            Y[:, :, None]
            - batch[:, 1]
            [None, None, :]
        )

        H += np.exp(
            -(
                dx * dx
                + dy * dy
            )
            / (
                2
                * sigma
                * sigma
            )
        ).sum(
            axis=2
        )

    return xs, ys, H


# =========================================================
# 드래그형 배치
# =========================================================

def canvas_json(zones):

    objects = []

    for name, z in zones.items():

        x = (
            z["x"]
            / 100
            * CANVAS_W
        )

        y = (
            1
            - (
                z["y"]
                + z["h"]
            )
            / 100
        ) * CANVAS_H

        w = (
            z["w"]
            / 100
            * CANVAS_W
        )

        h = (
            z["h"]
            / 100
            * CANVAS_H
        )

        r, g, b = ZONE_COLORS[
            z["kind"]
        ]

        objects.append(
            {
                "type": "rect",

                "left": x,

                "top": y,

                "width": w,

                "height": h,

                "fill": (
                    f"rgba("
                    f"{r},{g},{b},0.68)"
                ),

                "stroke": (
                    "rgba("
                    "255,255,255,0.95)"
                ),

                "strokeWidth": 2,

                "rx": 8,

                "ry": 8,

                "selectable": True,
            }
        )

    return {
        "version": "5.3.0",
        "objects": objects,
    }


def zones_from_canvas(
    data,
    old_zones,
):

    if (
        not data
        or "objects" not in data
    ):
        return (
            old_zones,
            False,
        )

    rects = [

        o

        for o in data["objects"]

        if o.get("type")
        == "rect"
    ]

    names = list(
        old_zones.keys()
    )

    if len(rects) != len(names):
        return (
            old_zones,
            False,
        )

    new = clean_zones(
        old_zones
    )

    changed = False

    for name, obj in zip(
        names,
        rects,
    ):

        left = float(
            obj.get(
                "left",
                0,
            )
        )

        top = float(
            obj.get(
                "top",
                0,
            )
        )

        width = (

            float(
                obj.get(
                    "width",
                    100,
                )
            )

            * float(
                obj.get(
                    "scaleX",
                    1,
                )
            )
        )

        height = (

            float(
                obj.get(
                    "height",
                    100,
                )
            )

            * float(
                obj.get(
                    "scaleY",
                    1,
                )
            )
        )

        x = np.clip(
            left
            / CANVAS_W
            * 100,

            0,
            95,
        )

        w = np.clip(
            width
            / CANVAS_W
            * 100,

            8,
            45,
        )

        h = np.clip(
            height
            / CANVAS_H
            * 100,

            7,
            40,
        )

        y = np.clip(
            100
            - top
            / CANVAS_H
            * 100
            - h,

            1,
            99 - h,
        )

        old = new[name]

        if max(
            abs(old["x"] - x),
            abs(old["y"] - y),
            abs(old["w"] - w),
            abs(old["h"] - h),
        ) > 0.3:

            changed = True

        old.update(

            x=float(x),

            y=float(y),

            w=float(w),

            h=float(h),
        )

    return (
        new,
        changed,
    )


def make_background():

    img = Image.new(
        "RGB",
        (
            CANVAS_W,
            CANVAS_H,
        ),
        (18, 22, 30),
    )

    draw = ImageDraw.Draw(img)

    # 그리드
    for x in range(
        0,
        CANVAS_W,
        45,
    ):

        draw.line(
            (
                x,
                0,
                x,
                CANVAS_H,
            ),
            fill=(
                40,
                46,
                58,
            ),
            width=1,
        )

    for y in range(
        0,
        CANVAS_H,
        45,
    ):

        draw.line(
            (
                0,
                y,
                CANVAS_W,
                y,
            ),
            fill=(
                40,
                46,
                58,
            ),
            width=1,
        )

    draw.text(
        (18, 15),
        "행사장 캔버스 · 구역을 드래그하여 배치",
        fill=(
            240,
            240,
            245,
        ),
    )

    return img


# =========================================================
# 추천 배치
# =========================================================

def recommended_layout(
    event_type,
    people,
    needs,
):

    z = clean_zones(
        DEFAULT_ZONES
    )

    if event_type in [
        "콘서트",
        "페스티벌",
    ]:

        z["① 웰컴존"].update(
            x=6,
            y=77,
            w=23,
            h=13,
        )

        z["② 메인존"].update(
            x=33,
            y=34,
            w=40,
            h=33,
        )

        z["③ 체험/콘텐츠존"].update(
            x=6,
            y=42,
            w=23,
            h=25,
        )

        z["④ 휴식존"].update(
            x=7,
            y=9,
            w=27,
            h=22,
        )

        z["⑤ 포토존"].update(
            x=77,
            y=75,
            w=16,
            h=14,
        )

        z["⑦ 푸드존"].update(
            x=76,
            y=37,
            w=18,
            h=27,
        )

    else:

        z["① 웰컴존"].update(
            x=6,
            y=76,
            w=23,
            h=14,
        )

        z["② 메인존"].update(
            x=37,
            y=36,
            w=30,
            h=28,
        )

        z["③ 체험/콘텐츠존"].update(
            x=7,
            y=43,
            w=26,
            h=24,
        )

        z["④ 휴식존"].update(
            x=7,
            y=9,
            w=27,
            h=23,
        )

        z["⑤ 포토존"].update(
            x=70,
            y=70,
            w=23,
            h=17,
        )

        z["⑦ 푸드존"].update(
            x=71,
            y=31,
            w=23,
            h=27,
        )

    # 대규모
    if people >= 500:

        z["① 웰컴존"]["w"] = min(
            28,
            z["① 웰컴존"]["w"] + 4,
        )

        z["④ 휴식존"]["w"] = min(
            31,
            z["④ 휴식존"]["w"] + 4,
        )

    # 접근성 요구가 있는 경우
    if needs:

        z[
            "♿ 접근성 휴식/지원"
        ].update(
            x=34,
            y=15,
            w=23,
            h=15,
        )

        z["④ 휴식존"].update(
            x=7,
            y=8,
            w=29,
            h=24,
        )

    return clean_zones(z)


def placement_score(
    zones,
    people,
    needs,
):

    score = 100.0

    c = centers(zones)

    names = list(zones)

    # 공간 겹침 평가
    for i, a_name in enumerate(
        names
    ):

        a = zones[a_name]

        for b_name in names[
            i + 1 :
        ]:

            b = zones[b_name]

            ow = max(
                0,
                min(
                    a["x"]
                    + a["w"],
                    b["x"]
                    + b["w"],
                )
                - max(
                    a["x"],
                    b["x"],
                ),
            )

            oh = max(
                0,
                min(
                    a["y"]
                    + a["h"],
                    b["y"]
                    + b["h"],
                )
                - max(
                    a["y"],
                    b["y"],
                ),
            )

            overlap = (
                ow * oh
            )

            score -= min(
                14,
                overlap * 0.25,
            )

    # 주요 동선 거리
    for a, b in [

        (
            "① 웰컴존",
            "② 메인존",
        ),

        (
            "② 메인존",
            "④ 휴식존",
        ),

        (
            "② 메인존",
            "⑤ 포토존",
        ),

        (
            "② 메인존",
            "⑦ 푸드존",
        ),
    ]:

        dist = np.linalg.norm(

            np.array(c[a])
            - np.array(c[b])
        )

        score -= max(
            0,
            dist - 42,
        ) * 0.25

    # 접근성 공간 위치
    if needs:

        access = np.array(
            c[
                "♿ 접근성 휴식/지원"
            ]
        )

        main = np.array(
            c["② 메인존"]
        )

        rest = np.array(
            c["④ 휴식존"]
        )

        score -= max(
            0,
            np.linalg.norm(
                access - main
            ) - 35,
        ) * 0.5

        score -= max(
            0,
            np.linalg.norm(
                access - rest
            ) - 28,
        ) * 0.3

    return float(
        np.clip(
            score,
            0,
            100,
        )
    )


# =========================================================
# 포용적 행사 설계
# =========================================================

def accessibility_tips(
    needs,
    goals,
):

    tips = []

    if (
        "이동 보조기기 접근"
        in needs
        or "무장애 동선"
        in goals
    ):

        tips.extend(

            [
                "입구 → 메인존 → 휴식존 → 화장실의 주요 경로가 끊기지 않도록 설계합니다.",

                "휠체어·유모차·보행 보조기기가 통과하고 회전할 수 있는 여유 공간을 확보합니다.",
            ]

        )

    if (
        "감각 과부하 완화"
        in needs
        or "조용한 휴식 공간"
        in goals
    ):

        tips.append(
            "음악·조명 강도가 높은 공간에서 떨어진 조용한 휴식 공간을 마련합니다."
        )

    if (
        "시각 정보 보완"
        in needs
        or "큰 글씨·고대비 안내"
        in goals
    ):

        tips.append(
            "색상만으로 정보를 전달하지 않고 큰 글씨·고대비·아이콘을 함께 사용합니다."
        )

    if (
        "청각 정보 보완"
        in needs
        or "수어/자막 등 청각 정보 보완"
        in goals
    ):

        tips.append(
            "중요한 안내와 공연 정보에 자막 등 대체 정보 채널을 제공합니다."
        )

    if "어린이 동반" in needs:

        tips.append(
            "보호자와 어린이가 함께 기다리고 쉴 수 있는 공간을 주요 동선 가까이에 둡니다."
        )

    if (
        "저비용 참여"
        in needs
        or "무료 물/쉼터"
        in goals
    ):

        tips.append(
            "기본적인 물·휴식·안내 서비스를 유료 콘텐츠와 분리해 접근성을 높입니다."
        )

    if (
        "외국어 안내"
        in needs
        or "다국어 안내"
        in goals
    ):

        tips.append(
            "핵심 안내를 다국어 표지와 쉬운 문장으로 제공하는 것을 검토합니다."
        )

    if not tips:

        tips.append(
            "모든 참가자가 이동·정보·휴식 측면에서 장벽을 덜 느끼도록 공간을 처음부터 포용적으로 설계합니다."
        )

    return tips


# =========================================================
# 로그인 화면
# =========================================================

if not st.session_state.logged_in:

    st.title(
        "🎪 행사장 디자이너"
    )

    st.caption(
        "행사 조건을 입력하면 공간 구성과 운영 아이디어를 설계합니다."
    )

    login_tab, signup_tab = st.tabs(
        [
            "로그인",
            "회원가입",
        ]
    )

    with login_tab:

        with st.form(
            "login"
        ):

            username = st.text_input(
                "아이디"
            )

            password = st.text_input(
                "비밀번호",
                type="password",
            )

            submit = st.form_submit_button(
                "로그인",
                use_container_width=True,
            )

        if submit:

            if authenticate(
                username,
                password,
            ):

                st.session_state.logged_in = True

                st.session_state.username = (
                    username.strip()
                )

                st.rerun()

            else:

                st.error(
                    "아이디 또는 비밀번호가 올바르지 않습니다."
                )

    with signup_tab:

        with st.form(
            "signup"
        ):

            new_username = st.text_input(
                "새 아이디"
            )

            new_password = st.text_input(
                "새 비밀번호",
                type="password",
            )

            new_password2 = st.text_input(
                "비밀번호 확인",
                type="password",
            )

            submit = st.form_submit_button(
                "회원가입",
                use_container_width=True,
            )

        if submit:

            if (
                new_password
                != new_password2
            ):

                st.error(
                    "비밀번호가 일치하지 않습니다."
                )

            else:

                ok, msg = create_user(
                    new_username,
                    new_password,
                )

                (
                    st.success
                    if ok
                    else st.error
                )(msg)

    st.info(
        "💡 프로토타입용 기본 로그인 기능입니다."
    )

    st.stop()


# =========================================================
# 사이드바
# =========================================================

with st.sidebar:

    st.success(
        f"👤 {st.session_state.username}님"
    )

    if st.button(
        "로그아웃",
        use_container_width=True,
    ):

        logout()


# =========================================================
# 메인 화면
# =========================================================

st.title(
    "🎪 행사장 설계 AI"
)

st.write(
    "기획안뿐 아니라 "
    "**실제 공간 배치·예상 혼잡도·밀집도·추천 배치·포용적 행사 설계**까지 확인합니다."
)


left, right = st.columns(2)


# =========================================================
# 기본 행사 정보
# =========================================================

with left:

    st.subheader(
        "1. 행사 기본 정보"
    )

    event_type = st.selectbox(
        "행사 유형",

        [
            "콘서트",
            "페스티벌",
            "전시회",
            "박람회",
            "기업 행사",
            "네트워킹 행사",
            "플리마켓",
            "팝업스토어",
            "세미나/컨퍼런스",
            "기타",
        ],
    )

    people = st.number_input(
        "예상 인원수",
        min_value=10,
        max_value=10000,
        value=300,
        step=10,
    )

    duration = st.number_input(
        "진행 시간(시간)",
        min_value=0.5,
        max_value=24.0,
        value=4.0,
        step=0.5,
    )

    age_group = st.selectbox(
        "예상 연령대",

        [
            "어린이 중심",
            "청소년 중심",
            "20~30대 중심",
            "30~40대 중심",
            "40~60대 중심",
            "전 연령대 / 가족",
            "혼합 연령대",
        ],
    )


# =========================================================
# 공간 방향
# =========================================================

with right:

    st.subheader(
        "2. 공간 방향"
    )

    mood = st.selectbox(
        "원하는 분위기",

        [
            "세련되고 모던한",
            "활기차고 축제 같은",
            "따뜻하고 감성적인",
            "고급스럽고 프리미엄한",
            "자연스럽고 편안한",
        ],
    )

    fee = st.number_input(
        "예상 입장료(원)",
        min_value=0,
        max_value=1000000,
        value=15000,
        step=1000,
    )

    place = st.radio(
        "행사 장소",
        [
            "실내",
            "실외",
        ],
        horizontal=True,
    )


# =========================================================
# 접근성 설정
# =========================================================

st.markdown("---")

st.subheader(
    "♿ 모두를 위한 접근성 설계"
)

st.caption(
    "특정 집단을 하나의 유형으로 가정하기보다 "
    "실제 공간에서 필요한 접근성 요구를 선택해 반영합니다."
)

a1, a2 = st.columns(2)


with a1:

    needs = st.multiselect(

        "우선 반영할 접근성 요구",

        [
            "이동 보조기기 접근",
            "감각 과부하 완화",
            "시각 정보 보완",
            "청각 정보 보완",
            "어린이 동반",
            "중장년층 편의",
            "고령 참가자 편의",
            "외국어 안내",
            "저비용 참여",
        ],

        default=[
            "이동 보조기기 접근",
            "감각 과부하 완화",
        ],
    )


with a2:

    goals = st.multiselect(

        "운영 장치",

        [
            "무장애 동선",
            "접근 가능한 화장실",
            "낮은 높이 안내 데스크",
            "큰 글씨·고대비 안내",
            "수어/자막 등 청각 정보 보완",
            "조용한 휴식 공간",
            "무료 물/쉼터",
            "다국어 안내",
        ],

        default=[
            "무장애 동선",
            "조용한 휴식 공간",
            "큰 글씨·고대비 안내",
        ],
    )


# =========================================================
# 설계 버튼
# =========================================================

generate = st.button(
    "✨ 행사장 설계안 만들기",
    type="primary",
    use_container_width=True,
)


if generate:

    st.session_state.design_result = (
        recommend_design(
            event_type,
            int(people),
            float(duration),
            age_group,
            mood,
            int(fee),
            place,
        )
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

    st.session_state.needs = list(
        needs
    )

    st.session_state.goals = list(
        goals
    )

    st.session_state.venue_zones = (
        recommended_layout(
            event_type,
            int(people),
            needs,
        )
    )

    st.session_state.layout_version = (
        st.session_state.get(
            "layout_version",
            0,
        )
        + 1
    )


if "design_result" not in st.session_state:

    st.info(
        "행사 조건을 입력한 뒤 "
        "**행사장 설계안 만들기**를 눌러주세요."
    )

    st.stop()


# =========================================================
# 저장값
# =========================================================

result = (
    st.session_state.design_result
)

saved = (
    st.session_state.design_inputs
)

st.session_state.needs = (
    st.session_state.get(
        "needs",
        needs,
    )
)

st.session_state.goals = (
    st.session_state.get(
        "goals",
        goals,
    )
)

st.session_state.venue_zones = clean_zones(
    st.session_state.get(
        "venue_zones",
        DEFAULT_ZONES,
    )
)

st.session_state.layout_version = (
    st.session_state.get(
        "layout_version",
        0,
    )
)


# =========================================================
# 기본 설계 결과
# =========================================================

st.markdown("---")

st.header(
    "🎯 추천 행사장 설계안"
)

c1, c2, c3 = st.columns(3)

c1.metric(
    "행사 규모",
    result["scale"],
)

c2.metric(
    "권장 공간 규모",
    result["area"],
)

c3.metric(
    "예상 입장료",
    f'{saved["fee"]:,}원',
)


st.subheader(
    "💡 행사 콘셉트"
)

st.info(

    f'**{saved["mood"]} '
    f'{saved["event_type"]}**를 콘셉트로 '

    f'{saved["people"]:,}명의 참가자가 '
    f'{saved["duration"]:g}시간 동안 '

    "자연스럽게 이동하고 머무를 수 있는 공간을 제안합니다."
)


st.subheader(
    "🚶 기존 추천 동선"
)

st.success(
    result["flow"]
)


# =========================================================
# 탭
# =========================================================

tab1, tab2, tab3 = st.tabs(
    [
        "🗺️ 공간 배치",
        "🔥 혼잡도 시뮬레이션",
        "♿ 포용적 행사 설계",
    ]
)


# =========================================================
# 탭 1 - 공간 배치
# =========================================================

with tab1:

    st.subheader(
        "🗺️ 실제 2D 공간 배치"
    )

    st.write(
        "색상 블록을 **드래그해서 이동**하고 "
        "모서리를 잡아 **크기 조절**할 수 있습니다."
    )

    b1, b2, b3 = st.columns(3)


    with b1:

        if st.button(
            "✨ 추천 배치 다시 적용",
            use_container_width=True,
        ):

            st.session_state.venue_zones = (
                recommended_layout(
                    saved["event_type"],
                    saved["people"],
                    st.session_state.needs,
                )
            )

            st.session_state.layout_version += 1

            st.rerun()


    with b2:

        if st.button(
            "↩️ 기본 배치",
            use_container_width=True,
        ):

            st.session_state.venue_zones = (
                clean_zones(
                    DEFAULT_ZONES
                )
            )

            st.session_state.layout_version += 1

            st.rerun()


    with b3:

        current_score = placement_score(
            st.session_state.venue_zones,
            saved["people"],
            st.session_state.needs,
        )

        st.metric(
            "현재 배치 점수",
            f"{current_score:.0f}/100",
        )


    # 드래그 캔버스
    if CANVAS_OK:

        canvas_key = (
            f"layout_canvas_"
            f"{st.session_state.layout_version}"
        )

        canvas = st_canvas(

            fill_color=(
                "rgba("
                "255,255,255,0.20)"
            ),

            stroke_color=(
                "rgba("
                "255,255,255,0.95)"
            ),

            stroke_width=2,

            background_color="#12161e",

            background_image=make_background(),

            initial_drawing=canvas_json(
                st.session_state.venue_zones
            ),

            drawing_mode="transform",

            height=CANVAS_H,

            width=CANVAS_W,


            update_streamlit=True,

            key=canvas_key,
        )


        new_zones, changed = (
            zones_from_canvas(
                canvas.json_data
                if canvas
                else None,

                st.session_state.venue_zones,
            )
        )


        if changed:

            st.session_state.venue_zones = (
                new_zones
            )

            st.session_state.layout_version += 1

            st.rerun()


    else:

        st.warning(

            "드래그 기능을 사용하려면 "
            "`streamlit-drawable-canvas`가 "
            "설치되어 있어야 합니다."
        )


    st.subheader(
        "📋 현재 공간 좌표"
    )

    layout_rows = []

    for name, z in (
        st.session_state.venue_zones.items()
    ):

        layout_rows.append(

            {
                "공간": name,

                "x": round(
                    z["x"],
                    1,
                ),

                "y": round(
                    z["y"],
                    1,
                ),

                "가로": round(
                    z["w"],
                    1,
                ),

                "세로": round(
                    z["h"],
                    1,
                ),

                "수용 기준": z[
                    "capacity"
                ],
            }
        )

    st.dataframe(
        pd.DataFrame(
            layout_rows
        ),

        hide_index=True,

        use_container_width=True,
    )


# =========================================================
# 탭 2 - 혼잡도
# =========================================================

with tab2:

    st.subheader(
        "🔥 예상 혼잡도 & 밀집도 시뮬레이션"
    )

    sc1, sc2, sc3, sc4 = st.columns(4)


    with sc1:

        sim_people = st.slider(

            "참가자 수",

            50,

            min(
                2000,
                max(
                    100,
                    saved["people"],
                ),
            ),

            min(
                saved["people"],
                500,
            ),

            10,
        )


    with sc2:

        total_min = max(
            60,
            int(
                saved["duration"]
                * 60
            ),
        )

        current_min = st.slider(

            "현재 시각(분)",

            0,

            total_min,

            min(
                90,
                total_min,
            ),

            5,
        )


    with sc3:

        main_w = st.slider(

            "메인존 활성도",

            0.5,
            2.0,
            1.0,
            0.1,
        )


    with sc4:

        content_w = st.slider(

            "체험존 활성도",

            0.5,
            2.0,
            1.0,
            0.1,
        )


    sc5, sc6, sc7 = st.columns(3)


    with sc5:

        rest_w = st.slider(
            "휴식존 활성도",
            0.5,
            2.0,
            1.0,
            0.1,
        )


    with sc6:

        photo_w = st.slider(
            "포토존 활성도",
            0.5,
            2.0,
            1.0,
            0.1,
        )


    with sc7:

        food_w = st.slider(
            "푸드존 활성도",
            0.5,
            2.0,
            1.0,
            0.1,
        )


    sim_weights = {

        "① 웰컴존": 1.0,

        "② 메인존": main_w,

        "③ 체험/콘텐츠존":
            content_w,

        "④ 휴식존":
            rest_w,

        "⑤ 포토존":
            photo_w,

        "⑥ 운영존": 0.7,

        "⑦ 푸드존":
            food_w,

        "♿ 접근성 휴식/지원":
            1.0,
    }


    positions = simulate_agents(

        sim_people,

        current_min,

        saved["event_type"],

        st.session_state.venue_zones,

        sim_weights,

        st.session_state.needs,
    )


    occ = zone_occupancy(

        positions,

        st.session_state.venue_zones,
    )


    # 혼잡 데이터
    rows = []

    for name, z in (
        st.session_state.venue_zones.items()
    ):

        count = occ[name]

        pct = (
            count
            / max(
                1,
                z["capacity"],
            )
            * 100
        )

        if pct >= 100:

            status = "🔴 매우 높음"

        elif pct >= 85:

            status = "🟠 높음"

        elif pct >= 65:

            status = "🟡 주의"

        else:

            status = "🟢 여유"


        rows.append(

            {
                "공간": name,

                "예상 인원": count,

                "수용 기준":
                    z["capacity"],

                "예상 밀집도":
                    f"{pct:.0f}%",

                "상태": status,
            }
        )


    congestion_df = (
        pd.DataFrame(rows)
        .sort_values(
            "예상 인원",
            ascending=False,
        )
    )


    peak = (
        congestion_df.iloc[0]
    )


    m1, m2, m3, m4 = st.columns(4)


    peak_pct = float(
        str(
            peak[
                "예상 밀집도"
            ]
        ).replace(
            "%",
            "",
        )
    )


    m1.metric(
        "현재 인원",
        f"{sim_people:,}명",
    )


    m2.metric(
        "최고 혼잡 공간",
        str(
            peak["공간"]
        ),
    )


    m3.metric(
        "최대 밀집도",
        f"{peak_pct:.0f}%",
    )


    operating_index = max(
        0,
        100
        - max(
            0,
            peak_pct - 65,
        ),
    )


    m4.metric(
        "운영 여유 지수",
        f"{operating_index:.0f}/100",
    )


    st.caption(
        "밀집도 = 예상 체류 인원 ÷ 해당 공간의 기획상 수용 기준"
    )


    # 지도
    map_col, table_col = st.columns(
        [3, 1]
    )


    with map_col:

        xs, ys, H = heatmap(
            positions
        )

        fig = go.Figure()


        fig.add_trace(

            go.Heatmap(

                x=xs,

                y=ys,

                z=H,

                colorscale="Turbo",

                opacity=0.52,

                colorbar=dict(
                    title="밀집도"
                ),

                hoverinfo="skip",
            )
        )


        fig.add_trace(

            go.Scatter(

                x=positions[:, 0],

                y=positions[:, 1],

                mode="markers",

                marker=dict(
                    size=4,
                    opacity=0.55,
                ),

                hoverinfo="skip",
            )
        )


        c = centers(
            st.session_state.venue_zones
        )


        path_pairs = [

            (
                "① 웰컴존",
                "② 메인존",
            ),

            (
                "② 메인존",
                "⑤ 포토존",
            ),

            (
                "② 메인존",
                "④ 휴식존",
            ),

            (
                "④ 휴식존",
                "⑦ 푸드존",
            ),

            (
                "② 메인존",
                "③ 체험/콘텐츠존",
            ),
        ]


        for a, b in path_pairs:

            fig.add_annotation(

                x=c[b][0],

                y=c[b][1],

                ax=c[a][0],

                ay=c[a][1],

                xref="x",

                yref="y",

                axref="x",

                ayref="y",

                showarrow=True,

                arrowhead=2,

                arrowwidth=2,

                arrowcolor=(
                    "rgba("
                    "255,255,255,0.65)"
                ),
            )


        for name, z in (
            st.session_state.venue_zones.items()
        ):

            pct = (
                occ[name]
                / max(
                    1,
                    z["capacity"],
                )
                * 100
            )


            fig.add_shape(

                type="rect",

                x0=z["x"],

                y0=z["y"],

                x1=z["x"] + z["w"],

                y1=z["y"] + z["h"],

                line=dict(
                    color="white",
                    width=2,
                ),

                fillcolor=(
                    "rgba("
                    "255,255,255,0.05)"
                ),
            )


            fig.add_annotation(

                x=(
                    z["x"]
                    + z["w"] / 2
                ),

                y=(
                    z["y"]
                    + z["h"] / 2
                ),

                text=(

                    f"<b>{name}</b>"
                    f"<br>{occ[name]}명"
                    f" · {pct:.0f}%"
                ),

                showarrow=False,

                font=dict(
                    size=11
                ),
            )


        fig.update_layout(

            height=620,

            margin=dict(
                l=5,
                r=5,
                t=5,
                b=5,
            ),

            xaxis=dict(
                range=[
                    0,
                    100,
                ],
                visible=False,
            ),

            yaxis=dict(
                range=[
                    0,
                    100,
                ],
                visible=False,
                scaleanchor="x",
            ),

            showlegend=False,
        )


        st.plotly_chart(

            fig,

            use_container_width=True,

            config={
                "displaylogo": False
            },
        )


    with table_col:

        st.dataframe(

            congestion_df,

            hide_index=True,

            use_container_width=True,
        )


    # 시간별 그래프
    st.subheader(
        "📈 시간대별 혼잡도"
    )


    times = np.linspace(
        0,
        total_min,
        10,
    ).astype(int)


    trend_rows = []


    for t in times:

        p = simulate_agents(

            min(
                sim_people,
                700,
            ),

            int(t),

            saved["event_type"],

            st.session_state.venue_zones,

            sim_weights,

            st.session_state.needs,
        )


        o = zone_occupancy(

            p,

            st.session_state.venue_zones,
        )


        for name, count in (
            o.items()
        ):

            pct = (
                count
                / max(
                    1,
                    st.session_state
                    .venue_zones[name]
                    ["capacity"],
                )
                * 100
            )


            trend_rows.append(

                {
                    "시간": int(t),

                    "공간": name,

                    "밀집도": pct,
                }
            )


    trend = pd.DataFrame(
        trend_rows
    )


    tf = go.Figure()


    for name in (
        st.session_state.venue_zones
    ):

        part = trend[
            trend["공간"] == name
        ]


        tf.add_trace(

            go.Scatter(

                x=part["시간"],

                y=part["밀집도"],

                mode="lines+markers",

                name=name,
            )
        )


    tf.add_hline(

        y=85,

        line_dash="dash",

        annotation_text="주의 85%",
    )


    tf.add_hline(

        y=100,

        line_dash="dot",

        annotation_text="수용 기준 100%",
    )


    tf.update_layout(

        height=380,

        margin=dict(
            l=10,
            r=10,
            t=10,
            b=10,
        ),

        xaxis_title=(
            "행사 진행 시간(분)"
        ),

        yaxis_title=(
            "예상 밀집도(%)"
        ),

        legend=dict(
            orientation="h",
            y=1.12,
        ),
    )


    st.plotly_chart(

        tf,

        use_container_width=True,

        config={
            "displaylogo": False
        },
    )


    # =====================================================
    # 추천 배치 비교
    # =====================================================

    st.subheader(
        "✨ AI 추천 배치"
    )


    recommended = (
        recommended_layout(
            saved["event_type"],
            saved["people"],
            st.session_state.needs,
        )
    )


    current_score = placement_score(

        st.session_state.venue_zones,

        saved["people"],

        st.session_state.needs,
    )


    recommended_score = placement_score(

        recommended,

        saved["people"],

        st.session_state.needs,
    )


    r1, r2, r3 = st.columns(3)


    r1.metric(
        "현재 배치 점수",
        f"{current_score:.0f}/100",
    )


    r2.metric(
        "추천 배치 점수",
        f"{recommended_score:.0f}/100",
    )


    r3.metric(
        "개선 여지",
        f"{max(0, recommended_score - current_score):.0f}점",
    )


    rec_positions = simulate_agents(

        min(
            sim_people,
            700,
        ),

        current_min,

        saved["event_type"],

        recommended,

        sim_weights,

        st.session_state.needs,
    )


    rec_occ = zone_occupancy(

        rec_positions,

        recommended,
    )


    rec_peak_pct, rec_peak_name = max(

        (
            rec_occ[n]
            / max(
                1,
                recommended[n][
                    "capacity"
                ],
            )
            * 100,

            n,
        )

        for n in rec_occ
    )


    st.info(

        f"현재 배치 최고 밀집도: "
        f"**{peak_pct:.0f}%**  →  "
        f"추천 배치 시 약 "
        f"**{rec_peak_pct:.0f}%**"
    )


    if st.button(
        "✅ 추천 배치를 실제 배치에 적용",
        type="primary",
        use_container_width=True,
    ):

        st.session_state.venue_zones = (
            recommended
        )

        st.session_state.layout_version += 1

        st.rerun()


# =========================================================
# 탭 3 - 포용적 행사
# =========================================================

with tab3:

    st.subheader(
        "♿ 포용적 행사 설계"
    )


    st.write(

        "모두를 위한 행사는 특정 집단만 따로 분리하기보다, "
        "**이동·정보·감각·휴식·비용의 장벽을 처음부터 낮추는 방식**으로 설계합니다."
    )


    t1, t2 = st.columns(2)


    with t1:

        st.markdown(
            "### 🚪 이동"
        )


        for tip in [

            "입구 → 주요 프로그램 → 휴식 → 화장실의 주요 경로가 끊기지 않도록 설계",

            "휠체어·유모차·보행 보조기기가 통과하고 회전할 수 있는 여유 공간 확보",

            "대기열을 주요 통로에 만들지 않고 별도 대기 공간으로 분리",
        ]:

            st.write(
                "• " + tip
            )


        st.markdown(
            "### 👁️👂 정보"
        )


        for tip in [

            "색상만으로 정보를 전달하지 않고 글자·아이콘을 함께 사용",

            "중요 안내를 문자·음성 등 한 가지 채널에만 의존하지 않기",

            "공연·발표에 자막 등 대체 정보 채널 제공",
        ]:

            st.write(
                "• " + tip
            )


    with t2:

        st.markdown(
            "### 🧘 감각·휴식"
        )


        for tip in [

            "소음·조명이 강한 공간에서 떨어진 조용한 휴식 공간 마련",

            "휴식 공간에 좌석과 물을 제공",

            "혼잡한 시간대를 미리 알려 참가자가 이동 시점을 선택할 수 있게 지원",
        ]:

            st.write(
                "• " + tip
            )


        st.markdown(
            "### 💳 비용·참여"
        )


        for tip in [

            "무료 또는 저비용으로 참여할 수 있는 콘텐츠 포함",

            "물·기본 안내·휴식 같은 필수 편의를 유료 콘텐츠와 분리",

            "관람만으로도 행사에 참여했다고 느낄 수 있는 콘텐츠 마련",
        ]:

            st.write(
                "• " + tip
            )


    st.markdown("---")


    st.subheader(
        "🔎 현재 선택 조건을 반영한 설계 제안"
    )


    for tip in accessibility_tips(

        st.session_state.needs,

        st.session_state.goals,
    ):

        st.write(
            "• " + tip
        )


    st.subheader(
        "✅ 접근성 체크리스트"
    )


    checklist = [

        (
            "무장애 동선",

            "주요 동선에 계단·단차 등 이동 장벽이 없는지 확인",
        ),

        (
            "접근 가능한 화장실",

            "주요 공간에서 접근 가능한 화장실 위치와 안내를 확인",
        ),

        (
            "정보 접근",

            "글자 크기·대비·아이콘·대체 정보 채널을 확인",
        ),

        (
            "감각 휴식",

            "조용한 공간과 강한 자극 공간을 분리",
        ),

        (
            "대기 부담",

            "장시간 서 있어야 하는 구간에 휴식·대기 공간이 있는지 확인",
        ),

        (
            "비용 장벽",

            "필수 편의가 유료 이용과 분리되어 있는지 확인",
        ),

        (
            "비상·안전",

            "실제 현장에서는 피난·소방·시설 기준을 별도로 확인",
        ),
    ]


    for label, help_text in checklist:

        st.checkbox(

            label,

            key="access_" + label,

            help=help_text,
        )


# =========================================================
# 기존 추천 내용 추가
# =========================================================

st.markdown("---")

st.subheader(
    "🎨 분위기 연출"
)

st.write(
    result["mood"]
)


st.subheader(
    "👥 인원 및 안전 운영"
)

st.write(
    result["crowd"]
)

st.write(
    result["safety"]
)


st.subheader(
    "🏠 장소 조건"
)

st.write(
    result["venue"]
)

st.write(
    result["weather"]
)


st.subheader(
    "💰 입장료 기반 운영 전략"
)

st.write(
    result["budget"]
)


st.markdown("---")

st.caption(

    "※ 본 앱의 혼잡도·밀집도는 행사 기획용 단순화 시뮬레이션입니다. "
    "실제 행사의 안전 판단에는 현장 실측, 통로 폭, 출입구, 피난 동선, "
    "소방·시설 기준 등의 별도 검토가 필요합니다."
)
