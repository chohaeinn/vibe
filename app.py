# -*- coding: utf-8 -*-
"""Event ON - AI 기반 행사 자동 설계 플랫폼 (단일 파일: app.py 하나만 올리면 실행된다)
필요 패키지: streamlit, numpy, pandas, reportlab   (한글 PDF 글꼴용 packages.txt: fonts-nanum)"""
from __future__ import annotations

import datetime as dt
import datetime as _dt
import html as _html
import json
import math
import re
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ===== ENGINE =====



# ----------------------------------------------------------------------------
# 상수
# ----------------------------------------------------------------------------
WORLD_W, WORLD_H = 160.0, 100.0          # 가상 좌표계 (단위: unit)
GX, GY = 40, 25                          # 밀집도 격자
CW, CH = WORLD_W / GX, WORLD_H / GY
MARGIN = 6.0
PAD = 4.0                                # 구역 사이 최소 통로
GATE_CLEAR = 9.0
APRON = 2.0                              # 구역 주변 대기/관람 여유
WARN_DENSITY = 0.5                       # 명/㎡  (혼잡)
DANGER_DENSITY = 0.9                     # 명/㎡  (위험)

OBJECTIVES = ["safety", "flow", "access", "cong", "space"]
OBJ_LABEL = {
    "safety": "비상 안전성",
    "flow": "동선 효율성",
    "access": "접근성",
    "cong": "혼잡도 분산",
    "space": "공간 활용성",
}

ZONE_META = {
    "stage":    dict(label="공연장",       color="#8b5cf6", icon="🎭", ht=14, attract=0.30),
    "food":     dict(label="푸드존",       color="#f59e0b", icon="🍔", ht=6,  attract=0.22),
    "booth":    dict(label="체험부스",     color="#3b82f6", icon="🧪", ht=6,  attract=0.20),
    "rest":     dict(label="휴게공간",     color="#10b981", icon="🛋️", ht=4,  attract=0.10),
    "medical":  dict(label="응급의료센터", color="#ef4444", icon="🏥", ht=7,  attract=0.00),
    "info":     dict(label="안내센터",     color="#0ea5e9", icon="ℹ️", ht=5,  attract=0.06),
    "restroom": dict(label="화장실",       color="#06b6d4", icon="🚻", ht=5,  attract=0.06),
    "custom":   dict(label="사용자 부스",  color="#ec4899", icon="⭐", ht=6,  attract=0.14),
}
COST = {"stage": 0, "food": 250, "booth": 120, "rest": 150, "medical": 350,
        "info": 80, "restroom": 120, "custom": 150}          # 만원

CUSTOM_CATS = {  # 사용자 부스 구분 -> (아이콘, 매력도)
    "체험": ("🧪", 0.20), "푸드": ("🍔", 0.22), "휴게": ("🛋️", 0.10),
    "공연": ("🎤", 0.28), "기타": ("⭐", 0.14),
}

GATE_POS = [(80, 98, "주출입구"), (80, 2, "북문"), (2, 50, "서문"),
            (158, 50, "동문"), (30, 98, "남서문"), (130, 98, "남동문")]

PURPOSES = {
    "휴식/힐링 페스티벌": dict(stage=0.8, booth=1.0, food=1.0, rest=1.6, w=dict(space=.04, access=.04)),
    "음악/대형 공연":     dict(stage=1.5, booth=0.7, food=1.1, rest=0.8, w=dict(cong=.08, safety=.06)),
    "학술/산업 박람회":   dict(stage=0.7, booth=1.6, food=0.7, rest=0.8, w=dict(flow=.08, access=.05)),
    "체험/플리마켓":      dict(stage=0.6, booth=1.5, food=1.3, rest=1.0, w=dict(flow=.05, space=.05)),
    "기업 브랜드 프로모션": dict(stage=1.0, booth=1.3, food=0.8, rest=0.9, w=dict(flow=.06, access=.04)),
}
MOODS = {
    "활기찬 / 축제":   dict(stage=1.2, nb=1, nr=0),
    "차분한 / 힐링":   dict(stage=0.85, nb=0, nr=1),
    "프리미엄 / 세련": dict(stage=1.0, nb=-1, nr=1),
    "가족 친화":       dict(stage=0.9, nb=1, nr=1),
    "트렌디 / MZ":     dict(stage=1.1, nb=2, nr=0),
}
AGES = {
    "전 연령층": dict(w={}, rest=1.0, restroom=1.0),
    "10~20대 청소년·대학생": dict(w=dict(cong=.04), rest=0.8, restroom=1.0),
    "30~40대 가족 단위": dict(w=dict(safety=.05, access=.04), rest=1.2, restroom=1.3),
    "50대 이상 시니어": dict(w=dict(access=.08, safety=.04), rest=1.6, restroom=1.4),
}
VENUES = {
    "야외 잔디광장": dict(kind="outdoor", ground="#3a7d44", groundRain="#2b5e33", path="#e2d9c8",
                          bg3d="#0f172a", g3d="#2e7d32"),
    "실내 컨벤션홀": dict(kind="indoor", ground="#cbd5e1", groundRain="#cbd5e1", path="#94a3b8",
                          bg3d="#1e293b", g3d="#94a3b8"),
    "실내 체육관":   dict(kind="indoor", ground="#d6b98c", groundRain="#d6b98c", path="#b08d57",
                          bg3d="#1e293b", g3d="#b08d57"),
    "도심 거리/광장": dict(kind="city", ground="#64748b", groundRain="#475569", path="#cbd5e1",
                          bg3d="#0f172a", g3d="#475569"),
}


# ----------------------------------------------------------------------------
# 행사장 모양 (가상 좌표 160x100 안에서 모양 마스크 정의)
# ----------------------------------------------------------------------------
SHAPE_MARGIN = 4.0            # 구역과 외벽 사이 최소 여유
DEFAULT_SHAPE = "직사각형 (기본)"
GATE_NAMES = ["주출입구", "북문", "서문", "동문", "남서문", "남동문"]


def _ellipse_pts(cx, cy, rx, ry, n=72):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _eg(cx, cy, rx, ry, deg, name):
    t = math.radians(deg)
    return (cx + (rx - 1.5) * math.cos(t), cy + (ry - 1.5) * math.sin(t), name,
            math.atan2(ry * math.cos(t), -rx * math.sin(t)))


_PI2 = math.pi / 2
SHAPES = {
    "직사각형 (기본)": dict(kind="rect", bbox=(0, 0, 160, 100), dome=False,
                      desc="가장 일반적인 사각 부지", gates=[
        (80, 98, "주출입구", 0), (80, 2, "북문", 0), (2, 50, "서문", _PI2), (158, 50, "동문", _PI2),
        (30, 98, "남서문", 0), (130, 98, "남동문", 0)]),
    "정사각형": dict(kind="rect", bbox=(30, 0, 130, 100), dome=False,
                  desc="가로·세로가 같은 정방형 부지", gates=[
        (80, 98, "주출입구", 0), (80, 2, "북문", 0), (32, 50, "서문", _PI2), (128, 50, "동문", _PI2),
        (52, 98, "남서문", 0), (108, 98, "남동문", 0)]),
    "원형 광장": dict(kind="ellipse", c=(80, 50), r=(50, 50), dome=False,
                  desc="원형 야외 광장", gates=[_eg(80, 50, 50, 50, d, n) for d, n in zip([90, 270, 180, 0, 125, 55], GATE_NAMES)]),
    "돔형 (지붕 있음)": dict(kind="ellipse", c=(80, 50), r=(50, 50), dome=True,
                      desc="원형 돔 경기장·아레나 (지붕 표시)", gates=[_eg(80, 50, 50, 50, d, n) for d, n in zip([90, 270, 180, 0, 125, 55], GATE_NAMES)]),
    "타원형 경기장": dict(kind="ellipse", c=(80, 50), r=(78, 48), dome=False,
                    desc="타원형 스타디움", gates=[_eg(80, 50, 78, 48, d, n) for d, n in zip([90, 270, 180, 0, 125, 55], GATE_NAMES)]),
    "L자형": dict(kind="poly", pts=[(0, 0), (90, 0), (90, 45), (160, 45), (160, 100), (0, 100)], dome=False,
                desc="모서리가 꺾인 L자 부지", gates=[
        (80, 98, "주출입구", 0), (45, 2, "북문", 0), (2, 50, "서문", _PI2), (158, 72, "동문", _PI2),
        (125, 46, "북동문", 0), (89, 22, "중앙문", _PI2)]),
}


def shape_info(name: str) -> dict:
    s_ = dict(SHAPES.get(name) or SHAPES[DEFAULT_SHAPE])
    k = s_["kind"]
    if k == "rect":
        x0, y0, x1, y1 = s_["bbox"]
        s_["outline"] = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        s_["area"] = (x1 - x0) * (y1 - y0)
    elif k == "ellipse":
        cx, cy = s_["c"]
        rx, ry = s_["r"]
        s_["outline"] = _ellipse_pts(cx, cy, rx, ry)
        s_["bbox"] = (cx - rx, cy - ry, cx + rx, cy + ry)
        s_["area"] = math.pi * rx * ry
    else:
        pts = s_["pts"]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        s_["outline"] = list(pts)
        s_["bbox"] = (min(xs), min(ys), max(xs), max(ys))
        s_["area"] = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                             for i in range(len(pts)))) / 2
    s_["name"] = name if name in SHAPES else DEFAULT_SHAPE
    return s_


def shape_inside(sh, x, y):
    k = sh["kind"]
    if k == "rect":
        x0, y0, x1, y1 = sh["bbox"]
        return x0 <= x <= x1 and y0 <= y <= y1
    if k == "ellipse":
        cx, cy = sh["c"]
        rx, ry = sh["r"]
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0
    pts, ins, j = sh["pts"], False, len(sh["pts"]) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins


def rect_in_shape(sh, x, y, w, h, m=SHAPE_MARGIN):
    return (shape_inside(sh, x - m, y - m) and shape_inside(sh, x + w + m, y - m)
            and shape_inside(sh, x - m, y + h + m) and shape_inside(sh, x + w + m, y + h + m))


def fmt_sec(s: float) -> str:
    s = int(round(s))
    m, r = divmod(s, 60)
    return f"{m}분 {r:02d}초" if m else f"{r}초"


# ----------------------------------------------------------------------------
# 1) 디지털 트윈: 구역 구성
# ----------------------------------------------------------------------------
def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def get_weights(p: dict) -> Dict[str, float]:
    w = dict(safety=.25, flow=.20, access=.15, cong=.25, space=.15)
    for d in (PURPOSES[p["purpose"]]["w"], AGES[p["age"]]["w"]):
        for k, v in d.items():
            w[k] += v
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def weight_breakdown(p: dict) -> Dict[str, dict]:
    base = dict(safety=.25, flow=.20, access=.15, cong=.25, space=.15)
    pa, ag = PURPOSES[p["purpose"]]["w"], AGES[p["age"]]["w"]
    raw = {k: base[k] + pa.get(k, 0.0) + ag.get(k, 0.0) for k in base}
    tot = sum(raw.values())
    return {k: dict(base=base[k], purpose=pa.get(k, 0.0), age=ag.get(k, 0.0), final=raw[k] / tot) for k in base}


def build_zones(p: dict, custom: List[dict]):
    """입력 조건 -> 구역 목록. 예산이 부족하면 부스/푸드 수를 줄인다."""
    V = p["visitors"]
    sh = shape_info(p.get("shape", DEFAULT_SHAPE))
    mpu = math.sqrt(p["area_m2"] / sh["area"])            # unit 당 미터 (모양의 실제 면적 기준)
    scale = p.get("size_scale") or {}
    pm, mm, am = PURPOSES[p["purpose"]], MOODS[p["mood"]], AGES[p["age"]]
    notes: List[str] = []

    SZ = 1.35   # 화면에서 잘 보이도록 구역을 키운다

    def u(m, cap, t):
        sc_ = float(scale.get(t, 1.0))
        return float(_clamp(m / mpu * SZ * sc_, 3.5, cap * 1.3 * max(1.0, sc_)))

    vs = _clamp(math.sqrt(V / 5000), 0.7, 1.6)
    n_food = int(_clamp(round(V / 2200) + 1, 1, 5))
    n_booth = int(_clamp(round(V / 900 * pm["booth"]) + mm["nb"], 2, 10))
    n_rest = int(_clamp(round(1 + pm["rest"] * 0.7 * am["rest"] + mm["nr"] * 0.5), 1, 4))
    n_restroom = int(_clamp(math.ceil(V / 2500 * am["restroom"]) + 1, 2, 6))
    n_info = 2 if V >= 5000 else 1
    n_med = 2 if V >= 8000 else 1
    n_custom = sum(int(c.get("count", 1)) for c in custom)

    # 사용자가 고른 시설만 만든다 (None 이면 전부). 응급의료센터와 메인 무대는 항상 포함한다.
    fac = p.get("facilities")
    if fac is not None:
        if "푸드존" not in fac:
            n_food = 0
        if "체험 부스" not in fac:
            n_booth = 0
        if "휴게 공간" not in fac:
            n_rest = 0
        if "안내센터" not in fac:
            n_info = 0
        if "화장실" not in fac:
            n_restroom = 0

    def total_cost():
        stage = 800 + V * 0.15
        return (stage + n_food * COST["food"] + n_booth * COST["booth"] + n_rest * COST["rest"]
                + n_med * COST["medical"] + n_info * COST["info"] + n_restroom * COST["restroom"]
                + n_custom * COST["custom"])

    budget = p["budget"]
    orig = (n_food, n_booth)
    while total_cost() > budget and (n_booth > 1 or n_food > 1):
        if n_booth >= n_food and n_booth > 1:
            n_booth -= 1
        elif n_food > 1:
            n_food -= 1
        else:
            break
    if (n_food, n_booth) != orig:
        notes.append(f"예산({budget:,}만원) 제약으로 푸드존 {orig[0]}→{n_food}개, 체험부스 {orig[1]}→{n_booth}개로 조정했습니다.")
    cost = total_cost()
    if cost > budget:
        notes.append(f"필수 시설만으로도 예상 비용 {cost:,.0f}만원이 예산을 초과합니다. 예산 또는 사용자 부스 수를 조정하세요.")

    zones: List[dict] = []

    def add(t, name, wm, hm, cap=45, attract=None, icon=None, ht=None):
        meta = ZONE_META[t]
        zones.append(dict(
            id=len(zones), type=t, name=name,
            w=round(u(wm, cap, t), 2), h=round(u(hm, cap * 0.7, t), 2),
            color=meta["color"], icon=icon or meta["icon"], ht=ht or meta["ht"],
            attract=float(meta["attract"] if attract is None else attract)))

    def multi(t, n, label, wm, hm, cap=30, attract=None):
        for i in range(n):
            add(t, f"{label} {i + 1}" if n > 1 else label, wm, hm, cap, attract)

    ss = pm["stage"] * mm["stage"] * vs
    add("stage", "메인 무대", 26 * ss, 15 * ss, cap=42)
    multi("food", n_food, "푸드존", 18, 12)
    multi("booth", n_booth, "체험부스", 16, 11)
    for i in range(n_rest):
        add("rest", f"휴게공간 {i + 1}" if n_rest > 1 else "휴게공간", 20, 14, 30,
            ZONE_META["rest"]["attract"] * am["rest"])
    multi("medical", n_med, "응급의료센터", 12, 9)
    multi("info", n_info, "안내센터", 9, 7)
    for i in range(n_restroom):
        add("restroom", f"화장실 {i + 1}", 10, 7, 20, ZONE_META["restroom"]["attract"] * am["restroom"])
    for c in custom:
        cat = c.get("cat", "기타")
        icon, att = CUSTOM_CATS.get(cat, CUSTOM_CATS["기타"])
        cnt = int(c.get("count", 1))
        for i in range(cnt):
            nm = c["name"] if cnt == 1 else f"{c['name']} {i + 1}"
            add("custom", nm, float(c.get("w", 8)), float(c.get("h", 6)), 30, att, icon,
                ZONE_META["stage"]["ht"] if cat == "공연" else None)
    area_sum = sum(z["w"] * z["h"] for z in zones)
    limit = 0.36 * sh["area"]
    if area_sum > limit:
        f = math.sqrt(limit / area_sum)
        for z in zones:
            z["w"] = round(max(4.0, z["w"] * f), 2)
            z["h"] = round(max(3.5, z["h"] * f), 2)
        notes.append("구역 면적의 합이 행사장의 36%를 넘어 모든 구역을 같은 비율로 자동 축소했습니다. (크기 배율을 줄이거나 면적/구역 수를 조정하면 해소됩니다)")
    for i, z in enumerate(zones):
        z["id"] = i
    return zones, notes, mpu, cost


def get_gates(n: int, sh: dict):
    idx = {2: [0, 1], 4: [0, 1, 2, 3], 6: [0, 1, 2, 3, 4, 5]}[n]
    gates = [dict(x=float(sh["gates"][i][0]), y=float(sh["gates"][i][1]), name=sh["gates"][i][2],
                  ang=float(sh["gates"][i][3])) for i in idx]
    shares = [0.4] + [0.6 / (len(gates) - 1)] * (len(gates) - 1)
    for g, s_ in zip(gates, shares):
        g["share"] = float(s_)
    return gates


def make_ctx(zones, p, mpu, gates, sh):
    n = len(zones)
    types = [z["type"] for z in zones]
    attract = np.array([z["attract"] for z in zones], float)
    dwell = [i for i, t in enumerate(types) if t != "medical"]
    a_norm = np.zeros(n)
    a_norm[dwell] = attract[dwell] / attract[dwell].sum()
    C = p["visitors"] * 0.5                       # 피크 동시 체류 인원
    return dict(
        mpu=mpu, n=n, types=types, dwell_idx=np.array(dwell), shape=sh, shape_area=sh["area"],
        ref_u=0.5 * math.sqrt(sh["area"] * 1.6),
        non_med=np.array([i for i, t in enumerate(types) if t != "medical"]),
        medical=np.array([i for i, t in enumerate(types) if t == "medical"]),
        restroom=np.array([i for i, t in enumerate(types) if t == "restroom"]),
        rest=np.array([i for i, t in enumerate(types) if t == "rest"]),
        info=np.array([i for i, t in enumerate(types) if t == "info"]),
        gates=np.array([[g["x"], g["y"]] for g in gates]),
        gate_xy=[(g["x"], g["y"]) for g in gates],
        gate_share=np.array([g["share"] for g in gates]),
        attract_norm=a_norm, concurrent=C,
        dwell_people=C * 0.75 * a_norm, path_people=C * 0.25,
        cell_area=CW * CH * mpu * mpu,
        t=np.linspace(0.06, 0.94, 12),
    )


# ----------------------------------------------------------------------------
# 2) 배치안 생성
# ----------------------------------------------------------------------------
def _pin_box(r, sh):
    x0, y0, x1, y1 = sh["bbox"]
    w_, h_ = x1 - x0, y1 - y0
    return x0 + r[0] * w_, x0 + r[1] * w_, y0 + r[2] * h_, y0 + r[3] * h_


def region_ok(z, x, y, pins, sh):
    r = pins.get(z["type"])
    if not r:
        return True
    px0, px1, py0, py1 = _pin_box(r, sh)
    cx, cy = x + z["w"] / 2, y + z["h"] / 2
    return px0 <= cx <= px1 and py0 <= cy <= py1


def _valid(x, y, w, h, P, mask, gates, sh):
    if not rect_in_shape(sh, x, y, w, h):
        return False
    for gx, gy in gates:
        nx, ny = min(max(gx, x), x + w), min(max(gy, y), y + h)
        if (gx - nx) ** 2 + (gy - ny) ** 2 < GATE_CLEAR ** 2:
            return False
    if mask.any():
        Q = P[mask]
        sep = ((x + w + PAD <= Q[:, 0]) | (Q[:, 0] + Q[:, 2] + PAD <= x)
               | (y + h + PAD <= Q[:, 1]) | (Q[:, 1] + Q[:, 3] + PAD <= y))
        if not sep.all():
            return False
    return True


def sample_layout(zones, ctx, pins, rng):
    sh = ctx["shape"]
    bx0, by0, bx1, by1 = sh["bbox"]
    n = len(zones)
    P = np.zeros((n, 4))
    mask = np.zeros(n, bool)
    order = sorted(range(n), key=lambda i: -zones[i]["w"] * zones[i]["h"])
    for i in order:
        z = zones[i]
        ok = False
        for _ in range(70):
            r = pins.get(z["type"])
            if r:
                px0, px1, py0, py1 = _pin_box(r, sh)
                cx, cy = rng.uniform(px0, px1), rng.uniform(py0, py1)
                x, y = cx - z["w"] / 2, cy - z["h"] / 2
            else:
                x = rng.uniform(bx0 + SHAPE_MARGIN, max(bx0 + SHAPE_MARGIN, bx1 - SHAPE_MARGIN - z["w"]))
                y = rng.uniform(by0 + SHAPE_MARGIN, max(by0 + SHAPE_MARGIN, by1 - SHAPE_MARGIN - z["h"]))
            if _valid(x, y, z["w"], z["h"], P, mask, ctx["gate_xy"], sh):
                P[i] = (x, y, z["w"], z["h"])
                mask[i] = True
                ok = True
                break
        if not ok:
            return None
    return P


def mutate(L, zones, ctx, pins, rng):
    sh = ctx["shape"]
    bx0, by0, bx1, by1 = sh["bbox"]
    P = L.copy()
    n = len(zones)
    for j in rng.choice(n, size=min(int(rng.integers(1, 4)), n), replace=False):
        z = zones[j]
        for _ in range(25):
            if rng.random() < 0.65:
                nx, ny = P[j, 0] + rng.normal(0, 9), P[j, 1] + rng.normal(0, 9)
            else:
                nx = rng.uniform(bx0 + SHAPE_MARGIN, max(bx0 + SHAPE_MARGIN, bx1 - SHAPE_MARGIN - z["w"]))
                ny = rng.uniform(by0 + SHAPE_MARGIN, max(by0 + SHAPE_MARGIN, by1 - SHAPE_MARGIN - z["h"]))
            if not region_ok(z, nx, ny, pins, sh):
                continue
            mask = np.ones(n, bool)
            mask[j] = False
            if _valid(nx, ny, z["w"], z["h"], P, mask, ctx["gate_xy"], sh):
                P[j, 0], P[j, 1] = nx, ny
                break
    return P


def baseline_layout(zones, ctx):
    """설계 전(기존) 배치: 주출입구 가까이에 우선순위 순으로 빈 곳부터 채워 넣는 전형적인 수작업 배치.
    (모든 행사장 모양에서 동작하도록 격자 탐색 방식)"""
    sh, gates = ctx["shape"], ctx["gate_xy"]
    mx, my = gates[0]
    pri = {"stage": 0, "food": 1, "booth": 2, "custom": 3, "rest": 4, "info": 5, "restroom": 6, "medical": 7}
    idx = sorted(range(len(zones)), key=lambda i: (pri[zones[i]["type"]], i))
    x0, y0, x1, y1 = sh["bbox"]
    pts = [(float(a_), float(b_)) for a_ in np.arange(x0 + SHAPE_MARGIN, x1 - SHAPE_MARGIN, 2.5)
           for b_ in np.arange(y0 + SHAPE_MARGIN, y1 - SHAPE_MARGIN, 2.5)]
    P = np.zeros((len(zones), 4))
    mask = np.zeros(len(zones), bool)
    for i in idx:
        z = zones[i]
        w, h = z["w"], z["h"]
        cand = sorted(pts, key=lambda p_: (p_[0] + w / 2 - mx) ** 2 + (p_[1] + h / 2 - my) ** 2)
        put = False
        for (px_, py_) in cand:
            if _valid(px_, py_, w, h, P, mask, gates, sh):
                P[i] = (px_, py_, w, h)
                mask[i] = True
                put = True
                break
        if not put:                                   # 최후 수단: 겹침 허용
            for (px_, py_) in cand:
                if rect_in_shape(sh, px_, py_, w, h):
                    P[i] = (px_, py_, w, h)
                    mask[i] = True
                    break
            else:
                P[i] = (x0 + SHAPE_MARGIN, y0 + SHAPE_MARGIN, w, h)
                mask[i] = True
    return P


# ----------------------------------------------------------------------------
# 3) 군중 시뮬레이션 + 목표 평가
# ----------------------------------------------------------------------------
def evaluate(L, ctx, detail=False):
    mpu = ctx["mpu"]
    x, y, w, h = L[:, 0], L[:, 1], L[:, 2], L[:, 3]
    cx, cy = x + w / 2, y + h / 2
    n = ctx["n"]
    D, G, gs, t = ctx["dwell_idx"], ctx["gates"], ctx["gate_share"], ctx["t"]
    S = len(t)
    grid = np.zeros((GY, GX))

    # (a) 구역 체류 군중
    for j in D:
        gx0 = max(0, int((x[j] - APRON) // CW)); gx1 = min(GX, int(math.ceil((x[j] + w[j] + APRON) / CW)))
        gy0 = max(0, int((y[j] - APRON) // CH)); gy1 = min(GY, int(math.ceil((y[j] + h[j] + APRON) / CH)))
        nc = max(1, (gx1 - gx0) * (gy1 - gy0))
        grid[gy0:gy1, gx0:gx1] += ctx["dwell_people"][j] / nc

    # (b) 출입구 -> 구역 이동 군중
    gxp, gyp = G[:, 0][:, None, None], G[:, 1][:, None, None]
    px = gxp + (cx[D][None, :, None] - gxp) * t[None, None, :]
    py = gyp + (cy[D][None, :, None] - gyp) * t[None, None, :]
    f = ctx["path_people"] * gs[:, None] * ctx["attract_norm"][D][None, :]          # G x D
    ix = np.clip((px // CW).astype(int), 0, GX - 1)
    iy = np.clip((py // CH).astype(int), 0, GY - 1)
    np.add.at(grid, (iy.ravel(), ix.ravel()), np.broadcast_to((f / S)[:, :, None], px.shape).ravel())
    dens = grid / ctx["cell_area"]

    # (c) 동선이 다른 구역을 관통하는 비율
    ins = ((px[..., None] >= x[None, None, None, :]) & (px[..., None] <= (x + w)[None, None, None, :]) &
           (py[..., None] >= y[None, None, None, :]) & (py[..., None] <= (y + h)[None, None, None, :]))
    own = np.zeros((len(D), n), bool)
    own[np.arange(len(D)), D] = True
    ins &= ~own[None, :, None, :]
    hit = ins.any(axis=3)
    obstruct = float((hit * f[:, :, None]).sum() / (f.sum() * S))
    dist_u = np.hypot(cx[D][None, :] - G[:, 0][:, None], cy[D][None, :] - G[:, 1][:, None])
    avg_dist_u = float((dist_u * f).sum() / f.sum())
    avg_dist_m = avg_dist_u * mpu

    # ---- 측정값 ----
    peak = float(dens.max())
    flat = np.sort(dens.ravel())[::-1]
    k5 = max(1, int(len(flat) * 0.05))
    top5 = float(flat[:k5].sum() / max(flat.sum(), 1e-9))

    med, oth = ctx["medical"], ctx["non_med"]
    dm = np.hypot(cx[oth][:, None] - cx[med][None, :], cy[oth][:, None] - cy[med][None, :]) * mpu
    t_resp = 15 + dm.min(axis=1) / 2.0
    t_max, t_mean = float(t_resp.max()), float(t_resp.mean())
    gd = np.hypot(cx[med][:, None] - G[:, 0][None, :], cy[med][:, None] - G[:, 1][None, :]) * mpu
    gate_med = float(gd.min(axis=1).mean())
    near_gate = np.hypot(cx[:, None] - G[:, 0][None, :], cy[:, None] - G[:, 1][None, :]).min(axis=1) * mpu
    evac = float(near_gate.mean())

    def mean_nearest(src, dst):
        if len(dst) == 0 or len(src) == 0:
            return None
        d = np.hypot(cx[src][:, None] - cx[dst][None, :], cy[src][:, None] - cy[dst][None, :]) * mpu
        return float(d.min(axis=1).mean())

    info_m = float(near_gate[ctx["info"]].mean()) if len(ctx["info"]) else 80.0
    non_rr = np.array([i for i in range(n) if i not in set(ctx["restroom"].tolist())])
    non_rest = np.array([i for i in range(n) if i not in set(ctx["rest"].tolist())])
    rr_m = mean_nearest(non_rr, ctx["restroom"]) or 80.0
    rest_m = mean_nearest(non_rest, ctx["rest"]) or 90.0

    cov = float((w * h).sum() / ctx["shape_area"])
    dc = np.hypot(cx[:, None] - cx[None, :], cy[:, None] - cy[None, :])
    np.fill_diagonal(dc, 1e9)
    nn = dc.min(axis=1)
    ideal_u = 0.55 * math.sqrt(ctx["shape_area"] / n)
    ref_m = ctx["ref_u"] * mpu
    nn_m = float(nn.mean() * mpu)

    # ---- 세부 지표: (목표, 키, 이름, 값, 단위, 만점기준, 0점기준, 비중, 설명, 소수자리) ----
    SUB = [
        ("safety", "t_max", "가장 먼 구역의 응급 도달시간", t_max, "초", 35, 165, .35,
         "응급의료센터에서 가장 먼 구역까지 (초동 15초 + 이동거리 ÷ 2.0m/s). 짧을수록 좋음", 0),
        ("safety", "t_mean", "구역 평균 응급 도달시간", t_mean, "초", 25, 125, .20,
         "모든 구역에서 가장 가까운 의료센터까지의 평균 도달시간", 0),
        ("safety", "gate_med", "의료센터-출입구 거리", gate_med, "m", 20, 150, .20,
         "의료센터에서 가장 가까운 출입구까지 평균 거리(구급차 진입 용이성)", 0),
        ("safety", "evac", "구역→출입구 평균 거리", evac, "m", 20, 140, .25,
         "각 구역에서 가장 가까운 출입구까지의 평균 거리(비상 대피 거리)", 0),
        ("flow", "obstruct", "동선 구역 관통률", obstruct * 100, "%", 0, 25, .50,
         "출입구→목적 구역 이동 경로가 다른 구역을 가로지르는 군중 비율", 1),
        ("flow", "avg_dist", "평균 이동거리", avg_dist_m, "m", 0.4 * ref_m, 1.2 * ref_m, .50,
         "방문 비중으로 가중한 출입구→목적 구역 평균 거리 (행사장 크기 대비 0.4배~1.2배 구간으로 채점)", 0),
        ("access", "info_m", "안내센터-출입구 거리", info_m, "m", 15, 105, .35,
         "안내센터가 입장 직후 닿는 거리에 있는지", 0),
        ("access", "rr_m", "화장실 평균 접근거리", rr_m, "m", 20, 120, .40,
         "각 구역에서 가장 가까운 화장실까지 평균 거리", 0),
        ("access", "rest_m", "휴게공간 평균 접근거리", rest_m, "m", 25, 155, .25,
         "각 구역에서 가장 가까운 휴게공간까지 평균 거리", 0),
        ("cong", "peak", "최대 군중 밀도", peak, "명/㎡", 0.15, 1.05, .70,
         "격자(셀)별 군중 밀도의 최댓값. 낮을수록 좋음", 2),
        ("cong", "top5", "상위 5% 격자의 군중 집중도", top5 * 100, "%", 18, 63, .30,
         "전체 군중 중 가장 붐비는 상위 5% 격자가 차지하는 비율(군중이 한곳에 몰리는 정도)", 0),
        ("space", "cov_dev", "구역 점유율의 목표 편차", abs(cov - 0.25) * 100, "%p", 0, 20, .35,
         f"구역이 차지하는 면적 비율 {cov * 100:.1f}% 와 목표(25%)의 차이. 너무 빽빽하거나 너무 휑하면 감점", 1),
        ("space", "nn_m", "구역 간 평균 최근접 거리", nn_m, "m", ideal_u * mpu, 0, .65,
         "각 구역에서 가장 가까운 다른 구역까지 거리의 평균. 이상값 이상이면 만점", 0),
    ]
    subs, tot_by = [], {k: 0.0 for k in OBJECTIVES}
    for obj, key, label, val, unit, best, worst, wt, why, dec in SUB:
        sub = float(np.clip(1 - (val - best) / (worst - best), 0, 1))
        tot_by[obj] += wt * sub
        b_txt = f"{best:.{dec}f}{unit} " + ("이하" if worst > best else "이상")
        w_txt = f"{worst:.{dec}f}{unit} " + ("이상" if worst > best else "이하")
        subs.append(dict(obj=obj, key=key, label=label, unit=unit, value=float(val), disp=f"{val:.{dec}f}{unit}",
                         sub=sub, w=wt, best_txt=b_txt, worst_txt=w_txt, why=why))
    s_safety, s_flow, s_access, s_cong, s_space = (100 * tot_by[k] for k in OBJECTIVES)
    sc = np.array([s_safety, s_flow, s_access, s_cong, s_space])
    if not detail:
        return sc, None

    zone_dens = []
    for j in range(n):
        gx0 = max(0, int((x[j] - APRON) // CW)); gx1 = min(GX, int(math.ceil((x[j] + w[j] + APRON) / CW)))
        gy0 = max(0, int((y[j] - APRON) // CH)); gy1 = min(GY, int(math.ceil((y[j] + h[j] + APRON) / CH)))
        zone_dens.append(float(dens[gy0:gy1, gx0:gx1].max()))
    active = int((dens >= 0.05).sum())
    det = dict(
        peak=peak, bottleneck=float(100 * (dens >= WARN_DENSITY).sum() / max(1, active)),
        risk_zones=int(sum(1 for d in zone_dens if d >= DANGER_DENSITY)),
        t_mean=t_mean, t_max=t_max, evac=evac, gate_med=gate_med, info_m=info_m, rr_m=rr_m, rest_m=rest_m,
        obstruct=obstruct, avg_dist_m=avg_dist_m, coverage=cov, top5=top5,
        zone_dens=zone_dens, near_gate=near_gate.tolist(),
        heat=np.round(dens, 3).tolist(), sub=subs,
    )
    return sc, det


def rect_gap(L, i, j):
    dx = max(0.0, max(L[j, 0] - (L[i, 0] + L[i, 2]), L[i, 0] - (L[j, 0] + L[j, 2])))
    dy = max(0.0, max(L[j, 1] - (L[i, 1] + L[i, 3]), L[i, 1] - (L[j, 1] + L[j, 3])))
    return math.hypot(dx, dy)


# ----------------------------------------------------------------------------
# 4) 다목적 최적화 + 5) XAI
# ----------------------------------------------------------------------------
def pareto_mask(S):
    n = len(S)
    keep = np.ones(n, bool)
    for i in range(n):
        if not keep[i]:
            continue
        dom = np.all(S >= S[i], axis=1) & np.any(S > S[i], axis=1)
        if dom.any():
            keep[i] = False
    return keep


def _zone_json(zones, L):
    out = []
    for z, r in zip(zones, L):
        d = dict(z)
        d.update(x=round(float(r[0]), 2), y=round(float(r[1]), 2), w=round(float(r[2]), 2), h=round(float(r[3]), 2))
        out.append(d)
    return out


def optimize(params: dict, custom: List[dict], pins: Dict[str, tuple], n_candidates: int = 3000,
             seed: int = 42, progress: Optional[Callable[[float, str], None]] = None) -> dict:
    prog = progress or (lambda f, m: None)
    rng = np.random.default_rng(seed)
    prog(0.02, "디지털 트윈(구역·출입구) 생성 중…")
    zones, notes, mpu, cost = build_zones(params, custom)
    sh = shape_info(params.get("shape", DEFAULT_SHAPE))
    gates = get_gates(params["gates"], sh)
    ctx = make_ctx(zones, params, mpu, gates, sh)
    weights = get_weights(params)

    # 행사장이 좁아 배치가 불가능하면 구역을 10%씩 줄이며 재시도
    shrunk = 0
    while shrunk < 8 and not any(sample_layout(zones, ctx, {}, rng) is not None for _ in range(40)):
        for z in zones:
            z["w"] = round(max(3.5, z["w"] * 0.9), 2)
            z["h"] = round(max(3.0, z["h"] * 0.9), 2)
        shrunk += 1
    if shrunk:
        notes.append(f"행사장 모양/면적에 비해 구역이 커서 배치가 불가능해, 모든 구역을 약 {int(round((1 - 0.9 ** shrunk) * 100))}% 자동 축소했습니다. (크기 배율을 낮추거나 면적을 키우세요)")
    wvec = np.array([weights[k] for k in OBJECTIVES])

    def gen(n_target, pins_):
        cands, scs, attempts = [], [], 0
        while len(cands) < n_target and attempts < n_target * 5:
            attempts += 1
            L = sample_layout(zones, ctx, pins_, rng)
            if L is None:
                continue
            cands.append(L)
            scs.append(evaluate(L, ctx)[0])
            if len(cands) % 100 == 0:
                prog(0.05 + 0.6 * len(cands) / n_target, f"배치안 생성·군중 시뮬레이션 {len(cands):,}/{n_target:,}")
        return cands, scs

    n_rand = int(n_candidates * 0.75)
    cands, scs = gen(n_rand, pins)
    used_pins = pins
    if len(cands) < 20 and pins:
        notes.append("요청하신 위치 제약을 만족하는 배치가 거의 없어 제약 없이 다시 탐색했습니다.")
        used_pins = {}
        cands, scs = gen(n_rand, used_pins)
    if len(cands) < 5:
        raise RuntimeError("배치 가능한 후보를 찾지 못했습니다. 행사장 면적을 키우거나 부스 수를 줄여 주세요.")
    n_rand_done = len(cands)

    # 상위안 변이 (진화적 탐색)
    top = np.argsort(-(np.array(scs) @ wvec))[:max(5, min(30, len(cands)))]
    n_mut = n_candidates - n_rand_done
    for i in range(max(0, n_mut)):
        base = cands[int(rng.choice(top))]
        L = mutate(base, zones, ctx, used_pins, rng)
        cands.append(L)
        scs.append(evaluate(L, ctx)[0])
        if i % 100 == 0:
            prog(0.68 + 0.2 * i / max(1, n_mut), f"상위 배치안 변이·재평가 {i:,}/{n_mut:,}")

    prog(0.9, "다목적 최적화(파레토) 및 최적안 선정 중…")
    S = np.array(scs)
    total = S @ wvec
    best = int(np.argmax(total))
    pmask = pareto_mask(S)
    rank_pct = 100.0 * (1 - (np.sum(total > total[best]) / len(total)))

    L = cands[best]
    sc, det = evaluate(L, ctx, detail=True)
    Lb = baseline_layout(zones, ctx)
    scb, detb = evaluate(Lb, ctx, detail=True)

    # ---- XAI ----
    pop_mean = S.mean(axis=0)
    pctl = [(S[:, k] < sc[k]).mean() * 100 for k in range(5)]
    contrib = []
    for k, key in enumerate(OBJECTIVES):
        contrib.append(dict(key=key, label=OBJ_LABEL[key], weight=float(weights[key]), score=float(sc[k]),
                            contribution=float(weights[key] * sc[k]), pct_rank=float(pctl[k]),
                            vs_mean=float(sc[k] - pop_mean[k]), base=float(scb[k])))
    tot = float(total[best])
    reasons = [
        f"생성한 {len(cands):,}개 배치안(군중 시뮬레이션 평가 완료) 중 종합점수 {tot:.1f}점으로 상위 {max(0.1, 100 - rank_pct):.1f}% 이내의 최적안을 선정했습니다.",
        f"응급의료센터는 가장 먼 구역까지 {fmt_sec(det['t_max'])}, 평균 {fmt_sec(det['t_mean'])}에 도달하도록 배치했고, 구급차 진입 출입구까지 약 {det['gate_med']:.0f}m입니다.",
        f"최대 군중 밀도를 {detb['peak']:.2f}→{det['peak']:.2f}명/㎡로 낮췄고, 병목 비율은 {detb['bottleneck']:.0f}%→{det['bottleneck']:.0f}%, 사고 위험구역은 {detb['risk_zones']}→{det['risk_zones']}개소입니다.",
        f"출입구에서 구역까지의 이동 동선 중 다른 구역을 관통하는 비율이 {detb['obstruct'] * 100:.0f}%→{det['obstruct'] * 100:.0f}%로 감소했습니다.",
    ]
    strong = sorted(contrib, key=lambda c: -c["pct_rank"])[:2]
    for c in strong:
        reasons.append(f"{c['label']} {c['score']:.0f}점: 후보 평균 대비 {c['vs_mean']:+.1f}p, 후보 중 상위 {max(0.1, 100 - c['pct_rank']):.0f}% 수준입니다.")
    weak = min(contrib, key=lambda c: c["pct_rank"])
    if weak["pct_rank"] < 85:
        reasons.append(f"트레이드오프: {weak['label']}({weak['score']:.0f}점)은 상대적으로 양보했습니다. 입력하신 목적·연령대 기준으로 가중치가 낮은 목표를 희생하고 안전·혼잡 목표를 우선했기 때문입니다.")
    if used_pins:
        reasons.append("사용자 요청 위치 제약(" + ", ".join(f"{ZONE_META[k]['label']}" for k in used_pins) + ")을 모든 후보에 하드 제약으로 반영했습니다.")

    n_z = len(zones)
    near = det["near_gate"]
    zr = []
    for j, z in enumerate(zones):
        gaps = [rect_gap(L, j, k) * mpu for k in range(n_z) if k != j]
        gap = min(gaps) if gaps else 0
        dz = det["zone_dens"][j]
        t_ = z["type"]
        if t_ == "stage":
            txt = f"출입구에서 {near[j]:.0f}m 떨어뜨려 입장 군중과 관람 대기열을 분리, 전면 밀집도 {dz:.2f}명/㎡."
        elif t_ == "food":
            txt = f"인접 구역과 {gap:.0f}m 이격해 줄서기 병목을 완화, 밀집도 {dz:.2f}명/㎡."
        elif t_ == "medical":
            txt = f"전 구역 {fmt_sec(det['t_max'])} 이내 도달, 출입구까지 {near[j]:.0f}m로 구급차 진입 확보."
        elif t_ == "info":
            txt = f"가장 가까운 출입구 {near[j]:.0f}m 지점에 배치해 도착 직후 안내를 제공."
        elif t_ == "restroom":
            txt = f"구역 평균 {det['rr_m']:.0f}m 안에서 접근 가능하도록 분산 배치."
        elif t_ == "rest":
            txt = f"혼잡 구역 사이 완충지대 역할, 구역 평균 {det['rest_m']:.0f}m 거리, 밀집도 {dz:.2f}명/㎡."
        else:
            txt = f"인접 구역과 {gap:.0f}m 이격, 밀집도 {dz:.2f}명/㎡로 병목 없이 수용."
        zr.append(dict(name=z["name"], icon=z["icon"], text=txt))

    alts = []
    for key, nm in (("safety", "안전 최우선안"), ("cong", "혼잡 최소화안"), ("flow", "동선 최단안")):
        k = OBJECTIVES.index(key)
        cand_idx = np.where(pmask)[0]
        i2 = int(cand_idx[np.argmax(S[cand_idx, k])])
        if i2 == best:
            continue
        diff = S[i2] - S[best]
        lose = OBJECTIVES[int(np.argmin(diff))]
        alts.append(dict(name=nm, total=float(total[i2]), delta_total=float(total[i2] - total[best]),
                         scores={OBJ_LABEL[o]: float(S[i2, q]) for q, o in enumerate(OBJECTIVES)},
                         note=f"{OBJ_LABEL[key]}은 {diff[k]:+.1f}p 높지만 {OBJ_LABEL[lose]}이 {diff[OBJECTIVES.index(lose)]:+.1f}p, 종합 {total[i2] - total[best]:+.1f}점이라 채택하지 않았습니다."))

    sel = rng.choice(len(S), size=min(700, len(S)), replace=False)
    cloud = [dict(safety=float(S[i, 0]), flow=float(S[i, 1]), access=float(S[i, 2]), cong=float(S[i, 3]),
                  space=float(S[i, 4]), total=float(total[i]), pareto=bool(pmask[i])) for i in sel]

    # ---- 점수 산출 근거 ----
    evid = []
    for a_, b_ in zip(det["sub"], detb["sub"]):
        evid.append(dict(obj=a_["obj"], objLabel=OBJ_LABEL[a_["obj"]], label=a_["label"], unit=a_["unit"],
                         v_after=a_["disp"], v_before=b_["disp"], sub_after=a_["sub"], sub_before=b_["sub"],
                         w=a_["w"], best_txt=a_["best_txt"], worst_txt=a_["worst_txt"], why=a_["why"]))
    formulas = {}
    for i_, k_ in enumerate(OBJECTIVES):
        its = [e for e in evid if e["obj"] == k_]
        formulas[k_] = " + ".join(f"{e['w']:.2f}×{e['sub_after'] * 100:.0f}" for e in its) + f" = {sc[i_]:.1f}점"
    total_formula = " + ".join(f"{weights[k_]:.2f}×{sc[i_]:.0f}" for i_, k_ in enumerate(OBJECTIVES)) + f" = {tot:.1f}점"
    pr = PURPOSES[params["purpose"]]
    zone_sizes = [dict(name=z["name"], type=ZONE_META[z["type"]]["label"],
                       w_m=round(z["w"] * mpu / 1.35, 1), h_m=round(z["h"] * mpu / 1.35, 1)) for z in zones]
    assumptions = [
        f"축척: 가상 좌표 1단위 ≈ {mpu:.2f}m (행사장 면적 {params['area_m2']:,}㎡, 모양 '{sh['name']}' 기준). 배치도의 구역은 가독성을 위해 실제 치수의 1.35배로 확대해 그립니다.",
        f"피크 동시 체류 인원 = 예상 방문객 {params['visitors']:,}명의 50% ≈ {params['visitors'] * 0.5:,.0f}명. 이 중 75%는 구역에 머물고 25%는 출입구→구역으로 이동 중이라고 가정했습니다.",
        "구역별 방문 비중은 구역 종류별 매력도(공연장 0.30, 푸드존 0.22, 체험부스 0.20, 휴게 0.10 등)에 비례하며, 입장은 주출입구 40%·나머지 출입구 균등 분담으로 가정했습니다.",
        f"군중 밀도 = 4×4 단위 격자(약 {ctx['cell_area']:.0f}㎡)의 인원 ÷ 면적. 혼잡 0.5명/㎡, 위험 0.9명/㎡ 기준은 이 시뮬레이션 안에서 배치안을 상대 비교하기 위한 값이며 법정 안전기준이 아닙니다.",
        "응급 도달시간 = 초동 15초 + 직선거리 ÷ 2.0m/s. 장애물·인파로 인한 지연은 반영하지 않았습니다.",
        "세부점수 = 만점 기준과 0점 기준 사이를 선형 보간(0~100). 목표 점수 = Σ(세부점수 × 비중), 종합 점수 = Σ(가중치 × 목표 점수).",
        f"가중치는 기본값(안전 25·혼잡 25·동선 20·접근 15·공간 15)에 행사 목적('{params['purpose']}')과 연령대('{params['age']}') 보정을 더한 뒤 합이 100%가 되도록 정규화했습니다.",
        "만점/0점 기준값은 이 도구의 설정값입니다. 실제 시행 시에는 현장 여건과 관할 기관 기준에 맞춰 조정해야 합니다.",
    ]

    prog(1.0, "완료")
    return dict(
        zones=_zone_json(zones, L), before_zones=_zone_json(zones, Lb), gates=gates,
        scores={k: float(sc[i]) for i, k in enumerate(OBJECTIVES)},
        before_scores={k: float(scb[i]) for i, k in enumerate(OBJECTIVES)},
        total=tot, before_total=float(scb @ wvec),
        detail=det, before_detail=detb, weights=weights, mpu=mpu,
        stats=dict(generated=len(cands), randomly=n_rand_done, mutated=len(cands) - n_rand_done,
                   pareto=int(pmask.sum()), rank_pct=float(rank_pct), zones=n_z),
        xai=dict(contrib=contrib, reasons=reasons, zone_reasons=zr, alternatives=alts),
        cloud=cloud, notes=notes, cost=dict(total=float(cost), budget=params["budget"]),
        evidence=evid, formulas=formulas, total_formula=total_formula, assumptions=assumptions,
        weight_detail=weight_breakdown(params), zone_sizes=zone_sizes,
        shape=dict(name=sh["name"], kind=sh["kind"], dome=bool(sh.get("dome")), bbox=list(sh["bbox"]),
                   outline=[[round(p_[0], 2), round(p_[1], 2)] for p_ in sh["outline"]], area=sh["area"]),
        params=dict(params), theme=VENUES[params["venue"]], pins={k: list(v) for k, v in used_pins.items()},
    )


# ----------------------------------------------------------------------------
# 대화형 명령 해석 (규칙 기반)
# ----------------------------------------------------------------------------
TYPE_KW = [
    ("medical", ["응급", "의료", "구급", "메디컬"]),
    ("stage", ["무대", "공연장", "스테이지"]),
    ("food", ["푸드", "음식", "먹거리", "식음"]),
    ("booth", ["체험"]),
    ("rest", ["휴게", "휴식", "쉼터", "라운지"]),
    ("info", ["안내"]),
    ("restroom", ["화장실"]),
]
DIR_KW = [
    (["우측", "오른쪽", "오른", "동쪽"], "x", (0.65, 0.93)),
    (["좌측", "왼쪽", "왼", "서쪽"], "x", (0.07, 0.35)),
    (["상단", "위쪽", "북쪽", "위로"], "y", (0.07, 0.35)),
    (["하단", "아래", "남쪽", "입구"], "y", (0.65, 0.93)),
    (["중앙", "가운데"], "xy", (0.35, 0.65, 0.35, 0.65)),
]
CAT_OF_TYPE = {"food": "푸드", "booth": "체험", "rest": "휴게", "stage": "공연"}


def _dir_ranges(c: str):
    xr, yr, found = (0.0, 1.0), (0.0, 1.0), False
    for kws, axis, rng_ in DIR_KW:
        if any(k in c for k in kws):
            found = True
            if axis == "x":
                xr = rng_
            elif axis == "y":
                yr = rng_
            else:
                xr, yr = rng_[:2], rng_[2:]
    return found, xr, yr


def parse_command(text: str) -> dict:
    pins, extras, msgs = {}, [], []
    clauses = [c.strip() for c in re.split(r"[,.;\n]+|(?<=고)\s+|\s그리고\s|\s및\s", text) if c.strip()]
    for c in clauses:
        types = [t for t, kws in TYPE_KW if any(k in c for k in kws)]
        if any(k in c for k in ("추가", "늘려", "만들어")):
            m = re.search(r"(\d+)\s*개", c)
            cnt = int(m.group(1)) if m else 1
            name = re.sub(r"\d+\s*개|추가|해줘|해 줘|해주세요|늘려줘|만들어줘|을|를|도|좀|\s+$", " ", c).strip()
            for kws, _ax, _r in DIR_KW:
                for k in kws:
                    name = name.replace(k, " ")
            name = re.sub(r"(에|으로|로|쪽|에서)\s*(?=\s|$)", " ", name)
            name = re.sub(r"\s+", " ", name).strip() or (ZONE_META[types[0]]["label"] if types else "사용자 부스")
            cat = CAT_OF_TYPE.get(types[0], "기타") if types else "기타"
            extras.append(dict(name=name, cat=cat, w=9 if cat != "푸드" else 10, h=6, count=cnt))
            msgs.append(f"'{name}' {cnt}개를 부스 목록에 추가했습니다.")
            fd, xr, yr = _dir_ranges(c)
            if fd:
                pins["custom"] = (xr[0], xr[1], yr[0], yr[1])
                msgs.append("추가 부스를 요청하신 방향에 배치하도록 제약을 걸었습니다.")
            continue
        if not types:
            continue
        xr, yr = (0.0, 1.0), (0.0, 1.0)
        found = False
        for kws, axis, rng_ in DIR_KW:
            if any(k in c for k in kws):
                found = True
                if axis == "x":
                    xr = rng_
                elif axis == "y":
                    yr = rng_
                else:
                    xr, yr = rng_[:2], rng_[2:]
        if found:
            for t in types:
                pins[t] = (xr[0], xr[1], yr[0], yr[1])
                msgs.append(f"{ZONE_META[t]['label']} 위치 제약을 적용했습니다.")
    return dict(pins=pins, extras=extras, msgs=msgs)

# ===== TWIN =====

TWIN_TEMPLATE = r"""
<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Pretendard,-apple-system,system-ui,sans-serif;background:transparent;color:#0f172a}
.bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px}
button{cursor:pointer;border:1px solid #cbd5e1;background:#f1f5f9;color:#334155;padding:6px 11px;border-radius:8px;font-size:12px;font-weight:700;font-family:inherit}
button:hover{background:#e2e8f0}
button.on{background:#2563eb;color:#fff;border-color:#1d4ed8}
button.warn.on{background:#f59e0b;border-color:#d97706}
button.danger.on{background:#ef4444;border-color:#dc2626}
.badge{font-size:11px;font-weight:700;color:#2563eb;background:#eff6ff;padding:3px 9px;border-radius:12px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:12px}
.card h4{font-size:13px;font-weight:800;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.wrap{position:relative;width:100%;background:#1e293b;border-radius:10px;overflow:hidden}
#wrap{aspect-ratio:1.85}
#wrap2{aspect-ratio:1.6}
.wrap canvas,.wrap .c3{position:absolute;inset:0;width:100%;height:100%}
.c3{cursor:grab;background:#dbe8f5}
.legend{position:absolute;left:8px;bottom:8px;background:rgba(255,255,255,.93);border-radius:8px;padding:6px 10px;font-size:11px;font-weight:700;display:grid;grid-template-columns:repeat(3,auto);gap:3px 12px;z-index:5;pointer-events:none}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px}
.hint{position:absolute;right:8px;top:8px;background:rgba(15,23,42,.65);color:#fff;font-size:10.5px;padding:4px 9px;border-radius:8px;z-index:5;pointer-events:none}
.tl{display:flex;align-items:center;gap:8px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:6px 10px;margin-bottom:8px;font-size:12px;font-weight:700;flex-wrap:wrap}
.tl input{flex:1;min-width:120px;accent-color:#2563eb}
.tm{background:#2563eb;color:#fff;border-radius:16px;padding:2px 10px;font-size:12px;min-width:56px;text-align:center}
.grid2{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:12px;margin-top:12px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.kpi{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:10px}
.kpi div{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;font-size:11px;color:#64748b;font-weight:700}
.kpi b{display:block;font-size:17px;color:#0f172a}
.hl{font-size:11px;color:#64748b;font-weight:700;display:flex;justify-content:space-around;margin-top:6px}
.zl{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:5px;font-size:11px;font-weight:700;max-height:190px;overflow:auto}
.zl span{background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid var(--c);border-radius:6px;padding:4px 7px}
</style></head><body>
<div class="bar">
  <button id="bMode" class="on" onclick="setMode('after')">✦ AI 최적 배치</button>
  <button id="bModeB" onclick="setMode('before')">설계 전(기존) 배치</button>
  <span style="width:10px"></span>
  <button id="b3d" class="on" onclick="setView(true)">🧊 3D 입체 설계도</button>
  <button id="b2d" onclick="setView(false)">🗺️ 2D 평면도</button>
  <button id="bHeat3" onclick="togHeat3()">🔥 히트맵 겹치기</button>
  <button id="bDome" class="on" onclick="togDome()" style="display:none">🏛️ 지붕 표시</button>
  <span style="flex:1"></span>
  <button id="bPlay" onclick="togSim()">⏸ 시뮬레이션 정지</button>
  <button id="bRain" class="warn" onclick="togRain()">🌧️ 우천</button>
  <button id="bEmg" class="danger" onclick="togEmg()">🚨 응급환자 발생</button>
</div>
<div class="tl">⏰ 시간대
  <button id="bTl" onclick="togTl()">▶ 재생</button>
  <input type="range" id="tSl" min="10" max="20" step="1" value="14" oninput="setTime(+this.value)">
  <span class="tm" id="tTxt">14:00</span><span id="tDesc" style="color:#64748b;font-weight:600"></span>
</div>
<div class="card"><h4><span>🗺️ 행사장 디지털 트윈 <span id="verTxt" style="color:#64748b;font-weight:600"></span></span>
  <span><span class="badge" id="peopleTxt"></span> <span class="badge" id="status">실시간 군중 시뮬레이션</span></span></h4>
  <div class="wrap" id="wrap">
    <canvas id="cv" style="display:none"></canvas><canvas id="hm" style="display:none;opacity:.75;pointer-events:none"></canvas><canvas id="pp" style="display:none;pointer-events:none"></canvas>
    <div class="c3" id="c3"></div>
    <div class="legend" id="legend"></div>
    <div class="hint" id="hint">드래그: 회전 · 휠: 확대/축소</div>
  </div>
</div>
<div class="grid2">
  <div class="card"><h4><span>🔥 실시간 군중 밀집도</span><span class="badge" id="envTxt">일반 상태</span></h4>
    <div class="wrap" id="wrap2"><canvas id="hm2"></canvas></div>
    <div class="hl"><span style="color:#10b981">🟢 원활</span><span style="color:#eab308">🟡 보통(0.25~)</span><span style="color:#f97316">🟠 혼잡(0.5~)</span><span style="color:#ef4444">🔴 위험(0.9~)</span></div>
    <div style="font-size:10px;color:#94a3b8;margin-top:4px;text-align:center">단위: 명/㎡ · 구역 체류 + 출입구 이동 군중 반영</div>
  </div>
  <div class="card"><h4><span>📊 현재 상태</span></h4>
    <div class="kpi">
      <div>현재 최대 밀도<b id="kPeak">-</b></div><div>혼잡 구역 비율<b id="kBott">-</b></div>
      <div>응급 최대 도달<b id="kMed">-</b></div><div>위험 구역<b id="kRisk">-</b></div>
    </div>
    <div style="font-size:12px;font-weight:800;margin:6px 0">📍 배치된 구역 <span id="zCnt" style="color:#64748b"></span></div>
    <div class="zl" id="zlist"></div>
  </div>
</div>
<script>
const D = __DATA__;
const WW=160, WH=100, GX=40, GY=25;
let mode='after', sim=true, rain=false, emg=null, tHour=14, tlTimer=null, is3d=true, heat3=false;
const $=id=>document.getElementById(id);
const cv=$('cv'), hm=$('hm'), pp=$('pp'), hm2=$('hm2');
const cx=cv.getContext('2d'), hx=hm.getContext('2d'), px=pp.getContext('2d'), h2=hm2.getContext('2d');
const wrap=$('wrap'), wrap2=$('wrap2');
let W=0,H=0,S=1,W2=0,H2=0;
const Z=()=> mode==='after'?D.zones:D.before_zones;
const mpu=D.mpu, cellArea=(WW/GX)*(WH/GY)*mpu*mpu;
const SHB=D.shape.bbox, SHC=[(SHB[0]+SHB[2])/2,(SHB[1]+SHB[3])/2];
function outlinePath(c,sx,sy){ const o=D.shape.outline; c.beginPath(); o.forEach((p,i)=>{ if(i) c.lineTo(p[0]*sx,p[1]*sy); else c.moveTo(p[0]*sx,p[1]*sy); }); c.closePath(); }
function pieces(step){ const o=D.shape.outline, out=[]; for(let i=0;i<o.length;i++){ const a=o[i], b=o[(i+1)%o.length]; const dx=b[0]-a[0], dy=b[1]-a[1], L=Math.hypot(dx,dy), n=Math.max(1,Math.round(L/step));
  for(let k=0;k<n;k++){ const t0=k/n,t1=(k+1)/n; const x0=a[0]+dx*t0,y0=a[1]+dy*t0,x1=a[0]+dx*t1,y1=a[1]+dy*t1; out.push({x:(x0+x1)/2,y:(y0+y1)/2,len:Math.hypot(x1-x0,y1-y0),ang:Math.atan2(dy,dx)}); } } return out; }
function insideShape(x,y){ const o=D.shape.outline; let ins=false; for(let i=0,j=o.length-1;i<o.length;j=i++){ const xi=o[i][0],yi=o[i][1],xj=o[j][0],yj=o[j][1]; if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi)) ins=!ins; } return ins; }
function mv(a,nx,ny){ if(D.shape.kind!=='poly'||insideShape(nx,ny)||!insideShape(a.x,a.y)){a.x=nx;a.y=ny;} else if(insideShape(nx,a.y)){a.x=nx;} else if(insideShape(a.x,ny)){a.y=ny;} else { a.x+=(SHC[0]-a.x)*.03; a.y+=(SHC[1]-a.y)*.03; } }
function treePos(pc){ const vx=SHC[0]-pc.x, vy=SHC[1]-pc.y, vl=Math.hypot(vx,vy)||1; return [pc.x+vx/vl*3.5, pc.y+vy/vl*3.5]; }
const NAG=320; let agents=[]; let raindrops=[];
let heat=new Float32Array(GX*GY);

$('legend').innerHTML=
 [['#8b5cf6','공연장'],['#3b82f6','체험부스'],['#f59e0b','푸드존'],['#10b981','휴게공간'],['#ef4444','응급의료'],['#0ea5e9','안내센터'],['#06b6d4','화장실'],['#ec4899','사용자 부스'],['#1e293b','출입구']]
 .map(a=>`<span><i style="background:${a[0]}"></i>${a[1]}</span>`).join('');

function resize(){
  W=wrap.clientWidth; H=wrap.clientHeight; S=W/WW;
  [cv,hm,pp].forEach(c=>{c.width=W;c.height=H});
  W2=wrap2.clientWidth; H2=wrap2.clientHeight; hm2.width=W2; hm2.height=H2;
  drawBase(); if(R3){ size3(); }
}
function factor(h){ if(h<12)return .55; if(h<15)return 1.0; if(h<18)return .8; return .65; }
function descT(h){ return h<12?'개장 초반 - 순차 입장(여유)':h<15?'피크 - 푸드·공연 집중(혼잡)':h<18?'오후 - 체험·휴게 분산':'폐장 전 - 공연 집중 및 퇴장'; }
function pickZone(){
  const Zs=Z(); let tot=0; const w=Zs.map(z=>{const a=(z.type==='medical')?0:z.attract*(z.type==='stage'&&tHour>=18?1.5:1)*(z.type==='food'&&tHour>=12&&tHour<15?1.5:1);tot+=a;return a});
  let r=Math.random()*tot; for(let i=0;i<Zs.length;i++){ r-=w[i]; if(r<=0) return i; } return 0;
}
function spawn(a){
  const g=D.gates[Math.floor(Math.random()*D.gates.length)];
  let sx=g.x,sy=g.y; for(let k=0;k<12;k++){ const tx=g.x+(Math.random()-.5)*6, ty=g.y+(Math.random()-.5)*6; if(insideShape(tx,ty)){sx=tx;sy=ty;break;} } a.x=sx; a.y=sy; a.leaving=false; a.dwell=0; a.zone=pickZone(); setTarget(a);
}
function setTarget(a){
  const z=Z()[a.zone]; a.tx=z.x-1.5+Math.random()*(z.w+3); a.ty=z.y-1.5+Math.random()*(z.h+3);
  a.sp=.28+Math.random()*.2;
}
function initAgents(){
  agents=[]; for(let i=0;i<NAG;i++){ const a={}; spawn(a); const t=Math.random(); a.x=a.x+(a.tx-a.x)*t; a.y=a.y+(a.ty-a.y)*t; a.active=i<NAG*factor(tHour); agents.push(a);}
  raindrops=[]; for(let i=0;i<110;i++) raindrops.push({x:Math.random()*W,y:Math.random()*H,l:7+Math.random()*10,v:6+Math.random()*6});
}
function step(dt){
  const f=factor(tHour); const n=Math.floor(NAG*f);
  agents.forEach((a,i)=>{ a.active=i<n; if(!a.active) return;
    if(a.dwell>0){ a.dwell-=dt; a.x+=(Math.random()-.5)*.06; a.y+=(Math.random()-.5)*.06;
      if(a.dwell<=0){ if(Math.random()<.35){ a.leaving=true; const g=D.gates[Math.floor(Math.random()*D.gates.length)]; a.tx=g.x; a.ty=g.y; } else { a.zone=pickZone(); setTarget(a);} } return; }
    let dx=a.tx-a.x, dy=a.ty-a.y, d=Math.hypot(dx,dy);
    let sp=a.sp*(rain?1.6:1);
    if(rain&&!a.leaving){ const st=Z().find(z=>z.type==='stage'); if(st){a.tx=st.x+st.w/2; a.ty=st.y+st.h/2+st.h*.7; dx=a.tx-a.x; dy=a.ty-a.y; d=Math.hypot(dx,dy);} }
    if(emg){ const ex=a.x-emg.x, ey=a.y-emg.y, ed=Math.hypot(ex,ey); if(ed<9&&ed>0){ a.x+=ex/ed*.5; a.y+=ey/ed*.5; } }
    if(d<1.2){ if(a.leaving){ spawn(a);} else { a.dwell=3+Math.random()*9; } }
    else { mv(a,a.x+dx/d*sp,a.y+dy/d*sp); }
  });
  for(let i=0;i<agents.length;i+=2){ const a=agents[i]; if(!a.active) continue; const b=agents[(i*7+3)%agents.length]; if(!b.active) continue;
    const dx=a.x-b.x, dy=a.y-b.y, d=Math.hypot(dx,dy); if(d>0&&d<1.2){ a.x+=dx/d*.1; a.y+=dy/d*.1; } }
  if(emg){ const meds=Z().filter(z=>z.type==='medical'); let best=null,bd=1e9;
    meds.forEach(m=>{const d=Math.hypot(m.x+m.w/2-emg.x,m.y+m.h/2-emg.y); if(d<bd){bd=d;best=m;}});
    emg.target=best;
    if(best&&bd>1.5){ emg.x+=(best.x+best.w/2-emg.x)/bd*.9; emg.y+=(best.y+best.h/2-emg.y)/bd*.9;
      $('status').textContent='🚑 응급 이송 중… 의료센터까지 '+(bd*mpu).toFixed(0)+'m';
    } else if(best){ $('status').textContent='✅ 의료센터 도착 · 이송 소요 '+Math.round((performance.now()-emg.t0)/1000)+'초(시뮬레이션)'; } }
  raindrops.forEach(r=>{r.y+=r.v;r.x-=1;if(r.y>H){r.y=0;r.x=Math.random()*W}});
}
function updateHeat(){
  const n=Math.floor(NAG*factor(tHour)); const per=D.params.visitors*.5/Math.max(1,n)*factor(tHour);
  const g=new Float32Array(GX*GY);
  agents.forEach(a=>{ if(!a.active) return; const ix=Math.min(GX-1,Math.max(0,Math.floor(a.x/(WW/GX)))), iy=Math.min(GY-1,Math.max(0,Math.floor(a.y/(WH/GY)))); g[iy*GX+ix]+=per; });
  const o=new Float32Array(GX*GY);
  for(let y=0;y<GY;y++)for(let x=0;x<GX;x++){ let s=0,c=0; for(let j=-1;j<=1;j++)for(let i=-1;i<=1;i++){const xx=x+i,yy=y+j; if(xx>=0&&xx<GX&&yy>=0&&yy<GY){const w=(i==0&&j==0)?2:1; s+=g[yy*GX+xx]*w; c+=w;}} o[y*GX+x]=s/c/cellArea; }
  for(let k=0;k<o.length;k++) heat[k]=heat[k]*.85+o[k]*.15;
}
function heatColor(d){ if(d<.12) return null; if(d<.25) return 'rgba(16,185,129,.5)'; if(d<.5) return 'rgba(234,179,8,.65)'; if(d<.9) return 'rgba(249,115,22,.75)'; return 'rgba(239,68,68,.88)'; }
function drawHeat(ctx,w,h,bg){
  ctx.clearRect(0,0,w,h);
  if(bg){ ctx.fillStyle='#020617'; ctx.fillRect(0,0,w,h); ctx.save(); outlinePath(ctx,w/WW,h/WH); ctx.fillStyle='#0f172a'; ctx.fill(); ctx.restore(); }
  const cw=w/GX, ch=h/GY; let peak=0,hot=0,act=0;
  ctx.save(); outlinePath(ctx,w/WW,h/WH); ctx.clip();
  for(let y=0;y<GY;y++)for(let x=0;x<GX;x++){ const d=heat[y*GX+x]; peak=Math.max(peak,d); if(d>=.12) act++; if(d>=.5) hot++; const c=heatColor(d); if(c){ ctx.fillStyle=c; ctx.fillRect(x*cw,y*ch,cw+.5,ch+.5);} }
  ctx.restore();
  if(bg){ outlinePath(ctx,w/WW,h/WH); ctx.strokeStyle='#94a3b8'; ctx.lineWidth=2; ctx.stroke();
    Z().forEach(z=>{ ctx.strokeStyle='rgba(255,255,255,.45)'; ctx.lineWidth=1; ctx.strokeRect(z.x*w/WW,z.y*h/WH,z.w*w/WW,z.h*h/WH);
      ctx.fillStyle='rgba(255,255,255,.85)'; ctx.font='bold 10px Pretendard,sans-serif'; ctx.textAlign='center'; ctx.fillText(z.name,(z.x+z.w/2)*w/WW,(z.y+z.h/2)*h/WH+3,z.w*w/WW); }); }
  return [peak,hot,act];
}
/* ---------- 2D 평면도 ---------- */
function drawBase(){
  const T=D.theme; cx.clearRect(0,0,W,H);
  cx.fillStyle='#334155'; cx.fillRect(0,0,W,H);
  cx.save(); outlinePath(cx,S,S); cx.clip();
  cx.fillStyle=rain?T.groundRain:T.ground; cx.fillRect(0,0,W,H);
  if(T.kind==='outdoor'&&!D.shape.dome){ cx.fillStyle='rgba(0,0,0,.14)'; pieces(9).forEach(pc=>{ const t=treePos(pc); cx.beginPath(); cx.arc(t[0]*S,t[1]*S,11,0,7); cx.fill(); }); }
  else { cx.strokeStyle='rgba(0,0,0,.12)'; cx.lineWidth=1; for(let x=0;x<W;x+=W/16){cx.beginPath();cx.moveTo(x,0);cx.lineTo(x,H);cx.stroke();} for(let y=0;y<H;y+=H/10){cx.beginPath();cx.moveTo(0,y);cx.lineTo(W,y);cx.stroke();} }
  cx.restore();
  outlinePath(cx,S,S); cx.strokeStyle='#f8fafc'; cx.lineWidth=D.shape.dome?3:5; cx.stroke();
  if(D.shape.dome){ cx.save(); cx.setLineDash([8,6]); cx.strokeStyle='rgba(255,255,255,.55)'; cx.lineWidth=1.5; cx.beginPath(); cx.ellipse(SHC[0]*S,SHC[1]*S,(SHB[2]-SHB[0])/2*S*.94,(SHB[3]-SHB[1])/2*S*.94,0,0,7); cx.stroke(); cx.restore(); }
  cx.strokeStyle=T.path; cx.globalAlpha=.6; cx.lineCap='round'; cx.lineWidth=Math.max(4,S*1.6);
  Z().forEach(z=>{ const g=nearestGate(z); cx.beginPath(); cx.moveTo(g.x*S,g.y*S); cx.lineTo((z.x+z.w/2)*S,(z.y+z.h/2)*S); cx.stroke(); });
  cx.globalAlpha=1;
  Z().forEach(z=>{ const x=z.x*S,y=z.y*S,w=z.w*S,h=z.h*S;
    cx.fillStyle='rgba(0,0,0,.28)'; cx.fillRect(x+3,y+3,w,h);
    cx.fillStyle=z.color; cx.beginPath(); cx.roundRect(x,y,w,h,7); cx.fill(); cx.strokeStyle='#fff'; cx.lineWidth=2; cx.stroke();
    cx.textAlign='center'; cx.fillStyle='#fff';
    cx.font=Math.max(14,Math.min(26,h*.4))+'px sans-serif'; cx.fillText(z.icon,x+w/2,y+h/2-2);
    cx.font='bold '+Math.max(11,Math.min(15,w/6.5))+'px Pretendard,sans-serif'; cx.shadowColor='rgba(0,0,0,.6)'; cx.shadowBlur=3;
    cx.fillText(z.name,x+w/2,y+h/2+Math.max(14,Math.min(20,h*.28)),w-6); cx.shadowBlur=0; });
  D.gates.forEach(g=>{ cx.fillStyle='#1e293b'; cx.beginPath(); cx.arc(g.x*S,g.y*S,10,0,7); cx.fill(); cx.strokeStyle='#fff'; cx.lineWidth=2; cx.stroke();
    cx.fillStyle='#fff'; cx.font='12px sans-serif'; cx.textAlign='center'; cx.fillText('🚪',g.x*S,g.y*S+4);
    const up=g.y>SHC[1]; cx.font='bold 11px Pretendard'; cx.fillStyle='#fff'; cx.shadowColor='#000'; cx.shadowBlur=3; cx.fillText(g.name,g.x*S,g.y*S+(up?-15:24)); cx.shadowBlur=0; });
}
function nearestGate(z){ let b=D.gates[0],bd=1e9; D.gates.forEach(g=>{const d=Math.hypot(g.x-(z.x+z.w/2),g.y-(z.y+z.h/2)); if(d<bd){bd=d;b=g;}}); return b; }
function drawPeople(){ px.clearRect(0,0,W,H);
  agents.forEach(a=>{ if(!a.active) return; px.fillStyle=rain?'#93c5fd':'#fff'; px.strokeStyle='rgba(0,0,0,.4)'; px.lineWidth=.8; px.beginPath(); px.arc(a.x*S,a.y*S,3.2,0,7); px.fill(); px.stroke(); });
  if(emg){ px.strokeStyle='#ef4444'; px.lineWidth=3; px.setLineDash([6,5]);
    if(emg.target){ px.beginPath(); px.moveTo(emg.x*S,emg.y*S); px.lineTo((emg.target.x+emg.target.w/2)*S,(emg.target.y+emg.target.h/2)*S); px.stroke(); }
    px.setLineDash([]); px.fillStyle='#ef4444'; px.beginPath(); px.arc(emg.x*S,emg.y*S,9+Math.sin(performance.now()/120)*2,0,7); px.fill();
    px.fillStyle='#fff'; px.font='bold 12px Pretendard'; px.textAlign='center'; px.fillText('🚑 응급',emg.x*S,emg.y*S-14); }
  if(rain){ px.strokeStyle='rgba(147,197,253,.55)'; px.lineWidth=1.1; raindrops.forEach(r=>{px.beginPath();px.moveTo(r.x,r.y);px.lineTo(r.x-2,r.y+r.l);px.stroke();}); }
}
/* ---------- 3D 아이소메트릭 ---------- */
let R3=null,S3,C3,G3,bodyM,headM,rainPts,emgGrp,emgLine,heatPlane,heatTex;
let yaw=.55,pitch=.72,zoom3=1.45*Math.min(1.45,WW/Math.max(D.shape.bbox[2]-D.shape.bbox[0],(D.shape.bbox[3]-D.shape.bbox[1])*1.3))*(D.shape.dome?.82:1),drag=false,lx=0,ly=0;
const DUM=new THREE.Object3D();
function M(c,o){return new THREE.MeshLambertMaterial(Object.assign({color:new THREE.Color(c)},o||{}));}
function bx(p,w,h,d,c,x,y,z,o){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),M(c,o));m.position.set(x,y,z);p.add(m);return m;}
function cyl(p,rt,rb,h,c,x,y,z,seg){const m=new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,seg||12),M(c));m.position.set(x,y,z);p.add(m);return m;}
function cone(p,r,h,c,x,y,z,seg){const m=new THREE.Mesh(new THREE.ConeGeometry(r,h,seg||8),M(c));m.position.set(x,y,z);p.add(m);return m;}
function tree(p,x,z){cyl(p,.5,.6,2.4,'#7c4a21',x,1.4,z,8);cone(p,2.3,4.6,'#2f855a',x,4.8,z,8);}
function seats(p,rows,cols,x0,z0,dx,dz,c){const im=new THREE.InstancedMesh(new THREE.BoxGeometry(1.2,1,1.2),M(c),rows*cols);let k=0;
  for(let r=0;r<rows;r++)for(let q=0;q<cols;q++){DUM.position.set(x0+q*dx,.9,z0+r*dz);DUM.scale.set(1,1,1);DUM.rotation.set(0,0,0);DUM.updateMatrix();im.setMatrixAt(k++,DUM.matrix);} p.add(im);}
function labelSprite(text,color){
  const c=document.createElement('canvas'); c.width=640; c.height=150; const t=c.getContext('2d');
  t.fillStyle='rgba(255,255,255,.96)'; t.beginPath(); t.roundRect(4,4,632,142,28); t.fill();
  t.fillStyle=color; t.beginPath(); t.roundRect(4,4,30,142,14); t.fill();
  t.strokeStyle='rgba(15,23,42,.25)'; t.lineWidth=3; t.beginPath(); t.roundRect(4,4,632,142,28); t.stroke();
  t.fillStyle='#0f172a'; t.font='bold 66px Pretendard,sans-serif'; t.textAlign='center'; t.textBaseline='middle'; t.fillText(text,340,78,570);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),depthTest:false,transparent:true})); sp.renderOrder=10; return sp;
}
function buildZone3(z){
  const g=new THREE.Group(); const cxz=z.x+z.w/2-WW/2, czz=z.y+z.h/2-WH/2; g.position.set(cxz,0,czz); G3.add(g);
  const w=z.w,h=z.h; const pale=new THREE.Color(z.color).lerp(new THREE.Color('#ffffff'),.65).getStyle();
  bx(g,w,.5,h,pale,0,.25,0);
  let top=8;
  switch(z.type){
    case 'stage':{ const s=(czz<0)?1:-1;
      bx(g,w*.96,3,h*.42,'#7c3aed',0,2,-s*h*.28); bx(g,w*.96,.4,h*.42,'#ddd6fe',0,3.7,-s*h*.28);
      bx(g,w*.92,z.ht,.9,'#312e81',0,3.5+z.ht/2,-s*h*.48,{emissive:new THREE.Color('#4338ca')});
      [-1,1].forEach(k=>bx(g,1.2,z.ht+1.5,1.2,'#1e1b4b',k*w*.46,(z.ht+1.5)/2+3.5,-s*h*.48));
      const rows=Math.max(1,Math.floor((h*.5-2.2)/1.9)+1), cols=Math.max(3,Math.floor((w-3)/1.9));
      seats(g,rows,cols,-(cols-1)*.95,s*1.4,1.9,s*1.9,'#1e3a8a'); top=z.ht+6; break; }
    case 'food':{
      bx(g,w*.9,3,2,'#92400e',0,2,-h*.33);
      const n=Math.max(3,Math.round(w/3)); for(let i=0;i<n;i++) bx(g,w*.95/n,.5,h*.42,(i%2?'#ffffff':z.color),-w*.475+(i+.5)*w*.95/n,6.4,-h*.28);
      [-1,1].forEach(k=>{cyl(g,.25,.25,5.8,'#475569',k*w*.46,3.3,-h*.48,8);cyl(g,.25,.25,5.8,'#475569',k*w*.46,3.3,-h*.08,8);});
      [-1,0,1].forEach(t=>{const x=t*w*.28; cyl(g,1.5,1.5,.3,'#ffffff',x,2,h*.2,16); cyl(g,.3,.3,1.6,'#64748b',x,1.2,h*.2,8); cyl(g,.6,.6,.8,z.color,x-2.2,1,h*.2,10); cyl(g,.6,.6,.8,z.color,x+2.2,1,h*.2,10);});
      top=8; break; }
    case 'rest':{
      bx(g,w*.96,.5,h*.96,'#4fa15a',0,.5,0); bx(g,w*.4,1,1.3,'#a16207',-w*.2,1.3,h*.12); bx(g,w*.4,1,1.3,'#a16207',w*.2,1.3,-h*.12);
      tree(g,-w*.4,-h*.3); tree(g,w*.4,h*.3); tree(g,w*.38,-h*.36); top=9; break; }
    case 'medical':{
      bx(g,w*.8,5,h*.7,'#ffffff',0,3,0); bx(g,w*.82,1,h*.72+.1,'#ef4444',0,2.4,0); bx(g,w*.84,.8,h*.74,'#f1f5f9',0,5.8,0);
      bx(g,4.2,.3,1.3,'#ef4444',0,6.4,0); bx(g,1.3,.3,4.2,'#ef4444',0,6.4,0); top=8.5; break; }
    case 'info':{
      bx(g,w*.6,3,h*.5,'#0ea5e9',0,2,0); bx(g,w*.85,.5,h*.75,'#e0f2fe',0,3.8,0); cyl(g,.2,.2,4.5,'#334155',w*.36,2.8,h*.3,8); cyl(g,1.1,1.1,.4,'#0ea5e9',w*.36,5.2,h*.3,16); top=7.5; break; }
    case 'restroom':{
      bx(g,w*.8,4,h*.7,'#e2e8f0',0,2.5,0); bx(g,w*.86,.6,h*.76,'#06b6d4',0,4.8,0);
      bx(g,1.4,2.4,.2,'#0f172a',-w*.15,1.7,h*.36); bx(g,1.4,2.4,.2,'#0f172a',w*.15,1.7,h*.36); top=7; break; }
    default:{ /* booth, custom : 텐트 */
      const px_=w*.38,pz=h*.38; [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(a=>cyl(g,.25,.25,4.8,'#475569',a[0]*px_,2.9,a[1]*pz,8));
      const roof=new THREE.Mesh(new THREE.ConeGeometry(1,3.4,4),M(z.color)); roof.rotation.y=Math.PI/4; roof.scale.set(w*.72,1,h*.72); roof.position.set(0,6.7,0); g.add(roof);
      bx(g,w*.5,1.6,h*.22,'#f8fafc',0,1.4,h*.15); [-1,0,1].forEach(k=>bx(g,1.4,1,1.4,z.color,k*w*.16,2.7,h*.15)); top=9.5; }
  }
  const sp=labelSprite(z.icon+' '+z.name,z.color); const ww=Math.min(30,Math.max(14,z.name.length*2.1+8)); sp.scale.set(ww,ww*150/640,1); sp.position.set(0,top+3,0); g.add(sp);
}
function shapeGeo(scale){ const sh=new THREE.Shape(); D.shape.outline.forEach((p,i)=>{ const x=(p[0]-WW/2)*scale, y=-(p[1]-WH/2)*scale; if(i) sh.lineTo(x,y); else sh.moveTo(x,y); }); sh.closePath(); return sh; }
function slab(depth,color,y,scale){ const m=new THREE.Mesh(new THREE.ExtrudeGeometry(shapeGeo(scale),{depth:depth,bevelEnabled:false}),M(color)); m.rotation.x=-Math.PI/2; m.position.y=y; G3.add(m); return m; }
let domeMeshes=[], domeOn=true;
function buildScene3(){
  if(G3) S3.remove(G3); G3=new THREE.Group(); S3.add(G3);
  const T=D.theme, dome=D.shape.dome; const ground=rain?T.groundRain:T.ground;
  slab(4,'#e5e7eb',-4.7,1.04); slab(.7,ground,-.7,1);
  if(T.kind==='outdoor'&&!dome){ pieces(9).forEach((pc,i)=>{ if(i%2) return; const t=treePos(pc); tree(G3,t[0]-WW/2,t[1]-WH/2); }); }
  const hh=dome?2.4:5;
  pieces(5).forEach(pc=>{ if(D.gates.some(g=>Math.hypot(g.x-pc.x,g.y-pc.y)<7.5)) return; const m=bx(G3,pc.len+.3,hh,1.4,'#f8fafc',pc.x-WW/2,hh/2,pc.y-WH/2); m.rotation.y=-pc.ang; });
  const pcol=T.path;
  Z().forEach(z=>{ const g=nearestGate(z); const x1=g.x-WW/2,z1=g.y-WH/2,x2=z.x+z.w/2-WW/2,z2=z.y+z.h/2-WH/2; const dx=x2-x1,dz=z2-z1,L=Math.hypot(dx,dz);
    const m=bx(G3,L,.3,3.2,pcol,(x1+x2)/2,.15,(z1+z2)/2); m.rotation.y=-Math.atan2(dz,dx); });
  D.gates.forEach(g=>{ const gg=new THREE.Group(); gg.position.set(g.x-WW/2,0,g.y-WH/2); gg.rotation.y=-g.ang; G3.add(gg);
    bx(gg,1.6,8,1.6,'#1e293b',-6,4,0); bx(gg,1.6,8,1.6,'#1e293b',6,4,0); bx(gg,14,1.4,1.8,'#1e293b',0,8,0);
    const sp=labelSprite('🚪 '+g.name,'#1e293b'); sp.scale.set(15,15*150/640,1); sp.position.set(g.x-WW/2,12,g.y-WH/2); G3.add(sp); });
  Z().forEach(buildZone3);
  domeMeshes=[];
  if(dome){ const bw=SHB[2]-SHB[0], bh=SHB[3]-SHB[1];
    const dm=new THREE.Mesh(new THREE.SphereGeometry(1,48,20,0,Math.PI*2,0,Math.PI/2),new THREE.MeshLambertMaterial({color:0xbfdbfe,transparent:true,opacity:.14,side:THREE.DoubleSide,depthWrite:false}));
    dm.scale.set(bw/2,bw/2*.6,bh/2); dm.renderOrder=1; G3.add(dm);
    const wf=new THREE.Mesh(new THREE.SphereGeometry(1,16,6,0,Math.PI*2,0,Math.PI/2),new THREE.MeshBasicMaterial({color:0x475569,wireframe:true,transparent:true,opacity:.16,depthWrite:false}));
    wf.scale.copy(dm.scale); wf.renderOrder=1; G3.add(wf); domeMeshes=[dm,wf]; domeMeshes.forEach(m=>m.visible=domeOn); }
  $('zlist').innerHTML=Z().map(z=>`<span style="--c:${z.color}">${z.icon} ${z.name}</span>`).join(''); $('zCnt').textContent='('+Z().length+'개)';
}
function initR3(){
  const el=$('c3'); try{ R3=new THREE.WebGLRenderer({antialias:true}); }catch(e){ R3=null; is3d=false; $('hint').textContent='이 브라우저는 3D를 지원하지 않아 2D로 표시합니다'; return; }
  el.appendChild(R3.domElement);
  S3=new THREE.Scene(); S3.background=new THREE.Color('#dbe8f5'); S3.add(new THREE.AmbientLight(0xffffff,.82)); const dl=new THREE.DirectionalLight(0xffffff,.65); dl.position.set(-60,120,50); S3.add(dl);
  C3=new THREE.OrthographicCamera(-1,1,1,-1,-800,1200);
  const N=NAG; bodyM=new THREE.InstancedMesh(new THREE.CylinderGeometry(.55,.65,2.4,8),M('#f97316'),N); headM=new THREE.InstancedMesh(new THREE.SphereGeometry(.7,10,8),M('#fde68a'),N);
  bodyM.frustumCulled=false; headM.frustumCulled=false; S3.add(bodyM); S3.add(headM);
  const rp=new Float32Array(500*3); for(let i=0;i<500;i++){rp[i*3]=(Math.random()-.5)*WW;rp[i*3+1]=Math.random()*60;rp[i*3+2]=(Math.random()-.5)*WH;}
  rainPts=new THREE.Points(new THREE.BufferGeometry().setAttribute('position',new THREE.BufferAttribute(rp,3)),new THREE.PointsMaterial({color:0x60a5fa,size:1.2})); rainPts.visible=false; rainPts.frustumCulled=false; S3.add(rainPts);
  emgGrp=new THREE.Mesh(new THREE.SphereGeometry(1.8,16,12),new THREE.MeshBasicMaterial({color:0xef4444})); emgGrp.visible=false; S3.add(emgGrp);
  emgLine=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),new THREE.LineBasicMaterial({color:0xef4444})); emgLine.visible=false; emgLine.frustumCulled=false; S3.add(emgLine);
  heatTex=new THREE.CanvasTexture(hm); heatPlane=new THREE.Mesh(new THREE.PlaneGeometry(WW,WH),new THREE.MeshBasicMaterial({map:heatTex,transparent:true,opacity:.8,depthWrite:false})); heatPlane.rotation.x=-Math.PI/2; heatPlane.position.y=.5; heatPlane.visible=false; S3.add(heatPlane);
  const e=R3.domElement;
  e.onmousedown=ev=>{drag=true;lx=ev.clientX;ly=ev.clientY;}; window.addEventListener('mouseup',()=>drag=false);
  e.onmousemove=ev=>{ if(!drag)return; yaw-=(ev.clientX-lx)*.008; pitch=Math.min(1.35,Math.max(.3,pitch+(ev.clientY-ly)*.006)); lx=ev.clientX; ly=ev.clientY; };
  e.addEventListener('wheel',ev=>{ev.preventDefault(); zoom3=Math.min(3.2,Math.max(.6,zoom3*(ev.deltaY<0?1.1:.9)));},{passive:false});
  e.addEventListener('touchstart',ev=>{drag=true;lx=ev.touches[0].clientX;ly=ev.touches[0].clientY;},{passive:true});
  e.addEventListener('touchmove',ev=>{ if(!drag)return; const t=ev.touches[0]; yaw-=(t.clientX-lx)*.008; pitch=Math.min(1.35,Math.max(.3,pitch+(t.clientY-ly)*.006)); lx=t.clientX; ly=t.clientY;},{passive:true});
  e.addEventListener('touchend',()=>drag=false);
  size3(); buildScene3();
}
function size3(){ if(!R3) return; const el=$('c3'); const w=el.clientWidth,h=el.clientHeight; R3.setPixelRatio(Math.min(2,window.devicePixelRatio||1)); R3.setSize(w,h); const f=72,asp=w/h; C3.left=-f*asp; C3.right=f*asp; C3.top=f; C3.bottom=-f; C3.updateProjectionMatrix(); }
function render3(){
  if(!R3) return; const Rr=400;
  C3.position.set(Math.sin(yaw)*Math.cos(pitch)*Rr,Math.sin(pitch)*Rr,Math.cos(yaw)*Math.cos(pitch)*Rr); C3.lookAt(0,0,0); C3.zoom=zoom3; C3.updateProjectionMatrix();
  for(let i=0;i<agents.length;i++){ const a=agents[i]; const s=a.active?1:0.0001; DUM.rotation.set(0,0,0); DUM.scale.set(s,s,s);
    DUM.position.set(a.x-WW/2,1.7,a.y-WH/2); DUM.updateMatrix(); bodyM.setMatrixAt(i,DUM.matrix); DUM.position.y=3.6; DUM.updateMatrix(); headM.setMatrixAt(i,DUM.matrix); }
  bodyM.instanceMatrix.needsUpdate=true; headM.instanceMatrix.needsUpdate=true; bodyM.material.color.set(rain?'#2563eb':'#f97316');
  rainPts.visible=rain; if(rain){ const p=rainPts.geometry.attributes.position; for(let i=0;i<500;i++){ let y=p.getY(i)-1.4; if(y<0) y=60; p.setY(i,y);} p.needsUpdate=true; }
  if(emg){ emgGrp.visible=true; emgGrp.position.set(emg.x-WW/2,3,emg.y-WH/2); const sc=1+Math.sin(performance.now()/120)*.25; emgGrp.scale.set(sc,sc,sc);
    if(emg.target){ emgLine.visible=true; const tp=emgLine.geometry.attributes.position; tp.setXYZ(0,emg.x-WW/2,3,emg.y-WH/2); tp.setXYZ(1,emg.target.x+emg.target.w/2-WW/2,3,emg.target.y+emg.target.h/2-WH/2); tp.needsUpdate=true; } }
  else { emgGrp.visible=false; emgLine.visible=false; }
  heatPlane.visible=heat3; if(heat3) heatTex.needsUpdate=true;
  R3.render(S3,C3);
}
/* ---------- 루프 & 컨트롤 ---------- */
let last=performance.now(), kt=0;
function loop(now){ const dt=(now-last)/1000; last=now;
  if(sim){ step(dt); }
  updateHeat(); const r=drawHeat(hx,W,H,false); drawHeat(h2,W2,H2,true);
  if(is3d) render3(); else drawPeople();
  const n=Math.round(D.params.visitors*.5*factor(tHour)); $('peopleTxt').textContent='시뮬레이션 군중 ≈ '+n.toLocaleString()+'명';
  kt+=dt; if(kt>.4){ kt=0; $('kPeak').textContent=r[0].toFixed(2)+' 명/㎡'; $('kBott').textContent=(r[2]?Math.round(100*r[1]/r[2]):0)+'%';
    const de=mode==='after'?D.detail:D.before_detail; $('kMed').textContent=Math.round(de.t_max)+'초'; $('kRisk').textContent=de.risk_zones+'개소'; }
  requestAnimationFrame(loop);
}
function setView(v3){ if(v3&&!R3) return; is3d=v3; $('c3').style.display=v3?'block':'none'; [cv,hm,pp].forEach(c=>c.style.display=v3?'none':'block');
  hm.style.display=(!v3&&heat3)?'block':'none'; $('b3d').className=v3?'on':''; $('b2d').className=v3?'':'on'; $('hint').style.display=v3?'block':'none'; $('bDome').style.display=(v3&&D.shape.dome)?'inline-block':'none';
  if(v3) size3(); }
function togDome(){ domeOn=!domeOn; domeMeshes.forEach(m=>m.visible=domeOn); $('bDome').className=domeOn?'on':''; $('bDome').textContent=domeOn?'🏛️ 지붕 표시':'🏛️ 지붕 숨김'; }
function togHeat3(){ heat3=!heat3; $('bHeat3').className=heat3?'on':''; if(!is3d) hm.style.display=heat3?'block':'none'; }
function setMode(m){ mode=m; $('bMode').className=m==='after'?'on':''; $('bModeB').className=m==='before'?'on':'';
  $('verTxt').textContent=m==='after'?'· AI 최적 배치(종합 '+D.total.toFixed(1)+'점)':'· 설계 전(종합 '+D.before_total.toFixed(1)+'점)';
  heat.fill(0); initAgents(); emg=null; $('bEmg').className='danger'; $('bEmg').textContent='🚨 응급환자 발생'; drawBase(); if(R3) buildScene3(); $('status').textContent='실시간 군중 시뮬레이션'; }
function togSim(){ sim=!sim; $('bPlay').textContent=sim?'⏸ 시뮬레이션 정지':'▶ 시뮬레이션 시작'; }
function togRain(){ rain=!rain; const b=$('bRain'); b.className='warn'+(rain?' on':''); b.textContent=rain?'🌧️ 우천(ON)':'🌧️ 우천'; $('envTxt').textContent=rain?'🌧️ 우천: 무대 쪽으로 대피':'일반 상태';
  agents.forEach(a=>{ if(!rain&&!a.leaving) setTarget(a); }); drawBase(); if(R3) buildScene3(); }
function togEmg(){ const b=$('bEmg');
  if(emg){ emg=null; b.className='danger'; b.textContent='🚨 응급환자 발생'; $('status').textContent='실시간 군중 시뮬레이션'; return; }
  const Zs=Z().filter(z=>z.type!=='medical'); const z=Zs[Math.floor(Math.random()*Zs.length)];
  emg={x:z.x+z.w/2,y:z.y+z.h+2,trail:[],t0:performance.now(),target:null}; b.className='danger on'; b.textContent='🚨 응급 해제'; sim=true; $('bPlay').textContent='⏸ 시뮬레이션 정지'; }
function setTime(h){ tHour=h; $('tSl').value=h; $('tTxt').textContent=h+':00'; $('tDesc').textContent=descT(h); }
function togTl(){ const b=$('bTl'); if(tlTimer){clearInterval(tlTimer);tlTimer=null;b.textContent='▶ 재생';} else { b.textContent='⏸ 일시정지'; tlTimer=setInterval(()=>{ let n=tHour+1; if(n>20)n=10; setTime(n); },2500); } }
window.addEventListener('resize',resize);
setTime(14); resize(); initR3(); setView(is3d&&!!R3); setMode('after'); resize(); requestAnimationFrame(loop);
</script></body></html>
"""


def build_twin_html(result: dict) -> str:
    data = dict(
        zones=result["zones"], before_zones=result["before_zones"], gates=result["gates"],
        theme=result["theme"], params=dict(visitors=result["params"]["visitors"]), mpu=result["mpu"],
        shape=dict(kind=result["shape"]["kind"], dome=result["shape"]["dome"], bbox=result["shape"]["bbox"],
                   outline=result["shape"]["outline"]),
        total=result["total"], before_total=result["before_total"],
        detail=dict(t_max=result["detail"]["t_max"], risk_zones=result["detail"]["risk_zones"]),
        before_detail=dict(t_max=result["before_detail"]["t_max"], risk_zones=result["before_detail"]["risk_zones"]),
    )
    return TWIN_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))



# ===== REPORT =====
# 보고서 내용을 "블록" 목록으로 한 번만 만들고, 화면(HTML) / PDF / Markdown 으로 각각 출력한다.
import io as _io
import os as _os

TEAM_NAME = "INCLUSE"
SCHOOL_NAME = "건양고등학교"
DISCLAIMER = ("이 보고서의 수치는 가상 군중 시뮬레이션으로 얻은 추정값이다. 실제 행사 기록으로 검증한 값이 아니므로, "
              "행사를 열기 전에는 현장 안전 점검과 관할 기관 협의가 필요하다.")


def grade(s: float) -> str:
    return "매우 우수" if s >= 90 else "우수" if s >= 80 else "보통" if s >= 65 else "개선 필요"


_PLAIN = [(r"(필요|충분|중요|가능|유리|안전|위험|편리|적합|우수|양호|불리|유용|원활|부족|상당|동일|유사|적절)합니다", r"\1하다"), (r"바랍니다", "바란다"), (r"합니다", "한다"), (r"됩니다", "된다"), (r"입니다", "이다"), (r"랍니다", "란다"),
          (r"있습니다", "있다"), (r"없습니다", "없다"), (r"않습니다", "않는다"), (r"했습니다", "했다"),
          (r"됐습니다", "됐다"), (r"줍니다", "준다"), (r"습니다", "다"), (r"하세요", "한다"), (r"해 주세요", "한다"),
          (r"해주세요", "한다"), (r"드립니다", "드린다"), (r"입력하신", "입력한"), (r"요청하신", "요청한")]


def plain(s: str) -> str:
    """'~했습니다' 같은 말투를 보고서용 평서체('~했다')로 바꾼다."""
    s = str(s)
    for a, b in _PLAIN:
        s = re.sub(a, b, s)
    return s


def demand_rows(r: dict) -> list:
    """엔진이 군중을 나눌 때 쓰는 시설별 방문 비중을 그대로 보여 준다 (시뮬레이션과 숫자가 일치)."""
    V = r["params"]["visitors"]
    acc: dict = {}
    for z in r["zones"]:
        if z["type"] == "medical":
            continue
        lab = ZONE_META[z["type"]]["label"] if z["type"] != "custom" else "사용자 부스"
        acc[lab] = acc.get(lab, 0.0) + float(z["attract"])
    tot = sum(acc.values()) or 1.0
    rows = [dict(name=k, share=v / tot, visits=int(round(V * v / tot))) for k, v in acc.items()]
    return sorted(rows, key=lambda x: -x["share"])


def caution_points(r: dict) -> list:
    d, b, p = r["detail"], r["before_detail"], r["params"]
    out = []
    pk = d["peak"]
    lvl = "위험 기준" if pk >= DANGER_DENSITY else "혼잡 기준" if pk >= WARN_DENSITY else "혼잡 기준 아래"
    out.append(f"최대 군중 밀도는 {pk:.2f}명/㎡로 {lvl}({WARN_DENSITY}명/㎡ 혼잡, {DANGER_DENSITY}명/㎡ 위험)에 해당한다.")
    if d["risk_zones"] > 0:
        out.append(f"사고 위험구역이 {d['risk_zones']}개소 남아 있다. 이 구역은 안내 요원을 두거나 대기줄 방향을 정해 두는 것이 좋다.")
    else:
        out.append("시뮬레이션에서는 사고 위험구역이 나타나지 않았다.")
    out.append(f"응급 최대 도달시간은 {fmt_sec(d['t_max'])}이다. 설계 전({fmt_sec(b['t_max'])})과 비교해 응급의료센터 앞 통로를 비워 두어야 한다.")
    if r["cost"]["total"] > r["cost"]["budget"]:
        out.append(f"예상 시설 비용({r['cost']['total']:,.0f}만원)이 예산({r['cost']['budget']:,}만원)보다 많아 조정이 필요하다.")
    low = [OBJ_LABEL[k] for k in OBJECTIVES if r["scores"][k] < 65]
    if low:
        out.append("점수가 낮은 항목은 " + ", ".join(low) + "이다. 구역 크기나 출입구 수를 바꿔 다시 설계해 볼 수 있다.")
    return out


def build_blocks(r: dict, team: str = TEAM_NAME, school: str = SCHOOL_NAME, author: str = "") -> list:
    p, d, b, st_ = r["params"], r["detail"], r["before_detail"], r["stats"]
    ev = p.get("event") or {}
    gain = r["total"] - r["before_total"]
    best_k = max(OBJECTIVES, key=lambda k: r["scores"][k] - r["before_scores"][k])
    worst_k = min(OBJECTIVES, key=lambda k: r["scores"][k])
    B = []

    B.append(("h2", "1. 행사 개요"))
    B.append(("p", f"{p['name']}은(는) {p['venue']}({p['location']})에서 열리는 {p['purpose']} 행사이다. "
                   f"예상 방문객은 {p['visitors']:,}명이고, 주요 연령대는 {p['age']}이다."))
    rows = [["행사 목적 / 분위기", f"{p['purpose']} / {p['mood']}"],
            ["장소 / 면적", f"{p['venue']} / {p['area_m2']:,}㎡ ({r['shape']['name']})"],
            ["예상 방문객 / 운영 시간", f"{p['visitors']:,}명 / {p['hours']}"],
            ["예산 / 예상 시설 비용", f"{p['budget']:,}만원 / {r['cost']['total']:,.0f}만원"]]
    if ev.get("date"):
        rows.append(["일정", f"{ev['date']} ({ev.get('days', 1)}일간) {ev.get('start', '')} ~ {ev.get('end', '')}"])
    if ev.get("inside"):
        tk = "무료" if ev.get("ticket", "무료") == "무료" else f"유료 {int(ev.get('ticket_price', 0)):,}원"
        rows.append(["실내·실외 / 입장료", f"{ev['inside']} / {tk}"])
    if p.get("facilities") is not None:
        rows.append(["선택한 시설", ", ".join(p["facilities"]) or "없음"])
    if ev.get("extra"):
        rows.append(["추가 요청", ev["extra"]])
    B.append(("table", "행사 개요", ["항목", "내용"], rows, (1,)))

    B.append(("h2", "2. 분석 방법"))
    B.append(("p", "행사 정보를 입력하면 가상 행사장(디지털 트윈)을 만들고, 여러 배치안을 만들어 군중 이동을 시뮬레이션한 뒤 점수가 가장 높은 안을 고른다."))
    B.append(("bul", [f"생성·평가한 배치안: {st_['generated']:,}개 (무작위 {st_['randomly']:,}개 + 변이 {st_['mutated']:,}개)",
                      f"파레토 최적해: {st_['pareto']}개, 배치 구역: {st_['zones']}개",
                      "평가 목표: " + ", ".join(OBJ_LABEL[k] for k in OBJECTIVES)]))
    B.append(("table", "평가 목표별 가중치", ["목표", "가중치"],
              [[OBJ_LABEL[k], f"{r['weights'][k] * 100:.0f}%"] for k in OBJECTIVES], ()))

    B.append(("h2", "3. 최적 배치안"))
    B.append(("p", f"종합 점수 {r['total']:.1f}점인 배치안을 {st_['generated']:,}개 후보 중에서 골랐다."))
    B.append(("layout", "AI가 제안한 최적 배치도", [("AI 최적 배치", r["zones"])], r))
    B.append(("table", "구역별 크기", ["구역", "종류", "가로(m)", "세로(m)"],
              [[z["name"], z["type"], z["w_m"], z["h_m"]] for z in r["zone_sizes"]], ()))
    dem = demand_rows(r)
    B.append(("h3", "시설별 예상 방문 비중"))
    B.append(("p", "시설마다 정해 둔 매력도로 방문객을 나눈 값이다. 시뮬레이션에서 방문객이 시설로 가는 비율과 같다. 실제 행사 기록으로 학습한 예측은 아니다."))
    B.append(("table", "시설별 예상 방문 비중", ["시설", "비중", "예상 방문 수"],
              [[x["name"], f"{x['share'] * 100:.0f}%", f"약 {x['visits']:,}명"] for x in dem], ()))

    B.append(("h2", "4. 설계 전·후 비교"))
    B.append(("p", f"종합 점수는 설계 전 {r['before_total']:.1f}점에서 설계 후 {r['total']:.1f}점으로 {gain:+.1f}점 달라졌다. "
                   f"가장 크게 좋아진 항목은 {OBJ_LABEL[best_k]}이다."))
    B.append(("layout", "설계 전(왼쪽)과 AI 최적 배치(오른쪽)", [("설계 전", r["before_zones"]), ("AI 최적", r["zones"])], r))
    B.append(("bars", "목표별 점수 비교", [OBJ_LABEL[k] for k in OBJECTIVES],
              [r["before_scores"][k] for k in OBJECTIVES], [r["scores"][k] for k in OBJECTIVES]))
    B.append(("table", "목표별 점수와 등급", ["평가 항목", "가중치", "설계 전", "설계 후", "등급"],
              [[OBJ_LABEL[k], f"{r['weights'][k] * 100:.0f}%", f"{r['before_scores'][k]:.0f}", f"{r['scores'][k]:.0f}", grade(r['scores'][k])]
               for k in OBJECTIVES], ()))
    B.append(("table", "시뮬레이션 지표 비교", ["지표", "설계 전", "설계 후"], [
        ["병목 발생율", f"{b['bottleneck']:.0f}%", f"{d['bottleneck']:.0f}%"],
        ["최대 군중 밀도", f"{b['peak']:.2f}명/㎡", f"{d['peak']:.2f}명/㎡"],
        ["응급 최대 도달시간", fmt_sec(b["t_max"]), fmt_sec(d["t_max"])],
        ["응급 평균 도달시간", fmt_sec(b["t_mean"]), fmt_sec(d["t_mean"])],
        ["사고 위험구역", f"{b['risk_zones']}개소", f"{d['risk_zones']}개소"],
        ["동선 구역 관통률", f"{b['obstruct'] * 100:.0f}%", f"{d['obstruct'] * 100:.0f}%"]], ()))

    B.append(("h2", "5. 설계 이유 (XAI)"))
    B.append(("h3", "5-1. 전체 설계 이유"))
    B.append(("bul", [plain(t) for t in r["xai"]["reasons"]]))
    B.append(("h3", "5-2. 구역별 배치 근거"))
    B.append(("bul", [f"{z['name']}: {plain(z['text'])}" for z in r["xai"]["zone_reasons"]]))
    if r["xai"]["alternatives"]:
        B.append(("h3", "5-3. 검토했으나 채택하지 않은 대안"))
        B.append(("bul", [f"{a['name']}: {plain(a['note'])}" for a in r["xai"]["alternatives"]]))

    B.append(("h2", "6. 점수 산출 근거"))
    B.append(("table", "가중치 구성", ["목표", "기본", "목적 보정", "연령대 보정", "최종"],
              [[OBJ_LABEL[k], f"{r['weight_detail'][k]['base'] * 100:.0f}%", f"{r['weight_detail'][k]['purpose'] * 100:+.0f}%p",
                f"{r['weight_detail'][k]['age'] * 100:+.0f}%p", f"{r['weight_detail'][k]['final'] * 100:.1f}%"] for k in OBJECTIVES], ()))
    B.append(("table", "세부 지표별 점수 (측정값을 0~100점으로 환산)",
              ["목표", "세부지표", "설계 전", "설계 후", "만점 기준", "0점 기준", "세부점수", "비중"],
              [[e["objLabel"], e["label"], e["v_before"], e["v_after"], e["best_txt"], e["worst_txt"],
                f"{e['sub_after'] * 100:.0f}", f"{e['w'] * 100:.0f}%"] for e in r["evidence"]], (1,)))
    B.append(("box", [f"{OBJ_LABEL[k]}: {r['formulas'][k]}" for k in OBJECTIVES] + [f"종합: {r['total_formula']}"]))
    B.append(("h3", "가정과 한계"))
    B.append(("bul", [plain(a) for a in r["assumptions"]]))

    B.append(("h2", "7. 결론 및 운영 시 확인할 점"))
    B.append(("p", f"AI 설계안은 종합 {r['total']:.1f}점으로 기존 배치({r['before_total']:.1f}점)보다 {gain:+.1f}점 달라졌다. "
                   f"상대적으로 낮은 항목은 {OBJ_LABEL[worst_k]}({r['scores'][worst_k]:.0f}점)이다."))
    B.append(("bul", caution_points(r)))
    if r["notes"]:
        B.append(("h3", "설계 중 자동 조정한 내용"))
        B.append(("bul", [plain(n) for n in r["notes"]]))
    B.append(("note", DISCLAIMER))
    return B


# ----------------------------------------------------------------------------- 그림 (SVG, 화면용)
def _e(x) -> str:
    return _html.escape(str(x))


def svg_layout(zones, gates, shape, title="") -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in shape["outline"])
    o = ['<svg viewBox="-2 -2 164 104" xmlns="http://www.w3.org/2000/svg" font-family="Malgun Gothic,Noto Sans KR,sans-serif">',
         f'<polygon points="{pts}" fill="#f8fafc" stroke="#334155" stroke-width="0.8"/>']
    for z in zones:
        fs = max(1.9, min(3.0, z["w"] / max(3, len(z["name"])) * 0.95))
        o.append(f'<rect x="{z["x"]}" y="{z["y"]}" width="{z["w"]}" height="{z["h"]}" rx="1" fill="{z["color"]}" fill-opacity=".8" stroke="#fff" stroke-width=".4"/>')
        o.append(f'<text x="{z["x"] + z["w"] / 2}" y="{z["y"] + z["h"] / 2 + fs / 3}" font-size="{fs:.1f}" fill="#fff" text-anchor="middle" font-weight="700">{_e(z["name"])}</text>')
    for g in gates:
        o.append(f'<circle cx="{g["x"]}" cy="{g["y"]}" r="2" fill="#0f172a"/>')
        o.append(f'<text x="{g["x"]}" y="{g["y"] - 3}" font-size="2.6" text-anchor="middle" fill="#0f172a">{_e(g["name"])}</text>')
    if title:
        o.append(f'<text x="2" y="-0.2" font-size="3.4" fill="#0f172a" font-weight="700">{_e(title)}</text>')
    o.append("</svg>")
    return "".join(o)


def svg_bars(labels, before, after) -> str:
    W, H, L, Bm = 640, 280, 40, 50
    gw = (W - L - 10) / len(labels)
    o = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Malgun Gothic,Noto Sans KR,sans-serif" font-size="12">']
    for t in (0, 25, 50, 75, 100):
        y = H - Bm - (H - Bm - 20) * t / 100
        o.append(f'<line x1="{L}" x2="{W - 10}" y1="{y}" y2="{y}" stroke="#e2e8f0"/><text x="{L - 6}" y="{y + 4}" text-anchor="end" fill="#64748b">{t}</text>')
    for i, (lb, bv, av) in enumerate(zip(labels, before, after)):
        x0, bw = L + i * gw + gw * 0.18, gw * 0.30
        for j, (v, col) in enumerate(((bv, "#94a3b8"), (av, "#1e3a8a"))):
            h = (H - Bm - 20) * max(0, min(100, v)) / 100
            x = x0 + j * (bw + 3)
            o.append(f'<rect x="{x}" y="{H - Bm - h}" width="{bw}" height="{h}" fill="{col}"/>')
            o.append(f'<text x="{x + bw / 2}" y="{H - Bm - h - 4}" text-anchor="middle" font-size="11" fill="#334155">{v:.0f}</text>')
        o.append(f'<text x="{L + i * gw + gw / 2}" y="{H - Bm + 18}" text-anchor="middle" fill="#334155">{_e(lb)}</text>')
    o.append(f'<rect x="{W - 170}" y="4" width="10" height="10" fill="#94a3b8"/><text x="{W - 156}" y="13" fill="#334155">설계 전</text>')
    o.append(f'<rect x="{W - 95}" y="4" width="10" height="10" fill="#1e3a8a"/><text x="{W - 81}" y="13" fill="#334155">AI 설계</text></svg>')
    return "".join(o)


REPORT_CSS = """
@page{size:A4;margin:20mm 18mm}
*{box-sizing:border-box}
body{font-family:Pretendard,'Malgun Gothic','Noto Sans KR',sans-serif;color:#1e293b;line-height:1.75;font-size:14px;margin:0;background:#f1f5f9}
.doc{max-width:820px;margin:0 auto;background:#fff;padding:0 48px 40px}
.bar{position:sticky;top:0;background:#1e3a8a;color:#fff;padding:8px 16px;text-align:right;z-index:9}
.bar button{background:#fff;color:#1e3a8a;border:0;border-radius:6px;padding:6px 14px;font-weight:700;cursor:pointer}
.cover{min-height:860px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;border-bottom:1px solid #e2e8f0}
.cover .tag{color:#1e3a8a;font-weight:700;letter-spacing:2px;margin-bottom:18px}
.cover h1{font-size:34px;line-height:1.4;margin:0 0 14px;color:#0f172a}
.cover .sub{color:#64748b;font-size:16px;margin-bottom:60px}
.cover .meta{color:#475569;line-height:2}
.toc{padding:40px 0;min-height:420px}.toc li{margin:10px 0;font-size:16px}
h2{font-size:21px;color:#1e3a8a;border-bottom:2px solid #1e3a8a;padding-bottom:5px;margin:40px 0 14px;page-break-after:avoid}
h3{font-size:16px;margin:22px 0 8px;color:#0f172a;page-break-after:avoid}
p{margin:6px 0}.li{margin:3px 0 3px 10px}
table{border-collapse:collapse;width:100%;margin:8px 0 4px;font-size:13px;page-break-inside:avoid}
th,td{border:1px solid #cbd5e1;padding:6px 9px;text-align:center}th{background:#eff6ff}td.l{text-align:left}
.cap{text-align:center;color:#64748b;font-size:12.5px;margin:4px 0 16px}
figure{margin:10px 0;text-align:center;page-break-inside:avoid}figure svg{max-width:100%;height:auto}
.two{display:flex;gap:12px}.two figure{flex:1;margin:0}
.box{background:#f8fafc;border-left:4px solid #1e3a8a;padding:10px 14px;margin:10px 0;font-size:13px}
.note{color:#64748b;font-size:12.5px;margin-top:30px;border-top:1px solid #e2e8f0;padding-top:8px}
@media print{body{background:#fff}.doc{padding:0;max-width:none}.bar{display:none}.cover,.toc{page-break-after:always}.cover{min-height:240mm}.toc{min-height:0}}
"""

TOC_TITLES = ["행사 개요", "분석 방법", "최적 배치안", "설계 전·후 비교", "설계 이유 (XAI)", "점수 산출 근거", "결론 및 운영 시 확인할 점"]


def render_html(blocks, r, team=TEAM_NAME, school=SCHOOL_NAME, author="", with_bar=True) -> str:
    p = r["params"]
    nf, nt = [0], [0]
    today = _dt.date.today().strftime("%Y. %m. %d.")
    s = []
    if with_bar:
        s.append('<div class="bar"><button onclick="window.print()">🖨️ PDF로 저장 (인쇄 → PDF)</button></div>')
    s.append('<div class="doc">')
    meta = f"{_e(school)}<br>팀명 {_e(team)}" + (f"<br>작성자 {_e(author)}" if author else "") + f"<br>{today}"
    s.append(f'<section class="cover"><div class="tag">EVENT ON REPORT</div><h1>{_e(p["name"])}<br>AI 행사장 설계 분석 보고서</h1>'
             f'<div class="sub">군중 시뮬레이션 기반 최적 배치 결과</div><div class="meta">{meta}</div></section>')
    s.append('<section class="toc"><h2 style="margin-top:0">목차</h2><ol>' + "".join(f"<li>{t}</li>" for t in TOC_TITLES) + "</ol></section>")
    for blk in blocks:
        k = blk[0]
        if k == "h2":
            s.append(f"<h2>{_e(blk[1])}</h2>")
        elif k == "h3":
            s.append(f"<h3>{_e(blk[1])}</h3>")
        elif k == "p":
            s.append(f"<p>{_e(blk[1])}</p>")
        elif k == "bul":
            s.append("".join(f"<p class='li'>• {_e(t)}</p>" for t in blk[1]))
        elif k == "table":
            nt[0] += 1
            _, cap, head, rows, left = blk
            h = "".join(f"<th>{_e(c)}</th>" for c in head)
            bd = "".join("<tr>" + "".join(f'<td class="{"l" if i in left else ""}">{_e(c)}</td>' for i, c in enumerate(rw)) + "</tr>" for rw in rows)
            s.append(f'<div class="cap" style="margin-bottom:2px"><b>표 {nt[0]}.</b> {_e(cap)}</div><table><tr>{h}</tr>{bd}</table><br>')
        elif k == "layout":
            nf[0] += 1
            _, cap, items, R_ = blk
            figs = "".join(f"<figure>{svg_layout(z, R_['gates'], R_['shape'], t if len(items) > 1 else '')}</figure>" for t, z in items)
            s.append(f'<div class="{"two" if len(items) > 1 else ""}">{figs}</div><div class="cap">그림 {nf[0]}. {_e(cap)}</div>')
        elif k == "bars":
            nf[0] += 1
            s.append(f'<figure>{svg_bars(blk[2], blk[3], blk[4])}<div class="cap">그림 {nf[0]}. {_e(blk[1])}</div></figure>')
        elif k == "box":
            s.append("<div class='box'><b>계산식</b><br>" + "<br>".join(_e(t) for t in blk[1]) + "</div>")
        elif k == "note":
            s.append(f"<div class='note'>{_e(blk[1])}</div>")
    s.append("</div>")
    return ("<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>Event ON 보고서</title><style>"
            + REPORT_CSS + "</style></head><body>" + "".join(s) + "</body></html>")


def render_md(blocks, r, team=TEAM_NAME, school=SCHOOL_NAME) -> str:
    p = r["params"]
    L = [f"# {p['name']} — AI 행사장 설계 분석 보고서", f"{school} · 팀 {team} · {_dt.date.today():%Y-%m-%d}", ""]
    for blk in blocks:
        k = blk[0]
        if k == "h2":
            L += ["", f"## {blk[1]}", ""]
        elif k == "h3":
            L += ["", f"### {blk[1]}", ""]
        elif k == "p":
            L += [blk[1], ""]
        elif k == "bul":
            L += [f"- {t}" for t in blk[1]] + [""]
        elif k == "table":
            _, cap, head, rows, _l = blk
            L += [f"**{cap}**", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
            L += ["| " + " | ".join(str(c).replace("|", "/") for c in rw) + " |" for rw in rows] + [""]
        elif k == "layout":
            L += [f"_(그림: {blk[1]} — PDF·화면 보고서에서 확인)_", ""]
        elif k == "bars":
            L += [f"_(그림: {blk[1]})_", ""]
        elif k == "box":
            L += [f"> {t}  " for t in blk[1]] + [""]
        elif k == "note":
            L += ["---", f"※ {blk[1]}"]
    return "\n".join(L)


# ----------------------------------------------------------------------------- PDF (reportlab)
def _find_font():
    cands = ["/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "/usr/share/fonts/nanum/NanumGothic.ttf",
             "C:/Windows/Fonts/malgun.ttf", "/Library/Fonts/NanumGothic.ttf", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"]
    try:
        import koreanize_matplotlib as _k
        cands.insert(0, _os.path.join(_os.path.dirname(_k.__file__), "fonts", "NanumGothic.ttf"))
    except Exception:
        pass
    for c in cands:
        if _os.path.exists(c):
            bold = c.replace("NanumGothic.ttf", "NanumGothicBold.ttf").replace("malgun.ttf", "malgunbd.ttf")
            return c, (bold if _os.path.exists(bold) else c)
    return None, None


def render_pdf(blocks, r, team=TEAM_NAME, school=SCHOOL_NAME, author="") -> bytes:
    """보고서 PDF. reportlab 이 없으면 ImportError 를 그대로 올린다(호출하는 쪽에서 처리)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                    KeepTogether, Flowable)
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.graphics.shapes import Drawing, Rect, String, Polygon, Circle, Line

    reg, bold = _find_font()
    if reg:
        pdfmetrics.registerFont(TTFont("KR", reg))
        pdfmetrics.registerFont(TTFont("KR-B", bold))
        F, FB = "KR", "KR-B"
    else:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
        F = FB = "HYSMyeongJo-Medium"

    NAVY = colors.HexColor("#1e3a8a")
    st_body = ParagraphStyle("b", fontName=F, fontSize=10, leading=16, wordWrap="CJK")
    st_li = ParagraphStyle("li", parent=st_body, leftIndent=12, bulletIndent=2)
    st_h2 = ParagraphStyle("h2", fontName=FB, fontSize=15, leading=20, textColor=NAVY, spaceBefore=16, spaceAfter=8)
    st_h3 = ParagraphStyle("h3", fontName=FB, fontSize=11.5, leading=16, spaceBefore=10, spaceAfter=4)
    st_cap = ParagraphStyle("cap", parent=st_body, fontSize=8.5, leading=12, alignment=1, textColor=colors.HexColor("#64748b"))
    st_cell = ParagraphStyle("cell", fontName=F, fontSize=8, leading=11, alignment=1, wordWrap="CJK")
    st_cell_l = ParagraphStyle("celll", parent=st_cell, alignment=0)
    st_cell_h = ParagraphStyle("cellh", parent=st_cell, fontName=FB)
    st_note = ParagraphStyle("note", parent=st_body, fontSize=8.5, textColor=colors.HexColor("#64748b"))
    st_box = ParagraphStyle("box", parent=st_body, fontSize=8.5, leading=13)
    esc = lambda t: _html.escape(str(t))

    class Doc(BaseDocTemplate):
        def afterFlowable(self, fl):
            if isinstance(fl, Paragraph) and fl.style.name == "h2":
                self.notify("TOCEntry", (0, fl.getPlainText(), self.page))

    buf = _io.BytesIO()
    doc = Doc(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
              title=f"{r['params']['name']} 설계 분석 보고서", author=author or team)
    fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def footer(c, d):
        c.saveState()
        c.setFont(F, 8)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(A4[0] / 2, 10 * mm, f"Event ON · {d.page}")
        c.restoreState()

    doc.addPageTemplates([PageTemplate(id="cover", frames=[fr]), PageTemplate(id="body", frames=[fr], onPage=footer)])
    from reportlab.platypus import NextPageTemplate

    p = r["params"]
    today = _dt.date.today().strftime("%Y. %m. %d.")
    S = [Spacer(1, 60 * mm),
         Paragraph("EVENT ON REPORT", ParagraphStyle("t", fontName=FB, fontSize=11, textColor=NAVY, alignment=1)),
         Spacer(1, 6 * mm),
         Paragraph(esc(p["name"]) + "<br/>AI 행사장 설계 분석 보고서", ParagraphStyle("ti", fontName=FB, fontSize=24, leading=34, alignment=1)),
         Spacer(1, 6 * mm),
         Paragraph("군중 시뮬레이션 기반 최적 배치 결과", ParagraphStyle("s", fontName=F, fontSize=12, alignment=1, textColor=colors.HexColor("#64748b"))),
         Spacer(1, 45 * mm),
         Paragraph(esc(school) + f"<br/>팀명 {esc(team)}" + (f"<br/>작성자 {esc(author)}" if author else "") + f"<br/>{today}",
                   ParagraphStyle("m", fontName=F, fontSize=11, leading=20, alignment=1)),
         NextPageTemplate("body"), PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("toc0", fontName=F, fontSize=11.5, leading=22, leftIndent=8)]
    S += [Paragraph("목차", ParagraphStyle("tt", fontName=FB, fontSize=16, textColor=NAVY, spaceAfter=10)), toc, PageBreak()]

    def layout_drawing(items, R_, width):
        n = len(items)
        w1 = (width - 8 * (n - 1)) / n
        sc = w1 / 164.0
        h1 = 104 * sc
        d = Drawing(width, h1 + (10 if n > 1 else 0))
        for i, (title, zones) in enumerate(items):
            ox, oy = i * (w1 + 8), 0
            X = lambda x: ox + (x + 2) * sc
            Y = lambda y: h1 - (y + 2) * sc + oy
            pts = []
            for x, y in R_["shape"]["outline"]:
                pts += [X(x), Y(y)]
            d.add(Polygon(pts, fillColor=colors.HexColor("#f8fafc"), strokeColor=colors.HexColor("#334155"), strokeWidth=0.8))
            for z in zones:
                d.add(Rect(X(z["x"]), Y(z["y"] + z["h"]), z["w"] * sc, z["h"] * sc, fillColor=colors.HexColor(z["color"]),
                           strokeColor=colors.white, strokeWidth=0.5))
                fs = max(4.0, min(7.5, z["w"] * sc / max(3, len(z["name"])) * 1.9))
                d.add(String(X(z["x"] + z["w"] / 2), Y(z["y"] + z["h"] / 2) - fs / 3, z["name"], fontName=FB, fontSize=fs,
                             fillColor=colors.white, textAnchor="middle"))
            for g in R_["gates"]:
                d.add(Circle(X(g["x"]), Y(g["y"]), 2.2, fillColor=colors.HexColor("#0f172a"), strokeColor=None))
            if n > 1:
                d.add(String(ox + w1 / 2, h1 + 1, title, fontName=FB, fontSize=9, textAnchor="middle"))
        return d

    def bars_drawing(labels, bef, aft, width):
        H = 150
        d = Drawing(width, H + 20)
        L, Bm = 28, 30
        gw = (width - L - 5) / len(labels)
        for t in (0, 25, 50, 75, 100):
            y = Bm + (H - Bm - 10) * t / 100
            d.add(Line(L, y, width - 5, y, strokeColor=colors.HexColor("#e2e8f0")))
            d.add(String(L - 4, y - 3, str(t), fontName=F, fontSize=7, textAnchor="end", fillColor=colors.HexColor("#64748b")))
        for i, (lb, bv, av) in enumerate(zip(labels, bef, aft)):
            x0, bw = L + i * gw + gw * 0.18, gw * 0.3
            for j, (v, col) in enumerate(((bv, "#94a3b8"), (av, "#1e3a8a"))):
                h = (H - Bm - 10) * max(0, min(100, v)) / 100
                x = x0 + j * (bw + 2)
                d.add(Rect(x, Bm, bw, h, fillColor=colors.HexColor(col), strokeColor=None))
                d.add(String(x + bw / 2, Bm + h + 2, f"{v:.0f}", fontName=F, fontSize=7, textAnchor="middle"))
            d.add(String(L + i * gw + gw / 2, Bm - 12, lb, fontName=F, fontSize=7.5, textAnchor="middle"))
        d.add(Rect(width - 110, H + 6, 8, 8, fillColor=colors.HexColor("#94a3b8"), strokeColor=None))
        d.add(String(width - 99, H + 7, "설계 전", fontName=F, fontSize=7.5))
        d.add(Rect(width - 55, H + 6, 8, 8, fillColor=colors.HexColor("#1e3a8a"), strokeColor=None))
        d.add(String(width - 44, H + 7, "AI 설계", fontName=F, fontSize=7.5))
        return d

    nf, nt = [0], [0]
    W = doc.width
    for blk in blocks:
        k = blk[0]
        if k == "h2":
            S.append(Paragraph(esc(blk[1]), st_h2))
        elif k == "h3":
            S.append(Paragraph(esc(blk[1]), st_h3))
        elif k == "p":
            S.append(Paragraph(esc(blk[1]), st_body))
        elif k == "bul":
            for t in blk[1]:
                S.append(Paragraph(esc(t), st_li, bulletText="•"))
        elif k == "table":
            nt[0] += 1
            _, cap, head, rows, left = blk
            data = [[Paragraph(esc(c), st_cell_h) for c in head]]
            for rw in rows:
                data.append([Paragraph(esc(c), st_cell_l if i in left else st_cell) for i, c in enumerate(rw)])
            ncol = len(head)
            if ncol == 8:
                cw = [0.11, 0.17, 0.1, 0.1, 0.19, 0.19, 0.08, 0.06]
            elif ncol == 2:
                cw = [0.28, 0.72]
            else:
                cw = [1.0 / ncol] * ncol
            tb = Table(data, colWidths=[W * c for c in cw], repeatRows=1)
            tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
                                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            S.append(KeepTogether([Paragraph(f"<b>표 {nt[0]}.</b> {esc(cap)}", st_cap), Spacer(1, 2), tb, Spacer(1, 8)]) if len(rows) < 22 else tb)
        elif k == "layout":
            nf[0] += 1
            _, cap, items, R_ = blk
            S.append(KeepTogether([layout_drawing(items, R_, W), Paragraph(f"그림 {nf[0]}. {esc(cap)}", st_cap), Spacer(1, 8)]))
        elif k == "bars":
            nf[0] += 1
            S.append(KeepTogether([bars_drawing(blk[2], blk[3], blk[4], W), Paragraph(f"그림 {nf[0]}. {esc(blk[1])}", st_cap), Spacer(1, 8)]))
        elif k == "box":
            bx = Table([[Paragraph("<b>계산식</b><br/>" + "<br/>".join(esc(t) for t in blk[1]), st_box)]], colWidths=[W])
            bx.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")), ("LINEBEFORE", (0, 0), (0, -1), 3, NAVY),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            S += [bx, Spacer(1, 6)]
        elif k == "note":
            S += [Spacer(1, 10), Paragraph(esc(blk[1]), st_note)]
    doc.multiBuild(S)
    return buf.getvalue()


def make_report(r: dict, team=TEAM_NAME, school=SCHOOL_NAME, author="") -> dict:
    blocks = build_blocks(r, team, school, author)
    out = dict(html=render_html(blocks, r, team, school, author), md=render_md(blocks, r, team, school), pdf=None, pdf_err="")
    try:
        out["pdf"] = render_pdf(blocks, r, team, school, author)
    except Exception as ex:  # noqa
        out["pdf_err"] = f"{type(ex).__name__}: {ex}"
    return out


def build_report_html(r: dict) -> str:
    return render_html(build_blocks(r), r)



# ===== UI =====
import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

import inspect

# Streamlit 버전이 달라도 동작하도록 하는 호환 코드
FW = dict(width="stretch") if "width" in inspect.signature(st.button).parameters else dict(use_container_width=True)


def embed_html(html_str: str, height: int):
    if hasattr(st, "iframe"):
        st.iframe(html_str, height=height)
    else:
        components.html(html_str, height=height, scrolling=True)


st.set_page_config(page_title="Event ON - AI 행사 자동 설계", page_icon="🎪", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1.2rem;max-width:1500px}
.eo-head{background:linear-gradient(135deg,#0f172a,#1e3a8a);color:#fff;padding:18px 24px;border-radius:16px;margin-bottom:14px}
.eo-head h1{font-size:26px;margin:0;color:#fff} .eo-head p{margin:4px 0 0;color:#bfdbfe;font-size:13px}
.wf{display:flex;gap:6px;align-items:stretch;flex-wrap:wrap;margin:6px 0 14px}
.wf .st{flex:1;min-width:130px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px 10px;text-align:center}
.wf .st .n{width:24px;height:24px;border-radius:50%;background:#2563eb;color:#fff;font-weight:800;font-size:12px;display:inline-grid;place-items:center}
.wf .st b{display:block;font-size:13px;margin:6px 0 2px;color:#0f172a} .wf .st span{font-size:11px;color:#64748b}
.wf .ar{align-self:center;color:#94a3b8;font-weight:900}
.eo-card{border:1px solid #e2e8f0;border-radius:14px;padding:14px 16px;background:#fff;margin-bottom:10px}
.eo-card b{color:#0f172a}.eo-card small{color:#64748b}
</style>""", unsafe_allow_html=True)

ss = st.session_state

# ----------------------------------------------------------------------------- 저장소 (SQLite)
try:
    APP_DIR = Path(__file__).parent
except NameError:
    APP_DIR = Path.cwd()
DB_PATH = APP_DIR / "event_on.db"


def _db():
    con = sqlite3.connect(str(DB_PATH))
    con.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT, pw_hash TEXT, display_name TEXT, school TEXT, team TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, title TEXT, data TEXT, updated_at TEXT)")
    return con


def _hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), 120_000).hex()


def db_register(username, pw, display):
    username = username.strip()
    if not (3 <= len(username) <= 20) or not re.fullmatch(r"[A-Za-z0-9_가-힣]+", username):
        return "아이디는 3~20자의 한글·영문·숫자·밑줄만 쓸 수 있다."
    if len(pw) < 6:
        return "비밀번호는 6자 이상이어야 한다."
    con = _db()
    try:
        if con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return "이미 있는 아이디이다."
        salt = secrets.token_hex(16)
        con.execute("INSERT INTO users VALUES(?,?,?,?,?,?)", (username, salt, _hash(pw, salt), display.strip() or username, SCHOOL_NAME, TEAM_NAME))
        con.commit()
    finally:
        con.close()
    return ""


def db_login(username, pw):
    con = _db()
    try:
        row = con.execute("SELECT salt,pw_hash,display_name,school,team FROM users WHERE username=?", (username.strip(),)).fetchone()
    finally:
        con.close()
    if not row or not secrets.compare_digest(_hash(pw, row[0]), row[1]):
        return None
    return dict(username=username.strip(), display=row[2], school=row[3] or SCHOOL_NAME, team=row[4] or TEAM_NAME)


def db_update_profile(username, display, school, team):
    con = _db()
    con.execute("UPDATE users SET display_name=?, school=?, team=? WHERE username=?", (display, school, team, username))
    con.commit()
    con.close()


def db_change_pw(username, old, new):
    if db_login(username, old) is None:
        return "현재 비밀번호가 맞지 않는다."
    if len(new) < 6:
        return "새 비밀번호는 6자 이상이어야 한다."
    salt = secrets.token_hex(16)
    con = _db()
    con.execute("UPDATE users SET salt=?, pw_hash=? WHERE username=?", (salt, _hash(new, salt), username))
    con.commit()
    con.close()
    return ""


def db_delete_user(username):
    con = _db()
    con.execute("DELETE FROM projects WHERE username=?", (username,))
    con.execute("DELETE FROM users WHERE username=?", (username,))
    con.commit()
    con.close()


def db_save_project(username, title, data):
    con = _db()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = con.execute("SELECT id FROM projects WHERE username=? AND title=?", (username, title)).fetchone()
    if row:
        con.execute("UPDATE projects SET data=?, updated_at=? WHERE id=?", (data, now, row[0]))
    else:
        con.execute("INSERT INTO projects(username,title,data,updated_at) VALUES(?,?,?,?)", (username, title, data, now))
    con.commit()
    con.close()


def db_list_projects(username):
    con = _db()
    rows = con.execute("SELECT id,title,updated_at,data FROM projects WHERE username=? ORDER BY updated_at DESC, id DESC", (username,)).fetchall()
    con.close()
    return rows


def db_delete_project(pid, username):
    con = _db()
    con.execute("DELETE FROM projects WHERE id=? AND username=?", (pid, username))
    con.commit()
    con.close()


# ----------------------------------------------------------------------------- 상태
FAC_OPTS = ["푸드존", "체험 부스", "휴게 공간", "안내센터", "화장실"]
PIN_TYPES = ["stage", "food", "booth", "rest", "medical", "info", "restroom"]
PAGES = ["🏠 홈", "📋 대시보드", "🧠 설계 분석", "📄 AI 보고서", "⚙️ 설정"]


def default_inp():
    return dict(name="2026 힐링 페스티벌", purpose=list(PURPOSES)[0], budget=5000, visitors=5000, venue=list(VENUES)[0],
                shape=DEFAULT_SHAPE, location="야외 종합 운동장 & 잔디 광장", area=50000, mood=list(MOODS)[0], age=list(AGES)[0],
                gates=4, n=2000, facilities=list(FAC_OPTS), size={t: 100 for t in ["stage", "food", "booth", "rest", "medical", "info", "restroom", "custom"]},
                date=(dt.date.today() + dt.timedelta(days=30)).isoformat(), days=1, start="10:00", end="20:00",
                inside="실외", ticket="무료", ticket_price=0, extra="")


ss.setdefault("inp", default_inp())
ss.setdefault("custom", [])
ss.setdefault("pins", {})
ss.setdefault("chat", [("ai", "안녕하세요! 예) '무대를 우측으로, 응급의료센터를 중앙에 배치해줘', '칵테일 바 2개 추가' 처럼 말씀해 주세요.")])
ss.setdefault("history", [])
ss.setdefault("view", None)
ss.setdefault("pending", None)
ss.setdefault("user", None)
ss.setdefault("rep", dict(school=SCHOOL_NAME, team=TEAM_NAME, author=""))
ss.setdefault("report_cache", {})
ss.setdefault("page", PAGES[0])


def go(page):
    ss.page = page


def current_params():
    i = ss.inp
    sh, eh = int(i["start"][:2]), int(i["end"][:2])
    return dict(name=i["name"], purpose=i["purpose"], budget=int(i["budget"]), visitors=int(i["visitors"]), venue=i["venue"],
                location=i["location"], area_m2=int(i["area"]), hours=f"{sh}시 - {eh}시", mood=i["mood"], age=i["age"],
                gates=int(i["gates"]), shape=i["shape"], size_scale={k: v / 100.0 for k, v in i["size"].items()},
                facilities=["공연장", "응급의료센터"] + list(i["facilities"]),
                event=dict(date=i["date"], days=int(i["days"]), start=i["start"], end=i["end"], inside=i["inside"],
                           ticket=i["ticket"], ticket_price=int(i["ticket_price"]), extra=i["extra"]))


def make_sig():
    return json.dumps(dict(p=current_params(), c=ss.custom, pins={k: list(v) for k, v in ss.pins.items()}, n=int(ss.inp["n"])),
                      sort_keys=True, ensure_ascii=False, default=str)


def project_json() -> str:
    return json.dumps(dict(app="event_on", inp=ss.inp, custom=ss.custom, pins={k: list(v) for k, v in ss.pins.items()}),
                      ensure_ascii=False)


def load_project_json(txt: str) -> str:
    try:
        d = json.loads(txt)
        if d.get("app") != "event_on":
            return "Event ON 프로젝트 파일이 아니다."
        base = default_inp()
        inp = {**base, **d["inp"]}
        inp["size"] = {**base["size"], **d["inp"].get("size", {})}
        if inp["purpose"] not in PURPOSES or inp["venue"] not in VENUES or inp["mood"] not in MOODS or inp["age"] not in AGES or inp["shape"] not in SHAPES:
            return "파일 안의 선택 항목이 현재 앱과 맞지 않는다."
        ss.inp = inp
        ss.custom = list(d.get("custom", []))
        ss.pins = {k: tuple(v) for k, v in d.get("pins", {}).items() if k in ZONE_META}
        ss.pending = "프로젝트 불러오기"
        ss.history = []
        ss.report_cache = {}
        return ""
    except Exception as ex:  # noqa
        return f"불러오지 못했다: {ex}"


def render_evidence(R):
    """점수 산출 근거: 가중치 → 목표 점수 → 세부 지표 → 가정"""
    st.markdown("**① 종합 점수 = Σ (가중치 × 목표 점수)**")
    st.code(R["total_formula"], language=None)
    st.dataframe(pd.DataFrame([dict(
        목표=OBJ_LABEL[k], 기본가중치=f"{R['weight_detail'][k]['base'] * 100:.0f}%",
        행사목적보정=f"{R['weight_detail'][k]['purpose'] * 100:+.0f}%p", 연령대보정=f"{R['weight_detail'][k]['age'] * 100:+.0f}%p",
        최종가중치=f"{R['weight_detail'][k]['final'] * 100:.1f}%", 목표점수=round(R["scores"][k], 1)) for k in OBJECTIVES]),
        hide_index=True, **FW)
    st.markdown("**② 목표 점수 = Σ (세부점수 × 비중)** — 각 항은 `비중×세부점수`")
    for k in OBJECTIVES:
        st.markdown(f"- {OBJ_LABEL[k]}: `{R['formulas'][k]}`")
    st.markdown("**③ 세부 지표 — 측정값이 만점 기준에 가까울수록 100점, 0점 기준에 가까울수록 0점 (사이는 직선 보간)**")
    st.dataframe(pd.DataFrame([dict(
        목표=e["objLabel"], 세부지표=e["label"], 설계전=e["v_before"], 설계후=e["v_after"], 만점기준=e["best_txt"],
        영점기준=e["worst_txt"], 세부점수_후=round(e["sub_after"] * 100), 세부점수_전=round(e["sub_before"] * 100),
        비중=f"{e['w'] * 100:.0f}%", 산정근거=e["why"]) for e in R["evidence"]]), hide_index=True, **FW)
    st.markdown("**④ 구역별 실제 크기 (m)**")
    st.dataframe(pd.DataFrame([dict(구역=z["name"], 종류=z["type"], 가로_m=z["w_m"], 세로_m=z["h_m"]) for z in R["zone_sizes"]]),
                 hide_index=True, **FW, height=220)
    st.markdown("**⑤ 가정과 한계**")
    for a_ in R["assumptions"]:
        st.markdown(f"- {a_}")


def run_design(label):
    bar = st.progress(0.0, text="AI 설계 시작…")
    try:
        res = optimize(current_params(), ss.custom, ss.pins, n_candidates=int(ss.inp["n"]),
                       progress=lambda f, m: bar.progress(min(1.0, f), text=m))
    except Exception as e:  # noqa
        bar.empty()
        st.error(f"설계 실패: {e}")
        return
    bar.empty()
    ss.history.append(dict(label=f"v{len(ss.history) + 1} · {label} ({dt.datetime.now():%H:%M:%S})", result=res, sig=make_sig()))
    ss.view = len(ss.history) - 1
    ss["hist_sel"] = ss.view


def get_report(idx):
    """보고서는 만드는 데 시간이 걸리므로 설계안·설정이 같으면 다시 만들지 않는다."""
    key = (idx, ss.history[idx]["label"], ss.rep["school"], ss.rep["team"], ss.rep["author"])
    if key not in ss.report_cache:
        ss.report_cache = {key: make_report(ss.history[idx]["result"], ss.rep["team"], ss.rep["school"], ss.rep["author"])}
    return ss.report_cache[key]


def pin_preview(R, tp, xr, yr):
    """위치 제약 범위를 배치도 위에 점선 사각형으로 보여 준다."""
    svg = svg_layout(R["zones"], R["gates"], R["shape"])
    xs = [p_[0] for p_ in R["shape"]["outline"]]
    ys = [p_[1] for p_ in R["shape"]["outline"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    rx, ry = x0 + (x1 - x0) * xr[0], y0 + (y1 - y0) * yr[0]
    rw, rh = (x1 - x0) * (xr[1] - xr[0]), (y1 - y0) * (yr[1] - yr[0])
    box = f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" fill="#f59e0b" fill-opacity=".18" stroke="#f59e0b" stroke-width="0.8" stroke-dasharray="2 1.5"/>'
    return svg.replace("</svg>", box + "</svg>")


# ----------------------------------------------------------------------------- 사이드바
with st.sidebar:
    st.markdown("## ✦ Event ON")
    st.caption("AI 기반 행사 설계·분석 플랫폼")
    st.radio("메뉴", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    if ss.user:
        st.markdown(f"👤 **{ss.user['display']}** 님")
        st.caption("프로젝트는 계정에 저장된다.")
        if st.button("로그아웃", **FW):
            ss.user = None
            st.rerun()
    else:
        st.caption("👤 게스트로 이용 중이다. 로그인하면 프로젝트를 저장할 수 있다.")
        with st.expander("로그인 / 회원가입"):
            tl, tr = st.tabs(["로그인", "회원가입"])
            with tl:
                with st.form("login_form"):
                    lu = st.text_input("아이디")
                    lp = st.text_input("비밀번호", type="password")
                    if st.form_submit_button("로그인", **FW):
                        u = db_login(lu, lp)
                        if u:
                            ss.user = u
                            ss.rep.update(school=u["school"], team=u["team"], author=u["display"])
                            st.rerun()
                        else:
                            st.error("아이디 또는 비밀번호가 맞지 않는다.")
            with tr:
                with st.form("reg_form"):
                    ru = st.text_input("아이디 (3~20자)")
                    rn = st.text_input("이름(표시 이름)")
                    rp = st.text_input("비밀번호 (6자 이상)", type="password")
                    rp2 = st.text_input("비밀번호 확인", type="password")
                    if st.form_submit_button("가입하기", **FW):
                        if rp != rp2:
                            st.error("비밀번호가 서로 다르다.")
                        else:
                            msg = db_register(ru, rp, rn)
                            st.error(msg) if msg else st.success("가입했다. 로그인 탭에서 로그인한다.")
    st.divider()
    st.caption("🧪 현재 점수는 가상 시뮬레이션 추정값이다. 실제 행사 기록으로 검증한 값이 아니다.")

# ----------------------------------------------------------------------------- 설계 실행
if not ss.history and not ss.pending and ss.page != PAGES[0]:
    ss.pending = "기본 설계"
if ss.pending:
    _label, ss.pending = ss.pending, None
    run_design(_label)
    st.toast(f"✅ 새 설계안이 반영되었습니다 ({_label})")

page = ss.page
R = ss.history[ss.view]["result"] if ss.history and ss.view is not None else None

# ============================================================================= 홈
if page == PAGES[0]:
    st.markdown("""<div class="eo-head"><h1>🎪 Event ON</h1>
<p>행사 정보를 입력하면 AI가 수천 개 배치안을 만들고 군중 이동을 시뮬레이션해서, 안전하고 효율적인 행사장 배치를 추천한다.</p></div>""",
                unsafe_allow_html=True)
    st.markdown("""
<div class="wf">
<div class="st"><div class="n">1</div><b>행사 정보 입력</b><span>목적·예산·방문객·시설</span></div><div class="ar">›</div>
<div class="st"><div class="n">2</div><b>배치안 생성</b><span>수천 개 후보 만들기</span></div><div class="ar">›</div>
<div class="st"><div class="n">3</div><b>군중 시뮬레이션</b><span>동선·혼잡도 확인</span></div><div class="ar">›</div>
<div class="st"><div class="n">4</div><b>최적안 선정</b><span>점수와 이유 확인</span></div><div class="ar">›</div>
<div class="st"><div class="n">5</div><b>보고서 만들기</b><span>PDF로 저장</span></div>
</div>""", unsafe_allow_html=True)
    st.button("✦ 대시보드에서 시작하기", type="primary", on_click=go, args=(PAGES[1],))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🕘 최근 저장한 프로젝트")
        if ss.user:
            rows = db_list_projects(ss.user["username"])[:3]
            if not rows:
                st.caption("아직 저장한 프로젝트가 없다.")
            for pid, title, upd, data in rows:
                a, b = st.columns([4, 1])
                a.markdown(f"<div class='eo-card'><b>{_html.escape(title)}</b><br><small>{upd}</small></div>", unsafe_allow_html=True)
                if b.button("열기", key=f"home_open_{pid}"):
                    msg = load_project_json(data)
                    if msg:
                        st.error(msg)
                    else:
                        ss.page = PAGES[1]
                        st.rerun()
        else:
            st.caption("로그인하면 저장한 프로젝트가 여기에 나온다. 게스트는 대시보드에서 파일로 내려받아 보관한다.")
    with c2:
        st.markdown("##### 📁 파일에서 불러오기")
        up = st.file_uploader("내려받은 프로젝트 파일(.json)", type=["json"], key="home_up")
        if up is not None and st.button("불러오기", key="home_up_btn"):
            msg = load_project_json(up.getvalue().decode("utf-8"))
            if msg:
                st.error(msg)
            else:
                ss.page = PAGES[1]
                st.rerun()

# ============================================================================= 대시보드
elif page == PAGES[1]:
    st.markdown("""<div class="eo-head"><h1>📋 대시보드</h1><p>행사 정보를 넣고 설계를 만들면 배치도, 방문 비중, 평가 결과가 한 화면에 나온다.</p></div>""", unsafe_allow_html=True)
    if R is None:
        st.stop()
    P = R["params"]
    if ss.history[ss.view].get("sig") != make_sig():
        st.warning("⚠️ 입력값이 지금 보이는 설계안과 다르다. '✦ AI 설계 생성 / 재배치'를 눌러야 반영된다.")
    for n in R["notes"]:
        st.warning(n)

    m = st.columns(5)
    m[0].metric("행사", P["name"])
    m[1].metric("방문객", f"{P['visitors']:,}명")
    m[2].metric("면적 · 모양", f"{P['area_m2']:,}㎡", R["shape"]["name"], delta_color="off")
    m[3].metric("종합 점수", f"{R['total']:.1f}점", f"{R['total'] - R['before_total']:+.1f} vs 설계 전")
    m[4].metric("예상 비용", f"{R['cost']['total']:,.0f}만원", f"예산 {R['cost']['budget']:,}만원", delta_color="off")

    # ---- 행사 정보 입력
    with st.expander("📝 행사 기본정보 입력 / 수정", expanded=False):
        i = ss.inp
        with st.form("info_form"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("행사명", i["name"])
            purpose = c2.selectbox("행사 목적", list(PURPOSES), index=list(PURPOSES).index(i["purpose"]))
            venue = c3.selectbox("행사 장소 유형", list(VENUES), index=list(VENUES).index(i["venue"]))
            c1, c2, c3, c4 = st.columns(4)
            budget = c1.number_input("예산(만원)", 500, 500000, int(i["budget"]), step=500)
            visitors = c2.number_input("예상 방문객(명)", 200, 100000, int(i["visitors"]), step=500)
            area = c3.number_input("면적(㎡)", 500, 1000000, int(i["area"]), step=1000)
            gates = c4.selectbox("출입구 수", [2, 4, 6], index=[2, 4, 6].index(int(i["gates"])), format_func=lambda n: f"{n}개")
            c1, c2 = st.columns(2)
            shape = c1.selectbox("행사장 모양", list(SHAPES), index=list(SHAPES).index(i["shape"]), help="모든 구역은 이 모양 안쪽에 배치된다.")
            location = c2.text_input("행사장 위치", i["location"])
            c1, c2, c3, c4 = st.columns(4)
            date_ = c1.date_input("행사 날짜", dt.date.fromisoformat(i["date"]))
            days = c2.number_input("행사 일수", 1, 14, int(i["days"]))
            t_start = c3.time_input("시작 시간", dt.time.fromisoformat(i["start"]))
            t_end = c4.time_input("종료 시간", dt.time.fromisoformat(i["end"]))
            c1, c2, c3, c4 = st.columns(4)
            mood = c1.selectbox("원하는 분위기", list(MOODS), index=list(MOODS).index(i["mood"]))
            age = c2.selectbox("예상 연령대", list(AGES), index=list(AGES).index(i["age"]))
            inside = c3.selectbox("실내·실외", ["실외", "실내", "실내+실외"], index=["실외", "실내", "실내+실외"].index(i["inside"]))
            ticket = c4.selectbox("입장료", ["무료", "유료"], index=["무료", "유료"].index(i["ticket"]))
            ticket_price = st.number_input("입장료 금액(원, 유료일 때)", 0, 500000, int(i["ticket_price"]), step=1000)
            facilities = st.multiselect("필요한 시설 (공연장·응급의료센터는 항상 포함)", FAC_OPTS, default=[f for f in i["facilities"] if f in FAC_OPTS])
            extra = st.text_area("추가 요청", i["extra"], placeholder="예: 휠체어 동선을 넓게 확보해 주세요")
            n_cand = st.select_slider("탐색할 배치안 수", [500, 1000, 2000, 3000, 5000], value=int(i["n"]) if int(i["n"]) in [500, 1000, 2000, 3000, 5000] else 2000)
            st.markdown("**📐 구역 크기 조절 (100% = 기본)**")
            sizes = {}
            cols = st.columns(4)
            for k, (t_, lab) in enumerate([("stage", "🎭 공연장"), ("food", "🍔 푸드존"), ("booth", "🧪 체험부스"), ("rest", "🛋️ 휴게공간"),
                                          ("medical", "🏥 응급의료센터"), ("info", "ℹ️ 안내센터"), ("restroom", "🚻 화장실"), ("custom", "⭐ 사용자 부스")]):
                sizes[t_] = cols[k % 4].slider(lab, 50, 200, int(i["size"].get(t_, 100)), 5, format="%d%%")
            s1, s2 = st.columns(2)
            go_btn = s1.form_submit_button("✦ 저장하고 AI 설계 생성 / 재배치", type="primary", **FW)
            rs_btn = s2.form_submit_button("입력값을 기본값으로 되돌리기", **FW)
        if go_btn:
            ss.inp = dict(name=name, purpose=purpose, budget=budget, visitors=visitors, venue=venue, shape=shape, location=location,
                          area=area, mood=mood, age=age, gates=gates, n=n_cand, facilities=facilities, size=sizes,
                          date=date_.isoformat(), days=int(days), start=t_start.strftime("%H:%M"), end=t_end.strftime("%H:%M"),
                          inside=inside, ticket=ticket, ticket_price=int(ticket_price), extra=extra)
            if t_end <= t_start:
                st.error("종료 시간은 시작 시간보다 늦어야 한다.")
            else:
                ss.pending = "입력값 반영"
                st.rerun()
        if rs_btn:
            ss.inp = default_inp()
            ss.pending = "기본값 복원"
            st.rerun()
        with st.expander("⭐ 원하는 부스 직접 추가"):
            with st.form("custom_form", clear_on_submit=True):
                cn = st.text_input("부스 이름", placeholder="예: 포토존, 버스킹 무대")
                cc = st.selectbox("종류", list(CUSTOM_CATS))
                cw, ch = st.columns(2)
                wm = cw.number_input("가로(m)", 3, 60, 8)
                hm = ch.number_input("세로(m)", 3, 60, 6)
                cnt = st.number_input("개수", 1, 10, 1)
                if st.form_submit_button("➕ 부스 추가") and cn.strip():
                    ss.custom.append(dict(name=cn.strip(), cat=cc, w=wm, h=hm, count=int(cnt)))
                    ss.pending = f"부스 추가: {cn.strip()}"
                    st.rerun()
            for k, c in enumerate(list(ss.custom)):
                a, b = st.columns([5, 1])
                a.caption(f"⭐ {c['name']} ({c['cat']}, {c['w']}×{c['h']}m) ×{c['count']}")
                if b.button("✕", key=f"del{k}"):
                    ss.custom.pop(k)
                    ss.pending = "부스 삭제"
                    st.rerun()

    if st.button("✦ AI 설계 생성 / 재배치", type="primary"):
        ss.pending = "다시 설계"
        st.rerun()

    # ---- AI 어시스턴트
    st.markdown("##### 🤖 AI 어시스턴트 — 말로 배치를 바꾸거나 부스를 추가한다")
    box = st.container(height=130)
    for who, msg in ss.chat[-6:]:
        box.chat_message("assistant" if who == "ai" else "user").write(msg)
    cmd = st.chat_input("예: 무대를 우측으로 옮기고 응급의료센터를 중앙에 배치해줘 / 포토존 2개 추가")
    if cmd:
        ss.chat.append(("user", cmd))
        parsed = parse_command(cmd)
        if not parsed["pins"] and not parsed["extras"]:
            ss.chat.append(("ai", "배치 지시를 이해하지 못했습니다. '무대 우측', '응급의료센터 중앙', '푸드트럭 3개 추가' 형태로 말씀해 주세요."))
        else:
            ss.pins.update(parsed["pins"])
            ss.custom.extend(parsed["extras"])
            ss.chat.append(("ai", " ".join(parsed["msgs"]) + " 반영하여 다시 최적화합니다."))
            ss.pending = "AI 어시스턴트: " + cmd[:18]
        st.rerun()

    # ---- 디지털 트윈
    embed_html(build_twin_html(R), 1330)

    # ---- 아래: 좌(수요·평가) / 우(AI 배치 분석·수정)
    left, right = st.columns([1.15, 1])
    d, b_ = R["detail"], R["before_detail"]
    with left:
        st.markdown("##### 🚶 시설별 예상 방문 비중")
        st.caption("시설마다 정해 둔 매력도로 방문객을 나눈 값이다. 시뮬레이션의 이동 비율과 같고, 실제 기록으로 학습한 예측은 아니다.")
        for x in demand_rows(R):
            st.progress(min(1.0, x["share"]), text=f"{x['name']} · {x['share'] * 100:.0f}% (약 {x['visits']:,}명)")
        st.markdown("##### 💡 AI 평가 결과")
        st.dataframe(pd.DataFrame([dict(항목=OBJ_LABEL[k], 설계전=round(R["before_scores"][k]), 설계후=round(R["scores"][k]),
                                       등급=grade(R["scores"][k])) for k in OBJECTIVES]), hide_index=True, **FW)
        st.markdown("##### ⚖️ 설계 전 / 후 비교")
        st.dataframe(pd.DataFrame([
            ("병목 발생율", f"{b_['bottleneck']:.0f}%", f"{d['bottleneck']:.0f}%"),
            ("최대 군중 밀도", f"{b_['peak']:.2f}명/㎡", f"{d['peak']:.2f}명/㎡"),
            ("응급 최대 도달", fmt_sec(b_["t_max"]), fmt_sec(d["t_max"])),
            ("사고 위험구역", f"{b_['risk_zones']}개소", f"{d['risk_zones']}개소"),
        ], columns=["지표", "설계 전", "설계 후"]), hide_index=True, **FW)
    with right:
        st.markdown("##### 🧠 구역별 AI 배치 분석")
        zr = R["xai"]["zone_reasons"]
        pick = st.selectbox("구역 선택", range(len(zr)), format_func=lambda k: f"{zr[k]['icon']} {zr[k]['name']}")
        st.info(plain(zr[pick]["text"]))
        st.markdown("##### ✋ AI 배치 수정 (위치 지정)")
        st.caption("시설 종류를 고르고 원하는 위치를 정하면, 그 종류의 시설이 모두 그 범위 안에 놓이도록 다시 설계한다.")
        tp = st.selectbox("시설 종류", PIN_TYPES, format_func=lambda t: f"{ZONE_META[t]['icon']} {ZONE_META[t]['label']}")
        px = st.slider("가로 위치 (왼쪽 0 ~ 오른쪽 100)", 0, 100, 50, 5)
        py = st.slider("세로 위치 (위 0 ~ 아래 100)", 0, 100, 50, 5)
        half = 0.14
        xr = (max(0.0, px / 100 - half), min(1.0, px / 100 + half))
        yr = (max(0.0, py / 100 - half), min(1.0, py / 100 + half))
        st.markdown(pin_preview(R, tp, xr, yr), unsafe_allow_html=True)
        st.caption("주황색 점선 상자가 지정한 범위이다.")
        p1, p2 = st.columns(2)
        if p1.button("이 위치로 재배치", **FW):
            ss.pins[tp] = (xr[0], xr[1], yr[0], yr[1])
            ss.pending = f"{ZONE_META[tp]['label']} 위치 지정"
            st.rerun()
        if p2.button("위치 제약 모두 해제", **FW, disabled=not ss.pins):
            ss.pins = {}
            ss.pending = "위치 제약 해제"
            st.rerun()
        if ss.pins:
            st.caption("📌 지정한 시설: " + " · ".join(ZONE_META[k]["label"] for k in ss.pins))

    # ---- 저장
    st.divider()
    st.markdown("##### 💾 프로젝트 저장")
    s1, s2, s3 = st.columns([2, 1, 1])
    title = s1.text_input("프로젝트 이름", ss.inp["name"], label_visibility="collapsed")
    if s2.button("계정에 저장", **FW, disabled=not ss.user):
        db_save_project(ss.user["username"], title.strip() or ss.inp["name"], project_json())
        st.success("저장했다.")
    s3.download_button("파일로 내려받기", project_json(), file_name="event_on_project.json", mime="application/json", **FW)
    if not ss.user:
        st.caption("계정에 저장하려면 왼쪽에서 로그인한다. 게스트는 파일로 내려받아 보관하고, 홈에서 다시 불러온다.")

# ============================================================================= 설계 분석
elif page == PAGES[2]:
    st.markdown("""<div class="eo-head"><h1>🧠 설계 분석</h1><p>설계가 어떤 과정을 거쳤는지, 왜 이 배치가 나왔는지, 설계안끼리 어떻게 다른지 본다.</p></div>""", unsafe_allow_html=True)
    if R is None:
        st.stop()
    labels = [h["label"] for h in ss.history]
    if ss.get("hist_sel") is None or ss["hist_sel"] >= len(labels):
        ss["hist_sel"] = len(labels) - 1
    ss.view = st.selectbox("📜 설계 히스토리", range(len(labels)), format_func=lambda k: labels[k], key="hist_sel")
    R = ss.history[ss.view]["result"]
    t1, t2, t3 = st.tabs(["⚙️ 설계 프로세스", "🧠 설계 이유 (XAI)", "⚖️ 설계안 비교"])
    with t1:
        st.markdown("""
<div class="wf">
<div class="st"><div class="n">1</div><b>행사 정보 입력</b><span>목적·예산·방문객·장소·분위기·연령</span></div><div class="ar">›</div>
<div class="st"><div class="n">2</div><b>디지털 트윈 생성</b><span>구역·출입구·보행로 모델링</span></div><div class="ar">›</div>
<div class="st"><div class="n">3</div><b>수천 개 배치안 생성</b><span>무작위 샘플링 + 상위안 변이</span></div><div class="ar">›</div>
<div class="st"><div class="n">4</div><b>군중 시뮬레이션</b><span>이동 동선·혼잡도 예측</span></div><div class="ar">›</div>
<div class="st"><div class="n">5</div><b>다목적 최적화</b><span>안전·동선·접근·혼잡·공간</span></div><div class="ar">›</div>
<div class="st"><div class="n">6</div><b>최적안 선정 + XAI</b><span>설계 이유 설명</span></div><div class="ar">›</div>
<div class="st"><div class="n">7</div><b>결과 제공</b><span>배치도·리포트·전/후 비교</span></div>
</div>""", unsafe_allow_html=True)
        s = R["stats"]
        c = st.columns(4)
        c[0].metric("생성·평가한 배치안", f"{s['generated']:,}개")
        c[1].metric("무작위 / 변이", f"{s['randomly']:,} / {s['mutated']:,}")
        c[2].metric("파레토 최적해", f"{s['pareto']}개")
        c[3].metric("배치 구역 수", f"{s['zones']}개")
        st.markdown("##### 후보 배치안 분포 (점이 위·오른쪽일수록 우수)")
        st.scatter_chart(pd.DataFrame(R["cloud"]).rename(columns={"safety": "비상 안전성", "cong": "혼잡도 분산"}),
                         x="비상 안전성", y="혼잡도 분산", color="total", height=340)
        st.caption("가중치: " + " · ".join(f"{OBJ_LABEL[k]} {R['weights'][k] * 100:.0f}%" for k in OBJECTIVES))
    with t2:
        X = R["xai"]
        st.markdown("#### 왜 이 배치인가요?")
        for t in X["reasons"]:
            st.markdown(f"- {plain(t)}")
        st.markdown("#### 목표별 기여도")
        st.dataframe(pd.DataFrame([dict(목표=c["label"], 가중치=f"{c['weight'] * 100:.0f}%", 점수=round(c["score"], 1),
                                       종합기여=round(c["contribution"], 1), 후보중상위=f"{max(0.1, 100 - c['pct_rank']):.0f}%",
                                       후보평균대비=f"{c['vs_mean']:+.1f}") for c in X["contrib"]]),
                     hide_index=True, **FW)
        st.bar_chart(pd.DataFrame({"종합 기여": {c["label"]: c["contribution"] for c in X["contrib"]}}))
        st.markdown("#### 점수는 어떻게 계산됐나요? (산출 근거)")
        render_evidence(R)
        st.markdown("#### 구역별 배치 근거")
        for z in X["zone_reasons"]:
            st.markdown(f"- {z['icon']} **{z['name']}** — {plain(z['text'])}")
        if X["alternatives"]:
            st.markdown("#### 검토했으나 채택하지 않은 대안")
            for a in X["alternatives"]:
                st.markdown(f"- **{a['name']}** (종합 {a['total']:.1f}점): {plain(a['note'])}")
    with t3:
        st.caption("지금까지 만든 설계안을 한눈에 비교한다. 입력을 바꿔 가며 설계해 보면 표가 늘어난다.")
        rows = []
        for h in ss.history:
            r_ = h["result"]
            rows.append({"설계안": h["label"], "종합": round(r_["total"], 1), **{OBJ_LABEL[k]: round(r_["scores"][k]) for k in OBJECTIVES},
                         "위험구역": r_["detail"]["risk_zones"], "최대밀도(명/㎡)": round(r_["detail"]["peak"], 2),
                         "예상비용(만원)": round(r_["cost"]["total"])})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, **FW)
        if len(df) > 1:
            st.bar_chart(df.set_index("설계안")[["종합"]])

# ============================================================================= AI 보고서
elif page == PAGES[3]:
    st.markdown("""<div class="eo-head"><h1>📄 AI 보고서</h1><p>선택한 설계안으로 표지·목차·본문이 있는 보고서를 만든다. PDF로 바로 내려받을 수 있다.</p></div>""", unsafe_allow_html=True)
    if R is None:
        st.stop()
    labels = [h["label"] for h in ss.history]
    if ss.get("hist_sel") is None or ss["hist_sel"] >= len(labels):
        ss["hist_sel"] = len(labels) - 1
    ss.view = st.selectbox("📜 보고서로 만들 설계안", range(len(labels)), format_func=lambda k: labels[k], key="hist_sel")
    with st.spinner("보고서를 만드는 중…"):
        rep = get_report(ss.view)
    safe = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", ss.history[ss.view]["result"]["params"]["name"]).strip("_") or "report"
    d1, d2, d3 = st.columns(3)
    if rep["pdf"]:
        d1.download_button("⬇️ PDF 보고서", rep["pdf"], file_name=f"{safe}_report.pdf", mime="application/pdf", type="primary", **FW)
    else:
        d1.button("PDF 만들 수 없음", disabled=True, **FW)
    d2.download_button("⬇️ HTML", rep["html"], file_name=f"{safe}_report.html", mime="text/html", **FW)
    d3.download_button("⬇️ Markdown", rep["md"], file_name=f"{safe}_report.md", mime="text/markdown", **FW)
    if not rep["pdf"]:
        st.warning(f"PDF를 만들지 못했다 ({rep['pdf_err']}). requirements.txt에 reportlab을 넣었는지 확인한다. 아래 보고서의 'PDF로 저장' 버튼(인쇄)으로 대신 저장할 수 있다.")
    st.caption("학교·팀·작성자 이름은 ⚙️ 설정에서 바꾼다.")
    embed_html(rep["html"], 900)

# ============================================================================= 설정
else:
    st.markdown("""<div class="eo-head"><h1>⚙️ 설정</h1><p>보고서에 들어갈 이름과 계정, 프로젝트를 관리한다.</p></div>""", unsafe_allow_html=True)
    st.markdown("##### 📄 보고서 설정")
    with st.form("rep_form"):
        c1, c2, c3 = st.columns(3)
        sc = c1.text_input("학교 이름", ss.rep["school"])
        tm = c2.text_input("팀 이름", ss.rep["team"])
        au = c3.text_input("작성자", ss.rep["author"])
        if st.form_submit_button("저장"):
            ss.rep = dict(school=sc, team=tm, author=au)
            if ss.user:
                db_update_profile(ss.user["username"], au or ss.user["display"], sc, tm)
                ss.user.update(display=au or ss.user["display"], school=sc, team=tm)
            st.success("저장했다.")
    st.markdown("##### 📁 프로젝트 관리")
    if ss.user:
        rows = db_list_projects(ss.user["username"])
        if not rows:
            st.caption("저장한 프로젝트가 없다.")
        for pid, title, upd, data in rows:
            a, b, c = st.columns([4, 1, 1])
            a.markdown(f"**{title}**  \n<small>{upd}</small>", unsafe_allow_html=True)
            if b.button("불러오기", key=f"ld{pid}"):
                msg = load_project_json(data)
                if msg:
                    st.error(msg)
                else:
                    ss.page = PAGES[1]
                    st.rerun()
            if c.button("삭제", key=f"rm{pid}"):
                db_delete_project(pid, ss.user["username"])
                st.rerun()
    else:
        st.caption("로그인하면 프로젝트 목록이 여기에 나온다.")
    up = st.file_uploader("프로젝트 파일(.json)에서 불러오기", type=["json"], key="set_up")
    if up is not None and st.button("파일 불러오기"):
        msg = load_project_json(up.getvalue().decode("utf-8"))
        if msg:
            st.error(msg)
        else:
            ss.page = PAGES[1]
            st.rerun()
    if ss.user:
        st.markdown("##### 🔐 계정")
        with st.form("pw_form"):
            o = st.text_input("현재 비밀번호", type="password")
            n = st.text_input("새 비밀번호 (6자 이상)", type="password")
            if st.form_submit_button("비밀번호 변경"):
                msg = db_change_pw(ss.user["username"], o, n)
                st.error(msg) if msg else st.success("바꿨다.")
        with st.expander("⚠️ 회원 탈퇴"):
            st.caption("계정과 저장한 프로젝트가 모두 지워지고 되돌릴 수 없다.")
            pw_ = st.text_input("비밀번호 확인", type="password", key="del_pw")
            if st.button("탈퇴하기"):
                if db_login(ss.user["username"], pw_):
                    db_delete_user(ss.user["username"])
                    ss.user = None
                    st.rerun()
                else:
                    st.error("비밀번호가 맞지 않는다.")
    st.caption("화면 테마(어두운 모드 등)는 Streamlit 오른쪽 위 메뉴 → Settings에서 바꾼다.")
