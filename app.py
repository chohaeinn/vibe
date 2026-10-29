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

TWIN_TEMPLATE = '\n<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">\n<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n<style>\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Pretendard,-apple-system,system-ui,sans-serif;background:transparent;color:#0f172a}\n.bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px}\nbutton{cursor:pointer;border:1px solid #cbd5e1;background:#f1f5f9;color:#334155;padding:6px 11px;border-radius:8px;font-size:12px;font-weight:700;font-family:inherit}\nbutton:hover{background:#e2e8f0}\nbutton.on{background:#2563eb;color:#fff;border-color:#1d4ed8}\nbutton.warn.on{background:#f59e0b;border-color:#d97706}\nbutton.danger.on{background:#ef4444;border-color:#dc2626}\n.badge{font-size:11px;font-weight:700;color:#2563eb;background:#eff6ff;padding:3px 9px;border-radius:12px}\n.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:12px}\n.card h4{font-size:13px;font-weight:800;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}\n.wrap{position:relative;width:100%;background:#1e293b;border-radius:10px;overflow:hidden}\n#wrap{aspect-ratio:1.85}\n#wrap2{aspect-ratio:1.6}\n.wrap canvas,.wrap .c3{position:absolute;inset:0;width:100%;height:100%}\n.c3{cursor:grab;background:#dbe8f5}\n.legend{position:absolute;left:8px;bottom:8px;background:rgba(255,255,255,.93);border-radius:8px;padding:6px 10px;font-size:11px;font-weight:700;display:grid;grid-template-columns:repeat(3,auto);gap:3px 12px;z-index:5;pointer-events:none}\n.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px}\n.hint{position:absolute;right:8px;top:8px;background:rgba(15,23,42,.65);color:#fff;font-size:10.5px;padding:4px 9px;border-radius:8px;z-index:5;pointer-events:none}\n.tl{display:flex;align-items:center;gap:8px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:6px 10px;margin-bottom:8px;font-size:12px;font-weight:700;flex-wrap:wrap}\n.tl input{flex:1;min-width:120px;accent-color:#2563eb}\n.tm{background:#2563eb;color:#fff;border-radius:16px;padding:2px 10px;font-size:12px;min-width:56px;text-align:center}\n.grid2{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:12px;margin-top:12px}\n@media(max-width:900px){.grid2{grid-template-columns:1fr}}\n.kpi{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:10px}\n.kpi div{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;font-size:11px;color:#64748b;font-weight:700}\n.kpi b{display:block;font-size:17px;color:#0f172a}\n.hl{font-size:11px;color:#64748b;font-weight:700;display:flex;justify-content:space-around;margin-top:6px}\n.zl{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:5px;font-size:11px;font-weight:700;max-height:190px;overflow:auto}\n.zl span{background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid var(--c);border-radius:6px;padding:4px 7px}\n\nbody{background:#f3f6fa;color:#172b46;padding:12px}\n.bar{background:#fff;padding:10px;border:1px solid #e2e8f0;border-radius:12px}\nbutton{background:#fff;border-color:#e3e9f1;border-radius:6px;font-size:11px}\nbutton.on{background:#173c72;border-color:#173c72}.card{border:1px solid #e2e8f0;box-shadow:0 3px 15px #1e3a5f08}\n#studio{display:grid;grid-template-columns:205px minmax(0,1fr);gap:14px;align-items:stretch}\n#explorer{background:white;border:1px solid #e2e8f0;border-radius:14px;padding:14px;max-height:720px;overflow:auto}\n#explorer h3{font-size:15px;margin:0 0 4px}#explorer p{font-size:11px;color:#789;margin-bottom:14px}\n#facilitySearch{width:100%;padding:9px;border:1px solid #dbe3ee;border-radius:7px;margin-bottom:12px}\n.explorerItem{display:block;width:100%;text-align:left;padding:10px 6px;margin:2px 0;border:0;border-bottom:1px solid #f1f5f9;font-weight:500}\n.explorerItem:hover{background:#eff6ff}#wrap{aspect-ratio:1.45;background:#edf2f7}.c3{background:#edf2f7}\n.grid2{margin-top:14px}.hint{background:#173c72cc}#facilityPopup{border-top:4px solid #2563eb!important}\n@media(max-width:760px){#studio{grid-template-columns:1fr}#explorer{max-height:180px}.explorerItem{display:inline-block;width:auto}}\n\nbody{background:#e9eee6;padding:16px;color:#283e35}\n#studio{grid-template-columns:190px minmax(0,1fr);gap:16px}\n#wrap{aspect-ratio:1.23;border-radius:18px;background:#edf0e9}\n.card{padding:16px;border:0;border-radius:22px;box-shadow:0 12px 35px #34493812}\n#explorer{border:0;border-radius:20px;background:#fafbf7;max-height:950px}\nbutton.on{background:#365e4a;border-color:#365e4a}.bar{border:0;background:#fafbf7}\n.campusHeader{display:flex;justify-content:space-between;align-items:center;margin:0 0 14px;padding:18px 22px;background:#263f35;color:#fff;border-radius:18px}\n.campusHeader strong{font-size:20px;letter-spacing:1px}.campusHeader small{display:block;font-size:11px;color:#cad9c9;margin-top:5px}\n@media(max-width:760px){#studio{grid-template-columns:1fr}#wrap{aspect-ratio:1}#explorer{max-height:180px}.campusHeader strong{font-size:15px}}\n</style></head><body><header class="campusHeader"><div><strong>EVENT ON · FESTIVAL CAMPUS</strong><small>부스 선택 · 현장 편집 · 시설 안내</small></div><div style="font-size:11px;text-align:right">전체 공간 재구성<br><b>DESIGN R4</b></div></header><div class="bar"><b>카메라</b><button onclick="campusCamera(\'isometric\')">전체 모형</button><button onclick="campusCamera(\'front\')">정면 관람</button><button onclick="campusCamera(\'plan\')">배치 확인</button><span style="font-size:11px;color:#647564">모형 길은 안내용이며 안전 검증 경로가 아닙니다.</span></div>\n<div class="bar">\n  <button id="bMode" class="on" onclick="setMode(\'after\')">✦ AI 최적 배치</button>\n  <button id="bModeB" onclick="setMode(\'before\')">설계 전(기존) 배치</button>\n  <span style="width:10px"></span>\n  <button id="b3d" class="on" onclick="setView(true)">🧊 3D 입체 설계도</button>\n  <button id="b2d" onclick="setView(false)">🗺️ 2D 평면도</button>\n  <button id="bHeat3" onclick="togHeat3()">🔥 히트맵 겹치기</button>\n  <button id="bDome" class="on" onclick="togDome()" style="display:none">🏛️ 지붕 표시</button>\n  <span style="flex:1"></span>\n  <button id="bPlay" onclick="togSim()">⏸ 시뮬레이션 정지</button>\n  <button id="bEmg" class="danger" onclick="togEmg()">🚨 응급환자 발생</button>\n</div>\n<div class="bar"><label>척도 <input type="range" min="0.6" max="3.2" step="0.1" value="1.5" oninput="zoom3=+this.value"></label>\n<label>사람 속도 <input type="range" min="0.1" max="1.5" step="0.1" value="0.5" oninput="crowdSpeed=+this.value"></label>\n<label>구급차 속도 <input type="range" min="0.1" max="1.5" step="0.1" value="0.4" oninput="ambulanceSpeed=+this.value"></label>\n<button onclick="peopleOn=!peopleOn">사람 전체 ON/OFF</button><button onclick="evacuatePeople()">사람들 탈출 시뮬레이션</button>\n<button onclick="evacuating=false;initAgents();sim=true">탈출 초기화</button><button onclick="whitePaths=!whitePaths;buildScene3()">하얀 길 ON/OFF</button></div>\n<div class="bar" id="editbar">\n<button id="editToggle" onclick="toggleEdit()">✋ 3D 편집 모드 OFF</button>\n<button onclick="deleteSelected()">선택 삭제</button><button onclick="undoEdit()">이전 조작 취소</button>\n<button onclick="save3Edit()">💾 3D 편집 저장</button>\n<button onclick="showRoute(\'exit\')">비상구·대피 경로 후보</button><button onclick="showRoute(\'accessible\')">배리어프리 경로 후보</button>\n<button onclick="clearRoutes()">경로 숨기기</button><span id="editStatus">저장 전 변경은 점수에 반영되지 않습니다.</span></div>\n<div class="tl">⏰ 시간대\n  <button id="bTl" onclick="togTl()">▶ 재생</button>\n  <input type="range" id="tSl" min="10" max="20" step="1" value="14" oninput="setTime(+this.value)">\n  <span class="tm" id="tTxt">14:00</span><span id="tDesc" style="color:#64748b;font-weight:600"></span>\n</div>\n<div id="studio"><aside id="explorer"><h3>시설 라이브러리</h3><p>시설 선택 · 위치 확인 · 상세 정보</p><input id="facilitySearch" placeholder="시설 이름 검색" oninput="populateExplorer()"><div id="facilityExplorer"></div><p style="margin-top:18px">행사장 경계 바깥에 외부 주차장을 별도로 표시합니다.</p></aside><main><div class="card"><h4><span>🗺️ 행사장 디지털 트윈 <span id="verTxt" style="color:#64748b;font-weight:600"></span></span>\n  <span><span class="badge" id="peopleTxt"></span> <span class="badge" id="status">실시간 군중 시뮬레이션</span></span></h4>\n  <div class="wrap" id="wrap">\n    <canvas id="cv" style="display:none"></canvas><canvas id="hm" style="display:none;opacity:.75;pointer-events:none"></canvas><canvas id="pp" style="display:none;pointer-events:none"></canvas>\n    <div class="c3" id="c3"></div>\n<div id="facilityPopup" style="display:none;position:absolute;z-index:30;width:290px;max-width:calc(100% - 16px);max-height:75%;overflow:auto;background:rgba(255,255,255,.98);border:1px solid #cbd5e1;border-radius:12px;padding:14px;box-shadow:0 8px 28px #0f172a33;font-size:12px;line-height:1.6;cursor:default">\n<button id="closeFacilityPopup" style="float:right;padding:0 6px" aria-label="시설 정보 닫기">×</button><div id="facilityInfo"></div></div>\n    <div class="legend" id="legend"></div>\n    <div class="hint" id="hint">드래그: 회전 · 휠: 확대/축소</div>\n  </div>\n</div>\n</main></div><div class="grid2">\n  <div class="card"><h4><span>🔥 실시간 군중 밀집도</span><span class="badge" id="envTxt">일반 상태</span></h4>\n    <div class="wrap" id="wrap2"><canvas id="hm2"></canvas></div>\n    <div class="hl"><span style="color:#10b981">🟢 원활</span><span style="color:#eab308">🟡 보통(0.25~)</span><span style="color:#f97316">🟠 혼잡(0.5~)</span><span style="color:#ef4444">🔴 위험(0.9~)</span></div>\n    <div style="font-size:10px;color:#94a3b8;margin-top:4px;text-align:center">단위: 명/㎡ · 구역 체류 + 출입구 이동 군중 반영</div>\n  </div>\n  <div class="card"><h4><span>📊 현재 상태</span></h4>\n    <div class="kpi">\n      <div>현재 최대 밀도<b id="kPeak">-</b></div><div>혼잡 구역 비율<b id="kBott">-</b></div>\n      <div>응급 최대 도달<b id="kMed">-</b></div><div>위험 구역<b id="kRisk">-</b></div>\n    </div>\n    <div style="font-size:12px;font-weight:800;margin:6px 0">📍 배치된 구역 <span id="zCnt" style="color:#64748b"></span></div>\n    <div class="zl" id="zlist" style="display:none"></div>\n  </div>\n</div>\n<script>\nconst D = __DATA__;\nconst WW=160, WH=100, GX=40, GY=25;\nconst WEATHER_DISABLED=true;\nlet mode=\'after\', sim=true, rain=false, emg=null, tHour=14, tlTimer=null, is3d=true, heat3=false;\nconst $=id=>document.getElementById(id);\nconst cv=$(\'cv\'), hm=$(\'hm\'), pp=$(\'pp\'), hm2=$(\'hm2\');\nconst cx=cv.getContext(\'2d\'), hx=hm.getContext(\'2d\'), px=pp.getContext(\'2d\'), h2=hm2.getContext(\'2d\');\nconst wrap=$(\'wrap\'), wrap2=$(\'wrap2\');\nlet W=0,H=0,S=1,W2=0,H2=0;\nconst Z=()=> mode===\'after\'?D.zones:D.before_zones;\nconst mpu=D.mpu, cellArea=(WW/GX)*(WH/GY)*mpu*mpu;\nconst SHB=D.shape.bbox, SHC=[(SHB[0]+SHB[2])/2,(SHB[1]+SHB[3])/2];\nfunction outlinePath(c,sx,sy){ const o=D.shape.outline; c.beginPath(); o.forEach((p,i)=>{ if(i) c.lineTo(p[0]*sx,p[1]*sy); else c.moveTo(p[0]*sx,p[1]*sy); }); c.closePath(); }\nfunction pieces(step){ const o=D.shape.outline, out=[]; for(let i=0;i<o.length;i++){ const a=o[i], b=o[(i+1)%o.length]; const dx=b[0]-a[0], dy=b[1]-a[1], L=Math.hypot(dx,dy), n=Math.max(1,Math.round(L/step));\n  for(let k=0;k<n;k++){ const t0=k/n,t1=(k+1)/n; const x0=a[0]+dx*t0,y0=a[1]+dy*t0,x1=a[0]+dx*t1,y1=a[1]+dy*t1; out.push({x:(x0+x1)/2,y:(y0+y1)/2,len:Math.hypot(x1-x0,y1-y0),ang:Math.atan2(dy,dx)}); } } return out; }\nfunction insideShape(x,y){ const o=D.shape.outline; let ins=false; for(let i=0,j=o.length-1;i<o.length;j=i++){ const xi=o[i][0],yi=o[i][1],xj=o[j][0],yj=o[j][1]; if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi)) ins=!ins; } return ins; }\nfunction mv(a,nx,ny){ if(D.shape.kind!==\'poly\'||insideShape(nx,ny)||!insideShape(a.x,a.y)){a.x=nx;a.y=ny;} else if(insideShape(nx,a.y)){a.x=nx;} else if(insideShape(a.x,ny)){a.y=ny;} else { a.x+=(SHC[0]-a.x)*.03; a.y+=(SHC[1]-a.y)*.03; } }\nfunction treePos(pc){ const vx=SHC[0]-pc.x, vy=SHC[1]-pc.y, vl=Math.hypot(vx,vy)||1; return [pc.x+vx/vl*3.5, pc.y+vy/vl*3.5]; }\nconst NAG=320; let agents=[]; let raindrops=[];\nlet heat=new Float32Array(GX*GY);\n\n$(\'legend\').innerHTML=\n [[\'#8b5cf6\',\'공연장\'],[\'#3b82f6\',\'체험부스\'],[\'#f59e0b\',\'푸드존\'],[\'#10b981\',\'휴게공간\'],[\'#ef4444\',\'응급의료\'],[\'#0ea5e9\',\'안내센터\'],[\'#06b6d4\',\'화장실\'],[\'#ec4899\',\'사용자 부스\'],[\'#1e293b\',\'출입구\']]\n .map(a=>`<span><i style="background:${a[0]}"></i>${a[1]}</span>`).join(\'\');\n\nfunction resize(){\n  W=wrap.clientWidth; H=wrap.clientHeight; S=W/WW;\n  [cv,hm,pp].forEach(c=>{c.width=W;c.height=H});\n  W2=wrap2.clientWidth; H2=wrap2.clientHeight; hm2.width=W2; hm2.height=H2;\n  drawBase(); if(R3){ size3(); }\n}\nfunction factor(h){ if(h<12)return .55; if(h<15)return 1.0; if(h<18)return .8; return .65; }\nfunction descT(h){ return h<12?\'개장 초반 - 순차 입장(여유)\':h<15?\'피크 - 푸드·공연 집중(혼잡)\':h<18?\'오후 - 체험·휴게 분산\':\'폐장 전 - 공연 집중 및 퇴장\'; }\nfunction pickZone(){\n  const Zs=Z(); let tot=0; const w=Zs.map(z=>{const a=(z.type===\'medical\')?0:z.attract*(z.type===\'stage\'&&tHour>=18?1.5:1)*(z.type===\'food\'&&tHour>=12&&tHour<15?1.5:1);tot+=a;return a});\n  let r=Math.random()*tot; for(let i=0;i<Zs.length;i++){ r-=w[i]; if(r<=0) return i; } return 0;\n}\nfunction spawn(a){\n  const g=D.gates[Math.floor(Math.random()*D.gates.length)];\n  let sx=g.x,sy=g.y; for(let k=0;k<12;k++){ const tx=g.x+(Math.random()-.5)*6, ty=g.y+(Math.random()-.5)*6; if(insideShape(tx,ty)){sx=tx;sy=ty;break;} } a.x=sx; a.y=sy; a.leaving=false; a.dwell=0; a.zone=pickZone(); setTarget(a);\n}\nfunction setTarget(a){\n  const z=Z()[a.zone]; a.tx=z.x-1.5+Math.random()*(z.w+3); a.ty=z.y-1.5+Math.random()*(z.h+3);\n  a.sp=.28+Math.random()*.2;\n}\nfunction initAgents(){\n  agents=[]; for(let i=0;i<NAG;i++){ const a={}; spawn(a); const t=Math.random(); a.x=a.x+(a.tx-a.x)*t; a.y=a.y+(a.ty-a.y)*t; a.active=i<NAG*factor(tHour); agents.push(a);}\n  raindrops=[]; for(let i=0;i<110;i++) raindrops.push({x:Math.random()*W,y:Math.random()*H,l:7+Math.random()*10,v:6+Math.random()*6});\n}\nfunction step(dt){\n  const f=factor(tHour); const n=Math.floor(NAG*f);\n  agents.forEach((a,i)=>{ a.active=i<n&&!a.evacuated; if(!a.active) return;\n    if(a.dwell>0){ a.dwell-=dt; a.x+=(Math.random()-.5)*.06; a.y+=(Math.random()-.5)*.06;\n      if(a.dwell<=0){ if(Math.random()<.35){ a.leaving=true; const g=D.gates[Math.floor(Math.random()*D.gates.length)]; a.tx=g.x; a.ty=g.y; } else { a.zone=pickZone(); setTarget(a);} } return; }\n    let dx=a.tx-a.x, dy=a.ty-a.y, d=Math.hypot(dx,dy);\n    let sp=a.sp*crowdSpeed;\n    if(emg){ const ex=a.x-emg.x, ey=a.y-emg.y, ed=Math.hypot(ex,ey); if(ed<9&&ed>0){ a.x+=ex/ed*.5; a.y+=ey/ed*.5; } }\n    if(d<1.2){ if(a.leaving){ if(evacuating){a.evacuated=true;a.active=false}else spawn(a);} else { a.dwell=3+Math.random()*9; } }\n    else { mv(a,a.x+dx/d*sp,a.y+dy/d*sp); }\n  });\n  for(let i=0;i<agents.length;i+=2){ const a=agents[i]; if(!a.active) continue; const b=agents[(i*7+3)%agents.length]; if(!b.active) continue;\n    const dx=a.x-b.x, dy=a.y-b.y, d=Math.hypot(dx,dy); if(d>0&&d<1.2){ a.x+=dx/d*.1; a.y+=dy/d*.1; } }\n  if(emg){ const meds=Z().filter(z=>z.type===\'medical\'); let best=null,bd=1e9;\n    meds.forEach(m=>{const d=Math.hypot(m.x+m.w/2-emg.x,m.y+m.h/2-emg.y); if(d<bd){bd=d;best=m;}});\n    emg.target=best;\n    if(best&&bd>1.5){ emg.x+=(best.x+best.w/2-emg.x)/bd*.9*ambulanceSpeed; emg.y+=(best.y+best.h/2-emg.y)/bd*.9*ambulanceSpeed;\n      $(\'status\').textContent=\'🚑 응급 이송 중… 의료센터까지 \'+(bd*mpu).toFixed(0)+\'m\';\n    } else if(best){ $(\'status\').textContent=\'✅ 의료센터 도착 · 이송 소요 \'+Math.round((performance.now()-emg.t0)/1000)+\'초(시뮬레이션)\'; } }\n  raindrops.forEach(r=>{r.y+=r.v;r.x-=1;if(r.y>H){r.y=0;r.x=Math.random()*W}});\n}\nfunction updateHeat(){\n  const n=Math.floor(NAG*factor(tHour)); const per=D.params.visitors*.5/Math.max(1,n)*factor(tHour);\n  const g=new Float32Array(GX*GY);\n  agents.forEach(a=>{ if(!a.active) return; const ix=Math.min(GX-1,Math.max(0,Math.floor(a.x/(WW/GX)))), iy=Math.min(GY-1,Math.max(0,Math.floor(a.y/(WH/GY)))); g[iy*GX+ix]+=per; });\n  const o=new Float32Array(GX*GY);\n  for(let y=0;y<GY;y++)for(let x=0;x<GX;x++){ let s=0,c=0; for(let j=-1;j<=1;j++)for(let i=-1;i<=1;i++){const xx=x+i,yy=y+j; if(xx>=0&&xx<GX&&yy>=0&&yy<GY){const w=(i==0&&j==0)?2:1; s+=g[yy*GX+xx]*w; c+=w;}} o[y*GX+x]=s/c/cellArea; }\n  for(let k=0;k<o.length;k++) heat[k]=heat[k]*.85+o[k]*.15;\n}\nfunction heatColor(d){ if(d<.12) return null; if(d<.25) return \'rgba(16,185,129,.5)\'; if(d<.5) return \'rgba(234,179,8,.65)\'; if(d<.9) return \'rgba(249,115,22,.75)\'; return \'rgba(239,68,68,.88)\'; }\nfunction drawHeat(ctx,w,h,bg){\n  ctx.clearRect(0,0,w,h);\n  if(bg){ ctx.fillStyle=\'#020617\'; ctx.fillRect(0,0,w,h); ctx.save(); outlinePath(ctx,w/WW,h/WH); ctx.fillStyle=\'#0f172a\'; ctx.fill(); ctx.restore(); }\n  const cw=w/GX, ch=h/GY; let peak=0,hot=0,act=0;\n  ctx.save(); outlinePath(ctx,w/WW,h/WH); ctx.clip();\n  for(let y=0;y<GY;y++)for(let x=0;x<GX;x++){ const d=heat[y*GX+x]; peak=Math.max(peak,d); if(d>=.12) act++; if(d>=.5) hot++; const c=heatColor(d); if(c){ ctx.fillStyle=c; ctx.fillRect(x*cw,y*ch,cw+.5,ch+.5);} }\n  ctx.restore();\n  if(bg){ outlinePath(ctx,w/WW,h/WH); ctx.strokeStyle=\'#94a3b8\'; ctx.lineWidth=2; ctx.stroke();\n    Z().forEach(z=>{ ctx.strokeStyle=\'rgba(255,255,255,.45)\'; ctx.lineWidth=1; ctx.strokeRect(z.x*w/WW,z.y*h/WH,z.w*w/WW,z.h*h/WH);\n      ctx.fillStyle=\'rgba(255,255,255,.85)\'; ctx.font=\'bold 10px Pretendard,sans-serif\'; ctx.textAlign=\'center\';  }); }\n  return [peak,hot,act];\n}\n/* ---------- 2D 평면도 ---------- */\nfunction drawBase(){\n  const T=D.theme; cx.clearRect(0,0,W,H);\n  cx.fillStyle=\'#334155\'; cx.fillRect(0,0,W,H);\n  cx.save(); outlinePath(cx,S,S); cx.clip();\n  cx.fillStyle=rain?T.groundRain:T.ground; cx.fillRect(0,0,W,H);\n  if(T.kind===\'outdoor\'&&!D.shape.dome){ cx.fillStyle=\'rgba(0,0,0,.14)\'; pieces(9).forEach(pc=>{ const t=treePos(pc); cx.beginPath(); cx.arc(t[0]*S,t[1]*S,11,0,7); cx.fill(); }); }\n  else { cx.strokeStyle=\'rgba(0,0,0,.12)\'; cx.lineWidth=1; for(let x=0;x<W;x+=W/16){cx.beginPath();cx.moveTo(x,0);cx.lineTo(x,H);cx.stroke();} for(let y=0;y<H;y+=H/10){cx.beginPath();cx.moveTo(0,y);cx.lineTo(W,y);cx.stroke();} }\n  cx.restore();\n  outlinePath(cx,S,S); cx.strokeStyle=\'#f8fafc\'; cx.lineWidth=D.shape.dome?3:5; cx.stroke();\n  if(D.shape.dome){ cx.save(); cx.setLineDash([8,6]); cx.strokeStyle=\'rgba(255,255,255,.55)\'; cx.lineWidth=1.5; cx.beginPath(); cx.ellipse(SHC[0]*S,SHC[1]*S,(SHB[2]-SHB[0])/2*S*.94,(SHB[3]-SHB[1])/2*S*.94,0,0,7); cx.stroke(); cx.restore(); }\n  cx.strokeStyle=T.path; cx.globalAlpha=.6; cx.lineCap=\'round\'; cx.lineWidth=Math.max(4,S*1.6);\n  Z().forEach(z=>{ const g=nearestGate(z); cx.beginPath(); cx.moveTo(g.x*S,g.y*S); cx.lineTo((z.x+z.w/2)*S,(z.y+z.h/2)*S); cx.stroke(); });\n  cx.globalAlpha=1;\n  Z().forEach(z=>{ const x=z.x*S,y=z.y*S,w=z.w*S,h=z.h*S;\n    cx.fillStyle=\'rgba(0,0,0,.28)\'; cx.fillRect(x+3,y+3,w,h);\n    cx.fillStyle=z.color; cx.beginPath(); cx.roundRect(x,y,w,h,7); cx.fill(); cx.strokeStyle=\'#fff\'; cx.lineWidth=2; cx.stroke();\n    cx.textAlign=\'center\'; cx.fillStyle=\'#fff\';\n    cx.font=Math.max(14,Math.min(26,h*.4))+\'px sans-serif\'; cx.fillText(z.icon,x+w/2,y+h/2-2);\n    cx.font=\'bold \'+Math.max(11,Math.min(15,w/6.5))+\'px Pretendard,sans-serif\'; cx.shadowColor=\'rgba(0,0,0,.6)\'; cx.shadowBlur=3;\n     cx.shadowBlur=0; });\n  D.gates.forEach(g=>{ cx.fillStyle=\'#1e293b\'; cx.beginPath(); cx.arc(g.x*S,g.y*S,10,0,7); cx.fill(); cx.strokeStyle=\'#fff\'; cx.lineWidth=2; cx.stroke();\n    cx.fillStyle=\'#fff\'; cx.font=\'12px sans-serif\'; cx.textAlign=\'center\'; cx.fillText(\'🚪\',g.x*S,g.y*S+4);\n    const up=g.y>SHC[1]; cx.font=\'bold 11px Pretendard\'; cx.fillStyle=\'#fff\'; cx.shadowColor=\'#000\'; cx.shadowBlur=3; cx.fillText(g.name,g.x*S,g.y*S+(up?-15:24)); cx.shadowBlur=0; });\n}\nfunction nearestGate(z){ let b=D.gates[0],bd=1e9; D.gates.forEach(g=>{const d=Math.hypot(g.x-(z.x+z.w/2),g.y-(z.y+z.h/2)); if(d<bd){bd=d;b=g;}}); return b; }\nfunction drawPeople(){ px.clearRect(0,0,W,H); if(!peopleOn)return;\n  agents.forEach(a=>{ if(!a.active) return; px.fillStyle=\'#fff\'; px.strokeStyle=\'rgba(0,0,0,.4)\'; px.lineWidth=.8; px.beginPath(); px.arc(a.x*S,a.y*S,3.2,0,7); px.fill(); px.stroke(); });\n  if(emg){ px.strokeStyle=\'#ef4444\'; px.lineWidth=3; px.setLineDash([6,5]);\n    if(emg.target){ px.beginPath(); px.moveTo(emg.x*S,emg.y*S); px.lineTo((emg.target.x+emg.target.w/2)*S,(emg.target.y+emg.target.h/2)*S); px.stroke(); }\n    px.setLineDash([]); px.fillStyle=\'#ef4444\'; px.beginPath(); px.arc(emg.x*S,emg.y*S,9+Math.sin(performance.now()/120)*2,0,7); px.fill();\n    px.fillStyle=\'#fff\'; px.font=\'bold 12px Pretendard\'; px.textAlign=\'center\'; px.fillText(\'🚑 응급\',emg.x*S,emg.y*S-14); }\n}\nfunction supportIcon(z){const n=z.name;if(/대피소/.test(n))return \'🛟\';if(/흡연/.test(n))return \'🚬\';if(/수유/.test(n))return \'🍼\';if(/화장실/.test(n))return \'🚻\';if(/의료|응급|안전관리/.test(n))return \'➕\';if(/음수/.test(n))return \'🚰\';if(/소방|화재/.test(n))return \'🧯\';if(/안내|분실물/.test(n))return \'ℹ\';if(/쓰레기|분리수거|분리배출/.test(n))return \'♻\';if(/미아/.test(n))return \'🧒\';if(/조명/.test(n))return \'💡\';if(/충전/.test(n))return \'🔋\';return null}\nfunction iconSprite(icon){const can=document.createElement(\'canvas\');can.width=128;can.height=128;const t=can.getContext(\'2d\');t.fillStyle=\'white\';t.beginPath();t.arc(64,64,54,0,7);t.fill();t.lineWidth=5;t.strokeStyle=\'#2563eb\';t.stroke();t.font=\'62px sans-serif\';t.textAlign=\'center\';t.textBaseline=\'middle\';t.fillStyle=\'#17324d\';t.fillText(icon,64,65);const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(can),depthTest:false}));sp.scale.set(7,7,1);sp.renderOrder=15;return sp}\nfunction buildCustom(g,z,w,h){let n=z.name,c=z.color;\n if(/조리|푸드|음식|식사/.test(n)){bx(g,w*.9,3,h*.5,\'#f8fafc\',0,1.5,-h*.2);for(let i=0;i<6;i++)bx(g,w/6,.35,h*.7,i%2?\'#fff\':\'#f59e0b\',-w/2+w/12+i*w/6,5,0);bx(g,w*.7,1,h*.25,\'#334155\',0,1,h*.25);}\n else if(/경기장/.test(n)){bx(g,w,.2,h,\'#2d9a68\',0,.2,0);const p=[[-w*.44,-h*.43],[w*.44,-h*.43],[w*.44,h*.43],[-w*.44,h*.43],[-w*.44,-h*.43]].map(a=>new THREE.Vector3(a[0],.4,a[1]));g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(p),new THREE.LineBasicMaterial({color:\'#fff\'})));bx(g,.18,.1,h*.86,\'white\',0,.4,0);}\n else if(/반려|급수|배변|동물/.test(n)){bx(g,w,.3,h,\'#c5e5bc\',0,.3,0);[-1,1].forEach(a=>bx(g,w,.8,.3,\'#eee2c8\',0,.7,a*h/2));cyl(g,1,1,.3,\'#60a5fa\',0,.7,0);cone(g,2,2,\'#be9067\',-w*.2,2,-h*.2);}\n else if(/대기실|스태프|통제실|창고|방송|조정실|기록실|심판실/.test(n)){bx(g,w*.95,4,h*.85,\'#f8fafc\',0,2,0);bx(g,w,.4,h*.9,\'#334155\',0,4.2,0);bx(g,w*.35,2,.2,\'#93c5fd\',-w*.2,2,h*.43);bx(g,w*.2,3,.22,\'#64748b\',w*.25,1.5,h*.43);}\n else if(D.theme.kind!==\'indoor\'){\n const idx=z.id%5,c=[\'#ef4444\',\'#3b82f6\',\'#f59e0b\',\'#8b5cf6\',\'#10b981\'][idx];\n [-1,1].forEach(a=>[-1,1].forEach(b=>cyl(g,.16,.16,4.6,\'#f8fafc\',a*w*.43,2.3,b*h*.42)));\n bx(g,w,.5,h,c,0,4.8,0);const roof=new THREE.Mesh(new THREE.ConeGeometry(1,2,4),M(c));roof.rotation.y=Math.PI/4;roof.scale.set(w*.68,1,h*.68);roof.position.y=5.8;g.add(roof);\n for(let k=0;k<6;k++)bx(g,w/6,.6,.5,k%2?\'#fff\':c,-w/2+w/12+k*w/6,4.4,h/2);\n bx(g,w*.8,1.4,h*.22,\'#fff7ed\',0,1,h*.28);\n }else{ // Open-front modular exhibition shell, counter and display wall.\n bx(g,w,.25,h,\'#dce8f8\',0,.3,0);bx(g,w,5,.3,\'#fff\',0,2.8,-h/2);bx(g,.3,5,h,\'#f1f5f9\',-w/2,2.8,0);bx(g,w,.65,.5,c,0,5.1,-h/2);bx(g,w*.4,1.8,h*.22,\'#fff\',w*.2,1.3,h*.2);bx(g,w*.38,2,.15,\'#334155\',0,3,-h*.47);}\n}\nfunction festivalDecor(){\n // Decorations occupy the edge setback, not extra optimizer facilities.\n const b=D.shape.bbox;\n pieces(10).forEach((pc,i)=>{if(D.gates.some(g=>Math.hypot(g.x-pc.x,g.y-pc.y)<10))return;const p=treePos(pc);if(i%2===0)tree(G3,p[0]-80,p[1]-50);else{const x=pc.x-80,z=pc.y-50;cyl(G3,.15,.15,10,\'#8b6b42\',x,5,z);const m=bx(G3,1.8,6,.15,[\'#ef4444\',\'#fbbf24\',\'#06b6d4\'][i%3],x+.8,7,z);m.rotation.z=.12;}});\n D.gates.forEach((g,i)=>{const sp=labelSprite(i===0?\'WELCOME · 주출입구\':\'EXIT · 비상구\',\'#174d3b\');sp.scale.set(18,4.2,1);sp.position.set(g.x-80,11,g.y-50);G3.add(sp)});\n}\nfunction buildParking(){\n const b=D.shape.bbox,left=b[0]-80,right=b[2]-80,front=b[3]-50+15;\n const g=new THREE.Group();G3.add(g);g.userData.parking=true;const width=Math.max(100,right-left),depth=48,cx=(left+right)/2;\n bx(g,width,.5,depth,\'#435266\',cx,-.4,front+depth/2);bx(g,width+2,.5,1,\'#cbd5e1\',cx,0,front);bx(g,width+2,.5,1,\'#cbd5e1\',cx,0,front+depth);\n // Central vehicle aisle, two parking banks, marked bays and accessible spaces.\n for(let row=0;row<2;row++)for(let col=0;col<Math.floor((width-12)/6);col++){\n  const x=cx-width/2+7+col*6,z=front+8+row*30;\n  bx(g,.15,.1,12,\'#f8fafc\',x-2.8,.05,z);bx(g,5.5,.1,.15,\'#f8fafc\',x,.05,z-6);\n  if(col<2)bx(g,5.3,.08,11,\'#2563eb\',x,.03,z);\n  if(col%3!==1){bx(g,3.4,1.5,7,[\'#e2e8f0\',\'#f8fafc\',\'#64748b\',\'#93c5fd\'][col%4],x,1,z);bx(g,2.8,1.1,3.5,\'#17324d\',x,2,z);[-1,1].forEach(a=>[-1,1].forEach(k=>cyl(g,.6,.6,.4,\'#111827\',x+a*1.7,.6,z+k*2.2)));}\n }\n for(let i=0;i<6;i++)bx(g,6,.08,.25,\'#e2e8f0\',cx-width/2+12+i*15,.1,front+23);\n // Pedestrian zebra link approaches the exterior, not through venue booths.\n const gate=D.gates.reduce((a,b)=>a.y>b.y?a:b),gx=gate.x-80;\n for(let i=0;i<7;i++)bx(g,5,.12,.7,\'#fff\',gx,.1,front-1-i*1.6);\n bx(g,1,4,1,\'#f59e0b\',cx+width/2-5,2,front+24);bx(g,8,.3,.6,\'#ef4444\',cx+width/2-8,3,front+24);\n const tag=labelSprite(\'P  외부 주차장 · 계획 예시\',\'#1e3a8a\');tag.scale.set(32,7.5,1);tag.position.set(cx,6,front+23);g.add(tag);\n const arrow=labelSprite(\'입구 → / ← 출구\',\'#334155\');arrow.scale.set(24,5.6,1);arrow.position.set(cx+width/2-9,5,front+24);g.add(arrow);\n}\nfunction populateExplorer(){const list=document.getElementById(\'facilityExplorer\');if(!list)return;const search=document.getElementById(\'facilitySearch\').value.toLowerCase();list.replaceChildren();Z().filter(z=>(z.name+\' \'+z.type).toLowerCase().includes(search)).forEach(z=>{const btn=document.createElement(\'button\');btn.className=\'explorerItem\';btn.textContent=(supportIcon(z)||z.icon||\'▣\')+\'  \'+z.name;btn.onclick=()=>{selectedId=z.id;updateFacilityInfo(z);refreshSelection();positionFacilityPopup()};list.appendChild(btn)})}\n\n// 3D selection and editing: ground-plane ray projection, independent of camera orbit.\nlet peopleOn=true,crowdSpeed=.5,ambulanceSpeed=.4,evacuating=false,whitePaths=false;\nfunction evacuatePeople(){evacuating=true;sim=true;agents.forEach(a=>{a.evacuated=false;a.dwell=0;a.leaving=true;let gate=D.gates.reduce((b,g)=>Math.hypot(g.x-a.x,g.y-a.y)<Math.hypot(b.x-a.x,b.y-a.y)?g:b,D.gates[0]);a.tx=gate.x;a.ty=gate.y});editNote("직선 이동 기반 탈출 시뮬레이션입니다. 실제 대피시간·장애물 회피 검증이 아닙니다.")}\nlet editing=false, selectedId=null, editDrag=null, editUndo=[], editDirty=false, selectionGroup=null, routeGroup=null;\nconst ray3=new THREE.Raycaster(), ground3=new THREE.Plane(new THREE.Vector3(0,1,0),0);\nfunction setRay(ev){const r=R3.domElement.getBoundingClientRect();ray3.setFromCamera(new THREE.Vector2((ev.clientX-r.left)/r.width*2-1,-(ev.clientY-r.top)/r.height*2+1),C3)}\nfunction groundPoint(ev){setRay(ev);return ray3.ray.intersectPlane(ground3,new THREE.Vector3())}\nfunction editNote(text){$(\'editStatus\').textContent=text}\nfunction toggleEdit(){editing=!editing;setView(true);if(editing){setMode(\'after\');sim=false;$(\'bPlay\').textContent=\'▶ 시뮬레이션 시작\';domeOn=false;domeMeshes.forEach(m=>m.visible=false)}$(\'editToggle\').textContent=\'✋ 3D 편집 모드 \'+(editing?\'ON\':\'OFF\');$(\'editToggle\').className=editing?\'on\':\'\';$(\'hint\').textContent=editing?\'부스: 이동 · 노란 손잡이: 크기 · 빈 곳: 회전\':\'드래그: 회전 · 휠: 확대/축소\';editNote(editing?\'부스를 클릭하거나 드래그하세요.\':\'시점 회전 모드\');refreshSelection()}\nfunction selectedZone(){return Z().find(z=>z.id===selectedId)}\nfunction disposeGroup(g){if(!g)return;S3.remove(g);g.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material)o.material.dispose()})}\nfunction refreshSelection(){if(!S3)return;disposeGroup(selectionGroup);selectionGroup=null;const z=selectedZone();if(!z||!editing||mode!==\'after\')return;selectionGroup=new THREE.Group();S3.add(selectionGroup);const points=[[z.x,z.y],[z.x+z.w,z.y],[z.x+z.w,z.y+z.h],[z.x,z.y+z.h],[z.x,z.y]].map(p=>new THREE.Vector3(p[0]-80,.8,p[1]-50));selectionGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0xfbbf24,depthTest:false})));const knob=new THREE.Mesh(new THREE.BoxGeometry(2.6,2.6,2.6),new THREE.MeshBasicMaterial({color:0xfbbf24,depthTest:false}));knob.position.set(z.x+z.w-80,2,z.y+z.h-50);knob.userData.resize=true;knob.renderOrder=99;selectionGroup.add(knob);editNote(z.name+\' · \'+(z.w*mpu/1.35).toFixed(2)+\' × \'+(z.h*mpu/1.35).toFixed(2)+\'m · 未저장 변경은 저장 버튼으로 반영\'.replace(\'未\',\'미\'))}\nfunction updateFacilityInfo(z){const panel=$(\'facilityInfo\');panel.replaceChildren();$(\'facilityPopup\').style.display=z?\'block\':\'none\';if(!z){panel.textContent=\'시설을 클릭하면 이름·설명·배치 근거가 표시됩니다.\';return}for(const [title,text] of [[\'이름\',z.name],[\'설명\',z.description||\'사용자가 추가한 행사 시설입니다.\'],[\'배치 근거\',editDirty?\'직접 편집 중인 위치입니다. 저장하면 실제 위치 기준 출입구 거리와 근거를 갱신합니다.\':z.placement_reason||\'저장 후 위치 기반 근거를 확인할 수 있습니다.\']]){const line=document.createElement(\'p\');line.style.margin=\'6px 0\';line.textContent=title+\': \'+text;panel.appendChild(line)}}\nfunction positionFacilityPopup(){\n const popup=$(\'facilityPopup\'),z=selectedZone();if(!z||popup.style.display===\'none\')return;\n const w=wrap.clientWidth,h=wrap.clientHeight;let x,y;\n if(is3d&&C3){const p=new THREE.Vector3(z.x+z.w/2-80,Math.max(3,z.ht||6),z.y+z.h/2-50).project(C3);if(p.z < -1||p.z>1){popup.style.visibility=\'hidden\';return}popup.style.visibility=\'visible\';x=(p.x+1)*w/2;y=(1-p.y)*h/2;}\n else{x=(z.x+z.w/2)/160*w;y=(z.y+z.h/2)/100*h;popup.style.visibility=\'visible\';}\n const pw=popup.offsetWidth,ph=popup.offsetHeight;let left=x+20;if(left+pw>w-8)left=x-pw-20;\n popup.style.left=Math.max(8,Math.min(w-pw-8,left))+\'px\';popup.style.top=Math.max(8,Math.min(h-ph-8,y-ph/2))+\'px\';\n}\nfunction pickFacility(ev){setRay(ev);for(const hit of ray3.intersectObjects(G3.children,true)){let o=hit.object;while(o&&o!==G3){if(o.userData.zoneId!==undefined)return o.userData.zoneId;o=o.parent}}return null}\nfunction pointerDown3(ev){if(!editing){selectedId=pickFacility(ev);updateFacilityInfo(selectedZone());}if(ev.button!==0)return;R3.domElement.setPointerCapture(ev.pointerId);setRay(ev);if(editing&&mode===\'after\'){\n if(selectionGroup&&ray3.intersectObjects(selectionGroup.children,true).some(h=>h.object.userData.resize)){const p=groundPoint(ev);if(p){editUndo.push(JSON.stringify(D.zones));editDrag={kind:\'resize\',point:p,zone:{...selectedZone()}};return}}\n const hits=ray3.intersectObjects(G3.children,true);let id=null;for(const hit of hits){let o=hit.object;while(o&&o!==G3){if(o.userData.zoneId!==undefined){id=o.userData.zoneId;break}o=o.parent}if(id!==null)break}\n selectedId=id;updateFacilityInfo(selectedZone());refreshSelection();if(id!==null){const p=groundPoint(ev);if(p){editUndo.push(JSON.stringify(D.zones));editDrag={kind:\'move\',point:p,zone:{...selectedZone()}};return}}\n }drag=true;lx=ev.clientX;ly=ev.clientY}\nfunction pointerMove3(ev){if(editDrag){const p=groundPoint(ev),z=selectedZone();if(!p||!z)return;const dx=p.x-editDrag.point.x,dy=p.z-editDrag.point.z,old=editDrag.zone;if(editDrag.kind===\'move\'){z.x=Math.max(0,Math.min(160-z.w,old.x+dx));z.y=Math.max(0,Math.min(100-z.h,old.y+dy))}else{z.w=Math.max(1,Math.min(150,160-z.x,old.w+dx));z.h=Math.max(1,Math.min(95,100-z.y,old.h+dy))}editDirty=true;updateFacilityInfo(selectedZone());buildScene3();drawBase();return}if(drag){yaw-=(ev.clientX-lx)*.008;pitch=Math.min(1.35,Math.max(.3,pitch+(ev.clientY-ly)*.006));lx=ev.clientX;ly=ev.clientY}}\nfunction deleteSelected(){if(!editing||mode!==\'after\'||!selectedZone()){editNote(\'편집 모드에서 삭제할 시설을 선택하세요.\');return}const z=selectedZone();if(z.type===\'medical\'&&D.zones.filter(q=>q.type===\'medical\').length===1){editNote(\'마지막 응급의료센터는 삭제할 수 없습니다.\');return}if(D.zones.length<=2){editNote(\'시설은 최소 2개 필요합니다.\');return}editUndo.push(JSON.stringify(D.zones));D.zones=D.zones.filter(z=>z.id!==selectedId);selectedId=null;editDirty=true;emg=null;initAgents();buildScene3();drawBase();editNote(\'삭제했습니다. 저장 버튼을 눌러 반영하세요.\')}\nfunction undoEdit(){if(!editUndo.length)return;D.zones=JSON.parse(editUndo.pop());selectedId=null;editDirty=true;emg=null;initAgents();buildScene3();drawBase();editNote(\'이전 조작으로 되돌렸습니다. 저장 후 반영됩니다.\')}\nfunction save3Edit(){if(mode!==\'after\'){editNote(\'설계 후 배치에서만 저장할 수 있습니다.\');return}parent.postMessage({type:\'event:save\',zones:D.zones},\'*\');editNote(\'저장 요청 중입니다. 충돌·외곽 침범 시 앱에 오류가 표시됩니다.\')}\nfunction isProp(n){return /그늘막|조명|책상|테이블|의자|파라솔|천막|알림막|깃발|연단|가림막|전광판|키오스크|쓰레기|분리수거/.test(n)}\nfunction buildProp(g,z,w,h){const n=z.name,c=z.color;\n if(/조명/.test(n)){cyl(g,.18,.18,7,\'#64748b\',0,3.5,0);bx(g,2,.5,1,\'#fff4ba\',0,7,0,{emissive:new THREE.Color(\'#ffe39c\'),emissiveIntensity:.9});const light=new THREE.PointLight(0xffedbe,.65,20);light.position.set(0,6,0);g.add(light)}\n else if(/책상|테이블/.test(n)){bx(g,w*.9,.45,h*.85,c,0,2.7,0);[-1,1].forEach(a=>[-1,1].forEach(b=>bx(g,.35,2.5,.35,\'#64748b\',a*w*.35,1.25,b*h*.3)));}\n else if(/의자/.test(n)){bx(g,w*.7,.4,h*.65,c,0,1.5,0);bx(g,w*.7,2,.35,c,0,2.3,-h*.3);[-1,1].forEach(a=>[-1,1].forEach(b=>bx(g,.3,1.5,.3,\'#64748b\',a*w*.28,.75,b*h*.25)));}\n else if(/파라솔/.test(n)){cyl(g,.16,.16,5,\'#64748b\',0,2.5,0);const roof=new THREE.Mesh(new THREE.ConeGeometry(1,1.5,16),M(c));roof.scale.set(w*.5,1,h*.5);roof.position.y=5;g.add(roof)}\n else if(/쓰레기|분리수거|분리배출/.test(n)){cyl(g,w*.35,w*.3,3,c,0,1.5,0);cyl(g,w*.4,w*.4,.4,\'#334155\',0,3.1,0)}\n else if(/연단/.test(n)){bx(g,w*.9,2,h*.9,c,0,1,0)}\n else if(/천막|그늘막/.test(n)){[-1,1].forEach(a=>[-1,1].forEach(b=>cyl(g,.16,.16,5,\'#64748b\',a*w*.4,2.5,b*h*.4)));bx(g,w,1,h,c,0,5,0)}\n else{bx(g,.4,5,.4,\'#475569\',0,2.5,0);bx(g,w*.85,3,Math.max(.3,h*.15),/전광판|키오스크/.test(n)?\'#0f172a\':c,0,4,0)}\n}\n// Grid BFS: indicative routes only, not a certified evacuation/accessibility design.\nfunction clearRoutes(){if(routeGroup){disposeGroup(routeGroup);routeGroup=null}}\nfunction showRoute(kind){if(!R3||mode!==\'after\'){editNote(\'설계 후 3D 화면에서 경로를 표시하세요.\');return}clearRoutes();routeGroup=new THREE.Group();S3.add(routeGroup);const step=2,nx=80,ny=50,key=(x,y)=>y*nx+x;\n const free=(x,y)=>x>=0&&x<nx&&y>=0&&y<ny&&insideShape(x*step+1,y*step+1)&&!D.zones.some(z=>x*step+1>=z.x-1&&x*step+1<=z.x+z.w+1&&y*step+1>=z.y-1&&y*step+1<=z.y+z.h+1);\n const near=(x,y)=>{let best=null,d=Infinity;for(let yy=0;yy<ny;yy++)for(let xx=0;xx<nx;xx++)if(free(xx,yy)){let dd=(xx*step+1-x)**2+(yy*step+1-y)**2;if(dd<d){d=dd;best=[xx,yy]}}return best};\n const route=(start,goal)=>{if(!start||!goal)return null;const q=[start],prev=new Map([[key(...start),null]]);let found=null;for(let i=0;i<q.length;i++){let [x,y]=q[i];if(x===goal[0]&&y===goal[1]){found=[x,y];break}for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){let a=x+dx,b=y+dy,k=key(a,b);if(free(a,b)&&!prev.has(k)){prev.set(k,[x,y]);q.push([a,b])}}}if(!found)return null;let points=[];while(found){points.push(new THREE.Vector3(found[0]*step+1-80,1.1,found[1]*step+1-50));found=prev.get(key(...found))}return points};\n let shown=0,failed=0;const targets=kind===\'accessible\'?D.zones.filter(z=>/사회적|화장실|의료|응급|무대|공연|안내/.test(z.name)):D.zones;\n for(const z of targets){let start=near(z.x+z.w/2,z.y+z.h+3),best=null;const gates=kind===\'accessible\'?D.gates.slice(0,1):D.gates;for(const g of gates){const pts=route(start,near(g.x,g.y));if(pts&&(!best||pts.length<best.length))best=pts}if(best){routeGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(best),new THREE.LineBasicMaterial({color:kind===\'accessible\'?0x2563eb:0x16a34a,depthTest:false})));shown++}else failed++}\n editNote((kind===\'accessible\'?\'사회적 약자 이동경로 후보\':\'비상 대피로 후보\')+\' \'+shown+\'개 · 탐색 실패 \'+failed+\'개. 격자 기반 참고 경로이며 통로 폭·경사·단차·출입문 유효폭은 검증하지 않았습니다.\');\n}\n\n/* ---------- 3D 아이소메트릭 ---------- */\nlet R3=null,S3,C3,G3,bodyM,headM,rainPts,emgGrp,emgLine,heatPlane,heatTex;\nlet yaw=-.65,pitch=.78,zoom3=.95*Math.min(1.45,WW/Math.max(D.shape.bbox[2]-D.shape.bbox[0],(D.shape.bbox[3]-D.shape.bbox[1])*1.3))*(D.shape.dome?.82:1),drag=false,lx=0,ly=0;\nconst DUM=new THREE.Object3D();\nfunction M(c,o){return new THREE.MeshLambertMaterial(Object.assign({color:new THREE.Color(c)},o||{}));}\nfunction bx(p,w,h,d,c,x,y,z,o){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),M(c,o));m.position.set(x,y,z);p.add(m);return m;}\nfunction cyl(p,rt,rb,h,c,x,y,z,seg){const m=new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,seg||12),M(c));m.position.set(x,y,z);p.add(m);return m;}\nfunction cone(p,r,h,c,x,y,z,seg){const m=new THREE.Mesh(new THREE.ConeGeometry(r,h,seg||8),M(c));m.position.set(x,y,z);p.add(m);return m;}\nfunction tree(p,x,z){cyl(p,.5,.6,2.4,\'#7c4a21\',x,1.4,z,8);cone(p,2.3,4.6,\'#2f855a\',x,4.8,z,8);}\nfunction seats(p,rows,cols,x0,z0,dx,dz,c){const im=new THREE.InstancedMesh(new THREE.BoxGeometry(1.2,1,1.2),M(c),rows*cols);let k=0;\n  for(let r=0;r<rows;r++)for(let q=0;q<cols;q++){DUM.position.set(x0+q*dx,.9,z0+r*dz);DUM.scale.set(1,1,1);DUM.rotation.set(0,0,0);DUM.updateMatrix();im.setMatrixAt(k++,DUM.matrix);} p.add(im);}\nfunction labelSprite(text,color){\n  const c=document.createElement(\'canvas\'); c.width=640; c.height=150; const t=c.getContext(\'2d\');\n  t.fillStyle=\'rgba(255,255,255,.96)\'; t.beginPath(); t.roundRect(4,4,632,142,28); t.fill();\n  t.fillStyle=color; t.beginPath(); t.roundRect(4,4,30,142,14); t.fill();\n  t.strokeStyle=\'rgba(15,23,42,.25)\'; t.lineWidth=3; t.beginPath(); t.roundRect(4,4,632,142,28); t.stroke();\n  t.fillStyle=\'#0f172a\'; t.font=\'bold 66px Pretendard,sans-serif\'; t.textAlign=\'center\'; t.textBaseline=\'middle\'; t.fillText(text,340,78,570);\n  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),depthTest:false,transparent:true})); sp.renderOrder=10; return sp;\n}\nfunction buildZone3(z){\n  const g=new THREE.Group(); const cxz=z.x+z.w/2-WW/2, czz=z.y+z.h/2-WH/2; g.position.set(cxz,0,czz); G3.add(g); g.userData.zoneId=z.id;\n  if(supportIcon(z)){const sp=iconSprite(supportIcon(z));sp.position.set(0,4,0);g.add(sp);return;}\n  const w=z.w,h=z.h; const pale=new THREE.Color(z.color).lerp(new THREE.Color(\'#ffffff\'),.65).getStyle();\n  if(z.shape && z.shape!==\'rect\'){\n    let pts=[]; if(z.shape===\'ellipse\'){for(let i=0;i<64;i++){let t=i*Math.PI*2/64;pts.push([Math.cos(t)*w/2,Math.sin(t)*h/2]);}}\n    else {pts=[[-w/2,-h/2],[w*.05,-h/2],[w*.05,-h*.05],[w/2,-h*.05],[w/2,h/2],[-w/2,h/2]];}\n    const sh=new THREE.Shape();pts.forEach((p,i)=>i?sh.lineTo(p[0],p[1]):sh.moveTo(p[0],p[1]));sh.closePath();\n    const mesh=new THREE.Mesh(new THREE.ExtrudeGeometry(sh,{depth:z.type===\'stage\'?3:.8,bevelEnabled:false}),M(z.color));mesh.rotation.x=-Math.PI/2;g.add(mesh);\n  } else bx(g,w,.5,h,pale,0,.25,0);\n  let top=8;\n  switch(z.shape && z.shape!==\'rect\' ? \'__shaped\' : (z.type===\'custom\'?(isProp(z.name)?\'__prop\':\'__custom\'):z.type)){\n    case \'__custom\': {buildCustom(g,z,w,h);top=6;break;}\n    case \'__prop\': {buildProp(g,z,w,h);top=8;break;}\n    case \'__shaped\': {top=6;break;}\n    case \'stage\':{ const s=(czz<0)?1:-1;\n      bx(g,w,1,h*.58,\'#ffffff\',0,z.ht+5,-s*h*.2);\n      [-1,1].forEach(a=>[-1,1].forEach(b=>bx(g,.65,z.ht+4,.65,\'#64748b\',a*w*.47,(z.ht+4)/2,b*h*.24-s*h*.2)));\n      bx(g,w*.96,3,h*.42,\'#7c3aed\',0,2,-s*h*.28); bx(g,w*.96,.4,h*.42,\'#ddd6fe\',0,3.7,-s*h*.28);\n      bx(g,w*.92,z.ht,.9,\'#312e81\',0,3.5+z.ht/2,-s*h*.48,{emissive:new THREE.Color(\'#4338ca\')});\n      [-1,1].forEach(k=>bx(g,1.2,z.ht+1.5,1.2,\'#1e1b4b\',k*w*.46,(z.ht+1.5)/2+3.5,-s*h*.48));\n      const rows=Math.max(1,Math.floor((h*.5-2.2)/1.9)+1), cols=Math.max(3,Math.floor((w-3)/1.9));\n      seats(g,rows,cols,-(cols-1)*.95,s*1.4,1.9,s*1.9,\'#1e3a8a\'); top=z.ht+6; break; }\n    case \'food\':{\n      bx(g,w*.9,3,2,\'#92400e\',0,2,-h*.33);\n      const n=Math.max(3,Math.round(w/3)); for(let i=0;i<n;i++) bx(g,w*.95/n,.5,h*.42,(i%2?\'#ffffff\':z.color),-w*.475+(i+.5)*w*.95/n,6.4,-h*.28);\n      [-1,1].forEach(k=>{cyl(g,.25,.25,5.8,\'#475569\',k*w*.46,3.3,-h*.48,8);cyl(g,.25,.25,5.8,\'#475569\',k*w*.46,3.3,-h*.08,8);});\n      [-1,0,1].forEach(t=>{const x=t*w*.28; cyl(g,1.5,1.5,.3,\'#ffffff\',x,2,h*.2,16); cyl(g,.3,.3,1.6,\'#64748b\',x,1.2,h*.2,8); cyl(g,.6,.6,.8,z.color,x-2.2,1,h*.2,10); cyl(g,.6,.6,.8,z.color,x+2.2,1,h*.2,10);});\n      top=8; break; }\n    case \'rest\':{\n      bx(g,w*.96,.5,h*.96,\'#4fa15a\',0,.5,0); bx(g,w*.4,1,1.3,\'#a16207\',-w*.2,1.3,h*.12); bx(g,w*.4,1,1.3,\'#a16207\',w*.2,1.3,-h*.12);\n      tree(g,-w*.4,-h*.3); tree(g,w*.4,h*.3); tree(g,w*.38,-h*.36); top=9; break; }\n    case \'medical\':{\n      bx(g,w*.8,5,h*.7,\'#ffffff\',0,3,0); bx(g,w*.82,1,h*.72+.1,\'#ef4444\',0,2.4,0); bx(g,w*.84,.8,h*.74,\'#f1f5f9\',0,5.8,0);\n      bx(g,4.2,.3,1.3,\'#ef4444\',0,6.4,0); bx(g,1.3,.3,4.2,\'#ef4444\',0,6.4,0); top=8.5; break; }\n    case \'info\':{\n      bx(g,w*.6,3,h*.5,\'#0ea5e9\',0,2,0); bx(g,w*.85,.5,h*.75,\'#e0f2fe\',0,3.8,0); cyl(g,.2,.2,4.5,\'#334155\',w*.36,2.8,h*.3,8); cyl(g,1.1,1.1,.4,\'#0ea5e9\',w*.36,5.2,h*.3,16); top=7.5; break; }\n    case \'restroom\':{\n      bx(g,w*.8,4,h*.7,\'#e2e8f0\',0,2.5,0); bx(g,w*.86,.6,h*.76,\'#06b6d4\',0,4.8,0);\n      bx(g,1.4,2.4,.2,\'#0f172a\',-w*.15,1.7,h*.36); bx(g,1.4,2.4,.2,\'#0f172a\',w*.15,1.7,h*.36); top=7; break; }\n    default:{ /* booth, custom : 텐트 */\n      const px_=w*.38,pz=h*.38; [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(a=>cyl(g,.25,.25,4.8,\'#475569\',a[0]*px_,2.9,a[1]*pz,8));\n      const roof=new THREE.Mesh(new THREE.ConeGeometry(1,3.4,4),M(z.color)); roof.rotation.y=Math.PI/4; roof.scale.set(w*.72,1,h*.72); roof.position.set(0,6.7,0); g.add(roof);\n      bx(g,w*.5,1.6,h*.22,\'#f8fafc\',0,1.4,h*.15); [-1,0,1].forEach(k=>bx(g,1.4,1,1.4,z.color,k*w*.16,2.7,h*.15)); top=9.5; }\n  }\n  const sp=labelSprite(\'\',z.color); const ww=Math.min(30,Math.max(14,z.name.length*2.1+8)); sp.scale.set(ww,ww*150/640,1); sp.position.set(0,top+3,0); /* facility labels are intentionally hidden */\n}\nfunction shapeGeo(scale){ const sh=new THREE.Shape(); D.shape.outline.forEach((p,i)=>{ const x=(p[0]-WW/2)*scale, y=-(p[1]-WH/2)*scale; if(i) sh.lineTo(x,y); else sh.moveTo(x,y); }); sh.closePath(); return sh; }\nfunction slab(depth,color,y,scale){ const m=new THREE.Mesh(new THREE.ExtrudeGeometry(shapeGeo(scale),{depth:depth,bevelEnabled:false}),M(color)); m.rotation.x=-Math.PI/2; m.position.y=y; G3.add(m); return m; }\nlet domeMeshes=[], domeOn=true;\nfunction buildScene3(){\n  clearRoutes();\n  if(G3){ S3.remove(G3); G3.traverse(o=>{if(o.geometry)o.geometry.dispose(); if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach(m=>{if(m.map)m.map.dispose();m.dispose()})}}); } G3=new THREE.Group(); S3.add(G3);\n  const T=D.theme, dome=D.shape.dome; const ground=T.kind===\'indoor\'?T.ground:\'#93b879\';\n  slab(4,\'#e5e7eb\',-4.7,1.04); slab(.7,ground,-.7,1);\n  if(T.kind===\'outdoor\'&&!dome){ pieces(9).forEach((pc,i)=>{ if(i%2) return; const t=treePos(pc); tree(G3,t[0]-WW/2,t[1]-WH/2); }); }\n  const hh=dome?2.4:5;\n  pieces(5).forEach(pc=>{ if(D.gates.some(g=>Math.hypot(g.x-pc.x,g.y-pc.y)<7.5)) return; const m=bx(G3,pc.len+.3,hh,1.4,\'#f8fafc\',pc.x-WW/2,hh/2,pc.y-WH/2); m.rotation.y=-pc.ang; });\n  const pcol=T.path;\n  if(whitePaths) Z().forEach(z=>{ const g=nearestGate(z); const x1=g.x-WW/2,z1=g.y-WH/2,x2=z.x+z.w/2-WW/2,z2=z.y+z.h/2-WH/2; const dx=x2-x1,dz=z2-z1,L=Math.hypot(dx,dz);\n    const m=bx(G3,L,.3,3.2,pcol,(x1+x2)/2,.15,(z1+z2)/2); m.rotation.y=-Math.atan2(dz,dx); });\n  D.gates.forEach(g=>{ const gg=new THREE.Group(); gg.position.set(g.x-WW/2,0,g.y-WH/2); gg.rotation.y=-g.ang; G3.add(gg);\n    bx(gg,1.6,8,1.6,\'#1e293b\',-6,4,0); bx(gg,1.6,8,1.6,\'#1e293b\',6,4,0); bx(gg,14,1.4,1.8,\'#1e293b\',0,8,0);\n    const sp=labelSprite(\'🚪 \'+g.name,\'#1e293b\'); sp.scale.set(15,15*150/640,1); sp.position.set(g.x-WW/2,12,g.y-WH/2); G3.add(sp); });\n  Z().forEach(buildZone3);buildParking();festivalDecor();populateExplorer();\n  domeMeshes=[];\n  if(dome){ const bw=SHB[2]-SHB[0], bh=SHB[3]-SHB[1];\n    const dm=new THREE.Mesh(new THREE.SphereGeometry(1,48,20,0,Math.PI*2,0,Math.PI/2),new THREE.MeshLambertMaterial({color:0xbfdbfe,transparent:true,opacity:.14,side:THREE.DoubleSide,depthWrite:false}));\n    dm.scale.set(bw/2,bw/2*.6,bh/2); dm.renderOrder=1; G3.add(dm);\n    const wf=new THREE.Mesh(new THREE.SphereGeometry(1,16,6,0,Math.PI*2,0,Math.PI/2),new THREE.MeshBasicMaterial({color:0x475569,wireframe:true,transparent:true,opacity:.16,depthWrite:false}));\n    wf.scale.copy(dm.scale); wf.renderOrder=1; G3.add(wf); domeMeshes=[dm,wf]; domeMeshes.forEach(m=>m.visible=domeOn); }\n  refreshSelection();\n  $(\'zlist\').replaceChildren(...Z().map(z=>{const el=document.createElement(\'span\');el.style.setProperty(\'--c\',z.color);el.textContent=z.icon+\' \'+z.name;return el})); $(\'zCnt\').textContent=\'(\'+Z().length+\'개)\';\n}\n// Detailed, editable diorama models: all additions are children of each zone group.\nfunction sphereDetail(p,r,c,x,y,z,sx=1,sy=1,sz=1){const m=new THREE.Mesh(new THREE.SphereGeometry(r,12,8),M(c));m.position.set(x,y,z);m.scale.set(sx,sy,sz);p.add(m);return m}\nfunction detailedTree(p,x,z){cyl(p,.32,.48,3.4,\'#79533a\',x,1.7,z,9);[[-.9,4.2,0],[.8,4.5,.35],[0,5.1,-.3]].forEach((a,i)=>sphereDetail(p,1.55,[\'#347845\',\'#458f48\',\'#609f50\'][i],x+a[0],a[1],z+a[2],1,.78,1))}\ntree=detailedTree;\nconst originalZoneModel=buildZone3;\nbuildZone3=function(z){originalZoneModel(z);if(supportIcon(z))return;const g=G3.children.find(q=>q.userData.zoneId===z.id);if(!g)return;const w=z.w,h=z.h;if(z.shape&&z.shape!==\'rect\')return;\n if(z.type===\'stage\'){\n const sign=(z.y+z.h/2-WH/2<0)?1:-1;\n // Speaker cabinets with visible cones and perimeter truss cross-bracing.\n [-1,1].forEach(k=>{const x=k*w*.42,zz=-sign*h*.38;bx(g,w*.09,6,h*.085,\'#202832\',x,4,zz);for(let j=0;j<3;j++){const disc=cyl(g,.52,.52,.12,\'#111827\',x,2.1+j*1.6,zz+sign*h*.045,16);disc.rotation.x=Math.PI/2;sphereDetail(g,.22,\'#46515c\',x,2.1+j*1.6,zz+sign*h*.052,1,1,.3)}for(let j=0;j<4;j++){const bar=bx(g,.15,2.6,.15,\'#e2e8f0\',k*w*.47,1.8+j*2,-sign*h*.4);bar.rotation.z=(j%2?1:-1)*.45}});\n for(let i=0;i<6;i++){const x=(i-2.5)*w*.13;cyl(g,.35,.35,.65,\'#202d40\',x,z.ht+3.9,-sign*h*.14,10);sphereDetail(g,.24,[\'#60a5fa\',\'#fbbf24\',\'#f472b6\'][i%3],x,z.ht+3.5,-sign*h*.14)}\n for(let i=0;i<3;i++)bx(g,w*.15,.55,h*.07,\'#59616c\',0,.45+i*.55,sign*(h*.13+i*.045));\n }else if(z.type===\'food\'||/푸드트럭/.test(z.name)){\n // Counter equipment and serving window, sized to the existing zone.\n bx(g,w*.68,.24,h*.2,\'#d6dbe1\',0,3.6,-h*.3);\n for(let i=0;i<3;i++){bx(g,w*.09,.55,h*.09,[\'#c4a06e\',\'#c65238\',\'#52845b\'][i],(i-1)*w*.18,3.95,-h*.3)}\n bx(g,w*.52,1.2,.12,\'#304750\',0,4.7,-h*.42);\n if(/트럭/.test(z.name)){bx(g,w*.23,3,h*.4,\'#f2b444\',w*.32,2,-h*.28);[-1,1].forEach(k=>{const m=cyl(g,.68,.68,.4,\'#26313d\',k*w*.32,.8,-h*.08,16);m.rotation.x=Math.PI/2})}\n }else if(z.type===\'booth\'){\n // Display plinths, product boxes, framed rear display and shelf.\n bx(g,w*.68,3.1,.16,\'#f8fafc\',0,2.15,-h*.35);bx(g,w*.42,1.45,.18,\'#36546f\',0,2.8,-h*.34);\n bx(g,w*.68,.16,h*.13,\'#c4aa87\',0,2.0,-h*.22);\n for(let i=0;i<3;i++)bx(g,w*.09,.6,h*.1,[\'#e0a73f\',\'#71a68e\',\'#cc7d6b\'][i],(i-1)*w*.2,2.4,-h*.22);\n }else if(z.type===\'rest\'){\n [-1,1].forEach(k=>{bx(g,w*.3,.25,.9,\'#b98b51\',k*w*.22,1.6,0);bx(g,w*.3,.8,.18,\'#b98b51\',k*w*.22,2.1,-.45);[-1,1].forEach(j=>bx(g,.18,1.4,.7,\'#485b50\',k*w*.22+j*w*.1,.7,0))});\n }\n};\nconst originalSceneModel=buildScene3;\nbuildScene3=function(){originalSceneModel();G3.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true}})};\n\n// Unified normalized models. Model footprints scale with editable zone dimensions.\nfunction timber(p,w,h,d,x,y,z){return bx(p,w,h,d,\'#b88b59\',x,y,z)}\nfunction fabricRoof(p,w,d,y,col){\n const pts=new Float32Array([-w/2,0,-d/2,w/2,0,-d/2,w/2,0,d/2,-w/2,0,d/2,0,1.5,0]);\n const geo=new THREE.BufferGeometry();geo.setAttribute(\'position\',new THREE.BufferAttribute(pts,3));geo.setIndex([0,4,1,1,4,2,2,4,3,3,4,0]);geo.computeVertexNormals();const mesh=new THREE.Mesh(geo,M(col,{side:THREE.DoubleSide}));mesh.position.y=y;p.add(mesh);\n bx(p,w,.35,.12,col,0,y,-d/2);bx(p,w,.35,.12,col,0,y,d/2);\n}\nfunction frameBar(p,a,b,r,c){const v=new THREE.Vector3(...a),u=new THREE.Vector3(...b),delta=u.clone().sub(v);const m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,delta.length(),7),M(c));m.position.copy(v.add(u).multiplyScalar(.5));m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());p.add(m)}\nfunction canopy(p,color){[-1,1].forEach(x=>[-1,1].forEach(z=>bx(p,.13,3.3,.13,\'#f5f4e9\',x*3.4,1.8,z*3.2)));fabricRoof(p,7.3,7,3.7,color);[-1,1].forEach(x=>{bx(p,.1,2.8,6.4,\'#faf7ea\',x*3.45,1.75,0)});}\nfunction modelStage(p){\n bx(p,9.4,.9,6.7,\'#343c50\',0,.45,-.9);bx(p,9.3,.12,6.6,\'#737b83\',0,.96,-.9);\n [-1,1].forEach(x=>[-1,1].forEach(z=>{const xx=x*4.65,zz=z*2.9-.9;[-.14,.14].forEach(a=>bx(p,.08,6,.08,\'#bbc7d0\',xx+a,3.7,zz));for(let k=0;k<5;k++){frameBar(p,[xx-.14,1+k,zz],[xx+.14,2+k,zz],.045,\'#e2e8ef\')}}));\n bx(p,9.8,.25,6.4,\'#eef1f0\',0,6.8,-.9);bx(p,7.7,3.7,.22,\'#101b30\',0,3.5,-3.7);\n // Abstract LED wall uses geometry, not text textures.\n for(let i=0;i<18;i++){const height=1+Math.sin(i*.8)*.65;bx(p,.26,height,.05,[\'#42b9d4\',\'#9579e7\',\'#e198bd\'][i%3],-3.3+i*.39,3.4,-3.55)}\n [-1,1].forEach(k=>{for(let j=0;j<4;j++){bx(p,.7,.7,.6,\'#182231\',k*4,1.5+j*.76,-2.5);const sp=cyl(p,.24,.24,.08,\'#475261\',k*4,1.5+j*.76,-2.15,16);sp.rotation.x=Math.PI/2}for(let j=0;j<3;j++)bx(p,.18,.4,.2,\'#162633\',k*(1+j),6.4,1.8)});\n for(let i=0;i<3;i++)bx(p,2,.25,.5,\'#687583\',0,.15+i*.25,2.6-i*.5);\n for(let r=0;r<3;r++)for(let c=0;c<8;c++){const x=-3.8+c*1.08,z=3.1+r*.75;bx(p,.55,.12,.42,\'#334d70\',x,.6,z);bx(p,.55,.5,.08,\'#334d70\',x,.85,z-.18)}\n}\nfunction modelTruck(p,color){\n bx(p,7,2.6,3.7,color,-.6,2,0);bx(p,2.1,2.9,3.6,\'#f6ebc7\',3.35,2.15,0);bx(p,1.7,1.2,.08,\'#436577\',3.35,2.8,1.85);bx(p,.08,1.3,2.9,\'#476c7b\',4.44,2.8,0);\n bx(p,5.1,1.3,.12,\'#273f49\',-.8,2.5,1.9);bx(p,5.3,.18,1.2,\'#e4d2aa\',-.8,1.85,2.25);\n for(let i=0;i<10;i++){const aw=bx(p,.55,.12,2.2,i%2?\'#fff8e4\':color,-3.25+i*.55,3.7,2);aw.rotation.x=.16}\n [-1,1].forEach(x=>[-1,1].forEach(z=>{const wheel=cyl(p,.64,.64,.32,\'#26323b\',x*2.8,.75,z*1.92,18);wheel.rotation.x=Math.PI/2;const hub=cyl(p,.28,.28,.34,\'#a3afb6\',x*2.8,.75,z*1.94,12);hub.rotation.x=Math.PI/2}));\n for(let i=0;i<3;i++)bx(p,.42,.55,.35,[\'#d5b263\',\'#a2543c\',\'#527959\'][i],-2.5+i*1.5,2.2,2.3);\n}\nfunction modelTent(p,col){canopy(p,col);timber(p,5.6,1.3,1.5,0,.9,1.5);bx(p,5.8,.15,1.7,\'#f4e5c9\',0,1.62,1.5);bx(p,5.8,2.3,.12,\'#f5efe3\',0,1.6,-2.9);bx(p,3.8,1.2,.1,\'#5a7680\',0,2,-2.8);for(let i=0;i<5;i++)bx(p,.55,.5,.55,[\'#c98756\',\'#789d78\',\'#d9bb72\'][i%3],-2+i,1.95,1.5)}\nfunction bench(p,x,z){timber(p,2.8,.18,.8,x,.85,z);timber(p,2.8,.5,.12,x,1.2,z-.38);[-1,1].forEach(k=>bx(p,.15,.85,.65,\'#475b55\',x+k,z===999?0:.42,z))}\nfunction modelGarden(p){bx(p,9,.15,8,\'#9abd73\',0,.12,0);[-1,1].forEach(k=>{tree(p,k*3,-2.5);bench(p,k*2.7,1.3)});const pool=cyl(p,1.8,1.8,.5,\'#cbd1c6\',0,.45,0,32);cyl(p,1.55,1.55,.12,\'#70becd\',0,.75,0,32);cyl(p,.25,.45,1.5,\'#eee6cb\',0,1.4,0,16);sphereDetail(p,.6,\'#97d4dd\',0,2.25,0,1,.25,1)}\nconst legacyModel=buildZone3;\nbuildZone3=function(z){\n if(supportIcon(z)||z.shape&&z.shape!==\'rect\'){legacyModel(z);return}\n const g=new THREE.Group();g.userData.zoneId=z.id;g.position.set(z.x+z.w/2-WW/2,0,z.y+z.h/2-WH/2);G3.add(g);\n const p=new THREE.Group();g.add(p);p.scale.set(z.w/10,Math.min(1.4,Math.max(.65,Math.sqrt(z.w*z.h)/10)),z.h/10);\n bx(p,9.8,.12,9.8,\'#d2c7aa\',0,.06,0);\n const palette=[\'#d8974e\',\'#638ba2\',\'#cf7860\',\'#76a18a\',\'#d5b767\'];let hash=0;for(const a of z.id)hash=(hash+a.charCodeAt(0))%palette.length;const col=palette[hash];\n if(z.type===\'stage\')modelStage(p);else if(z.type===\'food\'||/푸드트럭|조리/.test(z.name))modelTruck(p,col);else if(z.type===\'rest\')modelGarden(p);else if(z.type===\'booth\'||/전시|판매|체험/.test(z.name))modelTent(p,col);else{\n bx(p,7.7,3.2,6.3,\'#e9e5d7\',0,1.7,0);fabricRoof(p,8.4,7,3.5,\'#789596\');bx(p,1.3,2.1,.12,\'#55727d\',1.7,1.3,3.2);[-1,0].forEach(k=>{bx(p,1.6,1,.13,\'#6e9fae\',-2+k*2,2,3.2);bx(p,1.7,.09,.16,\'#f3edda\',-2+k*2,2,3.3)})\n }\n};\n\n// Whole-site composition, keeping simulation geometry and editable facility IDs unchanged.\nfunction campusCamera(view){if(view===\'front\'){yaw=0;pitch=.68;zoom3=1.05}else if(view===\'plan\'){yaw=0;pitch=1.34;zoom3=.92}else{yaw=-.65;pitch=.78;zoom3=.96}}\nfunction campusTiles(){\n const step=2,cols=80,rows=50,grid=new Uint8Array(cols*rows),used=new Set();\n for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const x=i*step+1,y=j*step+1;grid[j*cols+i]=!insideShape(x,y)||Z().some(z=>x>z.x-.6&&x<z.x+z.w+.6&&y>z.y-.6&&y<z.y+z.h+.6)?1:0}\n function near(x,y){let best=-1,dist=Infinity;for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const k=j*cols+i;if(grid[k])continue;const d=(i*step+1-x)**2+(j*step+1-y)**2;if(d<dist){dist=d;best=k}}return best}\n const root=near(SHC[0],SHC[1]);if(root<0)return;\n const targets=[...D.gates.map(g=>[g.x,g.y]),...Z().filter(z=>!supportIcon(z)).map(z=>[z.x+z.w/2,z.y+z.h+1])];\n const prev=new Int32Array(cols*rows).fill(-1),q=[root];prev[root]=root;\n for(let k=0;k<q.length;k++){const a=q[k],i=a%cols,j=Math.floor(a/cols);for(const [di,dj]of [[1,0],[-1,0],[0,1],[0,-1]]){const ii=i+di,jj=j+dj;if(ii<0||jj<0||ii>=cols||jj>=rows)continue;const b=jj*cols+ii;if(grid[b]||prev[b]!==-1)continue;prev[b]=a;q.push(b)}}\n for(const [x,y]of targets){let k=near(x,y);if(k<0||prev[k]<0)continue;let guard=0;while(k!==root&&guard++<4000){used.add(k);k=prev[k]}used.add(root)}\n if(used.size){const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1.96,.12,1.96),M(\'#d8c7a5\'),used.size);let i=0;for(const k of used){DUM.position.set((k%cols)*step+1-WW/2,.18,Math.floor(k/cols)*step+1-WH/2);DUM.scale.set(1,1,1);DUM.rotation.set(0,0,0);DUM.updateMatrix();mesh.setMatrixAt(i++,DUM.matrix)}mesh.receiveShadow=true;G3.add(mesh)}\n // Decorative lamps only occupy genuinely free cells, never facility footprints.\n let count=0;for(const k of used){if(count++%22!==0)continue;const x=(k%cols)*step+1-WW/2,z=Math.floor(k/cols)*step+1-WH/2;cyl(G3,.09,.13,3.4,\'#5c695d\',x,1.9,z,7);sphereDetail(G3,.34,\'#f6e9ba\',x,3.7,z)}\n}\nfunction campusScenery(){if(D.theme.kind===\'indoor\')return;\n // Landscape outside the operational footprint rather than silently moving booths.\n const outline=D.shape.outline;\n outline.forEach((a,i)=>{if(i%2)return;const vx=a[0]-SHC[0],vy=a[1]-SHC[1],len=Math.hypot(vx,vy)||1,x=a[0]+vx/len*7-WW/2,z=a[1]+vy/len*7-WH/2;\n if(z>WH/2+4)return;\n tree(G3,x,z);cyl(G3,1.9,2.2,.55,\'#bca381\',x,.05,z,12);\n });\n // A raised exhibition-board base defines the whole composition.\n const base=bx(G3,WW+28,2.5,WH+85,\'#d7dfd2\',0,-6,22);base.receiveShadow=true;\n const lip=bx(G3,WW+30,.5,WH+87,\'#f2f0e7\',0,-7.4,22);lip.receiveShadow=true;\n}\nconst sceneBeforeCampus=buildScene3;\nbuildScene3=function(){const previousPaths=whitePaths;whitePaths=false;try{sceneBeforeCampus()}finally{whitePaths=previousPaths}if(whitePaths)campusTiles();campusScenery();G3.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true}})};\n\nfunction initR3(){\n  const el=$(\'c3\'); try{ R3=new THREE.WebGLRenderer({antialias:true}); }catch(e){ R3=null; is3d=false; $(\'hint\').textContent=\'이 브라우저는 3D를 지원하지 않아 2D로 표시합니다\'; return; }\n  el.appendChild(R3.domElement);\n  S3=new THREE.Scene(); S3.background=new THREE.Color(\'#eef0e8\'); S3.add(new THREE.HemisphereLight(0xe6f1ff,0x64764c,.75)); const dl=new THREE.DirectionalLight(0xfff2dc,1.05); dl.position.set(-60,120,50); dl.castShadow=true; dl.shadow.mapSize.set(2048,2048); Object.assign(dl.shadow.camera,{left:-180,right:180,top:170,bottom:-170,near:1,far:400}); dl.shadow.bias=-.001; dl.shadow.normalBias=.15; S3.add(dl); R3.shadowMap.enabled=true; R3.shadowMap.type=THREE.PCFSoftShadowMap; R3.outputEncoding=THREE.sRGBEncoding; R3.toneMapping=THREE.ACESFilmicToneMapping; R3.toneMappingExposure=1.12;\n  C3=new THREE.OrthographicCamera(-1,1,1,-1,-800,1200);\n  const N=NAG; bodyM=new THREE.InstancedMesh(new THREE.CylinderGeometry(.55,.65,2.4,8),M(\'#f97316\'),N); headM=new THREE.InstancedMesh(new THREE.SphereGeometry(.7,10,8),M(\'#fde68a\'),N);\n  bodyM.frustumCulled=false; headM.frustumCulled=false; S3.add(bodyM); S3.add(headM);\n  const rp=new Float32Array(500*3); for(let i=0;i<500;i++){rp[i*3]=(Math.random()-.5)*WW;rp[i*3+1]=Math.random()*60;rp[i*3+2]=(Math.random()-.5)*WH;}\n  rainPts=new THREE.Points(new THREE.BufferGeometry().setAttribute(\'position\',new THREE.BufferAttribute(rp,3)),new THREE.PointsMaterial({color:0x60a5fa,size:1.2})); rainPts.visible=false; rainPts.frustumCulled=false; S3.add(rainPts);\n  emgGrp=new THREE.Mesh(new THREE.SphereGeometry(1.8,16,12),new THREE.MeshBasicMaterial({color:0xef4444})); emgGrp.visible=false; S3.add(emgGrp);\n  emgLine=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),new THREE.LineBasicMaterial({color:0xef4444})); emgLine.visible=false; emgLine.frustumCulled=false; S3.add(emgLine);\n  heatTex=new THREE.CanvasTexture(hm); heatPlane=new THREE.Mesh(new THREE.PlaneGeometry(WW,WH),new THREE.MeshBasicMaterial({map:heatTex,transparent:true,opacity:.8,depthWrite:false})); heatPlane.rotation.x=-Math.PI/2; heatPlane.position.y=.5; heatPlane.visible=false; S3.add(heatPlane);\n  const e=R3.domElement;\n  e.style.touchAction=\'none\';\n  e.onpointerdown=pointerDown3;\n  e.onpointermove=pointerMove3;\n  e.onpointerup=e.onpointercancel=()=>{drag=false;editDrag=null};\n  e.addEventListener(\'wheel\',ev=>{ev.preventDefault();zoom3=Math.min(3.2,Math.max(.6,zoom3*(ev.deltaY<0?1.1:.9)));},{passive:false});\n  size3(); buildScene3();\n}\nfunction size3(){ if(!R3) return; const el=$(\'c3\'); const w=el.clientWidth,h=el.clientHeight; R3.setPixelRatio(Math.min(2,window.devicePixelRatio||1)); R3.setSize(w,h); const f=102,asp=w/h; C3.left=-f*asp; C3.right=f*asp; C3.top=f; C3.bottom=-f; C3.updateProjectionMatrix(); }\nfunction render3(){\n  if(!R3) return; const Rr=400;\n  C3.position.set(Math.sin(yaw)*Math.cos(pitch)*Rr,Math.sin(pitch)*Rr,Math.cos(yaw)*Math.cos(pitch)*Rr); C3.position.z+=22;C3.lookAt(0,0,22); C3.zoom=zoom3; C3.updateProjectionMatrix();\n  for(let i=0;i<agents.length;i++){ const a=agents[i]; const s=a.active&&peopleOn?1:0.0001; DUM.rotation.set(0,0,0); DUM.scale.set(s,s,s);\n    DUM.position.set(a.x-WW/2,1.7,a.y-WH/2); DUM.updateMatrix(); bodyM.setMatrixAt(i,DUM.matrix); DUM.position.y=3.6; DUM.updateMatrix(); headM.setMatrixAt(i,DUM.matrix); }\n  bodyM.instanceMatrix.needsUpdate=true; headM.instanceMatrix.needsUpdate=true; bodyM.material.color.set(\'#f97316\');\n  rainPts.visible=false; if(rain){ const p=rainPts.geometry.attributes.position; for(let i=0;i<500;i++){ let y=p.getY(i)-1.4; if(y<0) y=60; p.setY(i,y);} p.needsUpdate=true; }\n  if(emg){ emgGrp.visible=true; emgGrp.position.set(emg.x-WW/2,3,emg.y-WH/2); const sc=1+Math.sin(performance.now()/120)*.25; emgGrp.scale.set(sc,sc,sc);\n    if(emg.target){ emgLine.visible=true; const tp=emgLine.geometry.attributes.position; tp.setXYZ(0,emg.x-WW/2,3,emg.y-WH/2); tp.setXYZ(1,emg.target.x+emg.target.w/2-WW/2,3,emg.target.y+emg.target.h/2-WH/2); tp.needsUpdate=true; } }\n  else { emgGrp.visible=false; emgLine.visible=false; }\n  heatPlane.visible=heat3; if(heat3) heatTex.needsUpdate=true;\n  positionFacilityPopup();\n  R3.render(S3,C3);\n}\n/* ---------- 루프 & 컨트롤 ---------- */\nlet last=performance.now(), kt=0;\nfunction loop(now){ const dt=(now-last)/1000; last=now;\n  if(sim){ step(dt); }\n  updateHeat(); const r=drawHeat(hx,W,H,false); drawHeat(h2,W2,H2,true);\n  if(is3d) render3(); else {drawPeople();positionFacilityPopup();}\n  const n=Math.round(D.params.visitors*.5*factor(tHour)); $(\'peopleTxt\').textContent=\'시뮬레이션 군중 ≈ \'+n.toLocaleString()+\'명\';\n  kt+=dt; if(kt>.4){ kt=0; $(\'kPeak\').textContent=r[0].toFixed(2)+\' 명/㎡\'; $(\'kBott\').textContent=(r[2]?Math.round(100*r[1]/r[2]):0)+\'%\';\n    const de=mode===\'after\'?D.detail:D.before_detail; $(\'kMed\').textContent=editDirty?\'저장 후 재계산\':Math.round(de.t_max)+\'초\'; $(\'kRisk\').textContent=editDirty?\'저장 후 재계산\':de.risk_zones+\'개소\'; }\n  requestAnimationFrame(loop);\n}\nfunction setView(v3){ if(v3&&!R3) return; is3d=v3; $(\'c3\').style.display=v3?\'block\':\'none\'; [cv,hm,pp].forEach(c=>c.style.display=v3?\'none\':\'block\');\n  hm.style.display=(!v3&&heat3)?\'block\':\'none\'; $(\'b3d\').className=v3?\'on\':\'\'; $(\'b2d\').className=v3?\'\':\'on\'; $(\'hint\').style.display=v3?\'block\':\'none\'; $(\'bDome\').style.display=(v3&&D.shape.dome)?\'inline-block\':\'none\';\n  if(v3) size3(); }\nfunction togDome(){ domeOn=!domeOn; domeMeshes.forEach(m=>m.visible=domeOn); $(\'bDome\').className=domeOn?\'on\':\'\'; $(\'bDome\').textContent=domeOn?\'🏛️ 지붕 표시\':\'🏛️ 지붕 숨김\'; }\nfunction togHeat3(){ heat3=!heat3; $(\'bHeat3\').className=heat3?\'on\':\'\'; if(!is3d) hm.style.display=heat3?\'block\':\'none\'; }\nfunction setMode(m){ mode=m;selectedId=null;updateFacilityInfo(null); $(\'bMode\').className=m===\'after\'?\'on\':\'\'; $(\'bModeB\').className=m===\'before\'?\'on\':\'\';\n  $(\'verTxt\').textContent=m===\'after\'?\'· AI 최적 배치(종합 \'+D.total.toFixed(1)+\'점)\':\'· 설계 전(종합 \'+D.before_total.toFixed(1)+\'점)\';\n  heat.fill(0); initAgents(); emg=null; $(\'bEmg\').className=\'danger\'; $(\'bEmg\').textContent=\'🚨 응급환자 발생\'; drawBase(); if(R3) buildScene3(); $(\'status\').textContent=\'실시간 군중 시뮬레이션\'; }\nfunction togSim(){ sim=!sim; $(\'bPlay\').textContent=sim?\'⏸ 시뮬레이션 정지\':\'▶ 시뮬레이션 시작\'; }\nfunction togEmg(){ const b=$(\'bEmg\');\n  if(emg){ emg=null; b.className=\'danger\'; b.textContent=\'🚨 응급환자 발생\'; $(\'status\').textContent=\'실시간 군중 시뮬레이션\'; return; }\n  const Zs=Z().filter(z=>z.type!==\'medical\'); const z=Zs[Math.floor(Math.random()*Zs.length)];\n  emg={x:z.x+z.w/2,y:z.y+z.h+2,trail:[],t0:performance.now(),target:null}; b.className=\'danger on\'; b.textContent=\'🚨 응급 해제\'; sim=true; $(\'bPlay\').textContent=\'⏸ 시뮬레이션 정지\'; }\nfunction setTime(h){ tHour=h;if(typeof S3!==\'undefined\'&&S3){const night=h>=18||h<6;S3.background=new THREE.Color(night?\'#15223c\':\'#dceecf\');}  $(\'tSl\').value=h; $(\'tTxt\').textContent=h+\':00\'; $(\'tDesc\').textContent=descT(h); }\nfunction togTl(){ const b=$(\'bTl\'); if(tlTimer){clearInterval(tlTimer);tlTimer=null;b.textContent=\'▶ 재생\';} else { b.textContent=\'⏸ 일시정지\'; tlTimer=setInterval(()=>{ let n=tHour+1; if(n>20)n=10; setTime(n); },2500); } }\n$(\'closeFacilityPopup\').onclick=ev=>{ev.stopPropagation();selectedId=null;updateFacilityInfo(null);refreshSelection()};\n$(\'facilityPopup\').onpointerdown=ev=>ev.stopPropagation();\nwindow.addEventListener(\'resize\',resize);\ncv.addEventListener(\'click\',ev=>{const r=cv.getBoundingClientRect(),x=(ev.clientX-r.left)/r.width*160,y=(ev.clientY-r.top)/r.height*100;selectedId=([...Z()].reverse().find(z=>x>=z.x&&x<=z.x+z.w&&y>=z.y&&y<=z.y+z.h)||{}).id;updateFacilityInfo(selectedZone())});\n$(\'tSl\').min=0;$(\'tSl\').max=23;\nsetTime(D.params.start_hour??14); resize(); initR3(); setView(is3d&&!!R3); setMode(\'after\'); resize(); requestAnimationFrame(loop);\n</script></body></html>\n'


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
    def enrich(z):
        z=dict(z)
        z.setdefault('description',ZONE_META[z['type']]['label']+'로 사용하는 행사 시설입니다.')
        gate=min(result['gates'],key=lambda g:(g['x']-z['x']-z['w']/2)**2+(g['y']-z['y']-z['h']/2)**2)
        distance=math.hypot(gate['x']-z['x']-z['w']/2,gate['y']-z['y']-z['h']/2)*result['mpu']
        reason=z.get('planning_reason','행사 조건을 바탕으로 생성한 배치입니다.')
        z['placement_reason']=reason+f" 가장 가까운 출입구는 {gate['name']}이며 시설 중심에서 직선거리 약 {distance:.1f}m입니다. 위치는 통로·외곽·출입구 여유 조건으로 검사합니다. 직접 편집한 위치의 최적성은 보장하지 않습니다."
        return z
    data['zones']=[enrich(z) for z in data['zones']]
    data['before_zones']=[enrich(z) for z in data['before_zones']]
    data['params'].update(start_hour=result['params'].get('start_hour',10),end_hour=result['params'].get('end_hour',20))
    return TWIN_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("<", "\\u003c"))

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

_EDITOR_BOOTSTRAP_HTML = '<!doctype html><html><meta charset="utf-8"><style>body{margin:0}iframe{border:0;width:100%;height:1600px}</style><iframe id="scene" title="Event ON 3D 편집"></iframe><script>\nconst f=document.getElementById(\'scene\');let rev=null;\nconst send=(type,extra={})=>parent.postMessage({isStreamlitMessage:true,type,...extra},\'*\');\nwindow.addEventListener(\'message\',e=>{if(e.source===parent&&e.data.type===\'streamlit:render\'){const a=e.data.args;if(a.revision!==rev){rev=a.revision;f.srcdoc=a.html}send(\'streamlit:setFrameHeight\',{height:1600});}\nelse if(e.source===f.contentWindow&&e.data.type===\'event:save\'){send(\'streamlit:setComponentValue\',{dataType:\'json\',value:{zones:e.data.zones,revision:rev,token:Date.now()+\'-\'+Math.random()}})}});send(\'streamlit:componentReady\',{apiVersion:1});\n</script></html>'

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
    st.markdown('##### 🧊 행사장 공간 스튜디오')
    st.caption('지원시설은 아이콘으로 표시합니다. 아이콘도 시설의 운영 공간을 차지하므로 충돌 계산에는 기존 계획 면적을 유지합니다. 외부 주차장은 표시용 계획 예시이며 수용량·교통·비용 계산에서 제외합니다.')
    st.caption('편집 모드 → 부스 클릭 → 몸체 드래그로 이동, 노란 손잡이로 크기 조절. 빈 바닥 드래그는 시점 회전입니다. 저장해야 점수·리포트에 반영됩니다.')
    component=get_3d_editor_component()
    import hashlib
    scene_html=build_twin_html(R)
    scene_revision=hashlib.sha256(scene_html.encode('utf-8')).hexdigest()
    value=component(html=scene_html,revision=scene_revision,key='eo_3d_canvas_r4')
    if isinstance(value,dict) and value.get('token')!=ss.get('_last_edit_token'):
        ss['_last_edit_token']=value.get('token')
        try:
            if value.get('revision')!=scene_revision: raise ValueError('오래된 편집 요청입니다.')
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
