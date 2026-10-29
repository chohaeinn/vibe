# -*- coding: utf-8 -*-
"""Event ON - AI 기반 행사 자동 설계 플랫폼 (단일 파일 버전: app.py 하나만 올리면 실행됩니다)"""
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



EVENT_TYPES = ['페스티벌/공연','박람회/전시회','체육대회/스포츠','음식/조리','반려동물 중심 행사']
PROFILE_ITEMS = {
 '페스티벌/공연':[('음향조정실','음향·방송 장비를 운영하는 공간'),('무대 대기실','출연자가 공연 전 대기하는 공간'),('통제실','공연 진행과 현장 상황을 확인하는 공간')],
 '박람회/전시회':[('전시부스','작품·상품·기업 정보를 전시하는 공간')],
 '체육대회/스포츠':[('경기장','체육 활동과 경기를 진행하는 공간'),('선수 대기실','선수의 준비와 휴식을 위한 공간'),('심판실','심판의 경기 운영 준비 공간'),('기록실','경기 결과와 기록을 관리하는 공간')],
 '음식/조리':[('조리공간','음식 조리 작업 공간'),('식사구역','음식을 먹을 수 있는 공간'),('손 씻는 시설','조리·식사 전 손 위생을 위한 공간'),('식자재 보관 공간','식재료 보관을 위한 공간'),('음식물 폐기물 처리 공간','음식물 폐기물을 모으는 공간')],
 '반려동물 중심 행사':[('반려동물 휴식 공간','반려동물의 휴식을 위한 공간'),('급수 시설','반려동물에게 물을 제공하는 공간'),('배변 처리 시설','반려동물 배변을 수거하는 공간'),('동물 응급지원','동물 응급상황 지원을 위한 공간')]
}
COMMON_ITEMS=[('안전관리본부','현장 안전과 비상상황을 관리하는 공간'),('분실물보관소','습득 물품을 보관하는 공간'),('수유실','수유와 보호자의 돌봄을 위한 공간'),('분리수거함','쓰레기 분리배출 공간'),('방송실','안내방송과 방송 장비 운용 공간'),('음향조정실','현장 음향을 조정하는 공간'),('장비창고','운영 장비와 소모품 보관 공간'),('흡연구역','다른 이용 공간과 분리가 필요한 흡연 공간'),('여분 부스','운영 변화에 대비한 예비 공간'),('주차장','차량 주차 구역의 개략적 표식'),('미아보호소','보호자와 떨어진 사람을 지원하는 공간'),('구급차 접근 공간','구급차 진입·대기에 필요한 공간의 개략적 표식')]

COMMON_ITEMS.extend([('비상 대피소','비상 시 집결하는 위치의 계획용 표식'),('안내데스크','도착한 이용객에게 행사 정보를 안내하는 공간'),('스태프룸','현장 운영 인력의 휴식·업무 공간'),('소방·화재 대응 시설','소화 장비와 화재 대응을 위한 공간 표식'),('시설 유지관리 공간','행사장 설비 점검과 유지관리를 위한 공간')])

MANDATORY_ITEMS = [
 ('소방·화재 대응 시설','소화 장비와 화재 대응을 위한 계획 공간'),
 ('안내 데스크','행사장 정보와 이용 안내를 제공하는 공간'),
 ('스태프룸(직원휴게실)','운영 인력의 업무와 휴식을 위한 공간'),
 ('응급처치','응급처치 지원을 위한 공간'),
 ('음수대','방문객에게 식수를 제공하는 위치'),
 ('분실물 보관소','습득한 물품을 보관하는 공간'),
 ('수유실','수유와 영유아 돌봄을 위한 공간'),
 ('쓰레기·분리배출함','일반 쓰레기와 재활용품 분리배출 위치'),
 ('안내·운영 장비','현장 안내 및 운영 장비를 배치하는 공간'),
 ('방송실','안내방송 운영을 위한 공간'),
 ('음향 조정실','공연과 안내 음향을 조정하는 공간'),
 ('장비창고','장비와 물품을 보관하는 공간'),
 ('행사장 시설 유지 관리·수단','시설 점검 및 유지관리 인력·장비를 위한 공간'),
 ('흡연구역','다른 이용 공간과 분리가 필요한 흡연 위치'),
 ('여분 부스','행사 운영 변화에 대비한 예비 부스'),
 ('미아 보호소','보호자와 떨어진 방문객을 지원하는 공간'),
 ('구급차 접근 공간','구급차 진입·대기를 위한 계획 공간')]

def plan_facilities(p):
    items=list(MANDATORY_ITEMS)
    for typ in p.get('event_types',[]): items.extend(PROFILE_ITEMS.get(typ,[]))
    if p.get('is_outdoor',False):items.extend([('그늘막','야외 휴식용 그늘막'),('야외 운영 지원','야외 운영 지원 공간')])
    duration=(p.get('end_hour',20)-p.get('start_hour',10))%24 or 24
    if p.get('start_hour',10)+duration>18 or p.get('start_hour',10)<6:
        items.extend([('야간 조명','야간 활동용 조명'),('안전 조명','통로 시인성 확보용 조명'),('비상 조명','비상상황 대비 조명')])
    return list(dict(items).items())


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
    if not p.get("event_types") or "페스티벌/공연" in p["event_types"]:
        add("stage", "메인 무대", 26 * ss, 15 * ss, cap=42)
    if p.get("is_outdoor",True) or "음식/조리" in p.get("event_types",[]):
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
    if True:  # Application-required facilities are always included.
        for label,description in plan_facilities(p):
            if any(z['name']==label for z in zones): continue
            big=label in ('경기장','주차장','전시부스','식사구역')
            add('medical' if label=='응급처치' else ('info' if label=='안내 데스크' else 'custom'),label,12 if big else 4,8 if big else 3,cap=28,attract=0 if label=='응급처치' else .025)
            zones[-1]['description']=description
            zones[-1]['planning_reason']='선택한 행사 유형·운영 시간에 맞춰 자동 구성한 시설입니다.'
        # Rebuild a consistent simple estimate from the facilities that were actually included.
        cost=sum((800+V*.15) if z['type']=='stage' else COST[z['type']] for z in zones)
        if cost>budget: notes.append('자동 구성 시설을 포함한 종류별 단순 추정 비용이 예산을 초과합니다. 개수나 예산을 조정하세요.')
        notes.append('자동 시설 구성은 기획용 추천입니다. 필수 시설의 법적 요건·허가·수량을 판정하지 않으며 현장 검토가 필요합니다.')
    zones=[z for z in zones if '주차장' not in z['name']]
    cost=sum((800+V*.15) if z['type']=='stage' else COST[z['type']] for z in zones)
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

    prog(0.9, "다목적 최적화(파레토) 및 배치안 평가 중…")
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

TWIN_TEMPLATE = r'''<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
:root{--bg:#eef5fb;--card:#fff;--line:#e3ebf4;--ink:#13233a;--sub:#6b7f97;--mut:#93a4b8;--pri:#2f6bff;--pri2:#1f4fd6;--priBg:#eaf1ff;--ok:#12b981;--warn:#f59e0b;--bad:#ef4444}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent}
body{font-family:Pretendard,-apple-system,system-ui,sans-serif;color:var(--ink);background:linear-gradient(180deg,#eaf3fc,#f5f9fd 40%,#f3f7fb);padding:10px;font-size:12.5px}
button{cursor:pointer;font-family:inherit;border:1px solid var(--line);background:#fff;color:#334155;padding:6px 11px;border-radius:8px;font-size:12px;font-weight:700;transition:.15s}
button:hover{background:#f1f6fd;border-color:#cfdcec}
button.on{background:var(--pri);color:#fff;border-color:var(--pri2)}
button.danger.on{background:var(--bad);border-color:#dc2626}
button.ghost{border-color:transparent;background:transparent}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 4px 18px #1e3a5f0c;padding:14px}
.card h4{font-size:13.5px;font-weight:800;display:flex;align-items:center;gap:7px;margin-bottom:10px}
.card h4 .ic{width:22px;height:22px;border-radius:7px;background:var(--priBg);color:var(--pri);display:inline-grid;place-items:center;font-size:12px}
.card h4 .sp{flex:1}
.badge{font-size:11px;font-weight:700;color:var(--pri);background:var(--priBg);padding:3px 9px;border-radius:12px}
.badge.ok{color:#0d8a5f;background:#e3f8ef}.badge.warn{color:#b45309;background:#fef3c7}.badge.gray{color:#64748b;background:#eef2f7}

/* ---- top bar ---- */
.topbar{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid var(--line);border-radius:16px;padding:10px 16px;box-shadow:0 4px 18px #1e3a5f0c;margin-bottom:10px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:10px}
.logo svg{width:34px;height:34px}
.logo b{font-size:19px;letter-spacing:.3px;color:#1c3f95;font-weight:900;display:block;line-height:1.1}
.logo span{font-size:10.5px;color:var(--sub);font-weight:600}
.tb-field{display:flex;flex-direction:column;gap:2px}
.tb-field label{font-size:10px;color:var(--mut);font-weight:700}
.tb-field .v{border:1px solid var(--line);background:#f8fbfe;border-radius:8px;padding:6px 12px;font-weight:700;min-width:170px;font-size:12.5px}
.tb-sp{flex:1}
.btn-pri{background:linear-gradient(135deg,#3b82f6,#2f6bff);color:#fff;border:0;padding:9px 16px;border-radius:10px;font-size:13px;box-shadow:0 4px 12px #2f6bff44}
.btn-pri:hover{background:linear-gradient(135deg,#2f6bff,#1f4fd6)}
.menuwrap{position:relative}
.menu{position:absolute;right:0;top:110%;background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px #1e3a5f22;padding:5px;z-index:60;display:none;min-width:170px}
.menu.open{display:block}.menu button{display:block;width:100%;text-align:left;border:0;background:transparent;padding:8px 10px}
.avatar{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;display:grid;place-items:center;font-weight:800;font-size:14px}

/* ---- 3 column layout ---- */
.layout{display:grid;grid-template-columns:262px minmax(0,1fr) 308px;gap:10px;align-items:start}
.col{display:flex;flex-direction:column;gap:10px;min-width:0}
@media(max-width:1320px){.layout{grid-template-columns:250px minmax(0,1fr)}.col.right{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}}
@media(max-width:820px){.layout{grid-template-columns:1fr}}

/* left */
.info-row{display:grid;grid-template-columns:20px 1fr;gap:2px 8px;align-items:start;margin-bottom:9px}
.info-row i{font-style:normal;font-size:14px;grid-row:span 2;color:var(--pri);margin-top:2px}
.info-row small{font-size:10.5px;color:var(--mut);font-weight:700}
.info-row div{border:1px solid var(--line);background:#f8fbfe;border-radius:8px;padding:6px 9px;font-weight:700;font-size:12px;line-height:1.35;word-break:keep-all}
.goal{display:flex;gap:9px;align-items:center;width:100%;text-align:left;padding:9px 10px;margin-bottom:6px;border-radius:10px;border:1px solid var(--line);background:#fff}
.goal .gi{width:26px;height:26px;border-radius:8px;background:#f1f5fb;display:grid;place-items:center;font-size:14px;flex:none}
.goal b{font-size:12.5px;display:block}.goal small{font-size:10.5px;color:var(--sub);font-weight:600}
.goal.on{background:var(--priBg);border-color:#bcd2ff;color:var(--ink)}
.goal.on .gi{background:var(--pri);color:#fff}
.tg{display:flex;align-items:center;gap:9px;padding:7px 4px;border-bottom:1px solid #f0f4f9}
.tg:last-child{border:0}
.tg .gi{width:24px;height:24px;border-radius:7px;display:grid;place-items:center;font-size:13px;color:#fff;flex:none}
.tg .nm{flex:1;font-weight:700;font-size:12.5px}.tg .ct{font-size:11px;color:var(--mut);font-weight:700;margin-right:4px}
.sw{position:relative;width:34px;height:19px;border-radius:12px;background:#cdd7e4;transition:.2s;flex:none;cursor:pointer}
.sw::after{content:'';position:absolute;top:2px;left:2px;width:15px;height:15px;border-radius:50%;background:#fff;box-shadow:0 1px 3px #0003;transition:.2s}
.sw.on{background:var(--pri)}.sw.on::after{left:17px}
#facilitySearch{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;margin-bottom:8px;font-family:inherit;font-size:12px;background:#f8fbfe}
#facilityExplorer{max-height:190px;overflow:auto}
.explorerItem{display:block;width:100%;text-align:left;padding:7px 6px;border:0;border-bottom:1px solid #f1f5f9;font-weight:600;background:transparent;border-radius:0}
.explorerItem:hover{background:#eff6ff}.explorerItem.sel{background:var(--priBg);color:var(--pri2)}

/* center */
.mapcard{padding:10px}
.mhead{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.seg{display:inline-flex;background:#eef3fa;border-radius:10px;padding:3px;gap:2px}
.seg button{border:0;background:transparent;padding:6px 12px;border-radius:8px}
.seg button.on{background:#fff;color:var(--pri2);box-shadow:0 1px 4px #1e3a5f22}
.wrap{position:relative;width:100%;border-radius:12px;overflow:hidden;background:#dbe8f5}
#wrap{aspect-ratio:1.5;min-height:480px}
#wrap:fullscreen{aspect-ratio:auto;min-height:0}
#wrap2{aspect-ratio:1.6;background:#1e293b}
.wrap canvas,.wrap .c3{position:absolute;inset:0;width:100%;height:100%}
.c3{cursor:grab;background:#dbe8f5}
.chips{position:absolute;left:10px;top:10px;z-index:8;display:flex;flex-wrap:wrap;gap:4px;background:rgba(255,255,255,.94);padding:5px 7px;border-radius:11px;box-shadow:0 3px 14px #1e3a5f22;max-width:calc(100% - 70px)}
.chip{display:flex;align-items:center;gap:5px;padding:4px 9px;border-radius:8px;font-size:11.5px;font-weight:700;color:#475569;border:1px solid transparent;background:transparent;cursor:pointer}
.chip .cb{width:13px;height:13px;border-radius:4px;border:1.5px solid #b8c6d8;display:grid;place-items:center;font-size:9px;color:#fff;background:#fff}
.chip.on{color:var(--ink);background:var(--priBg)}.chip.on .cb{background:var(--pri);border-color:var(--pri)}
.zoomc{position:absolute;right:10px;top:10px;z-index:8;display:flex;flex-direction:column;background:#fff;border-radius:10px;box-shadow:0 3px 14px #1e3a5f22;overflow:hidden}
.zoomc button{border:0;border-bottom:1px solid var(--line);border-radius:0;width:36px;height:34px;font-size:16px;padding:0;color:#475569}
.zoomc button:last-child{border:0}
.legend{position:absolute;left:10px;bottom:10px;background:rgba(255,255,255,.94);border-radius:10px;padding:7px 11px;font-size:10.5px;font-weight:700;display:grid;grid-template-columns:repeat(3,auto);gap:3px 14px;z-index:6;pointer-events:none;box-shadow:0 3px 12px #1e3a5f1f}
.legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px}
.hint{position:absolute;left:50%;transform:translateX(-50%);bottom:12px;background:rgba(19,35,58,.7);color:#fff;font-size:10.5px;padding:4px 9px;border-radius:8px;z-index:5;pointer-events:none}
.mapstat{position:absolute;right:10px;bottom:10px;z-index:6;display:flex;gap:6px;pointer-events:none}
.mapstat .badge{background:rgba(255,255,255,.94);box-shadow:0 3px 12px #1e3a5f1f}
#labels{position:absolute;inset:0;z-index:7;pointer-events:none;overflow:hidden}
.lbl{position:absolute;left:0;top:0;display:flex;flex-direction:column;align-items:center;pointer-events:auto;cursor:pointer;will-change:transform}
.lbl .pill{background:#111c2d;color:#fff;font-size:11px;font-weight:700;padding:4px 11px;border-radius:14px;white-space:nowrap;border:1.5px solid #fff;box-shadow:0 3px 10px #0f172a44}
.lbl .stem{width:1.6px;height:13px;background:#fff;box-shadow:0 0 0 .6px #0f172a55}
.lbl .dot{width:8px;height:8px;border-radius:50%;background:#fff;border:2px solid #111c2d}
.lbl:hover .pill,.lbl.sel .pill{background:var(--pri)}
.lbl.sel{z-index:3}
.toolrow{display:flex;flex-wrap:wrap;gap:8px;margin-top:9px}
.tgrp{display:flex;flex-wrap:wrap;gap:5px;align-items:center;background:#f6f9fd;border:1px solid var(--line);border-radius:11px;padding:6px 8px;font-size:11.5px;font-weight:700;color:#475569}
.tgrp .gt{font-size:10.5px;color:var(--mut);margin-right:2px}
.tgrp input[type=range]{accent-color:var(--pri);width:92px}
#editStatus{font-size:11px;color:var(--sub);font-weight:600;max-width:340px}
.tl{display:flex;align-items:center;gap:8px;margin-top:8px;background:#f6f9fd;border:1px solid var(--line);border-radius:11px;padding:6px 10px;font-weight:700;flex-wrap:wrap}
.tl input{flex:1;min-width:120px;accent-color:var(--pri)}
.tm{background:var(--pri);color:#fff;border-radius:14px;padding:2px 10px;font-size:12px;min-width:56px;text-align:center}

/* right */
.fcard .thumb{display:flex;gap:11px;margin-bottom:10px}
.fcard canvas{width:92px;height:70px;border-radius:10px;background:#eef4fb;flex:none}
.fcard .tt b{font-size:16px;display:block;margin-bottom:4px}
.tag{display:inline-block;font-size:10.5px;font-weight:800;padding:2px 8px;border-radius:6px}
.fdesc{font-size:12px;color:var(--sub);line-height:1.55;margin:8px 0 10px;padding-bottom:10px;border-bottom:1px solid var(--line)}
.frow{display:grid;grid-template-columns:20px 74px 1fr;gap:6px;align-items:start;padding:5px 0;font-size:12px}
.frow i{font-style:normal;color:var(--pri)}.frow span{color:var(--sub);font-weight:700}.frow b{font-weight:700;line-height:1.4}
.fwhy{background:#f6f9fd;border-radius:9px;padding:8px 10px;font-size:11px;color:var(--sub);line-height:1.5;margin-top:6px}
.empty{color:var(--mut);font-size:12px;text-align:center;padding:18px 6px;line-height:1.6}
.bar{display:grid;grid-template-columns:78px 1fr 40px;gap:8px;align-items:center;margin:8px 0;font-size:12px;font-weight:700}
.bar .tr{height:8px;border-radius:6px;background:#e9f0f8;overflow:hidden}
.bar .fl{height:100%;border-radius:6px;background:linear-gradient(90deg,#7dd3fc,#3b82f6)}
.bar.hi .fl{background:linear-gradient(90deg,#60a5fa,#2f6bff)}.bar.hi span:first-child{color:var(--pri2)}
.bar.low .fl{background:linear-gradient(90deg,#fcd34d,#f59e0b)}.bar.bad .fl{background:linear-gradient(90deg,#fca5a5,#ef4444)}
.bar em{font-style:normal;text-align:right;color:#334155}
.bar small{grid-column:1/-1;font-size:10px;color:var(--mut);font-weight:600;margin-top:-4px}
.aitxt{font-size:12px;line-height:1.6;color:#41536b}.aitxt p{margin-bottom:5px}
.sugg{list-style:none}.sugg li{position:relative;padding:5px 0 5px 14px;font-size:12px;line-height:1.5;color:#41536b}
.sugg li::before{content:'';position:absolute;left:2px;top:12px;width:5px;height:5px;border-radius:50%;background:var(--pri)}
.sugg li.w::before{background:var(--warn)}.sugg li.b::before{background:var(--bad)}

/* bottom */
.bottom{display:grid;grid-template-columns:1fr 1.25fr 1.45fr;gap:10px;margin-top:10px}
@media(max-width:980px){.bottom{grid-template-columns:1fr}}
.prog{display:flex;gap:14px;align-items:center}
.ring{--p:70;width:92px;height:92px;border-radius:50%;background:conic-gradient(var(--pri) calc(var(--p)*1%),#e6eef8 0);display:grid;place-items:center;flex:none}
.ring div{width:70px;height:70px;border-radius:50%;background:#fff;display:grid;place-items:center;text-align:center;font-size:20px;font-weight:900;color:var(--pri2);line-height:1.1}
.ring small{display:block;font-size:9.5px;color:var(--mut);font-weight:700}
.steps{list-style:none;font-size:11.5px;line-height:1.9;color:#41536b;font-weight:600}.steps li::before{content:'✔ ';color:var(--ok);font-weight:900}
.steps li.pend::before{content:'● ';color:var(--warn)}
.cmp{display:flex;align-items:center;gap:8px}
.cmp .it{flex:1;text-align:center}.cmp canvas{width:100%;aspect-ratio:1.6;border-radius:9px;background:#eef4fb;border:1px solid var(--line)}
.cmp .it span{display:block;font-size:11.5px;font-weight:700;margin-top:4px;color:#475569}
.cmp .ar{font-size:20px;color:var(--pri);font-weight:900}
.delta{margin-top:8px;font-size:11.5px;font-weight:700;color:#41536b;background:#f6f9fd;border-radius:9px;padding:7px 10px;line-height:1.55}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.tile{border:1px solid var(--line);border-radius:12px;padding:9px 10px;display:flex;gap:9px;align-items:center}
.tile .ti{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-size:16px;flex:none}
.tile small{display:block;font-size:10.5px;color:var(--sub);font-weight:700}.tile b{font-size:16px}
.grid2{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:10px;margin-top:10px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.kpi{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:10px}
.kpi div{background:#f6f9fd;border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:11px;color:var(--sub);font-weight:700}
.kpi b{display:block;font-size:17px;color:var(--ink)}
.hl{font-size:11px;color:#64748b;font-weight:700;display:flex;justify-content:space-around;margin-top:6px}
.zl{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:5px;font-size:11px;font-weight:700;max-height:190px;overflow:auto}
.zl span{background:#f8fafc;border:1px solid var(--line);border-left:5px solid var(--c);border-radius:6px;padding:4px 7px}
</style></head><body>

<div class="topbar">
  <div class="logo"><svg viewBox="0 0 40 40"><path d="M20 3 36 33H4z" fill="#3b82f6"/><path d="M20 12 29 29H11z" fill="#bfdbfe"/><circle cx="20" cy="22" r="3.4" fill="#1d4ed8"/></svg>
    <div><b>EVENT ON DESIGNER</b><span>행사 공간 자동 설계 대시보드</span></div></div>
  <div class="tb-field"><label>행사장</label><div class="v" id="tbProject">-</div></div>
  <div class="tb-field"><label>행사명</label><div class="v" id="tbEvent">-</div></div>
  <span class="tb-sp"></span>
  <button class="btn-pri" onclick="runDesign()">✦ 설계 실행</button>
  <button onclick="save3Edit()">💾 저장하기</button>
  <div class="menuwrap"><button onclick="$('expMenu').classList.toggle('open')">⬇ 내보내기 ▾</button>
    <div class="menu" id="expMenu"><button onclick="exportPNG()">🖼 현재 화면 PNG</button><button onclick="exportJSON()">🧾 배치 데이터 JSON</button></div></div>
  <div class="avatar" id="tbAvatar">E</div>
</div>

<div class="layout">
  <!-- ================= LEFT ================= -->
  <aside class="col left">
    <div class="card"><h4><span class="ic">🏷</span>행사 기본 정보</h4><div id="infoRows"></div>
      <div style="font-size:10.5px;color:var(--mut);line-height:1.5">값 변경은 좌측 사이드바에서 한 뒤 <b>설계 실행</b>을 누르세요.</div></div>
    <div class="card"><h4><span class="ic">🎯</span>설계 목표</h4><div id="goalList"></div>
      <div style="font-size:10.5px;color:var(--mut);line-height:1.5">선택한 목표는 우측 지표 강조용입니다. 실제 점수 가중치는 행사 목적·연령대로 정해집니다.</div></div>
    <div class="card"><h4><span class="ic">🗂</span>시설 목록 <span class="sp"></span><span class="badge" id="facTotal">0개</span></h4><div id="groupList"></div></div>
    <div class="card"><h4><span class="ic">🔎</span>시설 찾기</h4><input id="facilitySearch" placeholder="시설 이름 검색" oninput="populateExplorer()"><div id="facilityExplorer"></div></div>
  </aside>

  <!-- ================= CENTER ================= -->
  <main class="col">
    <div class="card mapcard">
      <div class="mhead">
        <div class="seg"><button id="bMode" class="on" onclick="setMode('after')">✦ AI 최적 배치</button><button id="bModeB" onclick="setMode('before')">설계 전(기존)</button></div>
        <div class="seg"><button id="b3d" class="on" onclick="setView(true)">🧊 3D</button><button id="b2d" onclick="setView(false)">🗺 2D</button></div>
        <button id="bHeat3" onclick="togHeat3()">🔥 히트맵</button>
        <button id="bLbl" class="on" onclick="togLabels()">🏷 라벨</button>
        <button id="bDome" class="on" onclick="togDome()" style="display:none">🏛 지붕</button>
        <span style="flex:1"></span>
        <span class="badge" id="verTxt"></span><span class="badge ok" id="status">실시간 군중 시뮬레이션</span>
      </div>
      <div class="wrap" id="wrap">
        <canvas id="cv" style="display:none"></canvas><canvas id="hm" style="display:none;opacity:.75;pointer-events:none"></canvas><canvas id="pp" style="display:none;pointer-events:none"></canvas>
        <div class="c3" id="c3"></div>
        <div id="labels"></div>
        <div class="chips" id="chips"></div>
        <div class="zoomc"><button onclick="zoomBy(1.2)" title="확대">＋</button><button onclick="zoomBy(1/1.2)" title="축소">－</button><button onclick="resetView()" title="시점 초기화">◎</button><button onclick="goFull()" title="전체 화면">⛶</button></div>
        <div class="legend" id="legend"></div>
        <div class="hint" id="hint">드래그: 회전 · 휠: 확대/축소 · 시설 클릭: 상세</div>
        <div class="mapstat"><span class="badge" id="peopleTxt"></span></div>
      </div>
      <div class="tl">⏰ 시간대 <button id="bTl" onclick="togTl()">▶ 재생</button>
        <input type="range" id="tSl" min="10" max="20" step="1" value="14" oninput="setTime(+this.value)"><span class="tm" id="tTxt">14:00</span><span id="tDesc" style="color:var(--sub);font-weight:600"></span></div>
      <div class="toolrow">
        <div class="tgrp"><span class="gt">시뮬레이션</span><button id="bPlay" onclick="togSim()">⏸ 정지</button>
          <label>사람 <input type="range" min="0.1" max="1.5" step="0.1" value="0.5" oninput="crowdSpeed=+this.value"></label>
          <label>구급차 <input type="range" min="0.1" max="1.5" step="0.1" value="0.4" oninput="ambulanceSpeed=+this.value"></label>
          <button onclick="peopleOn=!peopleOn">👥 ON/OFF</button>
          <button id="bEmg" class="danger" onclick="togEmg()">🚨 응급환자</button>
          <button onclick="evacuatePeople()">🏃 탈출</button><button onclick="evacuating=false;initAgents();sim=true">초기화</button>
          <button onclick="whitePaths=!whitePaths;buildScene3()">하얀 길</button></div>
        <div class="tgrp"><span class="gt">3D 편집</span><button id="editToggle" onclick="toggleEdit()">✋ 편집 OFF</button>
          <button onclick="deleteSelected()">선택 삭제</button><button onclick="undoEdit()">되돌리기</button>
          <button onclick="showRoute('exit')">비상 대피 경로</button><button onclick="showRoute('accessible')">배리어프리 경로</button><button onclick="clearRoutes()">경로 숨김</button>
          <span id="editStatus">저장 전 변경은 점수에 반영되지 않습니다.</span></div>
      </div>
    </div>
<div class="grid2" style="margin-top:0">
  <div class="card"><h4><span class="ic">🔥</span>실시간 군중 밀집도 <span class="sp"></span><span class="badge" id="envTxt">일반 상태</span></h4>
    <div class="wrap" id="wrap2"><canvas id="hm2"></canvas></div>
    <div class="hl"><span style="color:#10b981">🟢 원활</span><span style="color:#eab308">🟡 보통(0.25~)</span><span style="color:#f97316">🟠 혼잡(0.5~)</span><span style="color:#ef4444">🔴 위험(0.9~)</span></div>
    <div style="font-size:10px;color:#94a3b8;margin-top:4px;text-align:center">단위: 명/㎡ · 구역 체류 + 출입구 이동 군중 반영</div></div>
  <div class="card"><h4><span class="ic">📊</span>현재 상태</h4>
    <div class="kpi"><div>현재 최대 밀도<b id="kPeak">-</b></div><div>혼잡 구역 비율<b id="kBott">-</b></div><div>응급 최대 도달<b id="kMed">-</b></div><div>위험 구역<b id="kRisk">-</b></div></div>
    <div style="font-size:12px;font-weight:800;margin:6px 0">📍 배치된 구역 <span id="zCnt" style="color:#64748b"></span></div><div class="zl" id="zlist" style="display:none"></div></div>
</div>
  </main>

  <!-- ================= RIGHT ================= -->
  <aside class="col right">
    <div class="card fcard"><h4><span class="ic">📍</span>선택한 시설 <span class="sp"></span><button class="ghost" id="closeFacilityPopup" aria-label="선택 해제" style="padding:2px 8px;font-size:16px">×</button></h4><div id="facilityInfo"></div></div>
    <div class="card"><h4><span class="ic">📈</span>주요 지표 <span class="sp"></span><span class="badge" id="metricTag">AI 최적</span></h4><div id="metricBars"></div></div>
    <div class="card"><h4><span class="ic">🤖</span>AI 설계 결과 <span class="sp"></span><span class="badge ok" id="aiBadge">분석 완료</span></h4><div class="aitxt" id="aiResult"></div></div>
    <div class="card"><h4><span class="ic">💡</span>개선 제안</h4><ul class="sugg" id="suggList"></ul></div>
  </aside>
</div>

<!-- ================= BOTTOM ================= -->
<div class="bottom">
  <div class="card"><h4><span class="ic">⏳</span>설계 진행 상태</h4>
    <div class="prog"><div class="ring" id="ring"><div><span id="ringTxt">0</span></div></div><div><b id="progTitle" style="font-size:14px">설계 완료</b>
      <div style="font-size:11px;color:var(--sub);margin:2px 0 6px" id="progSub"></div><ul class="steps" id="steps"></ul></div></div></div>
  <div class="card"><h4><span class="ic">⚖</span>설계 비교</h4>
    <div class="cmp"><div class="it"><canvas id="miniB"></canvas><span id="miniBt">설계 전</span></div><div class="ar">→</div><div class="it"><canvas id="miniA"></canvas><span id="miniAt">현재 설계</span></div></div>
    <div class="delta" id="deltaTxt"></div></div>
  <div class="card"><h4><span class="ic">📋</span>설계 결과 요약</h4><div class="tiles" id="tiles"></div></div>
</div>

<div id="facilityPopup" style="display:none"></div>
<script>
const D = __DATA__;
const WW=160, WH=100, GX=40, GY=25;
const WEATHER_DISABLED=true;
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
  drawBase(); if(R3){ size3(); } try{drawMinis();}catch(e){} postH();
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
  agents.forEach((a,i)=>{ a.active=i<n&&!a.evacuated; if(!a.active) return;
    if(a.dwell>0){ a.dwell-=dt; a.x+=(Math.random()-.5)*.06; a.y+=(Math.random()-.5)*.06;
      if(a.dwell<=0){ if(Math.random()<.35){ a.leaving=true; const g=D.gates[Math.floor(Math.random()*D.gates.length)]; a.tx=g.x; a.ty=g.y; } else { a.zone=pickZone(); setTarget(a);} } return; }
    let dx=a.tx-a.x, dy=a.ty-a.y, d=Math.hypot(dx,dy);
    let sp=a.sp*crowdSpeed;
    if(emg){ const ex=a.x-emg.x, ey=a.y-emg.y, ed=Math.hypot(ex,ey); if(ed<9&&ed>0){ a.x+=ex/ed*.5; a.y+=ey/ed*.5; } }
    if(d<1.2){ if(a.leaving){ if(evacuating){a.evacuated=true;a.active=false}else spawn(a);} else { a.dwell=3+Math.random()*9; } }
    else { mv(a,a.x+dx/d*sp,a.y+dy/d*sp); }
  });
  for(let i=0;i<agents.length;i+=2){ const a=agents[i]; if(!a.active) continue; const b=agents[(i*7+3)%agents.length]; if(!b.active) continue;
    const dx=a.x-b.x, dy=a.y-b.y, d=Math.hypot(dx,dy); if(d>0&&d<1.2){ a.x+=dx/d*.1; a.y+=dy/d*.1; } }
  if(emg){ const meds=Z().filter(z=>z.type==='medical'); let best=null,bd=1e9;
    meds.forEach(m=>{const d=Math.hypot(m.x+m.w/2-emg.x,m.y+m.h/2-emg.y); if(d<bd){bd=d;best=m;}});
    emg.target=best;
    if(best&&bd>1.5){ emg.x+=(best.x+best.w/2-emg.x)/bd*.9*ambulanceSpeed; emg.y+=(best.y+best.h/2-emg.y)/bd*.9*ambulanceSpeed;
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
      ctx.fillStyle='rgba(255,255,255,.85)'; ctx.font='bold 10px Pretendard,sans-serif'; ctx.textAlign='center';  }); }
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
  ZV().forEach(z=>{ const g=nearestGate(z); cx.beginPath(); cx.moveTo(g.x*S,g.y*S); cx.lineTo((z.x+z.w/2)*S,(z.y+z.h/2)*S); cx.stroke(); });
  cx.globalAlpha=1;
  ZV().forEach(z=>{ const x=z.x*S,y=z.y*S,w=z.w*S,h=z.h*S;
    cx.fillStyle='rgba(0,0,0,.28)'; cx.fillRect(x+3,y+3,w,h);
    cx.fillStyle=z.color; cx.beginPath(); cx.roundRect(x,y,w,h,7); cx.fill(); cx.strokeStyle='#fff'; cx.lineWidth=2; cx.stroke();
    cx.textAlign='center'; cx.fillStyle='#fff';
    cx.font=Math.max(14,Math.min(26,h*.4))+'px sans-serif'; cx.fillText(z.icon,x+w/2,y+h/2-2);
    cx.font='bold '+Math.max(11,Math.min(15,w/6.5))+'px Pretendard,sans-serif'; cx.shadowColor='rgba(0,0,0,.6)'; cx.shadowBlur=3;
     cx.shadowBlur=0; });
  if(vis.gate) D.gates.forEach(g=>{ cx.fillStyle='#1e293b'; cx.beginPath(); cx.arc(g.x*S,g.y*S,10,0,7); cx.fill(); cx.strokeStyle='#fff'; cx.lineWidth=2; cx.stroke();
    cx.fillStyle='#fff'; cx.font='12px sans-serif'; cx.textAlign='center'; cx.fillText('🚪',g.x*S,g.y*S+4);
    const up=g.y>SHC[1]; cx.font='bold 11px Pretendard'; cx.fillStyle='#fff'; cx.shadowColor='#000'; cx.shadowBlur=3; cx.fillText(g.name,g.x*S,g.y*S+(up?-15:24)); cx.shadowBlur=0; });
}
function nearestGate(z){ let b=D.gates[0],bd=1e9; D.gates.forEach(g=>{const d=Math.hypot(g.x-(z.x+z.w/2),g.y-(z.y+z.h/2)); if(d<bd){bd=d;b=g;}}); return b; }
function drawPeople(){ px.clearRect(0,0,W,H); const sz=selectedZone(); if(sz&&vis[grp(sz)]){px.strokeStyle='#2f6bff';px.lineWidth=3;px.strokeRect(sz.x*S-3,sz.y*S-3,sz.w*S+6,sz.h*S+6);} if(!peopleOn)return;
  agents.forEach(a=>{ if(!a.active) return; px.fillStyle='#fff'; px.strokeStyle='rgba(0,0,0,.4)'; px.lineWidth=.8; px.beginPath(); px.arc(a.x*S,a.y*S,3.2,0,7); px.fill(); px.stroke(); });
  if(emg){ px.strokeStyle='#ef4444'; px.lineWidth=3; px.setLineDash([6,5]);
    if(emg.target){ px.beginPath(); px.moveTo(emg.x*S,emg.y*S); px.lineTo((emg.target.x+emg.target.w/2)*S,(emg.target.y+emg.target.h/2)*S); px.stroke(); }
    px.setLineDash([]); px.fillStyle='#ef4444'; px.beginPath(); px.arc(emg.x*S,emg.y*S,9+Math.sin(performance.now()/120)*2,0,7); px.fill();
    px.fillStyle='#fff'; px.font='bold 12px Pretendard'; px.textAlign='center'; px.fillText('🚑 응급',emg.x*S,emg.y*S-14); }
}
function supportIcon(z){const n=z.name;if(/대피소/.test(n))return '🛟';if(/흡연/.test(n))return '🚬';if(/수유/.test(n))return '🍼';if(/화장실/.test(n))return '🚻';if(/의료|응급|안전관리/.test(n))return '➕';if(/음수/.test(n))return '🚰';if(/소방|화재/.test(n))return '🧯';if(/안내|분실물/.test(n))return 'ℹ';if(/쓰레기|분리수거|분리배출/.test(n))return '♻';if(/미아/.test(n))return '🧒';if(/조명/.test(n))return '💡';if(/충전/.test(n))return '🔋';return null}
function iconSprite(icon){const can=document.createElement('canvas');can.width=128;can.height=128;const t=can.getContext('2d');t.fillStyle='white';t.beginPath();t.arc(64,64,54,0,7);t.fill();t.lineWidth=5;t.strokeStyle='#2563eb';t.stroke();t.font='62px sans-serif';t.textAlign='center';t.textBaseline='middle';t.fillStyle='#17324d';t.fillText(icon,64,65);const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(can),depthTest:false}));sp.scale.set(7,7,1);sp.renderOrder=15;return sp}
function buildCustom(g,z,w,h){let n=z.name,c=z.color;
 if(/조리|푸드|음식|식사/.test(n)){bx(g,w*.9,3,h*.5,'#f8fafc',0,1.5,-h*.2);for(let i=0;i<6;i++)bx(g,w/6,.35,h*.7,i%2?'#fff':'#f59e0b',-w/2+w/12+i*w/6,5,0);bx(g,w*.7,1,h*.25,'#334155',0,1,h*.25);}
 else if(/경기장/.test(n)){bx(g,w,.2,h,'#2d9a68',0,.2,0);const p=[[-w*.44,-h*.43],[w*.44,-h*.43],[w*.44,h*.43],[-w*.44,h*.43],[-w*.44,-h*.43]].map(a=>new THREE.Vector3(a[0],.4,a[1]));g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(p),new THREE.LineBasicMaterial({color:'#fff'})));bx(g,.18,.1,h*.86,'white',0,.4,0);}
 else if(/반려|급수|배변|동물/.test(n)){bx(g,w,.3,h,'#c5e5bc',0,.3,0);[-1,1].forEach(a=>bx(g,w,.8,.3,'#eee2c8',0,.7,a*h/2));cyl(g,1,1,.3,'#60a5fa',0,.7,0);cone(g,2,2,'#be9067',-w*.2,2,-h*.2);}
 else if(/대기실|스태프|통제실|창고|방송|조정실|기록실|심판실/.test(n)){bx(g,w*.95,4,h*.85,'#f8fafc',0,2,0);bx(g,w,.4,h*.9,'#334155',0,4.2,0);bx(g,w*.35,2,.2,'#93c5fd',-w*.2,2,h*.43);bx(g,w*.2,3,.22,'#64748b',w*.25,1.5,h*.43);}
 else if(D.theme.kind!=='indoor'){
 const idx=z.id%5,c=['#ef4444','#3b82f6','#f59e0b','#8b5cf6','#10b981'][idx];
 [-1,1].forEach(a=>[-1,1].forEach(b=>cyl(g,.16,.16,4.6,'#f8fafc',a*w*.43,2.3,b*h*.42)));
 bx(g,w,.5,h,c,0,4.8,0);const roof=new THREE.Mesh(new THREE.ConeGeometry(1,2,4),M(c));roof.rotation.y=Math.PI/4;roof.scale.set(w*.68,1,h*.68);roof.position.y=5.8;g.add(roof);
 for(let k=0;k<6;k++)bx(g,w/6,.6,.5,k%2?'#fff':c,-w/2+w/12+k*w/6,4.4,h/2);
 bx(g,w*.8,1.4,h*.22,'#fff7ed',0,1,h*.28);
 }else{ // Open-front modular exhibition shell, counter and display wall.
 bx(g,w,.25,h,'#dce8f8',0,.3,0);bx(g,w,5,.3,'#fff',0,2.8,-h/2);bx(g,.3,5,h,'#f1f5f9',-w/2,2.8,0);bx(g,w,.65,.5,c,0,5.1,-h/2);bx(g,w*.4,1.8,h*.22,'#fff',w*.2,1.3,h*.2);bx(g,w*.38,2,.15,'#334155',0,3,-h*.47);}
}
function festivalDecor(){
 // Decorations occupy the edge setback, not extra optimizer facilities.
 const b=D.shape.bbox;
 pieces(10).forEach((pc,i)=>{if(D.gates.some(g=>Math.hypot(g.x-pc.x,g.y-pc.y)<10))return;const p=treePos(pc);if(i%2===0)tree(G3,p[0]-80,p[1]-50);else{const x=pc.x-80,z=pc.y-50;cyl(G3,.15,.15,10,'#8b6b42',x,5,z);const m=bx(G3,1.8,6,.15,['#ef4444','#fbbf24','#06b6d4'][i%3],x+.8,7,z);m.rotation.z=.12;}});
 D.gates.forEach((g,i)=>{const sp=labelSprite(i===0?'WELCOME · 주출입구':'EXIT · 비상구','#174d3b');sp.scale.set(18,4.2,1);sp.position.set(g.x-80,11,g.y-50);G3.add(sp)});
}
function buildParking(){
 const b=D.shape.bbox,left=b[0]-80,right=b[2]-80,front=b[3]-50+15;
 const g=new THREE.Group();G3.add(g);g.userData.parking=true;const width=Math.max(100,right-left),depth=48,cx=(left+right)/2;
 bx(g,width,.5,depth,'#435266',cx,-.4,front+depth/2);bx(g,width+2,.5,1,'#cbd5e1',cx,0,front);bx(g,width+2,.5,1,'#cbd5e1',cx,0,front+depth);
 // Central vehicle aisle, two parking banks, marked bays and accessible spaces.
 for(let row=0;row<2;row++)for(let col=0;col<Math.floor((width-12)/6);col++){
  const x=cx-width/2+7+col*6,z=front+8+row*30;
  bx(g,.15,.1,12,'#f8fafc',x-2.8,.05,z);bx(g,5.5,.1,.15,'#f8fafc',x,.05,z-6);
  if(col<2)bx(g,5.3,.08,11,'#2563eb',x,.03,z);
  if(col%3!==1){bx(g,3.4,1.5,7,['#e2e8f0','#f8fafc','#64748b','#93c5fd'][col%4],x,1,z);bx(g,2.8,1.1,3.5,'#17324d',x,2,z);[-1,1].forEach(a=>[-1,1].forEach(k=>cyl(g,.6,.6,.4,'#111827',x+a*1.7,.6,z+k*2.2)));}
 }
 for(let i=0;i<6;i++)bx(g,6,.08,.25,'#e2e8f0',cx-width/2+12+i*15,.1,front+23);
 // Pedestrian zebra link approaches the exterior, not through venue booths.
 const gate=D.gates.reduce((a,b)=>a.y>b.y?a:b),gx=gate.x-80;
 for(let i=0;i<7;i++)bx(g,5,.12,.7,'#fff',gx,.1,front-1-i*1.6);
 bx(g,1,4,1,'#f59e0b',cx+width/2-5,2,front+24);bx(g,8,.3,.6,'#ef4444',cx+width/2-8,3,front+24);
 const tag=labelSprite('P  외부 주차장 · 계획 예시','#1e3a8a');tag.scale.set(32,7.5,1);tag.position.set(cx,6,front+23);g.add(tag);
 const arrow=labelSprite('입구 → / ← 출구','#334155');arrow.scale.set(24,5.6,1);arrow.position.set(cx+width/2-9,5,front+24);g.add(arrow);
}

// 3D selection and editing: ground-plane ray projection, independent of camera orbit.
let peopleOn=true,crowdSpeed=.5,ambulanceSpeed=.4,evacuating=false,whitePaths=false;
function evacuatePeople(){evacuating=true;sim=true;agents.forEach(a=>{a.evacuated=false;a.dwell=0;a.leaving=true;let gate=D.gates.reduce((b,g)=>Math.hypot(g.x-a.x,g.y-a.y)<Math.hypot(b.x-a.x,b.y-a.y)?g:b,D.gates[0]);a.tx=gate.x;a.ty=gate.y});editNote("직선 이동 기반 탈출 시뮬레이션입니다. 실제 대피시간·장애물 회피 검증이 아닙니다.")}
let editing=false, selectedId=null, editDrag=null, editUndo=[], editDirty=false, selectionGroup=null, routeGroup=null;
const ray3=new THREE.Raycaster(), ground3=new THREE.Plane(new THREE.Vector3(0,1,0),0);
function setRay(ev){const r=R3.domElement.getBoundingClientRect();ray3.setFromCamera(new THREE.Vector2((ev.clientX-r.left)/r.width*2-1,-(ev.clientY-r.top)/r.height*2+1),C3)}
function groundPoint(ev){setRay(ev);return ray3.ray.intersectPlane(ground3,new THREE.Vector3())}
function editNote(text){$('editStatus').textContent=text}
function toggleEdit(){editing=!editing;setView(true);if(editing){setMode('after');sim=false;$('bPlay').textContent='▶ 시작';domeOn=false;domeMeshes.forEach(m=>m.visible=false)}$('editToggle').textContent='✋ 편집 '+(editing?'ON':'OFF');$('editToggle').className=editing?'on':'';$('hint').textContent=editing?'부스: 이동 · 노란 손잡이: 크기 · 빈 곳: 회전':'드래그: 회전 · 휠: 확대/축소';editNote(editing?'부스를 클릭하거나 드래그하세요.':'시점 회전 모드');refreshSelection()}
function selectedZone(){return Z().find(z=>z.id===selectedId)}
function disposeGroup(g){if(!g)return;S3.remove(g);g.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material)o.material.dispose()})}
function pickFacility(ev){setRay(ev);for(const hit of ray3.intersectObjects(G3.children,true)){let o=hit.object;while(o&&o!==G3){if(o.userData.zoneId!==undefined)return o.userData.zoneId;o=o.parent}}return null}
function pointerDown3(ev){if(!editing){clickCand={x:ev.clientX,y:ev.clientY,id:pickFacility(ev)};}if(ev.button!==0)return;R3.domElement.setPointerCapture(ev.pointerId);setRay(ev);if(editing&&mode==='after'){
 if(selectionGroup&&ray3.intersectObjects(selectionGroup.children,true).some(h=>h.object.userData.resize)){const p=groundPoint(ev);if(p){editUndo.push(JSON.stringify(D.zones));editDrag={kind:'resize',point:p,zone:{...selectedZone()}};return}}
 const hits=ray3.intersectObjects(G3.children,true);let id=null;for(const hit of hits){let o=hit.object;while(o&&o!==G3){if(o.userData.zoneId!==undefined){id=o.userData.zoneId;break}o=o.parent}if(id!==null)break}
 selectedId=id;updateFacilityInfo(selectedZone());refreshSelection();if(id!==null){const p=groundPoint(ev);if(p){editUndo.push(JSON.stringify(D.zones));editDrag={kind:'move',point:p,zone:{...selectedZone()}};return}}
 }drag=true;lx=ev.clientX;ly=ev.clientY}
function pointerMove3(ev){if(editDrag){const p=groundPoint(ev),z=selectedZone();if(!p||!z)return;const dx=p.x-editDrag.point.x,dy=p.z-editDrag.point.z,old=editDrag.zone;if(editDrag.kind==='move'){z.x=Math.max(0,Math.min(160-z.w,old.x+dx));z.y=Math.max(0,Math.min(100-z.h,old.y+dy))}else{z.w=Math.max(1,Math.min(150,160-z.x,old.w+dx));z.h=Math.max(1,Math.min(95,100-z.y,old.h+dy))}editDirty=true;updateFacilityInfo(selectedZone());buildScene3();drawBase();return}if(drag){yaw-=(ev.clientX-lx)*.008;pitch=Math.min(1.35,Math.max(.3,pitch+(ev.clientY-ly)*.006));lx=ev.clientX;ly=ev.clientY}}
function deleteSelected(){if(!editing||mode!=='after'||!selectedZone()){editNote('편집 모드에서 삭제할 시설을 선택하세요.');return}const z=selectedZone();if(z.type==='medical'&&D.zones.filter(q=>q.type==='medical').length===1){editNote('마지막 응급의료센터는 삭제할 수 없습니다.');return}if(D.zones.length<=2){editNote('시설은 최소 2개 필요합니다.');return}editUndo.push(JSON.stringify(D.zones));D.zones=D.zones.filter(z=>z.id!==selectedId);selectedId=null;editDirty=true;emg=null;initAgents();buildScene3();drawBase();editNote('삭제했습니다. 저장 버튼을 눌러 반영하세요.')}
function undoEdit(){if(!editUndo.length)return;D.zones=JSON.parse(editUndo.pop());selectedId=null;editDirty=true;emg=null;initAgents();buildScene3();drawBase();editNote('이전 조작으로 되돌렸습니다. 저장 후 반영됩니다.')}
function save3Edit(){if(mode!=='after'){editNote('설계 후 배치에서만 저장할 수 있습니다.');return}parent.postMessage({type:'event:save',zones:D.zones},'*');editNote('저장 요청 중입니다. 충돌·외곽 침범 시 앱에 오류가 표시됩니다.')}
function isProp(n){return /그늘막|조명|책상|테이블|의자|파라솔|천막|알림막|깃발|연단|가림막|전광판|키오스크|쓰레기|분리수거/.test(n)}
function buildProp(g,z,w,h){const n=z.name,c=z.color;
 if(/조명/.test(n)){cyl(g,.18,.18,7,'#64748b',0,3.5,0);bx(g,2,.5,1,'#fff4ba',0,7,0,{emissive:new THREE.Color('#ffe39c'),emissiveIntensity:.9});const light=new THREE.PointLight(0xffedbe,.65,20);light.position.set(0,6,0);g.add(light)}
 else if(/책상|테이블/.test(n)){bx(g,w*.9,.45,h*.85,c,0,2.7,0);[-1,1].forEach(a=>[-1,1].forEach(b=>bx(g,.35,2.5,.35,'#64748b',a*w*.35,1.25,b*h*.3)));}
 else if(/의자/.test(n)){bx(g,w*.7,.4,h*.65,c,0,1.5,0);bx(g,w*.7,2,.35,c,0,2.3,-h*.3);[-1,1].forEach(a=>[-1,1].forEach(b=>bx(g,.3,1.5,.3,'#64748b',a*w*.28,.75,b*h*.25)));}
 else if(/파라솔/.test(n)){cyl(g,.16,.16,5,'#64748b',0,2.5,0);const roof=new THREE.Mesh(new THREE.ConeGeometry(1,1.5,16),M(c));roof.scale.set(w*.5,1,h*.5);roof.position.y=5;g.add(roof)}
 else if(/쓰레기|분리수거|분리배출/.test(n)){cyl(g,w*.35,w*.3,3,c,0,1.5,0);cyl(g,w*.4,w*.4,.4,'#334155',0,3.1,0)}
 else if(/연단/.test(n)){bx(g,w*.9,2,h*.9,c,0,1,0)}
 else if(/천막|그늘막/.test(n)){[-1,1].forEach(a=>[-1,1].forEach(b=>cyl(g,.16,.16,5,'#64748b',a*w*.4,2.5,b*h*.4)));bx(g,w,1,h,c,0,5,0)}
 else{bx(g,.4,5,.4,'#475569',0,2.5,0);bx(g,w*.85,3,Math.max(.3,h*.15),/전광판|키오스크/.test(n)?'#0f172a':c,0,4,0)}
}
// Grid BFS: indicative routes only, not a certified evacuation/accessibility design.
function clearRoutes(){if(routeGroup){disposeGroup(routeGroup);routeGroup=null}}
function showRoute(kind){if(!R3||mode!=='after'){editNote('설계 후 3D 화면에서 경로를 표시하세요.');return}clearRoutes();routeGroup=new THREE.Group();S3.add(routeGroup);const step=2,nx=80,ny=50,key=(x,y)=>y*nx+x;
 const free=(x,y)=>x>=0&&x<nx&&y>=0&&y<ny&&insideShape(x*step+1,y*step+1)&&!D.zones.some(z=>x*step+1>=z.x-1&&x*step+1<=z.x+z.w+1&&y*step+1>=z.y-1&&y*step+1<=z.y+z.h+1);
 const near=(x,y)=>{let best=null,d=Infinity;for(let yy=0;yy<ny;yy++)for(let xx=0;xx<nx;xx++)if(free(xx,yy)){let dd=(xx*step+1-x)**2+(yy*step+1-y)**2;if(dd<d){d=dd;best=[xx,yy]}}return best};
 const route=(start,goal)=>{if(!start||!goal)return null;const q=[start],prev=new Map([[key(...start),null]]);let found=null;for(let i=0;i<q.length;i++){let [x,y]=q[i];if(x===goal[0]&&y===goal[1]){found=[x,y];break}for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){let a=x+dx,b=y+dy,k=key(a,b);if(free(a,b)&&!prev.has(k)){prev.set(k,[x,y]);q.push([a,b])}}}if(!found)return null;let points=[];while(found){points.push(new THREE.Vector3(found[0]*step+1-80,1.1,found[1]*step+1-50));found=prev.get(key(...found))}return points};
 let shown=0,failed=0;const targets=kind==='accessible'?D.zones.filter(z=>/사회적|화장실|의료|응급|무대|공연|안내/.test(z.name)):D.zones;
 for(const z of targets){let start=near(z.x+z.w/2,z.y+z.h+3),best=null;const gates=kind==='accessible'?D.gates.slice(0,1):D.gates;for(const g of gates){const pts=route(start,near(g.x,g.y));if(pts&&(!best||pts.length<best.length))best=pts}if(best){routeGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(best),new THREE.LineBasicMaterial({color:kind==='accessible'?0x2563eb:0x16a34a,depthTest:false})));shown++}else failed++}
 editNote((kind==='accessible'?'사회적 약자 이동경로 후보':'비상 대피로 후보')+' '+shown+'개 · 탐색 실패 '+failed+'개. 격자 기반 참고 경로이며 통로 폭·경사·단차·출입문 유효폭은 검증하지 않았습니다.');
}

/* ---------- 3D 아이소메트릭 ---------- */
let R3=null,S3,C3,G3,bodyM,headM,rainPts,emgGrp,emgLine,heatPlane,heatTex;
let yaw=.35,pitch=.88,zoom3=1.2*Math.min(1.45,WW/Math.max(D.shape.bbox[2]-D.shape.bbox[0],(D.shape.bbox[3]-D.shape.bbox[1])*1.3))*(D.shape.dome?.82:1),drag=false,lx=0,ly=0;
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
  const g=new THREE.Group(); const cxz=z.x+z.w/2-WW/2, czz=z.y+z.h/2-WH/2; g.position.set(cxz,0,czz); G3.add(g); g.userData.zoneId=z.id;
  if(supportIcon(z)){const sp=iconSprite(supportIcon(z));sp.position.set(0,4,0);g.add(sp);return;}
  const w=z.w,h=z.h; const pale=new THREE.Color(z.color).lerp(new THREE.Color('#ffffff'),.65).getStyle();
  if(z.shape && z.shape!=='rect'){
    let pts=[]; if(z.shape==='ellipse'){for(let i=0;i<64;i++){let t=i*Math.PI*2/64;pts.push([Math.cos(t)*w/2,Math.sin(t)*h/2]);}}
    else {pts=[[-w/2,-h/2],[w*.05,-h/2],[w*.05,-h*.05],[w/2,-h*.05],[w/2,h/2],[-w/2,h/2]];}
    const sh=new THREE.Shape();pts.forEach((p,i)=>i?sh.lineTo(p[0],p[1]):sh.moveTo(p[0],p[1]));sh.closePath();
    const mesh=new THREE.Mesh(new THREE.ExtrudeGeometry(sh,{depth:z.type==='stage'?3:.8,bevelEnabled:false}),M(z.color));mesh.rotation.x=-Math.PI/2;g.add(mesh);
  } else bx(g,w,.5,h,pale,0,.25,0);
  let top=8;
  switch(z.shape && z.shape!=='rect' ? '__shaped' : (z.type==='custom'?(isProp(z.name)?'__prop':'__custom'):z.type)){
    case '__custom': {buildCustom(g,z,w,h);top=6;break;}
    case '__prop': {buildProp(g,z,w,h);top=8;break;}
    case '__shaped': {top=6;break;}
    case 'stage':{ const s=(czz<0)?1:-1;
      bx(g,w,1,h*.58,'#ffffff',0,z.ht+5,-s*h*.2);
      [-1,1].forEach(a=>[-1,1].forEach(b=>bx(g,.65,z.ht+4,.65,'#64748b',a*w*.47,(z.ht+4)/2,b*h*.24-s*h*.2)));
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
  const sp=labelSprite('',z.color); const ww=Math.min(30,Math.max(14,z.name.length*2.1+8)); sp.scale.set(ww,ww*150/640,1); sp.position.set(0,top+3,0); /* facility labels are intentionally hidden */
}
function shapeGeo(scale){ const sh=new THREE.Shape(); D.shape.outline.forEach((p,i)=>{ const x=(p[0]-WW/2)*scale, y=-(p[1]-WH/2)*scale; if(i) sh.lineTo(x,y); else sh.moveTo(x,y); }); sh.closePath(); return sh; }
function slab(depth,color,y,scale){ const m=new THREE.Mesh(new THREE.ExtrudeGeometry(shapeGeo(scale),{depth:depth,bevelEnabled:false}),M(color)); m.rotation.x=-Math.PI/2; m.position.y=y; G3.add(m); return m; }
let domeMeshes=[], domeOn=true;
function buildScene3(){
  clearRoutes();
  if(G3){ S3.remove(G3); G3.traverse(o=>{if(o.geometry)o.geometry.dispose(); if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach(m=>{if(m.map)m.map.dispose();m.dispose()})}}); } G3=new THREE.Group(); S3.add(G3);
  const T=D.theme, dome=D.shape.dome; const ground=T.kind==='indoor'?T.ground:'#73b937';
  slab(4,'#e5e7eb',-4.7,1.04); slab(.7,ground,-.7,1);
  if(T.kind==='outdoor'&&!dome){ pieces(9).forEach((pc,i)=>{ if(i%2) return; const t=treePos(pc); tree(G3,t[0]-WW/2,t[1]-WH/2); }); }
  const hh=dome?2.4:5;
  pieces(5).forEach(pc=>{ if(D.gates.some(g=>Math.hypot(g.x-pc.x,g.y-pc.y)<7.5)) return; const m=bx(G3,pc.len+.3,hh,1.4,'#f8fafc',pc.x-WW/2,hh/2,pc.y-WH/2); m.rotation.y=-pc.ang; });
  const pcol=T.path;
  if(whitePaths) ZV().forEach(z=>{ const g=nearestGate(z); const x1=g.x-WW/2,z1=g.y-WH/2,x2=z.x+z.w/2-WW/2,z2=z.y+z.h/2-WH/2; const dx=x2-x1,dz=z2-z1,L=Math.hypot(dx,dz);
    const m=bx(G3,L,.3,3.2,pcol,(x1+x2)/2,.15,(z1+z2)/2); m.rotation.y=-Math.atan2(dz,dx); });
  if(vis.gate) D.gates.forEach(g=>{ const gg=new THREE.Group(); gg.position.set(g.x-WW/2,0,g.y-WH/2); gg.rotation.y=-g.ang; G3.add(gg);
    bx(gg,1.6,8,1.6,'#1e293b',-6,4,0); bx(gg,1.6,8,1.6,'#1e293b',6,4,0); bx(gg,14,1.4,1.8,'#1e293b',0,8,0);
    const sp=labelSprite('🚪 '+g.name,'#1e293b'); sp.scale.set(15,15*150/640,1); sp.position.set(g.x-WW/2,12,g.y-WH/2); G3.add(sp); });
  ZV().forEach(buildZone3);if(vis.parking)buildParking();festivalDecor();
  domeMeshes=[];
  if(dome){ const bw=SHB[2]-SHB[0], bh=SHB[3]-SHB[1];
    const dm=new THREE.Mesh(new THREE.SphereGeometry(1,48,20,0,Math.PI*2,0,Math.PI/2),new THREE.MeshLambertMaterial({color:0xbfdbfe,transparent:true,opacity:.14,side:THREE.DoubleSide,depthWrite:false}));
    dm.scale.set(bw/2,bw/2*.6,bh/2); dm.renderOrder=1; G3.add(dm);
    const wf=new THREE.Mesh(new THREE.SphereGeometry(1,16,6,0,Math.PI*2,0,Math.PI/2),new THREE.MeshBasicMaterial({color:0x475569,wireframe:true,transparent:true,opacity:.16,depthWrite:false}));
    wf.scale.copy(dm.scale); wf.renderOrder=1; G3.add(wf); domeMeshes=[dm,wf]; domeMeshes.forEach(m=>m.visible=domeOn); }
  refreshSelection(); refreshLists();
  $('zlist').replaceChildren(...Z().map(z=>{const el=document.createElement('span');el.style.setProperty('--c',z.color);el.textContent=z.icon+' '+z.name;return el})); $('zCnt').textContent='('+Z().length+'개)';
}
function initR3(){
  const el=$('c3'); try{ R3=new THREE.WebGLRenderer({antialias:true}); }catch(e){ R3=null; is3d=false; $('hint').textContent='이 브라우저는 3D를 지원하지 않아 2D로 표시합니다'; return; }
  el.appendChild(R3.domElement);
  S3=new THREE.Scene(); S3.background=new THREE.Color('#dceecf'); S3.add(new THREE.AmbientLight(0xffffff,.82)); const dl=new THREE.DirectionalLight(0xffffff,.65); dl.position.set(-60,120,50); S3.add(dl);
  C3=new THREE.OrthographicCamera(-1,1,1,-1,-800,1200);
  const N=NAG; bodyM=new THREE.InstancedMesh(new THREE.CylinderGeometry(.55,.65,2.4,8),M('#f97316'),N); headM=new THREE.InstancedMesh(new THREE.SphereGeometry(.7,10,8),M('#fde68a'),N);
  bodyM.frustumCulled=false; headM.frustumCulled=false; S3.add(bodyM); S3.add(headM);
  const rp=new Float32Array(500*3); for(let i=0;i<500;i++){rp[i*3]=(Math.random()-.5)*WW;rp[i*3+1]=Math.random()*60;rp[i*3+2]=(Math.random()-.5)*WH;}
  rainPts=new THREE.Points(new THREE.BufferGeometry().setAttribute('position',new THREE.BufferAttribute(rp,3)),new THREE.PointsMaterial({color:0x60a5fa,size:1.2})); rainPts.visible=false; rainPts.frustumCulled=false; S3.add(rainPts);
  emgGrp=new THREE.Mesh(new THREE.SphereGeometry(1.8,16,12),new THREE.MeshBasicMaterial({color:0xef4444})); emgGrp.visible=false; S3.add(emgGrp);
  emgLine=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),new THREE.LineBasicMaterial({color:0xef4444})); emgLine.visible=false; emgLine.frustumCulled=false; S3.add(emgLine);
  heatTex=new THREE.CanvasTexture(hm); heatPlane=new THREE.Mesh(new THREE.PlaneGeometry(WW,WH),new THREE.MeshBasicMaterial({map:heatTex,transparent:true,opacity:.8,depthWrite:false})); heatPlane.rotation.x=-Math.PI/2; heatPlane.position.y=.5; heatPlane.visible=false; S3.add(heatPlane);
  const e=R3.domElement;
  e.style.touchAction='none';
  e.onpointerdown=pointerDown3;
  e.onpointermove=pointerMove3;
  e.onpointerup=e.onpointercancel=ev=>{ if(clickCand&&ev.type==='pointerup'&&Math.hypot(ev.clientX-clickCand.x,ev.clientY-clickCand.y)<5){selectZone(clickCand.id);} clickCand=null; drag=false;editDrag=null; };
  e.addEventListener('wheel',ev=>{ev.preventDefault();zoom3=Math.min(3.2,Math.max(.6,zoom3*(ev.deltaY<0?1.1:.9)));},{passive:false});
  size3(); buildScene3();
}
function size3(){ if(!R3) return; const el=$('c3'); const w=el.clientWidth,h=el.clientHeight; R3.setPixelRatio(Math.min(2,window.devicePixelRatio||1)); R3.setSize(w,h); const f=102,asp=w/h; C3.left=-f*asp; C3.right=f*asp; C3.top=f; C3.bottom=-f; C3.updateProjectionMatrix(); }
function render3(){
  if(!R3) return; const Rr=400;
  C3.position.set(Math.sin(yaw)*Math.cos(pitch)*Rr,Math.sin(pitch)*Rr,Math.cos(yaw)*Math.cos(pitch)*Rr); C3.position.z+=22;C3.lookAt(0,0,22); C3.zoom=zoom3; C3.updateProjectionMatrix();
  for(let i=0;i<agents.length;i++){ const a=agents[i]; const s=a.active&&peopleOn?1:0.0001; DUM.rotation.set(0,0,0); DUM.scale.set(s,s,s);
    DUM.position.set(a.x-WW/2,1.7,a.y-WH/2); DUM.updateMatrix(); bodyM.setMatrixAt(i,DUM.matrix); DUM.position.y=3.6; DUM.updateMatrix(); headM.setMatrixAt(i,DUM.matrix); }
  bodyM.instanceMatrix.needsUpdate=true; headM.instanceMatrix.needsUpdate=true; bodyM.material.color.set('#f97316');
  rainPts.visible=false; if(rain){ const p=rainPts.geometry.attributes.position; for(let i=0;i<500;i++){ let y=p.getY(i)-1.4; if(y<0) y=60; p.setY(i,y);} p.needsUpdate=true; }
  if(emg){ emgGrp.visible=true; emgGrp.position.set(emg.x-WW/2,3,emg.y-WH/2); const sc=1+Math.sin(performance.now()/120)*.25; emgGrp.scale.set(sc,sc,sc);
    if(emg.target){ emgLine.visible=true; const tp=emgLine.geometry.attributes.position; tp.setXYZ(0,emg.x-WW/2,3,emg.y-WH/2); tp.setXYZ(1,emg.target.x+emg.target.w/2-WW/2,3,emg.target.y+emg.target.h/2-WH/2); tp.needsUpdate=true; } }
  else { emgGrp.visible=false; emgLine.visible=false; }
  heatPlane.visible=heat3; if(heat3) heatTex.needsUpdate=true;
  positionFacilityPopup();
  R3.render(S3,C3);
}
/* ---------- 루프 & 컨트롤 ---------- */
let last=performance.now(), kt=0;
function loop(now){ const dt=(now-last)/1000; last=now;
  if(sim){ step(dt); }
  updateHeat(); const r=drawHeat(hx,W,H,false); drawHeat(h2,W2,H2,true);
  if(is3d) render3(); else {drawPeople();positionFacilityPopup();}
  const n=Math.round(D.params.visitors*.5*factor(tHour)); $('peopleTxt').textContent='시뮬레이션 군중 ≈ '+n.toLocaleString()+'명';
  kt+=dt; if(kt>.4){ kt=0; $('kPeak').textContent=r[0].toFixed(2)+' 명/㎡'; $('kBott').textContent=(r[2]?Math.round(100*r[1]/r[2]):0)+'%';
    const de=mode==='after'?D.detail:D.before_detail; $('kMed').textContent=editDirty?'저장 후 재계산':Math.round(de.t_max)+'초'; $('kRisk').textContent=editDirty?'저장 후 재계산':de.risk_zones+'개소'; }
  liveTick(dt);
  requestAnimationFrame(loop);
}
function setView(v3){ if(v3&&!R3) return; is3d=v3; $('c3').style.display=v3?'block':'none'; [cv,hm,pp].forEach(c=>c.style.display=v3?'none':'block');
  hm.style.display=(!v3&&heat3)?'block':'none'; $('b3d').className=v3?'on':''; $('b2d').className=v3?'':'on'; $('hint').style.display=v3?'block':'none'; $('bDome').style.display=(v3&&D.shape.dome)?'inline-block':'none';
  if(v3) size3(); }
function togDome(){ domeOn=!domeOn; domeMeshes.forEach(m=>m.visible=domeOn); $('bDome').className=domeOn?'on':''; $('bDome').textContent=domeOn?'🏛 지붕':'🏛 지붕 숨김'; }
function togHeat3(){ heat3=!heat3; $('bHeat3').className=heat3?'on':''; if(!is3d) hm.style.display=heat3?'block':'none'; }
function setMode(m){ mode=m;selectedId=null;updateFacilityInfo(null); $('bMode').className=m==='after'?'on':''; $('bModeB').className=m==='before'?'on':'';
  $('verTxt').textContent=m==='after'?'· AI 최적 배치(종합 '+D.total.toFixed(1)+'점)':'· 설계 전(종합 '+D.before_total.toFixed(1)+'점)';
  heat.fill(0); initAgents(); emg=null; $('bEmg').className='danger'; $('bEmg').textContent='🚨 응급환자'; drawBase(); if(R3) buildScene3(); else refreshLists(); renderBottom(); renderMetrics(); $('status').textContent='실시간 군중 시뮬레이션'; }
function togSim(){ sim=!sim; $('bPlay').textContent=sim?'⏸ 정지':'▶ 시작'; }
function togEmg(){ const b=$('bEmg');
  if(emg){ emg=null; b.className='danger'; b.textContent='🚨 응급환자'; $('status').textContent='실시간 군중 시뮬레이션'; return; }
  const Zs=Z().filter(z=>z.type!=='medical'); const z=Zs[Math.floor(Math.random()*Zs.length)];
  emg={x:z.x+z.w/2,y:z.y+z.h+2,trail:[],t0:performance.now(),target:null}; b.className='danger on'; b.textContent='🚨 응급 해제'; sim=true; $('bPlay').textContent='⏸ 정지'; }
function setTime(h){ tHour=h;if(typeof S3!=='undefined'&&S3){const night=h>=18||h<6;S3.background=new THREE.Color(night?'#15223c':'#dceecf');}  $('tSl').value=h; $('tTxt').textContent=h+':00'; $('tDesc').textContent=descT(h); }
function togTl(){ const b=$('bTl'); if(tlTimer){clearInterval(tlTimer);tlTimer=null;b.textContent='▶ 재생';} else { b.textContent='⏸ 일시정지'; tlTimer=setInterval(()=>{ let n=tHour+1; if(n>20)n=10; setTime(n); },2500); } }

/* ================= 대시보드(사진 참고 UI) ================= */
const P=D.params, AI=D.ai||{reasons:[],suggestions:[],steps:[]};
const GRP=[['stage','메인 무대·공연','🎭','#8b5cf6'],['food','푸드존','🍔','#f59e0b'],['booth','체험·사용자 부스','🧪','#3b82f6'],
 ['rest','휴게공간','🛋️','#10b981'],['medical','응급의료','🏥','#ef4444'],['info','안내센터','ℹ️','#0ea5e9'],
 ['restroom','화장실','🚻','#06b6d4'],['support','지원·운영 시설','🧰','#64748b'],['gate','출입구','🚪','#1e293b'],['parking','외부 주차장','🅿️','#475569']];
const GINFO={}; GRP.forEach(g=>GINFO[g[0]]={label:g[1],icon:g[2],color:g[3]});
const vis={}; GRP.forEach(g=>vis[g[0]]=true);
const CHIPS=[['all','전체 보기',null],['stage','공연',['stage']],['food','음식',['food']],['booth','체험·부스',['booth']],
 ['amen','편의시설',['rest','restroom','info','support']],['safe','의료·안전',['medical']],['traffic','출입구·주차',['gate','parking']]];
let chip='all', showLbl=true, lblEls=[], clickCand=null, goal='safety', liveT=0;
const zoom0=zoom3, yaw0=yaw, pitch0=pitch;
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function grp(z){
  if(['stage','food','rest','medical','info','restroom'].includes(z.type)) return z.type;
  if(z.type==='custom'&&(supportIcon(z)||isProp(z.name)||/대기실|스태프|통제|창고|방송|조정|기록|심판|여분|그늘|야외 운영|유지/.test(z.name))) return 'support';
  return 'booth';
}
function ZV(){ return Z().filter(z=>vis[grp(z)]); }
function shade(hex,f){ const n=parseInt(String(hex).replace('#','').padEnd(6,'0').slice(0,6),16); let r=n>>16,g=(n>>8)&255,b=n&255; const m=f<0?0:255,p=Math.abs(f); r=Math.round((m-r)*p+r); g=Math.round((m-g)*p+g); b=Math.round((m-b)*p+b); return 'rgb('+r+','+g+','+b+')'; }
function budgetEff(){ const c=D.cost||{total:0,budget:1}; const r=c.total/Math.max(1,c.budget); return Math.max(0,Math.min(100,100*(1.3-r)/0.4)); }
function curScores(){ return mode==='after'?D.scores:D.before_scores; }

/* ----- 상단바 / 좌측 ----- */
function renderTop(){ $('tbProject').textContent=P.venue+' · '+D.shape.name; $('tbEvent').textContent=P.name; $('tbAvatar').textContent=(P.name||'E').trim().charAt(0).toUpperCase(); }
function renderInfo(){
  const rows=[['🎪','행사명',P.name],['🎫','행사 유형',(P.event_types&&P.event_types.length?P.event_types.join(' · '):P.purpose)+' / '+P.purpose],
   ['📍','행사 장소',P.venue+' — '+P.location],['📐','공간 크기',Number(P.area_m2).toLocaleString()+'㎡ · '+D.shape.name+' (1단위≈'+mpu.toFixed(2)+'m)'],
   ['👥','예상 방문객',Number(P.visitors).toLocaleString()+'명 · '+P.age],['🕒','운영 시간',P.hours],['💰','예산',Number(P.budget).toLocaleString()+'만원'],['✨','분위기 / 출입구',P.mood+' · 출입구 '+D.gates.length+'개']];
  $('infoRows').innerHTML=rows.map(r=>'<div class="info-row"><i>'+r[0]+'</i><small>'+r[1]+'</small><div>'+esc(r[2])+'</div></div>').join('');
}
const GOALS=[['safety','안전 중심','🛡','사고·응급 대응 우선',['safety','cong']],['exp','참여 경험 중심','❤','접근성·동선 우선',['access','flow']],
 ['ops','운영 효율 중심','⚙','공간·동선 효율 우선',['flow','space']],['budget','예산 효율 중심','🪙','비용 대비 구성 우선',['budget']]];
function renderGoals(){
  $('goalList').replaceChildren(...GOALS.map(g=>{ const b=document.createElement('button'); b.className='goal'+(goal===g[0]?' on':''); b.innerHTML='<span class="gi">'+g[2]+'</span><span><b>'+g[1]+'</b><small>'+g[3]+'</small></span>'; b.onclick=()=>{goal=g[0];renderGoals();renderMetrics();}; return b; }));
}
function renderChips(){
  $('chips').replaceChildren(...CHIPS.map(c=>{ const d=document.createElement('div'); d.className='chip'+(chip===c[0]?' on':''); d.innerHTML='<span class="cb">'+(chip===c[0]?'✓':'')+'</span>'+c[1]; d.onclick=()=>applyChip(c[0]); return d; }));
}
function renderGroups(){
  const cnt={}; GRP.forEach(g=>cnt[g[0]]=0); Z().forEach(z=>cnt[grp(z)]++); cnt.gate=D.gates.length; cnt.parking=1;
  $('facTotal').textContent=Z().length+'개';
  $('groupList').replaceChildren(...GRP.filter(g=>cnt[g[0]]>0).map(g=>{ const r=document.createElement('div'); r.className='tg';
    r.innerHTML='<span class="gi" style="background:'+g[3]+'">'+g[2]+'</span><span class="nm">'+g[1]+'</span><span class="ct">'+cnt[g[0]]+'</span><span class="sw'+(vis[g[0]]?' on':'')+'"></span>';
    r.querySelector('.sw').onclick=()=>{vis[g[0]]=!vis[g[0]];chip='custom';applyVis();}; return r; }));
}
function applyChip(k){
  chip=k; GRP.forEach(g=>vis[g[0]]=false);
  if(k==='all') GRP.forEach(g=>vis[g[0]]=true); else CHIPS.find(c=>c[0]===k)[2].forEach(x=>vis[x]=true);
  applyVis();
}
function applyVis(){
  const s=selectedZone(); if(s&&!vis[grp(s)]){selectedId=null;updateFacilityInfo(null);}
  if(R3) buildScene3(); else refreshLists(); drawBase(); renderChips();
}
function populateExplorer(){
  const list=$('facilityExplorer'); if(!list) return; const q=$('facilitySearch').value.toLowerCase(); list.replaceChildren();
  Z().filter(z=>(z.name+' '+z.type).toLowerCase().includes(q)).forEach(z=>{ const b=document.createElement('button'); b.className='explorerItem'+(z.id===selectedId?' sel':'');
    b.textContent=(supportIcon(z)||z.icon||'▣')+'  '+z.name; b.onclick=()=>selectZone(z.id); list.appendChild(b); });
}

/* ----- 라벨 핀 ----- */
const LPRI={stage:0,medical:1,food:2,info:3,restroom:4,rest:5,booth:6,custom:7};
function populateLabels(){
  const box=$('labels'); box.replaceChildren(); lblEls=[];
  ZV().slice().sort((a,b)=>(LPRI[a.type]-LPRI[b.type])||(b.w*b.h-a.w*a.h)).forEach(z=>{
    const e=document.createElement('div'); e.className='lbl'+(z.id===selectedId?' sel':''); e.innerHTML='<span class="pill"></span><i class="stem"></i><i class="dot"></i>';
    e.firstChild.textContent=z.name; e.onclick=ev=>{ev.stopPropagation();selectZone(z.id);}; box.appendChild(e); lblEls.push({z,e}); });
}
function labelAnchor(z){
  if(is3d&&C3){ const v=new THREE.Vector3(z.x+z.w/2-80,Math.max(6,(z.ht||6)+3),z.y+z.h/2-50).project(C3); if(v.z<-1||v.z>1) return null; return [(v.x+1)*wrap.clientWidth/2,(1-v.y)*wrap.clientHeight/2]; }
  return [(z.x+z.w/2)*W/WW,(z.y+z.h/2)*H/WH];
}
function updateLabels(){
  const box=$('labels'); if(!showLbl||editDrag){box.style.display='none';return;} box.style.display='block';
  const placed=[], order=lblEls.slice().sort((a,b)=>(b.z.id===selectedId)-(a.z.id===selectedId));
  const ww=wrap.clientWidth, hh=wrap.clientHeight;
  order.forEach(o=>{ const e=o.e, a=labelAnchor(o.z), sel=o.z.id===selectedId;
    if(!a||a[0]<-20||a[1]<-20||a[0]>ww+20||a[1]>hh+20){e.style.visibility='hidden';return;}
    const w=e._w||(e._w=e.offsetWidth||70), h=e._h||(e._h=e.offsetHeight||44);
    const small=o.z.w*o.z.h<26&&!sel&&zoom3<1.7; const r=[a[0]-w/2-2,a[1]-h-2,a[0]+w/2+2,a[1]+2];
    const hit=placed.some(p=>!(r[2]<p[0]||r[0]>p[2]||r[3]<p[1]||r[1]>p[3]));
    if(small||(hit&&!sel)){e.style.visibility='hidden';return;}
    placed.push(r); e.style.visibility='visible'; e.style.transform='translate('+Math.round(a[0]-w/2)+'px,'+Math.round(a[1]-h)+'px)'; });
}
function positionFacilityPopup(){ updateLabels(); }
function togLabels(){ showLbl=!showLbl; $('bLbl').className=showLbl?'on':''; updateLabels(); }

/* ----- 시설 선택 / 상세 패널 ----- */
function selectZone(id){ selectedId=(id===undefined||id===null)?null:id; updateFacilityInfo(selectedZone()); refreshSelection(); }
function regionTxt(z){ const cx=z.x+z.w/2, cy=z.y+z.h/2, bx=(cx-SHB[0])/(SHB[2]-SHB[0]), by=(cy-SHB[1])/(SHB[3]-SHB[1]);
  const h=bx<.34?'서':bx>.66?'동':'', v=by<.34?'북':by>.66?'남':''; return (v+h)?(v+h+'쪽 구역'):'행사장 중앙부'; }
function capText(z){ let tot=0; Z().forEach(q=>{ if(q.type!=='medical') tot+=q.attract||0; });
  if(z.type!=='medical'&&(z.attract||0)>0&&tot>0) return '피크 체류 약 '+Math.round(P.visitors*.5*.75*z.attract/tot).toLocaleString()+'명';
  return '상시 운영 시설(수용 기준 없음)'; }
function zoneHeat(z){ const cw=WW/GX,ch=WH/GY; let m=0; for(let y=Math.max(0,Math.floor((z.y-2)/ch));y<Math.min(GY,Math.ceil((z.y+z.h+2)/ch));y++)for(let x=Math.max(0,Math.floor((z.x-2)/cw));x<Math.min(GX,Math.ceil((z.x+z.w+2)/cw));x++)m=Math.max(m,heat[y*GX+x]); return m; }
function drawThumb(c,z){
  const t=c.getContext('2d'), w=c.width, h=c.height, g=t.createLinearGradient(0,0,0,h); g.addColorStop(0,'#e3effb'); g.addColorStop(1,'#f8fcff'); t.fillStyle=g; t.fillRect(0,0,w,h);
  const cx=w/2, cy=h*.66, a=w*.30, b=a*.5, th=(z.type==='stage'?h*.42:z.type==='medical'||z.type==='info'?h*.30:h*.24);
  t.fillStyle='rgba(15,35,58,.12)'; t.beginPath(); t.ellipse(cx,cy+b*.35,a*1.15,b*1.1,0,0,7); t.fill();
  const top=[[cx,cy-th-b],[cx+a,cy-th],[cx,cy-th+b],[cx-a,cy-th]], L=[[cx-a,cy-th],[cx,cy-th+b],[cx,cy+b],[cx-a,cy]], R=[[cx+a,cy-th],[cx,cy-th+b],[cx,cy+b],[cx+a,cy]];
  [[L,shade(z.color,-.18)],[R,shade(z.color,-.34)],[top,shade(z.color,.28)]].forEach(p=>{ t.fillStyle=p[1]; t.beginPath(); p[0].forEach((q,i)=>i?t.lineTo(q[0],q[1]):t.moveTo(q[0],q[1])); t.closePath(); t.fill(); t.strokeStyle='rgba(255,255,255,.7)'; t.lineWidth=1.5; t.stroke(); });
  t.font=Math.round(h*.3)+'px sans-serif'; t.textAlign='center'; t.textBaseline='middle'; t.fillStyle='#fff'; t.fillText(supportIcon(z)||z.icon||'▣',cx,cy-th);
}
function updateFacilityInfo(z){
  const panel=$('facilityInfo'); lblEls.forEach(o=>o.e.classList.toggle('sel',!!z&&o.z.id===z.id)); populateExplorer();
  if(!z){ panel.innerHTML='<div class="empty">지도의 시설이나 라벨을 클릭하면<br>위치·크기·수용 인원·배치 근거가 표시됩니다.</div>'; return; }
  const gi=GINFO[grp(z)], wm=z.w*mpu/1.35, hm_=z.h*mpu/1.35, g=nearestGate(z), gd=Math.hypot(g.x-z.x-z.w/2,g.y-z.y-z.h/2)*mpu;
  const why=editDirty?'직접 편집 중인 위치입니다. 저장하면 실제 위치 기준 출입구 거리와 근거를 갱신합니다.':(z.placement_reason||'저장 후 위치 기반 근거를 확인할 수 있습니다.');
  panel.innerHTML='<div class="thumb"><canvas width="184" height="140"></canvas><div class="tt"><b>'+esc(z.name)+'</b><span class="tag" style="background:'+gi.color+'22;color:'+gi.color+'">'+gi.icon+' '+esc(gi.label)+'</span></div></div>'
   +'<div class="fdesc">'+esc(z.description||'사용자가 추가한 행사 시설입니다.')+'</div>'
   +'<div class="frow"><i>📍</i><span>위치</span><b>'+regionTxt(z)+' <small style="color:var(--mut)">('+(z.x+z.w/2).toFixed(0)+', '+(z.y+z.h/2).toFixed(0)+')</small></b></div>'
   +'<div class="frow"><i>📐</i><span>크기</span><b>가로 '+wm.toFixed(1)+'m × 세로 '+hm_.toFixed(1)+'m <small style="color:var(--mut)">('+Math.round(wm*hm_)+'㎡)</small></b></div>'
   +'<div class="frow"><i>👥</i><span>수용 인원</span><b>'+capText(z)+'</b></div>'
   +'<div class="frow"><i>🕒</i><span>운영 시간</span><b>'+esc(P.hours)+'</b></div>'
   +'<div class="frow"><i>🚪</i><span>출입구</span><b>'+esc(g.name)+' · 직선 약 '+gd.toFixed(0)+'m</b></div>'
   +'<div class="frow"><i>🔥</i><span>현재 밀집도</span><b id="fDens">-</b></div>'
   +'<div class="fwhy"><b>배치 근거</b><br>'+esc(why)+'</div>';
  drawThumb(panel.querySelector('canvas'),z); liveFacility();
}
function liveFacility(){ const z=selectedZone(), el=$('fDens'); if(!z||!el) return; const d=zoneHeat(z); const lv=d<.25?'원활':d<.5?'보통':d<.9?'혼잡':'위험'; el.textContent=d.toFixed(2)+' 명/㎡ · '+lv; el.style.color=d<.25?'#0d8a5f':d<.5?'#a16207':d<.9?'#c2410c':'#dc2626'; }
function refreshSelection(){
  if(!S3) return; disposeGroup(selectionGroup); selectionGroup=null; const z=selectedZone(); if(!z||!vis[grp(z)]) return;
  selectionGroup=new THREE.Group(); S3.add(selectionGroup); const col=editing?0xfbbf24:0x2f6bff;
  const pts=[[z.x,z.y],[z.x+z.w,z.y],[z.x+z.w,z.y+z.h],[z.x,z.y+z.h],[z.x,z.y]].map(p=>new THREE.Vector3(p[0]-80,.9,p[1]-50));
  selectionGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineBasicMaterial({color:col,depthTest:false})));
  const pl=new THREE.Mesh(new THREE.PlaneGeometry(z.w+2,z.h+2),new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:.22,depthTest:false,depthWrite:false})); pl.rotation.x=-Math.PI/2; pl.position.set(z.x+z.w/2-80,.7,z.y+z.h/2-50); pl.renderOrder=90; selectionGroup.add(pl);
  if(editing&&mode==='after'){ const knob=new THREE.Mesh(new THREE.BoxGeometry(2.6,2.6,2.6),new THREE.MeshBasicMaterial({color:0xfbbf24,depthTest:false})); knob.position.set(z.x+z.w-80,2,z.y+z.h-50); knob.userData.resize=true; knob.renderOrder=99; selectionGroup.add(knob);
    editNote(z.name+' · '+(z.w*mpu/1.35).toFixed(2)+' × '+(z.h*mpu/1.35).toFixed(2)+'m · 미저장 변경은 저장 버튼으로 반영'); }
}

/* ----- 우측: 지표 / AI 결과 / 개선 제안 ----- */
const MET=[['safety','비상 안전성'],['access','접근성'],['cong','혼잡도 분산'],['flow','동선 효율성'],['space','공간 활용성'],['budget','예산 효율성']];
function renderMetrics(){
  const sc=curScores(), bs=D.before_scores, hi=(GOALS.find(g=>g[0]===goal)||GOALS[0])[4];
  $('metricTag').textContent=editDirty?'저장 후 재계산':(mode==='after'?'AI 최적':'설계 전'); $('metricTag').className='badge'+(editDirty?' warn':'');
  $('metricBars').innerHTML=MET.map(m=>{ const v=m[0]==='budget'?budgetEff():sc[m[0]], b=m[0]==='budget'?budgetEff():bs[m[0]]; const cls=(hi.includes(m[0])?'hi ':'')+(v<65?'bad':v<80?'low':'');
    const sm=m[0]==='budget'?('예상 비용 '+Math.round(D.cost.total).toLocaleString()+' / 예산 '+Number(D.cost.budget).toLocaleString()+'만원'):(mode==='after'?('설계 전 '+b.toFixed(0)+' → '+(v-b>=0?'+':'')+(v-b).toFixed(0)):'');
    return '<div class="bar '+cls+'"><span>'+m[1]+'</span><div class="tr"><div class="fl" style="width:'+v.toFixed(0)+'%"></div></div><em>'+v.toFixed(0)+'%</em>'+(sm?'<small>'+sm+'</small>':'')+'</div>'; }).join('');
  const tot=mode==='after'?D.total:D.before_total;
  $('aiBadge').textContent=editDirty?'편집됨':(D.stats.generated?'분석 완료':'직접 편집'); $('aiBadge').className='badge '+(editDirty?'warn':'ok');
  $('aiResult').innerHTML='<p><b>종합 '+tot.toFixed(1)+'점</b>'+(mode==='after'?' (설계 전 '+D.before_total.toFixed(1)+'점)':' · 비교용 기존 배치')+'</p>'+(AI.reasons||[]).slice(0,3).map(t=>'<p>• '+esc(t)+'</p>').join('');
  $('suggList').innerHTML=(AI.suggestions||[]).map(s=>'<li class="'+(s.lvl||'')+'">'+esc(s.text)+'</li>').join('')||'<li>현재 지표에서 눈에 띄는 개선 필요 항목이 없습니다.</li>';
}

/* ----- 하단: 진행 / 비교 / 요약 ----- */
function drawMini(c,zs){
  const r=c.getBoundingClientRect(), w=c.width=Math.max(240,Math.round((r.width||160)*2)), h=c.height=Math.round(w/1.6), t=c.getContext('2d'), sx=w/WW, sy=h/WH;
  t.fillStyle='#f1f7fd'; t.fillRect(0,0,w,h); t.beginPath(); D.shape.outline.forEach((p,i)=>i?t.lineTo(p[0]*sx,p[1]*sy):t.moveTo(p[0]*sx,p[1]*sy)); t.closePath();
  t.fillStyle='#d9efc9'; t.fill(); t.strokeStyle='#64748b'; t.lineWidth=2; t.stroke();
  zs.forEach(z=>{ t.fillStyle=z.color; t.globalAlpha=.9; t.fillRect(z.x*sx,z.y*sy,z.w*sx,z.h*sy); t.globalAlpha=1; t.strokeStyle='#fff'; t.lineWidth=1; t.strokeRect(z.x*sx,z.y*sy,z.w*sx,z.h*sy); });
  D.gates.forEach(g=>{ t.fillStyle='#0f172a'; t.beginPath(); t.arc(g.x*sx,g.y*sy,4,0,7); t.fill(); });
}
function drawMinis(){ drawMini($('miniB'),D.before_zones); drawMini($('miniA'),D.zones); }
function renderBottom(){
  const tot=mode==='after'?D.total:D.before_total, st=D.stats;
  $('ring').style.setProperty('--p',Math.max(0,Math.min(100,tot))); $('ringTxt').innerHTML=tot.toFixed(0)+'<small>종합 점수</small>';
  $('progTitle').textContent=editDirty?'수정 중 · 저장 필요':'설계 완료'; $('progSub').textContent=st.generated?(st.generated.toLocaleString()+'개 배치안 평가 · 파레토 '+st.pareto+'개'):'직접 편집 설계 · 재최적화 미수행';
  $('steps').innerHTML=(AI.steps||[]).map(s=>'<li>'+esc(s)+'</li>').join('')+(editDirty?'<li class="pend">3D 편집 내용 저장 대기</li>':'');
  const a=D.detail, b=D.before_detail, dt=D.total-D.before_total;
  $('miniBt').textContent='설계 전 · '+D.before_total.toFixed(1)+'점'; $('miniAt').textContent='현재 설계 · '+D.total.toFixed(1)+'점';
  $('deltaTxt').innerHTML='종합 <b>'+(dt>=0?'+':'')+dt.toFixed(1)+'점</b><br>최대 밀도 '+b.peak.toFixed(2)+' → '+a.peak.toFixed(2)+' 명/㎡ · 응급 최대 도달 '+Math.round(b.t_max)+' → '+Math.round(a.t_max)+'초 · 위험구역 '+b.risk_zones+' → '+a.risk_zones+'개소';
  const zs=Z(), occ=zs.reduce((s,z)=>s+z.w*z.h,0)/D.shape.area*100;
  const tiles=[['🧩','총 시설 수',zs.length+'개','#eaf1ff'],['📐','행사장 면적',Number(P.area_m2).toLocaleString()+'㎡','#e3f8ef'],['👥','예상 방문객',Number(P.visitors).toLocaleString()+'명','#fff1e0'],
    ['🏅','종합 점수',tot.toFixed(1)+'점','#f1e8ff'],['🧱','시설 점유율',occ.toFixed(1)+'%','#e0f6fb'],['💰','예상 비용',Math.round(D.cost.total).toLocaleString()+'만원','#fde8ec']];
  $('tiles').innerHTML=tiles.map(t=>'<div class="tile"><span class="ti" style="background:'+t[3]+'">'+t[0]+'</span><div><small>'+t[1]+'</small><b>'+t[2]+'</b></div></div>').join('');
}
function refreshLists(){ if(!editDrag) populateLabels(); renderGroups(); populateExplorer(); drawMinis(); renderBottom(); renderMetrics(); }

/* ----- 버튼 동작 ----- */
function runDesign(){ parent.postMessage({type:'event:action',action:'redesign'},'*'); editNote('설계 실행 요청을 보냈습니다. 잠시 후 새 설계안으로 갱신됩니다.'); }
function zoomBy(f){ zoom3=Math.min(3.2,Math.max(.6,zoom3*f)); }
function resetView(){ yaw=yaw0; pitch=pitch0; zoom3=zoom0; }
function goFull(){ const no=()=>editNote('이 환경에서는 전체 화면을 지원하지 않습니다.'); try{ const el=$('wrap'); const pr=document.fullscreenElement?document.exitFullscreen():el.requestFullscreen(); if(pr&&pr.catch) pr.catch(no); }catch(e){ no(); } }
document.addEventListener('fullscreenchange',()=>setTimeout(resize,80));
function dl(url,name){ const a=document.createElement('a'); a.href=url; a.download=name; document.body.appendChild(a); a.click(); a.remove(); }
function exportPNG(){ $('expMenu').classList.remove('open');
  try{ let url; if(is3d&&R3){ render3(); url=R3.domElement.toDataURL('image/png'); } else { const c=document.createElement('canvas'); c.width=W; c.height=H; const t=c.getContext('2d'); t.drawImage(cv,0,0); if(heat3) t.drawImage(hm,0,0); t.drawImage(pp,0,0); url=c.toDataURL('image/png'); }
    dl(url,(P.name||'event')+'_배치도.png'); editNote('PNG를 내보냈습니다. (시설 라벨은 포함되지 않습니다)'); }catch(e){ editNote('PNG 내보내기에 실패했습니다: '+e.message); } }
function exportJSON(){ $('expMenu').classList.remove('open');
  try{ const blob=new Blob([JSON.stringify({event:P.name,meters_per_unit:mpu,mode,scores:curScores(),zones:Z().map(z=>({id:z.id,name:z.name,type:z.type,x:z.x,y:z.y,w_m:+(z.w*mpu/1.35).toFixed(2),h_m:+(z.h*mpu/1.35).toFixed(2)})),gates:D.gates.map(g=>({name:g.name,x:g.x,y:g.y}))},null,2)],{type:'application/json'});
    const u=URL.createObjectURL(blob); dl(u,(P.name||'event')+'_layout.json'); setTimeout(()=>URL.revokeObjectURL(u),2000); editNote('배치 데이터를 JSON으로 내보냈습니다.'); }catch(e){ editNote('JSON 내보내기에 실패했습니다: '+e.message); } }
function liveTick(dt){ liveT+=dt; if(liveT>.5){ liveT=0; liveFacility(); } }
function postH(){ try{ parent.postMessage({type:'event:height',h:document.documentElement.scrollHeight+6},'*'); }catch(e){} }
if(window.ResizeObserver) new ResizeObserver(postH).observe(document.body);
document.addEventListener('click',ev=>{ if(!ev.target.closest('.menuwrap')) $('expMenu').classList.remove('open'); });
renderTop(); renderInfo(); renderGoals(); renderChips();

$('closeFacilityPopup').onclick=ev=>{ev.stopPropagation();selectZone(null)};
window.addEventListener('resize',resize);
cv.addEventListener('click',ev=>{const r=cv.getBoundingClientRect(),x=(ev.clientX-r.left)/r.width*160,y=(ev.clientY-r.top)/r.height*100;const f=[...ZV()].reverse().find(z=>x>=z.x&&x<=z.x+z.w&&y>=z.y&&y<=z.y+z.h);selectZone(f?f.id:null)});
$('tSl').min=0;$('tSl').max=23;
setTime(D.params.start_hour??14); resize(); initR3(); setView(is3d&&!!R3); setMode('after'); resize(); requestAnimationFrame(loop);
</script></body></html>
'''


def _dash_ai(r: dict) -> dict:
    """대시보드 우측 패널용: AI 설계 결과 요약 · 개선 제안(규칙 기반) · 진행 단계."""
    d, sc, zr, st_ = r["detail"], r["scores"], r["zones"], r["stats"]
    sug = []
    zd = d.get("zone_dens", [])
    if zd and len(zd) == len(zr):
        j = int(np.argmax(zd))
        if zd[j] >= WARN_DENSITY:
            sug.append(dict(lvl="b" if zd[j] >= DANGER_DENSITY else "w",
                            text=f"'{zr[j]['name']}' 주변 밀도가 {zd[j]:.2f}명/㎡로 가장 높습니다. 인접 구역과의 간격을 넓히거나 휴게공간을 완충지대로 두는 것을 검토하세요."))
    if d["risk_zones"] > 0:
        sug.append(dict(lvl="b", text=f"밀도 {DANGER_DENSITY}명/㎡ 이상인 위험 구역이 {d['risk_zones']}곳입니다. 해당 구역의 면적을 키우거나 출입구 분산을 늘려 보세요."))
    if d["t_max"] > 90:
        sug.append(dict(lvl="w", text=f"응급 최대 도달시간이 {fmt_sec(d['t_max'])}입니다. 가장 먼 구역 쪽으로 응급의료센터를 옮기거나 1곳을 추가하는 안을 검토하세요."))
    if d["obstruct"] > 0.12:
        sug.append(dict(lvl="w", text=f"입장 동선의 {d['obstruct'] * 100:.0f}%가 다른 구역을 가로지릅니다. 구역 사이 통로 폭을 확보하면 병목을 줄일 수 있습니다."))
    if d["evac"] > 70:
        sug.append(dict(lvl="w", text=f"구역→출입구 평균 거리가 약 {d['evac']:.0f}m입니다. 출입구를 늘리거나 중심부 시설을 출입구 쪽으로 이동해 대피 거리를 줄여 보세요."))
    if d["rr_m"] > 75:
        sug.append(dict(lvl="w", text=f"화장실 평균 접근거리가 약 {d['rr_m']:.0f}m입니다. 화장실을 분산 배치하는 것을 고려하세요."))
    weak = min(OBJECTIVES, key=lambda k: sc[k])
    if sc[weak] < 70:
        sug.append(dict(lvl="w", text=f"'{OBJ_LABEL[weak]}' 점수가 {sc[weak]:.0f}점으로 가장 낮습니다. 구역 크기 배율·출입구 수를 조정한 뒤 다시 설계해 보세요."))
    if r["cost"]["total"] > r["cost"]["budget"]:
        sug.append(dict(lvl="b", text=f"예상 비용 {r['cost']['total']:,.0f}만원이 예산 {r['cost']['budget']:,}만원을 초과합니다. 부스 수나 예산을 조정하세요."))
    if not sug:
        sug.append(dict(lvl="", text="주요 지표에서 눈에 띄는 개선 필요 항목이 없습니다. 3D 편집으로 세부 위치를 다듬어 보세요."))
    if st_["generated"]:
        steps = ["행사 조건 입력 반영", f"디지털 트윈 생성 (구역 {st_['zones']}개 · 출입구 {len(r['gates'])}개)",
                 f"배치안 {st_['generated']:,}개 군중 시뮬레이션", f"다목적 최적화 (파레토 {st_['pareto']}개)", "XAI 설계 이유 생성"]
    else:
        steps = ["직접 편집한 배치로 점수 재계산"]
    return dict(reasons=list(r["xai"]["reasons"][:3]), suggestions=sug[:4], steps=steps)


def build_twin_html(result: dict) -> str:
    p = result["params"]
    data = dict(
        zones=result["zones"], before_zones=result["before_zones"], gates=result["gates"],
        theme=result["theme"], mpu=result["mpu"],
        params=dict(visitors=p["visitors"], name=p["name"], purpose=p["purpose"], event_types=list(p.get("event_types") or []),
                    venue=p["venue"], location=p["location"], area_m2=p["area_m2"], hours=p["hours"], budget=p["budget"],
                    mood=p["mood"], age=p["age"], start_hour=p.get("start_hour", 10), end_hour=p.get("end_hour", 20)),
        shape=dict(kind=result["shape"]["kind"], dome=result["shape"]["dome"], bbox=result["shape"]["bbox"],
                   outline=result["shape"]["outline"], name=result["shape"]["name"], area=result["shape"]["area"]),
        total=result["total"], before_total=result["before_total"],
        scores=result["scores"], before_scores=result["before_scores"],
        cost=dict(total=result["cost"]["total"], budget=result["cost"]["budget"]),
        stats=dict(generated=result["stats"]["generated"], pareto=result["stats"]["pareto"], zones=result["stats"]["zones"]),
        detail=dict(t_max=result["detail"]["t_max"], risk_zones=result["detail"]["risk_zones"], peak=result["detail"]["peak"]),
        before_detail=dict(t_max=result["before_detail"]["t_max"], risk_zones=result["before_detail"]["risk_zones"], peak=result["before_detail"]["peak"]),
        ai=_dash_ai(result),
    )

    def enrich(z):
        z = dict(z)
        z.setdefault('description', ZONE_META[z['type']]['label'] + '로 사용하는 행사 시설입니다.')
        gate = min(result['gates'], key=lambda g: (g['x'] - z['x'] - z['w'] / 2) ** 2 + (g['y'] - z['y'] - z['h'] / 2) ** 2)
        distance = math.hypot(gate['x'] - z['x'] - z['w'] / 2, gate['y'] - z['y'] - z['h'] / 2) * result['mpu']
        reason = z.get('planning_reason', '행사 조건을 바탕으로 생성한 배치입니다.')
        z['placement_reason'] = reason + f" 가장 가까운 출입구는 {gate['name']}이며 시설 중심에서 직선거리 약 {distance:.1f}m입니다. 위치는 통로·외곽·출입구 여유 조건으로 검사합니다. 직접 편집한 위치의 최적성은 보장하지 않습니다."
        return z

    data['zones'] = [enrich(z) for z in data['zones']]
    data['before_zones'] = [enrich(z) for z in data['before_zones']]
    return TWIN_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False, default=str).replace("<", "\\u003c"))


# ===== REPORT =====



def grade(s: float) -> str:
    return "매우 우수" if s >= 90 else "우수" if s >= 80 else "보통" if s >= 65 else "개선 필요"


def build_markdown(r: dict) -> str:
    p, d, b = r["params"], r["detail"], r["before_detail"]
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [f"# {p['name']} — AI 행사장 설계 분석 리포트", f"_생성: {now} · Event ON_", ""]
    L += ["## 1. 행사 개요",
          f"- 행사 목적: {p['purpose']} / 분위기: {p['mood']}",
          f"- 장소: {p['venue']} ({p['location']}), 면적 {p['area_m2']:,}㎡, 행사장 모양 {r['shape']['name']}",
          f"- 예상 방문객 {p['visitors']:,}명, 연령대 {p['age']}, 운영 {p['hours']}",
          f"- 예산 {p['budget']:,}만원 (예상 시설 비용 {r['cost']['total']:,.0f}만원)", ""]
    L += ["## 2. 최적화 요약",
          f"- 생성·평가한 배치안 {r['stats']['generated']:,}개 (무작위 {r['stats']['randomly']:,} + 변이 {r['stats']['mutated']:,})",
          f"- 파레토 최적해 {r['stats']['pareto']}개 중 가중 종합점수 배치안 평가: **{r['total']:.1f}점** (설계 전 {r['before_total']:.1f}점)", ""]
    L += ["| 평가 항목 | 가중치 | 설계 전 | 설계 후 | 등급 |", "|---|---|---|---|---|"]
    for k in OBJECTIVES:
        L.append(f"| {OBJ_LABEL[k]} | {r['weights'][k] * 100:.0f}% | {r['before_scores'][k]:.0f} | {r['scores'][k]:.0f} | {grade(r['scores'][k])} |")
    L += ["", "## 3. 설계 전 / 후 비교", "| 지표 | 설계 전 | 설계 후 |", "|---|---|---|",
          f"| 병목 발생율 | {b['bottleneck']:.0f}% | {d['bottleneck']:.0f}% |",
          f"| 최대 군중 밀도 | {b['peak']:.2f}명/㎡ | {d['peak']:.2f}명/㎡ |",
          f"| 응급 최대 도달시간 | {fmt_sec(b['t_max'])} | {fmt_sec(d['t_max'])} |",
          f"| 응급 평균 도달시간 | {fmt_sec(b['t_mean'])} | {fmt_sec(d['t_mean'])} |",
          f"| 사고 위험구역 | {b['risk_zones']}개소 | {d['risk_zones']}개소 |",
          f"| 동선 구역 관통률 | {b['obstruct'] * 100:.0f}% | {d['obstruct'] * 100:.0f}% |", ""]
    L += ["## 4. 설계 이유 (설명가능 AI)"] + [f"- {x}" for x in r["xai"]["reasons"]] + [""]
    L += ["### 구역별 배치 근거"] + [f"- {z['icon']} **{z['name']}**: {z['text']}" for z in r["xai"]["zone_reasons"]] + [""]
    if r["xai"]["alternatives"]:
        L += ["### 검토했으나 채택하지 않은 대안"] + [f"- **{a['name']}**: {a['note']}" for a in r["xai"]["alternatives"]] + [""]
    L += ["## 5. 점수 산출 근거", "", "### 가중치 구성",
          "| 목표 | 기본 | 행사 목적 보정 | 연령대 보정 | 최종(정규화) |", "|---|---|---|---|---|"]
    for k in OBJECTIVES:
        wd = r["weight_detail"][k]
        L.append(f"| {OBJ_LABEL[k]} | {wd['base'] * 100:.0f}% | {wd['purpose'] * 100:+.0f}%p | {wd['age'] * 100:+.0f}%p | {wd['final'] * 100:.1f}% |")
    L += ["", "### 세부 지표별 점수 (측정값 → 0~100점, 만점·0점 기준 사이 선형 보간)",
          "| 목표 | 세부지표 | 설계 전 | 설계 후 | 만점 기준 | 0점 기준 | 세부점수(후) | 비중 |", "|---|---|---|---|---|---|---|---|"]
    for e in r["evidence"]:
        L.append(f"| {e['objLabel']} | {e['label']} | {e['v_before']} | {e['v_after']} | {e['best_txt']} | {e['worst_txt']} | {e['sub_after'] * 100:.0f} | {e['w'] * 100:.0f}% |")
    L += ["", "### 계산식 (비중×세부점수)"] + [f"- {OBJ_LABEL[k]}: {r['formulas'][k]}" for k in OBJECTIVES]
    L += [f"- **종합: {r['total_formula']}**", "", "### 가정과 한계"] + [f"- {a}" for a in r["assumptions"]] + [""]
    if r["notes"]:
        L += ["## 6. 유의사항"] + [f"- {n}" for n in r["notes"]] + [""]
    L += ["---", "※ 수치는 가상 군중 시뮬레이션 기반 추정치이며, 실제 시행 전 현장 안전 점검·관할 기관 협의가 필요합니다."]
    return "\n".join(L)


# ----------------------------------------------------------------------------
# 보고서형 HTML (표지 → 목차 → 장별 본문 → 그림·표 캡션). 추가 라이브러리 없이 SVG로 그림을 그린다.
# 저장: 보고서 화면의 [PDF로 저장] 버튼(브라우저 인쇄) 또는 HTML 다운로드
# ----------------------------------------------------------------------------
TEAM_NAME = "INCLUSE"
SCHOOL_NAME = "건양고등학교"

REPORT_CSS = """
@page{size:A4;margin:20mm 18mm}
*{box-sizing:border-box}
body{font-family:Pretendard,'Malgun Gothic','Noto Sans KR',sans-serif;color:#1e293b;line-height:1.75;font-size:14px;margin:0;background:#f1f5f9}
.doc{max-width:820px;margin:0 auto;background:#fff;padding:0 48px 40px}
.bar{position:sticky;top:0;background:#1e3a8a;color:#fff;padding:8px 16px;text-align:right;z-index:9}
.bar button{background:#fff;color:#1e3a8a;border:0;border-radius:6px;padding:6px 14px;font-weight:700;cursor:pointer}
.cover{min-height:900px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;border-bottom:1px solid #e2e8f0}
.cover .tag{color:#1e3a8a;font-weight:700;letter-spacing:2px;margin-bottom:18px}
.cover h1{font-size:34px;line-height:1.4;margin:0 0 14px;color:#0f172a}
.cover .sub{color:#64748b;font-size:16px;margin-bottom:60px}
.cover .meta{color:#475569;line-height:2}
.toc{padding:40px 0;min-height:500px}
.toc li{margin:10px 0;font-size:16px}
h2{font-size:21px;color:#1e3a8a;border-bottom:2px solid #1e3a8a;padding-bottom:5px;margin:40px 0 14px;page-break-after:avoid}
h3{font-size:16px;margin:22px 0 8px;color:#0f172a;page-break-after:avoid}
p{margin:6px 0}.li{margin:3px 0 3px 10px}
table{border-collapse:collapse;width:100%;margin:8px 0 4px;font-size:13px;page-break-inside:avoid}
th,td{border:1px solid #cbd5e1;padding:6px 9px;text-align:center}th{background:#eff6ff}td.l{text-align:left}
.cap{text-align:center;color:#64748b;font-size:12.5px;margin:4px 0 16px}
figure{margin:10px 0;text-align:center;page-break-inside:avoid}figure svg{max-width:100%;height:auto}
.two{display:flex;gap:12px}.two figure{flex:1;margin:0}
.box{background:#f8fafc;border-left:4px solid #1e3a8a;padding:10px 14px;margin:10px 0}
.note{color:#64748b;font-size:12.5px;margin-top:30px;border-top:1px solid #e2e8f0;padding-top:8px}
.sec{page-break-before:auto}
@media print{body{background:#fff}.doc{padding:0;max-width:none}.bar{display:none}.cover,.toc{page-break-after:always}.cover{min-height:240mm}.toc{min-height:0}}
"""


def _plain(s: str) -> str:
    """'~했습니다' 말투를 보고서용 평서체('~했다')로 바꾼다."""
    for a, b in [("했습니다", "했다"), ("됩니다", "된다"), ("합니다", "한다"), ("입니다", "이다"), ("있습니다", "있다"),
                 ("줄였습니다", "줄였다"), ("낮췄고", "낮췄고"), ("양보했습니다", "양보했다"), ("바랍니다", "바란다"),
                 ("필요합니다", "필요하다"), ("입력하신", "입력한"), ("습니다", "다")]:
        s = s.replace(a, b)
    return s


def _e(x) -> str:
    return _html.escape(str(x))


def _svg_layout(zones, gates, shape, title, mpu) -> str:
    """배치도 SVG (160x100 가상 좌표)."""
    o = []
    pts = " ".join(f"{x},{y}" for x, y in shape["outline"])
    o.append(f'<svg viewBox="-2 -2 164 104" xmlns="http://www.w3.org/2000/svg" font-family="Malgun Gothic,sans-serif">')
    o.append(f'<polygon points="{pts}" fill="#f8fafc" stroke="#334155" stroke-width="0.8"/>')
    for z in zones:
        c = ZONE_META[z["type"]]["color"]
        o.append(f'<rect x="{z["x"]}" y="{z["y"]}" width="{z["w"]}" height="{z["h"]}" rx="1" fill="{c}" fill-opacity=".78" stroke="#fff" stroke-width=".4"/>')
        fs = max(1.9, min(3.0, z["w"] / max(3, len(z["name"])) * 0.95))
        o.append(f'<text x="{z["x"] + z["w"] / 2}" y="{z["y"] + z["h"] / 2 + fs / 3}" font-size="{fs:.1f}" fill="#fff" text-anchor="middle" font-weight="700">{_e(z["name"])}</text>')
    for g in gates:
        o.append(f'<circle cx="{g["x"]}" cy="{g["y"]}" r="2" fill="#0f172a"/>')
        o.append(f'<text x="{g["x"]}" y="{g["y"] - 3}" font-size="2.6" text-anchor="middle" fill="#0f172a">{_e(g["name"])}</text>')
    o.append("</svg>")
    return "".join(o)


def _svg_bars(labels, before, after) -> str:
    """설계 전·후 점수 막대그래프 SVG."""
    W, H, L, B = 640, 280, 40, 50
    n = len(labels)
    gw = (W - L - 10) / n
    o = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Malgun Gothic,sans-serif" font-size="12">']
    for t in (0, 25, 50, 75, 100):
        y = H - B - (H - B - 20) * t / 100
        o.append(f'<line x1="{L}" x2="{W - 10}" y1="{y}" y2="{y}" stroke="#e2e8f0"/><text x="{L - 6}" y="{y + 4}" text-anchor="end" fill="#64748b">{t}</text>')
    for i, (lb, b, a) in enumerate(zip(labels, before, after)):
        x0 = L + i * gw + gw * 0.18
        bw = gw * 0.30
        for j, (v, col) in enumerate(((b, "#94a3b8"), (a, "#1e3a8a"))):
            h = (H - B - 20) * max(0, min(100, v)) / 100
            x = x0 + j * (bw + 3)
            o.append(f'<rect x="{x}" y="{H - B - h}" width="{bw}" height="{h}" fill="{col}"/>')
            o.append(f'<text x="{x + bw / 2}" y="{H - B - h - 4}" text-anchor="middle" font-size="11" fill="#334155">{v:.0f}</text>')
        o.append(f'<text x="{L + i * gw + gw / 2}" y="{H - B + 18}" text-anchor="middle" fill="#334155">{_e(lb)}</text>')
    o.append(f'<rect x="{W - 170}" y="4" width="10" height="10" fill="#94a3b8"/><text x="{W - 156}" y="13" fill="#334155">설계 전</text>')
    o.append(f'<rect x="{W - 95}" y="4" width="10" height="10" fill="#1e3a8a"/><text x="{W - 81}" y="13" fill="#334155">AI 설계</text></svg>')
    return "".join(o)


def _tbl(head, rows, left_cols=()) -> str:
    h = "".join(f"<th>{_e(c)}</th>" for c in head)
    b = "".join("<tr>" + "".join(f'<td class="{"l" if i in left_cols else ""}">{_e(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b}</table>"


def build_report_html(r: dict, team: str = TEAM_NAME, school: str = SCHOOL_NAME) -> str:
    p, d, b, st_ = r["params"], r["detail"], r["before_detail"], r["stats"]
    n_fig, n_tbl = [0], [0]

    def fig(svg, cap):
        n_fig[0] += 1
        return f'<figure>{svg}<div class="cap">그림 {n_fig[0]}. {_e(cap)}</div></figure>'

    def tbl(head, rows, cap, left=()):
        n_tbl[0] += 1
        return f'<div class="cap" style="margin-bottom:2px"><b>표 {n_tbl[0]}.</b> {_e(cap)}</div>' + _tbl(head, rows, left) + "<br>"

    today = _dt.date.today().strftime("%Y. %m. %d.")
    gain = r["total"] - r["before_total"]
    best_k = max(OBJECTIVES, key=lambda k: r["scores"][k] - r["before_scores"][k])
    worst_k = min(OBJECTIVES, key=lambda k: r["scores"][k])
    toc = ["행사 개요", "분석 방법", "최적 배치안", "설계 전·후 비교", "설계 이유 (XAI)", "점수 산출 근거", "결론 및 유의사항"]

    s = []
    s.append(f'<div class="bar"><button onclick="window.print()">🖨️ PDF로 저장 (인쇄 → PDF)</button></div><div class="doc">')
    s.append(f'<section class="cover"><div class="tag">EVENT ON REPORT</div><h1>{_e(p["name"])}<br>AI 행사장 설계 분석 보고서</h1>'
             f'<div class="sub">군중 시뮬레이션 기반 최적 배치 결과</div>'
             f'<div class="meta">{_e(school)}<br>팀명 {_e(team)}<br>{today}</div></section>')
    s.append('<section class="toc"><h2 style="margin-top:0">목차</h2><ol>' + "".join(f"<li>{t}</li>" for t in toc) + "</ol></section>")

    # 1
    s.append("<h2>1. 행사 개요</h2>")
    s.append(f"<p>{_e(p['name'])}은(는) {_e(p['venue'])}({_e(p['location'])})에서 열리는 {_e(p['purpose'])} 행사이다. "
             f"예상 방문객은 {p['visitors']:,}명이고, 주요 연령대는 {_e(p['age'])}이다.</p>")
    s.append(tbl(["항목", "내용"], [
        ["행사 목적 / 분위기", f"{p['purpose']} / {p['mood']}"],
        ["장소 / 면적", f"{p['venue']} / {p['area_m2']:,}㎡ ({r['shape']['name']})"],
        ["예상 방문객 / 운영 시간", f"{p['visitors']:,}명 / {p['hours']}"],
        ["예산 / 예상 시설 비용", f"{p['budget']:,}만원 / {r['cost']['total']:,.0f}만원"],
    ], "행사 개요", left=(1,)))

    # 2
    s.append("<h2>2. 분석 방법</h2>")
    s.append("<p>행사 정보를 입력하면 가상 행사장(디지털 트윈)을 만들고, 여러 배치안을 만들어 군중 이동을 시뮬레이션한 뒤 점수가 가장 높은 안을 고른다.</p>")
    s.append(f"<p class='li'>• 생성·평가한 배치안: {st_['generated']:,}개 (무작위 {st_['randomly']:,}개 + 변이 {st_['mutated']:,}개)</p>"
             f"<p class='li'>• 파레토 최적해: {st_['pareto']}개, 배치 구역: {st_['zones']}개</p>"
             f"<p class='li'>• 평가 목표: {', '.join(OBJ_LABEL[k] for k in OBJECTIVES)}</p>")
    s.append(tbl(["목표", "가중치"], [[OBJ_LABEL[k], f"{r['weights'][k] * 100:.0f}%"] for k in OBJECTIVES], "평가 목표별 가중치"))

    # 3
    s.append("<h2>3. 최적 배치안</h2>")
    s.append(f"<p>종합 점수 {r['total']:.1f}점으로 후보 중 상위 {max(0.1, 100 - st_['rank_pct']):.1f}% 이내의 배치안을 선택했다.</p>")
    s.append(fig(_svg_layout(r["zones"], r["gates"], r["shape"], "", r["mpu"]), "AI가 제안한 최적 배치도"))
    s.append(tbl(["구역", "종류", "가로(m)", "세로(m)"], [[z["name"], z["type"], z["w_m"], z["h_m"]] for z in r["zone_sizes"]], "구역별 크기"))

    # 4
    s.append("<h2>4. 설계 전·후 비교</h2>")
    s.append(f"<p>종합 점수는 설계 전 {r['before_total']:.1f}점에서 설계 후 {r['total']:.1f}점으로 {gain:+.1f}점 달라졌다. "
             f"가장 크게 좋아진 항목은 {OBJ_LABEL[best_k]}이다.</p>")
    s.append('<div class="two">' + fig(_svg_layout(r["before_zones"], r["gates"], r["shape"], "", r["mpu"]), "설계 전(기존) 배치")
             + fig(_svg_layout(r["zones"], r["gates"], r["shape"], "", r["mpu"]), "AI 최적 배치") + "</div>")
    s.append(fig(_svg_bars([OBJ_LABEL[k] for k in OBJECTIVES], [r["before_scores"][k] for k in OBJECTIVES],
                           [r["scores"][k] for k in OBJECTIVES]), "목표별 점수 비교"))
    s.append(tbl(["평가 항목", "가중치", "설계 전", "설계 후", "등급"],
                 [[OBJ_LABEL[k], f"{r['weights'][k] * 100:.0f}%", f"{r['before_scores'][k]:.0f}", f"{r['scores'][k]:.0f}", grade(r["scores"][k])] for k in OBJECTIVES],
                 "목표별 점수와 등급"))
    s.append(tbl(["지표", "설계 전", "설계 후"], [
        ["병목 발생율", f"{b['bottleneck']:.0f}%", f"{d['bottleneck']:.0f}%"],
        ["최대 군중 밀도", f"{b['peak']:.2f}명/㎡", f"{d['peak']:.2f}명/㎡"],
        ["응급 최대 도달시간", fmt_sec(b["t_max"]), fmt_sec(d["t_max"])],
        ["응급 평균 도달시간", fmt_sec(b["t_mean"]), fmt_sec(d["t_mean"])],
        ["사고 위험구역", f"{b['risk_zones']}개소", f"{d['risk_zones']}개소"],
        ["동선 구역 관통률", f"{b['obstruct'] * 100:.0f}%", f"{d['obstruct'] * 100:.0f}%"],
    ], "시뮬레이션 지표 비교"))

    # 5
    s.append("<h2>5. 설계 이유 (XAI)</h2>")
    s.append("<h3>5-1. 전체 설계 이유</h3>" + "".join(f"<p class='li'>• {_e(_plain(t))}</p>" for t in r["xai"]["reasons"]))
    s.append("<h3>5-2. 구역별 배치 근거</h3>" + "".join(f"<p class='li'>• <b>{_e(z['name'])}</b>: {_e(_plain(z['text']))}</p>" for z in r["xai"]["zone_reasons"]))
    if r["xai"]["alternatives"]:
        s.append("<h3>5-3. 검토했으나 채택하지 않은 대안</h3>" + "".join(
            f"<p class='li'>• <b>{_e(a['name'])}</b>: {_e(_plain(a['note']))}</p>" for a in r["xai"]["alternatives"]))

    # 6
    s.append("<h2>6. 점수 산출 근거</h2>")
    s.append(tbl(["목표", "기본", "목적 보정", "연령대 보정", "최종"], [
        [OBJ_LABEL[k], f"{r['weight_detail'][k]['base'] * 100:.0f}%", f"{r['weight_detail'][k]['purpose'] * 100:+.0f}%p",
         f"{r['weight_detail'][k]['age'] * 100:+.0f}%p", f"{r['weight_detail'][k]['final'] * 100:.1f}%"] for k in OBJECTIVES], "가중치 구성"))
    s.append(tbl(["목표", "세부지표", "설계 전", "설계 후", "만점 기준", "0점 기준", "세부점수", "비중"],
                 [[e["objLabel"], e["label"], e["v_before"], e["v_after"], e["best_txt"], e["worst_txt"], f"{e['sub_after'] * 100:.0f}", f"{e['w'] * 100:.0f}%"] for e in r["evidence"]],
                 "세부 지표별 점수 (측정값을 0~100점으로 환산)", left=(1,)))
    s.append("<div class='box'><b>계산식</b><br>" + "<br>".join(f"{OBJ_LABEL[k]}: {_e(r['formulas'][k])}" for k in OBJECTIVES)
             + f"<br><b>종합: {_e(r['total_formula'])}</b></div>")
    s.append("<h3>가정과 한계</h3>" + "".join(f"<p class='li'>• {_e(_plain(a))}</p>" for a in r["assumptions"]))

    # 7
    s.append("<h2>7. 결론 및 유의사항</h2>")
    s.append(f"<p>AI 설계안은 종합 {r['total']:.1f}점으로 기존 배치({r['before_total']:.1f}점)보다 {gain:+.1f}점 높다. "
             f"최대 군중 밀도는 {b['peak']:.2f}→{d['peak']:.2f}명/㎡, 사고 위험구역은 {b['risk_zones']}→{d['risk_zones']}개소로 달라졌다. "
             f"상대적으로 낮은 항목은 {OBJ_LABEL[worst_k]}({r['scores'][worst_k]:.0f}점)이며, 구역 크기나 출입구 수를 조정해 더 개선해 볼 수 있다.</p>")
    if r["notes"]:
        s.append("<h3>유의사항</h3>" + "".join(f"<p class='li'>• {_e(_plain(n))}</p>" for n in r["notes"]))
    s.append("<div class='note'>이 보고서의 수치는 가상 군중 시뮬레이션으로 얻은 추정값이다. 실제로 행사를 열기 전에는 현장 안전 점검과 관할 기관 협의가 필요하다.</div>")
    s.append("</div>")
    return ("<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>Event ON 보고서</title><style>"
            + REPORT_CSS + "</style></head><body>" + "".join(s) + "</body></html>")


def build_html(r: dict) -> str:  # 예전 이름 호환
    return build_report_html(r)


# ===== UI =====

st.set_page_config(page_title="Event ON - AI 행사 자동 설계", page_icon="🎪", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1.4rem;max-width:1500px}
.eo-head{background:linear-gradient(135deg,#0f172a,#1e3a8a);color:#fff;padding:18px 24px;border-radius:16px;margin-bottom:14px}
.eo-head h1{font-size:26px;margin:0;color:#fff} .eo-head p{margin:4px 0 0;color:#bfdbfe;font-size:13px}
.wf{display:flex;gap:6px;align-items:stretch;flex-wrap:wrap;margin:6px 0 14px}
.wf .st{flex:1;min-width:130px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px 10px;text-align:center}
.wf .st .n{width:24px;height:24px;border-radius:50%;background:#2563eb;color:#fff;font-weight:800;font-size:12px;display:inline-grid;place-items:center}
.wf .st b{display:block;font-size:13px;margin:6px 0 2px;color:#0f172a} .wf .st span{font-size:11px;color:#64748b}
.wf .ar{align-self:center;color:#94a3b8;font-weight:900}
</style>""", unsafe_allow_html=True)


FACILITY_CATALOG = ['방송장비 배치', '흡연장', '수유실', '비상구', '안전관리본부', '쓰레기통', '분실물보관소', '안내데스크', '사회적 약자 우선 부스', '주차장', '무대 대기실', '스태프룸', '음향조정실', '장비창고', '충전공간', '미아보호소', '팝업장비 배치', '책상', '테이블', '의자', '파라솔', '천막', '알림막', '깃발', '연단', '가림막', '전광판', '키오스크', '포토부스', '체험부스', '푸드트럭', '플리마켓부스', '분리수거함', '종합조정실', '방송실', '경비실', '응급처치소', '화장실']

# AI/API and direct editing extension
import copy
import os
import pathlib
import urllib.request
import urllib.error
import uuid


def ai_request(text, result, endpoint, model, api_key):
    """User-configured Chat Completions-compatible API. Never executes generated code."""
    if not endpoint.startswith('https://'):
        raise ValueError('API 주소는 https://로 입력하세요.')
    if not api_key or not model:
        raise ValueError('API 키와 모델 이름을 입력하세요.')
    snapshot = dict(params=result['params'], zones=[dict(id=z['id'], name=z['name'], type=z['type'],
        x=z['x'], y=z['y'], width_m=z['w']*result['mpu']/1.35,
        depth_m=z['h']*result['mpu']/1.35, shape=z.get('shape','rect')) for z in result['zones']])
    instructions = '''You are an event layout assistant. Return ONLY a JSON object with summary (Korean) and operations (list, max 30).
Allowed operations:
{"op":"update","id":existing_id,"width_m":number,"depth_m":number,"x":number,"y":number,"shape":"rect|ellipse|L","name":"name"}
{"op":"add","type":"stage|food|booth|rest|medical|info|restroom|custom","name":"name","width_m":number,"depth_m":number,"shape":"rect|ellipse|L"}
{"op":"delete","id":existing_id}
Coordinates x,y are virtual units in 160x100, NOT meters. width_m/depth_m are meters. Update only fields requested, keep all unrelated items.
Use existing IDs, never infer ID by index. If placement unspecified on add omit x/y. If request vague recommend sensible dimensions. Circular stage = ellipse with equal dimensions. A request to double area multiplies both dimensions by sqrt(2).
No code, no arbitrary fields. Facility safety metrics are approximate; do not promise safety. If unsupported return operations:[] and explain. Event conditions cannot be changed through these operations; explain that sidebar controls them.'''
    body = dict(model=model, messages=[dict(role='system',content=instructions),
        dict(role='user',content=json.dumps(dict(current=snapshot,request=text),ensure_ascii=False))],
        response_format={'type':'json_object'})
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), method='POST',
        headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('API 응답이 너무 큽니다.')
        payload=json.loads(raw)
        content=payload['choices'][0]['message']['content']
        proposal=json.loads(content)
    except urllib.error.HTTPError as e:
        raise ValueError(f'API 요청 실패 (HTTP {e.code}). 주소·키·모델 및 JSON 응답 지원 여부를 확인하세요.') from None
    except (KeyError,TypeError,json.JSONDecodeError):
        raise ValueError('API가 지정된 JSON 형식으로 응답하지 않았습니다.') from None
    if not isinstance(proposal,dict) or not isinstance(proposal.get('operations'),list):
        raise ValueError('응답에 operations 목록이 없습니다.')
    if len(proposal['operations'])>30: raise ValueError('한 번에 30개 명령까지 가능합니다.')
    return proposal


def edit_number(value, low, high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'숫자는 {low}~{high} 범위여야 합니다.')
    return float(value)


def validate_edited(zones, result):
    required_names={name for name,_ in MANDATORY_ITEMS}
    existing={z['name'] for z in result['zones']}
    remaining={z['name'] for z in zones}
    missing=required_names.intersection(existing)-remaining
    if missing: raise ValueError('필수 구성은 삭제할 수 없습니다: '+', '.join(sorted(missing)))
    for typ,label in [('restroom','화장실'),('info','안내 시설')]:
        if not any(z['type']==typ for z in zones): raise ValueError(label+'은 최소 하나 유지해야 합니다.')
    if not 2<=len(zones)<=80: raise ValueError('시설은 2~80개여야 합니다.')
    if not any(z['type']=='medical' for z in zones): raise ValueError('마지막 응급의료센터는 삭제할 수 없습니다.')
    if not any(z['type']!='medical' for z in zones): raise ValueError('일반 시설이 최소 하나 필요합니다.')
    if len({z['id'] for z in zones})!=len(zones): raise ValueError('시설 ID가 중복되었습니다.')
    sh=shape_info(result['params'].get('shape',DEFAULT_SHAPE))
    rows=[]
    for z in zones:
        for key,lo,hi in [('x',0,160),('y',0,100),('w',1,150),('h',1,95)]:
            edit_number(z[key],lo,hi)
        if z.get('shape','rect') not in ('rect','ellipse','L'): raise ValueError('지원하지 않는 모양입니다.')
        # Conservative bounding boxes for all shapes.
        if not _valid(z['x'],z['y'],z['w'],z['h'],np.array(rows).reshape(-1,4),np.ones(len(rows),bool),
                      [(g['x'],g['y']) for g in result['gates']],sh):
            raise ValueError(f"{z['name']}: 외곽·시설 간 통로·출입구 공간을 침범합니다. 위치나 크기를 조정하세요.")
        rows.append([z[k] for k in ('x','y','w','h')])


def proposal_zones(proposal,result):
    zones=copy.deepcopy(result['zones'])
    for op in proposal['operations']:
        if not isinstance(op,dict): raise ValueError('명령은 객체여야 합니다.')
        action=op.get('op')
        if action not in ('add','update','delete'): raise ValueError('지원하지 않는 명령입니다.')
        if action=='add':
            if '주차장' in str(op.get('name','')): raise ValueError('주차장은 행사장 외부에 별도로 표시합니다. 내부 부스로 추가하지 않습니다.')
            typ=op.get('type','custom')
            if typ not in ZONE_META: raise ValueError('지원하지 않는 시설 종류입니다.')
            meta=ZONE_META[typ]
            z=dict(id=max([q['id'] for q in zones]+[-1])+1,type=typ,name=str(op.get('name',meta['label']))[:60],
                color=meta['color'],icon=meta['icon'],ht=meta['ht'],attract=meta['attract'],w=8,h=6,shape='rect')
            zones.append(z)
        else:
            candidates=[q for q in zones if q['id']==op.get('id')]
            if len(candidates)!=1: raise ValueError('대상 시설 ID를 찾을 수 없습니다.')
            z=candidates[0]
            if action=='delete': zones.remove(z); continue
        for key,out in [('width_m','w'),('depth_m','h')]:
            if key in op: z[out]=edit_number(op[key],1,150)*1.35/result['mpu']
        for key in ('x','y'):
            if key in op: z[key]=edit_number(op[key],0,160 if key=='x' else 100)
        if 'shape' in op: z['shape']=op['shape']
        if 'name' in op: z['name']=str(op['name'])[:60]
        if action=='add' and ('x' not in op or 'y' not in op):
            found=False
            for yy in np.arange(5,95,2):
                for xx in np.arange(5,155,2):
                    z.update(x=float(xx),y=float(yy))
                    try: validate_edited(zones,result); found=True; break
                    except ValueError: pass
                if found: break
            if not found: raise ValueError('새 시설을 넣을 빈 공간이 없습니다. 크기를 줄여 주세요.')
    validate_edited(zones,result)
    return zones


def edited_result(result,zones):
    validate_edited(zones,result)
    r=copy.deepcopy(result); r['zones']=copy.deepcopy(zones)
    L=np.array([[z[k] for k in ('x','y','w','h')] for z in zones])
    ctx=make_ctx(zones,r['params'],r['mpu'],r['gates'],shape_info(r['params'].get('shape',DEFAULT_SHAPE)))
    sc,det=evaluate(L,ctx,detail=True)
    r['detail']=det; r['scores']={k:float(sc[i]) for i,k in enumerate(OBJECTIVES)}
    r['total']=sum(r['weights'][k]*r['scores'][k] for k in OBJECTIVES)
    r['zone_sizes']=[dict(name=z['name'],type=ZONE_META[z['type']]['label'],w_m=round(z['w']*r['mpu']/1.35,2),h_m=round(z['h']*r['mpu']/1.35,2)) for z in zones]
    # Preserve before comparison. Recompute evidence, discard optimization claims after direct edits.
    old={(e['obj'],e['label']):e for e in r['evidence']}
    r['evidence']=[]
    for s in det['sub']:
        e=copy.deepcopy(old[(s['obj'],s['label'])]); e.update(v_after=s['disp'],sub_after=s['sub']); r['evidence'].append(e)
    r['formulas']={k:' + '.join(f"{e['w']:.2f}×{e['sub_after']*100:.0f}" for e in r['evidence'] if e['obj']==k)+f" = {r['scores'][k]:.1f}점" for k in OBJECTIVES}
    r['total_formula']=' + '.join(f"{r['weights'][k]:.2f}×{r['scores'][k]:.0f}" for k in OBJECTIVES)+f" = {r['total']:.1f}점"
    r['xai']=dict(contrib=[dict(key=k,label=OBJ_LABEL[k],weight=r['weights'][k],score=r['scores'][k],contribution=r['weights'][k]*r['scores'][k],pct_rank=0,vs_mean=0,base=r['before_scores'][k]) for k in OBJECTIVES],
        reasons=['직접 편집한 배치로 점수를 다시 계산했습니다. 기존 후보군 순위와 배치안 평가 근거는 적용하지 않습니다.'],zone_reasons=[],alternatives=[])
    r['cloud']=[]
    r['stats'].update(generated=0,randomly=0,mutated=0,pareto=0,rank_pct=0,zones=len(zones))
    r['cost']['total']=float(sum((800+r['params']['visitors']*.15) if z['type']=='stage' else COST[z['type']] for z in zones))
    r['notes']=['직접 편집한 설계입니다. 점수는 다시 계산했지만 최적화는 수행하지 않았습니다. 모양은 시각적으로 반영되며, 밀집도·충돌 계산은 외접 직사각형 기준입니다. 비용은 기존 종류별 단가의 단순 추정이며 크기·모양 변경 비용은 반영하지 않습니다.']
    if r['cost']['total']>r['cost']['budget']: r['notes'].append('예상 비용이 예산을 초과합니다.')
    return r


def save_edit(result,zones,label):
    res=edited_result(result,zones)
    ss.history.append(dict(label=f'v{len(ss.history)+1} · {label}',result=res,sig=make_sig()))
    ss.view=len(ss.history)-1
    ss['_next_hist']=ss.view



# Self-contained component assets: app.py can be deployed without a separate folder.
import tempfile

_EDITOR_BOOTSTRAP_HTML = r'''<!doctype html><html><meta charset="utf-8"><style>html,body{margin:0;background:transparent}iframe{border:0;width:100%;height:1500px;display:block}</style><iframe id="scene" title="Event ON 대시보드" allow="fullscreen" allowfullscreen></iframe><script>
const f=document.getElementById('scene');let rev=null,H=1500;
const send=(type,extra={})=>parent.postMessage({isStreamlitMessage:true,type,...extra},'*');
const setH=h=>{H=Math.max(700,Math.ceil(h));f.style.height=H+'px';send('streamlit:setFrameHeight',{height:H});};
const tok=()=>Date.now()+'-'+Math.random();
window.addEventListener('message',e=>{
 const d=e.data||{};
 if(e.source===parent&&d.type==='streamlit:render'){const a=d.args;if(a.revision!==rev){rev=a.revision;f.srcdoc=a.html}setH(H);}
 else if(e.source===f.contentWindow&&d.type==='event:save'){send('streamlit:setComponentValue',{dataType:'json',value:{zones:d.zones,revision:rev,token:tok()}})}
 else if(e.source===f.contentWindow&&d.type==='event:action'){send('streamlit:setComponentValue',{dataType:'json',value:{action:d.action,revision:rev,token:tok()}})}
 else if(e.source===f.contentWindow&&d.type==='event:height'){setH(d.h)}
});send('streamlit:componentReady',{apiVersion:1});
</script></html>'''

@st.cache_resource(show_spinner=False)
def get_3d_editor_component():
    # Use an absolute temporary asset directory, independent of repository layout
    # and repository write permissions. The cached component keeps it alive.
    folder = pathlib.Path(tempfile.mkdtemp(prefix='event_on_editor_'))
    (folder / 'index.html').write_text(_EDITOR_BOOTSTRAP_HTML, encoding='utf-8')
    return components.declare_component('event_on_3d_editor', path=str(folder.resolve()))


def render_ai_editor(R):
    st.caption('API 키는 비밀번호 칸 또는 배포 환경의 EVENT_AI_API_KEY로 설정합니다. 요청 시 행사 설정과 시설 목록이 입력한 API로 전송됩니다.')
    with st.expander('AI API 연결 설정',expanded=False):
        endpoint=st.text_input('Chat Completions API 전체 주소',value=os.environ.get('EVENT_AI_ENDPOINT',''),placeholder='https://…/v1/chat/completions',key='eo_endpoint')
        model=st.text_input('사용할 모델 이름',value=os.environ.get('EVENT_AI_MODEL',''),key='eo_model')
        key=st.text_input('API 키',type='password',key='eo_api_key') or os.environ.get('EVENT_AI_API_KEY','')
    for who,msg in ss.chat[-6:]:
        st.chat_message('assistant' if who=='ai' else 'user').write(msg)
    cmd=st.chat_input('예: 무대를 가로 15m 세로 10m의 타원형으로 바꾸고 포토존을 추가해줘')
    if cmd:
        ss.chat.append(('user',cmd))
        try:
            with st.spinner('AI가 변경안을 작성하고 있습니다…'):
                proposal=ai_request(cmd,R,endpoint,model,key)
                zones=proposal_zones(proposal,R)
            ss['_ai_proposal']=dict(proposal=proposal,zones=zones,base=ss.view)
        except Exception as e:
            st.error(str(e) if isinstance(e,ValueError) else 'AI 요청에 실패했습니다. 연결 설정과 네트워크를 확인하세요.')
    pending=ss.get('_ai_proposal')
    if pending:
        st.info(str(pending['proposal'].get('summary','AI 변경안')))
        st.json(pending['proposal']['operations'],expanded=False)
        a,b=st.columns(2)
        if a.button('변경안 적용',type='primary'):
            try:
                if pending['base']!=ss.view: raise ValueError('설계가 바뀌었습니다. 다시 요청해 주세요.')
                save_edit(R,pending['zones'],'AI 명령 반영')
                ss.chat.append(('ai',str(pending['proposal'].get('summary','변경했습니다.'))))
                del ss['_ai_proposal']; st.rerun()
            except ValueError as e: st.error(str(e))
        if b.button('변경안 취소'):
            del ss['_ai_proposal']; st.rerun()
    st.markdown('##### 🧰 사진 속 시설 추가')
    st.caption('개별 시설의 기본 크기는 편집용 예시입니다. 추가 후 3D에서 크기를 조절하세요. 배치 불가능한 공간에는 추가하지 않습니다.')
    with st.form('facility_catalog'):
        chosen=st.multiselect('추가할 시설',FACILITY_CATALOG)
        count=st.number_input('각 시설 개수',1,10,1)
        width=st.number_input('가로(m)',1.0,40.0,3.0,0.5)
        depth=st.number_input('세로(m)',1.0,40.0,3.0,0.5)
        if st.form_submit_button('선택 시설 추가'):
            try:
                ops=[]
                for name in chosen:
                    typ='medical' if name in ('응급처치소','안전관리본부') else ('restroom' if name=='화장실' else ('info' if name=='안내데스크' else 'custom'))
                    ops.extend(dict(op='add',type=typ,name=name,width_m=width,depth_m=depth) for _ in range(int(count)))
                if not ops: raise ValueError('추가할 시설을 선택하세요.')
                if len(ops)>30: raise ValueError('한 번에 30개까지 추가하세요.')
                save_edit(R,proposal_zones({'operations':ops},R),'시설 추가');st.rerun()
            except ValueError as e: st.error(str(e))
    st.markdown('##### 🧊 AI 행사장 설계 대시보드')
    st.caption('지원시설은 아이콘으로 표시합니다. 아이콘도 시설의 운영 공간을 차지하므로 충돌 계산에는 기존 계획 면적을 유지합니다. 외부 주차장은 표시용 계획 예시이며 수용량·교통·비용 계산에서 제외합니다.')
    st.caption('편집 모드 → 부스 클릭 → 몸체 드래그로 이동, 노란 손잡이로 크기 조절. 빈 바닥 드래그는 시점 회전입니다. 저장해야 점수·리포트에 반영됩니다.')
    component=get_3d_editor_component()
    value=component(html=build_twin_html(R),revision=ss.view,key='eo_3d_canvas')
    if isinstance(value,dict) and value.get('token')!=ss.get('_last_edit_token'):
        ss['_last_edit_token']=value.get('token')
        if value.get('action')=='redesign':
            ss.pending='대시보드에서 재설계'; st.rerun()
        try:
            if value.get('revision')!=ss.view: raise ValueError('오래된 편집 요청입니다.')
            edited=value.get('zones',[])
            known={z['id']:z for z in R['zones']}
            merged=[]
            for z in edited:
                if z.get('id') not in known: raise ValueError('알 수 없는 시설 ID입니다.')
                q=copy.deepcopy(known[z['id']])
                for k in ('x','y','w','h'): q[k]=z[k]
                merged.append(q)
            save_edit(R,merged,'마우스 편집'); st.rerun()
        except (ValueError,KeyError,TypeError) as e: st.error('저장하지 못했습니다: '+str(e))


ss = st.session_state
ss.setdefault("custom", [])
ss.setdefault("pins", {})
ss.setdefault("chat", [("ai", "안녕하세요! 예) '무대를 우측으로, 응급의료센터를 중앙에 배치해줘', '칵테일 바 2개 추가' 처럼 말씀해 주세요.")])
ss.setdefault("history", [])
ss.setdefault("result", None)
ss.setdefault("view", None)
ss.setdefault("pending", None)
if "_next_hist" in ss:
    ss["hist_sel"] = ss.pop("_next_hist")

# ----------------------------------------------------------------------------- 사이드바 입력
with st.sidebar:
    st.markdown("## ✦ Event ON")
    st.caption("AI 기반 행사 설계·분석 플랫폼")
    st.markdown("### 📝 행사 정보")
    name = st.text_input("행사명", "2025 힐링 페스티벌")
    purpose = st.selectbox("행사 목적", list(PURPOSES))
    event_types=st.multiselect('행사 유형 (여러 개 선택 가능)',EVENT_TYPES,default=['페스티벌/공연'])
    auto_facilities=True
    st.caption('필수 구성 자동 포함: 응급·안내·화장실·수유·음수·운영·분리배출·미아보호·구급차 접근 등. 출입구·주차장은 별도 구성합니다.')
    st.caption('실내/야외는 아래 행사 장소 유형으로 결정합니다. 자동 구성은 기획용 추천이며 법적 필수시설 판정이 아닙니다.')
    c1, c2 = st.columns(2)
    budget = c1.number_input("예산(만원)", 500, 500000, 5000, step=500)
    visitors = c2.number_input("예상 방문객(명)", 200, 100000, 5000, step=500)
    venue = st.selectbox("행사 장소 유형", list(VENUES))
    shape = st.selectbox("행사장 모양", list(SHAPES), help="행사장 외곽 모양입니다. 모든 구역은 이 모양 안쪽에 배치되고, 출입구도 모양에 맞게 생성됩니다.")
    st.caption("▫️ " + SHAPES[shape]["desc"])
    location = st.text_input("행사장 위치", "야외 종합 운동장 & 잔디 광장")
    c3, c4 = st.columns(2)
    area = c3.number_input("면적(㎡)", 500, 1000000, 50000, step=1000)
    start_hour=c4.number_input('시작 시각',0,23,10)
    end_hour=c4.number_input('종료 시각',0,23,20)
    hours=f'{start_hour:02d}:00 ~ {end_hour:02d}:00'+(' (다음 날)' if end_hour<=start_hour else '')
    st.caption('🌙 야간 포함 시 야간·안전·비상 조명을 자동 구성합니다.' if ((end_hour-start_hour)%24 or 24)+start_hour>18 or start_hour<6 else '☀️ 주간 행사')
    mood = st.selectbox("원하는 분위기", list(MOODS))
    age = st.selectbox("예상 연령대", list(AGES))
    gates = st.selectbox("출입구 수", [2, 4, 6], index=1, format_func=lambda n: f"{n}개")
    n_cand = st.select_slider("탐색할 배치안 수", [500, 1000, 2000, 3000, 5000], value=2000)

    with st.expander("📐 구역 크기 조절 (100% = 기본)"):
        st.caption("바꾼 뒤 상단의 '✦ AI 설계 생성 / 재배치'를 누르면 반영됩니다. 구역이 너무 커서 들어가지 않으면 자동으로 줄이고 알려드립니다.")
        size_scale = {}
        for _t, _lab in [("stage", "🎭 공연장"), ("food", "🍔 푸드존"), ("booth", "🧪 체험부스"), ("rest", "🛋️ 휴게공간"),
                         ("medical", "🏥 응급의료센터"), ("info", "ℹ️ 안내센터"), ("restroom", "🚻 화장실"), ("custom", "⭐ 사용자 부스")]:
            size_scale[_t] = st.slider(_lab, 50, 200, 100, 5, format="%d%%", key=f"sz_{_t}") / 100.0
        if st.button("크기 모두 100%로 되돌리기"):
            for _t in size_scale:
                st.session_state[f"sz_{_t}"] = 100
            st.rerun()

    st.markdown("### ⭐ 원하는 부스 직접 입력")
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
    for i, c in enumerate(list(ss.custom)):
        a, b = st.columns([4, 1])
        a.caption(f"⭐ {c['name']} ({c['cat']}, {c['w']}×{c['h']}m) ×{c['count']}")
        if b.button("✕", key=f"del{i}"):
            ss.custom.pop(i)
            ss.pending = "부스 삭제"
            st.rerun()
    if ss.pins:
        st.markdown("### 📌 위치 제약")
        st.caption(" · ".join(ZONE_META[k]["label"] for k in ss.pins))
        if st.button("제약 모두 해제"):
            ss.pins = {}
            ss.pending = "위치 제약 해제"


def current_params():
    return dict(name=name, purpose=purpose, budget=int(budget), visitors=int(visitors), venue=venue,
                location=location, area_m2=int(area), hours=hours, mood=mood, age=age, gates=int(gates),
                shape=shape, size_scale=dict(size_scale),event_types=event_types,auto_facilities=auto_facilities,is_outdoor=VENUES[venue]["kind"]!="indoor",start_hour=int(start_hour),end_hour=int(end_hour))


def make_sig():
    return json.dumps(dict(p=current_params(), c=ss.custom, pins={k: list(v) for k, v in ss.pins.items()}, n=int(n_cand)),
                      sort_keys=True, ensure_ascii=False, default=str)


def render_evidence(R):
    """점수 산출 근거: 가중치 → 목표 점수 → 세부 지표 → 가정"""
    st.markdown("**① 종합 점수 = Σ (가중치 × 목표 점수)**")
    st.code(R["total_formula"], language=None)
    st.dataframe(pd.DataFrame([dict(
        목표=OBJ_LABEL[k], 기본가중치=f"{R['weight_detail'][k]['base'] * 100:.0f}%",
        행사목적보정=f"{R['weight_detail'][k]['purpose'] * 100:+.0f}%p", 연령대보정=f"{R['weight_detail'][k]['age'] * 100:+.0f}%p",
        최종가중치=f"{R['weight_detail'][k]['final'] * 100:.1f}%", 목표점수=round(R["scores"][k], 1)) for k in OBJECTIVES]),
        hide_index=True, use_container_width=True)
    st.markdown("**② 목표 점수 = Σ (세부점수 × 비중)** — 각 항은 `비중×세부점수`")
    for k in OBJECTIVES:
        st.markdown(f"- {OBJ_LABEL[k]}: `{R['formulas'][k]}`")
    st.markdown("**③ 세부 지표 — 측정값이 만점 기준에 가까울수록 100점, 0점 기준에 가까울수록 0점 (사이는 직선 보간)**")
    st.dataframe(pd.DataFrame([dict(
        목표=e["objLabel"], 세부지표=e["label"], 설계전=e["v_before"], 설계후=e["v_after"], 만점기준=e["best_txt"],
        영점기준=e["worst_txt"], 세부점수_후=round(e["sub_after"] * 100), 세부점수_전=round(e["sub_before"] * 100),
        비중=f"{e['w'] * 100:.0f}%", 산정근거=e["why"]) for e in R["evidence"]]), hide_index=True, use_container_width=True)
    st.markdown("**④ 구역별 실제 크기 (m)**")
    st.dataframe(pd.DataFrame([dict(구역=z["name"], 종류=z["type"], 가로_m=z["w_m"], 세로_m=z["h_m"]) for z in R["zone_sizes"]]),
                 hide_index=True, use_container_width=True, height=220)
    st.markdown("**⑤ 가정과 한계**")
    for a_ in R["assumptions"]:
        st.markdown(f"- {a_}")


def run_design(label):
    bar = st.progress(0.0, text="AI 설계 시작…")
    try:
        res = optimize(current_params(), ss.custom, ss.pins, n_candidates=int(n_cand),
                       progress=lambda f, m: bar.progress(min(1.0, f), text=m))
    except Exception as e:  # noqa
        bar.empty()
        st.error(f"설계 실패: {e}")
        return
    bar.empty()
    ss.history.append(dict(label=f"v{len(ss.history) + 1} · {label} ({dt.datetime.now():%H:%M:%S})", result=res, sig=make_sig()))
    ss.view = len(ss.history) - 1
    ss["hist_sel"] = ss.view          # 선택 상자를 새 설계안으로 이동 (이게 없으면 옛 화면이 계속 보임)


# ----------------------------------------------------------------------------- 헤더
st.markdown("""<div class="eo-head"><h1>🎪 Event ON</h1>
<p>행사 정보를 입력하면 AI가 수천 개 배치안을 생성·시뮬레이션하고, 다목적 최적화로 가장 안전하고 효율적인 행사장을 설계합니다.</p></div>""",
            unsafe_allow_html=True)

b1, b2 = st.columns([1, 4])
if b1.button("✦ AI 설계 생성 / 재배치", type="primary", use_container_width=True):
    ss.pending = "조건 입력 설계"
if not ss.history and not ss.pending:
    ss.pending = "기본 설계"
if ss.pending:
    _label, ss.pending = ss.pending, None
    run_design(_label)
    st.toast(f"✅ 새 설계안이 반영되었습니다 ({_label})")

tab_main, tab_wf, tab_xai, tab_rep = st.tabs(["📋 행사 설계 메인", "⚙️ 설계 프로세스 (Workflow)", "🧠 설계 이유 (XAI)", "📊 분석 리포트"])

# ----------------------------------------------------------------------------- 메인
with tab_main:
    if ss.history:
        labels = [h["label"] for h in ss.history]
        if ss.get("hist_sel") is None or ss["hist_sel"] >= len(labels):
            ss["hist_sel"] = len(labels) - 1
        ss.view = st.selectbox("📜 설계 히스토리", range(len(labels)), format_func=lambda i: labels[i], key="hist_sel")
        R = ss.history[ss.view]["result"]
        P = R["params"]
        if ss.history[ss.view].get("sig") != make_sig():
            st.warning("⚠️ 사이드바 입력값(행사장 모양·구역 크기·예산 등)이 지금 보이는 설계안과 다릅니다. 상단의 '✦ AI 설계 생성 / 재배치'를 눌러야 반영됩니다.")
        for n in R["notes"]:
            st.warning(n)

        m = st.columns(5)
        m[0].metric("행사", P["name"])
        m[1].metric("방문객", f"{P['visitors']:,}명")
        m[2].metric("면적 · 모양", f"{P['area_m2']:,}㎡", R["shape"]["name"], delta_color="off")
        m[3].metric("종합 점수", f"{R['total']:.1f}점", f"{R['total'] - R['before_total']:+.1f} vs 설계 전")
        m[4].metric("예상 비용", f"{R['cost']['total']:,.0f}만원", f"예산 {R['cost']['budget']:,}만원", delta_color="off")

        # ---- AI 어시스턴트
        st.markdown("##### 🤖 AI 어시스턴트 — 말로 배치를 바꾸거나 부스를 추가하세요")
        render_ai_editor(R)

        # ---- 디지털 트윈
        # The existing digital twin is now rendered in the bidirectional 3D editor above.

        # ---- 평가/비교
        c_a, c_b, c_c = st.columns([1.1, 1.1, 1])
        with c_a:
            st.markdown("##### 💡 AI 평가 결과")
            st.dataframe(pd.DataFrame([dict(항목=OBJ_LABEL[k], 설계전=round(R["before_scores"][k]), 설계후=round(R["scores"][k]),
                                           등급=grade(R["scores"][k])) for k in OBJECTIVES]), hide_index=True, use_container_width=True)
        with c_b:
            st.markdown("##### ⚖️ 설계 전 / 후 비교")
            d, b_ = R["detail"], R["before_detail"]
            st.dataframe(pd.DataFrame([
                ("병목 발생율", f"{b_['bottleneck']:.0f}%", f"{d['bottleneck']:.0f}%"),
                ("최대 군중 밀도", f"{b_['peak']:.2f}명/㎡", f"{d['peak']:.2f}명/㎡"),
                ("응급 최대 도달", fmt_sec(b_["t_max"]), fmt_sec(d["t_max"])),
                ("사고 위험구역", f"{b_['risk_zones']}개소", f"{d['risk_zones']}개소"),
            ], columns=["지표", "설계 전", "설계 후"]), hide_index=True, use_container_width=True)
        with c_c:
            st.markdown("##### 📄 요약")
            st.info(f"{R['stats']['generated']:,}개 배치안 중 종합 {R['total']:.1f}점 배치안 평가. "
                    f"응급 최대 도달 {fmt_sec(d['t_max'])}, 위험구역 {d['risk_zones']}개소.")

        with st.expander("📐 점수는 어떻게 계산됐나요? (산출 근거 보기)"):
            render_evidence(R)

# ----------------------------------------------------------------------------- 프로세스
with tab_wf:
    st.markdown("""
<div class="wf">
<div class="st"><div class="n">1</div><b>행사 정보 입력</b><span>목적·예산·방문객·장소·분위기·연령</span></div><div class="ar">›</div>
<div class="st"><div class="n">2</div><b>디지털 트윈 생성</b><span>구역·출입구·보행로 모델링</span></div><div class="ar">›</div>
<div class="st"><div class="n">3</div><b>수천 개 배치안 생성</b><span>무작위 샘플링 + 상위안 변이</span></div><div class="ar">›</div>
<div class="st"><div class="n">4</div><b>군중 시뮬레이션</b><span>이동 동선·혼잡도 예측</span></div><div class="ar">›</div>
<div class="st"><div class="n">5</div><b>다목적 최적화</b><span>안전·동선·접근·혼잡·공간</span></div><div class="ar">›</div>
<div class="st"><div class="n">6</div><b>배치안 평가 + XAI</b><span>설계 이유 설명</span></div><div class="ar">›</div>
<div class="st"><div class="n">7</div><b>결과 제공</b><span>배치도·리포트·전/후 비교</span></div>
</div>""", unsafe_allow_html=True)
    if ss.history:
        R = ss.history[ss.view]["result"]
        s = R["stats"]
        c = st.columns(4)
        c[0].metric("생성·평가한 배치안", f"{s['generated']:,}개")
        c[1].metric("무작위 / 변이", f"{s['randomly']:,} / {s['mutated']:,}")
        c[2].metric("파레토 최적해", f"{s['pareto']}개")
        c[3].metric("배치 구역 수", f"{s['zones']}개")
        st.markdown("##### 후보 배치안 분포 (점이 위·오른쪽일수록 우수)")
        if R["cloud"]:
            st.scatter_chart(pd.DataFrame(R["cloud"]).rename(columns={"safety": "비상 안전성", "cong": "혼잡도 분산"}),
                             x="비상 안전성", y="혼잡도 분산", color="total", height=340)
        else:
            st.caption("직접 편집한 설계에는 후보군 순위와 분포를 표시하지 않습니다.")
        st.caption("가중치: " + " · ".join(f"{OBJ_LABEL[k]} {R['weights'][k] * 100:.0f}%" for k in OBJECTIVES))

# ----------------------------------------------------------------------------- XAI
with tab_xai:
    if ss.history:
        R = ss.history[ss.view]["result"]
        X = R["xai"]
        st.markdown("#### 왜 이 배치인가요?")
        for t in X["reasons"]:
            st.markdown(f"- {t}")
        st.markdown("#### 목표별 기여도")
        st.dataframe(pd.DataFrame([dict(목표=c["label"], 가중치=f"{c['weight'] * 100:.0f}%", 점수=round(c["score"], 1),
                                       종합기여=round(c["contribution"], 1), 후보중상위=f"{max(0.1, 100 - c['pct_rank']):.0f}%",
                                       후보평균대비=f"{c['vs_mean']:+.1f}") for c in X["contrib"]]),
                     hide_index=True, use_container_width=True)
        st.bar_chart(pd.DataFrame({"종합 기여": {c["label"]: c["contribution"] for c in X["contrib"]}}))
        st.markdown("#### 점수는 어떻게 계산됐나요? (산출 근거)")
        render_evidence(R)
        st.markdown("#### 구역별 배치 근거")
        for z in X["zone_reasons"]:
            st.markdown(f"- {z['icon']} **{z['name']}** — {z['text']}")
        if X["alternatives"]:
            st.markdown("#### 검토했으나 채택하지 않은 대안")
            for a in X["alternatives"]:
                st.markdown(f"- **{a['name']}** (종합 {a['total']:.1f}점): {a['note']}")

# ----------------------------------------------------------------------------- 리포트
with tab_rep:
    if ss.history:
        R = ss.history[ss.view]["result"]
        rep_html = build_report_html(R)
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ 보고서(HTML)", rep_html, file_name="event_on_report.html", mime="text/html")
        d2.download_button("⬇️ 보고서(Markdown)", build_markdown(R), file_name="event_on_report.md", mime="text/markdown")
        st.caption("PDF 저장: 아래 보고서 위쪽의 [PDF로 저장] 버튼을 누르고 '대상: PDF로 저장'을 선택한다.")
        components.html(rep_html, height=900, scrolling=True)
    else:
        st.info("먼저 [행사 설계 메인]에서 설계를 실행하면 보고서가 만들어진다.")
        
