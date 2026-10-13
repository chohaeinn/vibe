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


def build_zones(p: dict, custom: List[dict]):
    """입력 조건 -> 구역 목록. 예산이 부족하면 부스/푸드 수를 줄인다."""
    V = p["visitors"]
    mpu = math.sqrt(p["area_m2"] / (WORLD_W * WORLD_H))   # unit 당 미터
    pm, mm, am = PURPOSES[p["purpose"]], MOODS[p["mood"]], AGES[p["age"]]
    notes: List[str] = []

    SZ = 1.35   # 화면에서 잘 보이도록 구역을 키운다

    def u(m, cap):
        return float(_clamp(m / mpu * SZ, 5.0, cap * 1.3))

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
            w=round(u(wm, cap), 2), h=round(u(hm, cap * 0.7), 2),
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
    limit = 0.30 * WORLD_W * WORLD_H
    if area_sum > limit:
        f = math.sqrt(limit / area_sum)
        for z in zones:
            z["w"] = round(max(4.0, z["w"] * f), 2)
            z["h"] = round(max(3.5, z["h"] * f), 2)
        notes.append("구역 수가 많아 배치도에 모두 들어가도록 각 구역 크기를 자동으로 줄였습니다.")
    for i, z in enumerate(zones):
        z["id"] = i
    return zones, notes, mpu, cost


def get_gates(n: int):
    idx = {2: [0, 1], 4: [0, 1, 2, 3], 6: [0, 1, 2, 3, 4, 5]}[n]
    gates = [dict(x=float(GATE_POS[i][0]), y=float(GATE_POS[i][1]), name=GATE_POS[i][2]) for i in idx]
    shares = [0.4] + [0.6 / (len(gates) - 1)] * (len(gates) - 1)
    for g, s in zip(gates, shares):
        g["share"] = float(s)
    return gates


def make_ctx(zones, p, mpu, gates):
    n = len(zones)
    types = [z["type"] for z in zones]
    attract = np.array([z["attract"] for z in zones], float)
    dwell = [i for i, t in enumerate(types) if t != "medical"]
    a_norm = np.zeros(n)
    a_norm[dwell] = attract[dwell] / attract[dwell].sum()
    C = p["visitors"] * 0.5                       # 피크 동시 체류 인원
    return dict(
        mpu=mpu, n=n, types=types, dwell_idx=np.array(dwell),
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
def region_ok(z, x, y, pins):
    r = pins.get(z["type"])
    if not r:
        return True
    cx, cy = x + z["w"] / 2, y + z["h"] / 2
    return r[0] * WORLD_W <= cx <= r[1] * WORLD_W and r[2] * WORLD_H <= cy <= r[3] * WORLD_H


def _valid(x, y, w, h, P, mask, gates):
    if x < MARGIN or y < MARGIN or x + w > WORLD_W - MARGIN or y + h > WORLD_H - MARGIN:
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
                cx = rng.uniform(r[0] * WORLD_W, r[1] * WORLD_W)
                cy = rng.uniform(r[2] * WORLD_H, r[3] * WORLD_H)
                x, y = cx - z["w"] / 2, cy - z["h"] / 2
            else:
                x = rng.uniform(MARGIN, max(MARGIN, WORLD_W - MARGIN - z["w"]))
                y = rng.uniform(MARGIN, max(MARGIN, WORLD_H - MARGIN - z["h"]))
            if _valid(x, y, z["w"], z["h"], P, mask, ctx["gate_xy"]):
                P[i] = (x, y, z["w"], z["h"])
                mask[i] = True
                ok = True
                break
        if not ok:
            return None
    return P


def mutate(L, zones, ctx, pins, rng):
    P = L.copy()
    n = len(zones)
    for j in rng.choice(n, size=min(int(rng.integers(1, 4)), n), replace=False):
        z = zones[j]
        for _ in range(25):
            if rng.random() < 0.65:
                nx, ny = P[j, 0] + rng.normal(0, 9), P[j, 1] + rng.normal(0, 9)
            else:
                nx = rng.uniform(MARGIN, max(MARGIN, WORLD_W - MARGIN - z["w"]))
                ny = rng.uniform(MARGIN, max(MARGIN, WORLD_H - MARGIN - z["h"]))
            if not region_ok(z, nx, ny, pins):
                continue
            mask = np.ones(n, bool)
            mask[j] = False
            if _valid(nx, ny, z["w"], z["h"], P, mask, ctx["gate_xy"]):
                P[j, 0], P[j, 1] = nx, ny
                break
    return P


def baseline_layout(zones):
    """설계 전(기존) 배치: 출입구 인근에 일렬로 몰아서 배치하는 전형적인 수작업 배치."""
    pri = {"stage": 0, "food": 1, "booth": 2, "custom": 3, "rest": 4, "info": 5, "restroom": 6, "medical": 7}
    idx = sorted(range(len(zones)), key=lambda i: (pri[zones[i]["type"]], i))
    rows, cur, cw = [], [], MARGIN
    for i in idx:
        w = zones[i]["w"]
        if cur and cw + w > WORLD_W - MARGIN:
            rows.append(cur)
            cur, cw = [], MARGIN
        cur.append(i)
        cw += w + PAD
    rows.append(cur)
    L = np.zeros((len(zones), 4))
    y_bottom = WORLD_H - 8
    for row in rows:
        rh = max(zones[i]["h"] for i in row)
        y = max(2.0, y_bottom - rh)
        x = MARGIN
        for i in row:
            L[i] = (x, y, zones[i]["w"], zones[i]["h"])
            x += zones[i]["w"] + PAD
        y_bottom = y - PAD
    return L


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

    # 혼잡도
    peak = float(dens.max())
    flat = np.sort(dens.ravel())[::-1]
    k5 = max(1, int(len(flat) * 0.05))
    top5 = float(flat[:k5].sum() / max(flat.sum(), 1e-9))
    s_peak = float(np.clip(1 - (peak - 0.15) / 0.9, 0, 1))
    s_even = float(np.clip(1 - (top5 - 0.18) / 0.45, 0, 1))
    s_cong = 100 * (0.7 * s_peak + 0.3 * s_even)

    # 동선
    s_flow = 100 * (0.5 * np.clip(1 - obstruct / 0.25, 0, 1)
                    + 0.5 * np.clip(1 - (avg_dist_u / (0.5 * WORLD_W) - 0.4) / 0.8, 0, 1))

    # 안전
    med, oth = ctx["medical"], ctx["non_med"]
    dm = np.hypot(cx[oth][:, None] - cx[med][None, :], cy[oth][:, None] - cy[med][None, :]) * mpu
    t_resp = 15 + dm.min(axis=1) / 2.0
    t_max, t_mean = float(t_resp.max()), float(t_resp.mean())
    gd = np.hypot(cx[med][:, None] - G[:, 0][None, :], cy[med][:, None] - G[:, 1][None, :]) * mpu
    gate_med = float(gd.min(axis=1).mean())
    near_gate = np.hypot(cx[:, None] - G[:, 0][None, :], cy[:, None] - G[:, 1][None, :]).min(axis=1) * mpu
    evac = float(near_gate.mean())
    s_safety = 100 * (0.35 * np.clip(1 - (t_max - 35) / 130, 0, 1) + 0.20 * np.clip(1 - (t_mean - 25) / 100, 0, 1)
                      + 0.20 * np.clip(1 - (gate_med - 20) / 130, 0, 1) + 0.25 * np.clip(1 - (evac - 20) / 120, 0, 1))

    # 접근성
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
    s_access = 100 * (0.35 * np.clip(1 - (info_m - 15) / 90, 0, 1) + 0.40 * np.clip(1 - (rr_m - 20) / 100, 0, 1)
                      + 0.25 * np.clip(1 - (rest_m - 25) / 130, 0, 1))

    # 공간 활용
    cov = float((w * h).sum() / (WORLD_W * WORLD_H))
    dc = np.hypot(cx[:, None] - cx[None, :], cy[:, None] - cy[None, :])
    np.fill_diagonal(dc, 1e9)
    nn = dc.min(axis=1)
    ideal = 0.55 * math.sqrt(WORLD_W * WORLD_H / n)
    s_space = 100 * (0.35 * np.clip(1 - abs(cov - 0.25) / 0.2, 0, 1) + 0.65 * np.clip(nn.mean() / ideal, 0, 1))

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
        heat=np.round(dens, 3).tolist(),
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
    gates = get_gates(params["gates"])
    ctx = make_ctx(zones, params, mpu, gates)
    weights = get_weights(params)
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
    Lb = baseline_layout(zones)
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
  a.x=g.x+(Math.random()-.5)*4; a.y=g.y+(Math.random()-.5)*4; a.leaving=false; a.dwell=0; a.zone=pickZone(); setTarget(a);
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
    else { a.x+=dx/d*sp; a.y+=dy/d*sp; }
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
  if(bg){ ctx.fillStyle='#0f172a'; ctx.fillRect(0,0,w,h); }
  const cw=w/GX, ch=h/GY; let peak=0,hot=0,act=0;
  for(let y=0;y<GY;y++)for(let x=0;x<GX;x++){ const d=heat[y*GX+x]; peak=Math.max(peak,d); if(d>=.12) act++; if(d>=.5) hot++; const c=heatColor(d); if(c){ ctx.fillStyle=c; ctx.fillRect(x*cw,y*ch,cw+.5,ch+.5);} }
  if(bg){ Z().forEach(z=>{ ctx.strokeStyle='rgba(255,255,255,.45)'; ctx.lineWidth=1; ctx.strokeRect(z.x*w/WW,z.y*h/WH,z.w*w/WW,z.h*h/WH);
      ctx.fillStyle='rgba(255,255,255,.85)'; ctx.font='bold 10px Pretendard,sans-serif'; ctx.textAlign='center'; ctx.fillText(z.name,(z.x+z.w/2)*w/WW,(z.y+z.h/2)*h/WH+3,z.w*w/WW); }); }
  return [peak,hot,act];
}
/* ---------- 2D 평면도 ---------- */
function drawBase(){
  const T=D.theme; cx.clearRect(0,0,W,H);
  cx.fillStyle=rain?T.groundRain:T.ground; cx.fillRect(0,0,W,H);
  if(T.kind==='outdoor'){ cx.fillStyle='rgba(0,0,0,.14)'; for(let x=6;x<W;x+=26){cx.beginPath();cx.arc(x,7,11,0,7);cx.fill();cx.beginPath();cx.arc(x,H-7,11,0,7);cx.fill();} }
  else { cx.strokeStyle='rgba(0,0,0,.12)'; cx.lineWidth=1; for(let x=0;x<W;x+=W/16){cx.beginPath();cx.moveTo(x,0);cx.lineTo(x,H);cx.stroke();} for(let y=0;y<H;y+=H/10){cx.beginPath();cx.moveTo(0,y);cx.lineTo(W,y);cx.stroke();} }
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
    cx.font='bold 11px Pretendard'; cx.fillStyle='#fff'; cx.shadowColor='#000'; cx.shadowBlur=3; cx.fillText(g.name,g.x*S,g.y*S+(g.y>50?-15:24)); cx.shadowBlur=0; });
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
let yaw=.55,pitch=.72,zoom3=1.45,drag=false,lx=0,ly=0;
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
function wallSide(horiz,fixed,len,gates){
  const segs=[]; let cur=-len/2; const gs=gates.slice().sort((a,b)=>a-b);
  gs.forEach(gp=>{ if(gp-7>cur) segs.push([cur,gp-7]); cur=gp+7; }); if(cur<len/2) segs.push([cur,len/2]);
  segs.forEach(s=>{ const L=s[1]-s[0], mid=(s[0]+s[1])/2;
    if(horiz) bx(G3,L,5,1.4,'#f8fafc',mid,2.5,fixed); else bx(G3,1.4,5,L,'#f8fafc',fixed,2.5,mid); });
}
function buildScene3(){
  if(G3) S3.remove(G3); G3=new THREE.Group(); S3.add(G3);
  const T=D.theme; const ground=rain?T.groundRain:T.ground;
  bx(G3,WW+8,4,WH+8,'#e5e7eb',0,-2.7,0); bx(G3,WW,.7,WH,ground,0,-.35,0);
  if(T.kind==='outdoor'){ for(let x=-WW/2+4;x<WW/2;x+=14){ tree(G3,x,-WH/2+2.5); tree(G3,x+7,WH/2-2.5); } }
  const gT=[],gB=[],gL=[],gR=[];
  D.gates.forEach(g=>{ if(g.y<10) gT.push(g.x-WW/2); else if(g.y>90) gB.push(g.x-WW/2); else if(g.x<10) gL.push(g.y-WH/2); else gR.push(g.y-WH/2); });
  wallSide(true,-WH/2-.7,WW+2,gT); wallSide(true,WH/2+.7,WW+2,gB); wallSide(false,-WW/2-.7,WH+2,gL); wallSide(false,WW/2+.7,WH+2,gR);
  const pc=T.path;
  Z().forEach(z=>{ const g=nearestGate(z); const x1=g.x-WW/2,z1=g.y-WH/2,x2=z.x+z.w/2-WW/2,z2=z.y+z.h/2-WH/2; const dx=x2-x1,dz=z2-z1,L=Math.hypot(dx,dz);
    const m=bx(G3,L,.3,3.2,pc,(x1+x2)/2,.15,(z1+z2)/2); m.rotation.y=-Math.atan2(dz,dx); });
  D.gates.forEach(g=>{ const x=g.x-WW/2,zz=g.y-WH/2; const horiz=(g.y<10||g.y>90);
    const ox=horiz?6:0, oz=horiz?0:6;
    bx(G3,1.6,8,1.6,'#1e293b',x-ox,4,zz-oz); bx(G3,1.6,8,1.6,'#1e293b',x+ox,4,zz+oz);
    bx(G3,horiz?14:1.8,1.4,horiz?1.8:14,'#1e293b',x,8,zz);
    const sp=labelSprite('🚪 '+g.name,'#1e293b'); sp.scale.set(15,15*150/640,1); sp.position.set(x,12,zz); G3.add(sp); });
  Z().forEach(buildZone3);
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
  hm.style.display=(!v3&&heat3)?'block':'none'; $('b3d').className=v3?'on':''; $('b2d').className=v3?'':'on'; $('hint').style.display=v3?'block':'none';
  if(v3) size3(); }
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
        total=result["total"], before_total=result["before_total"],
        detail=dict(t_max=result["detail"]["t_max"], risk_zones=result["detail"]["risk_zones"]),
        before_detail=dict(t_max=result["before_detail"]["t_max"], risk_zones=result["before_detail"]["risk_zones"]),
    )
    return TWIN_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))

# ===== REPORT =====



def grade(s: float) -> str:
    return "매우 우수" if s >= 90 else "우수" if s >= 80 else "보통" if s >= 65 else "개선 필요"


def build_markdown(r: dict) -> str:
    p, d, b = r["params"], r["detail"], r["before_detail"]
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [f"# {p['name']} — AI 행사장 설계 분석 리포트", f"_생성: {now} · Event ON_", ""]
    L += ["## 1. 행사 개요",
          f"- 행사 목적: {p['purpose']} / 분위기: {p['mood']}",
          f"- 장소: {p['venue']} ({p['location']}), 면적 {p['area_m2']:,}㎡",
          f"- 예상 방문객 {p['visitors']:,}명, 연령대 {p['age']}, 운영 {p['hours']}",
          f"- 예산 {p['budget']:,}만원 (예상 시설 비용 {r['cost']['total']:,.0f}만원)", ""]
    L += ["## 2. 최적화 요약",
          f"- 생성·평가한 배치안 {r['stats']['generated']:,}개 (무작위 {r['stats']['randomly']:,} + 변이 {r['stats']['mutated']:,})",
          f"- 파레토 최적해 {r['stats']['pareto']}개 중 가중 종합점수 최고안 선정: **{r['total']:.1f}점** (설계 전 {r['before_total']:.1f}점)", ""]
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
    if r["notes"]:
        L += ["## 5. 유의사항"] + [f"- {n}" for n in r["notes"]] + [""]
    L += ["---", "※ 수치는 가상 군중 시뮬레이션 기반 추정치이며, 실제 시행 전 현장 안전 점검·관할 기관 협의가 필요합니다."]
    return "\n".join(L)


def build_html(r: dict) -> str:
    md = build_markdown(r)
    body, in_tbl = [], False
    for line in md.split("\n"):
        e = _html.escape(line)
        e = e.replace("**", "§")
        while "§" in e:
            e = e.replace("§", "<b>", 1).replace("§", "</b>", 1)
        if line.startswith("|"):
            if set(line.replace("|", "").strip()) <= {"-"}:
                continue
            cells = [c.strip() for c in e.strip("|").split("|")]
            if not in_tbl:
                body.append("<table>")
                in_tbl = True
                body.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
            else:
                body.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue
        if in_tbl:
            body.append("</table>")
            in_tbl = False
        if line.startswith("### "):
            body.append(f"<h3>{e[4:]}</h3>")
        elif line.startswith("## "):
            body.append(f"<h2>{e[3:]}</h2>")
        elif line.startswith("# "):
            body.append(f"<h1>{e[2:]}</h1>")
        elif line.startswith("- "):
            body.append(f"<p class='li'>• {e[2:]}</p>")
        elif line.strip():
            body.append(f"<p>{e}</p>")
    if in_tbl:
        body.append("</table>")
    return ("<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>Event ON 리포트</title><style>"
            "body{font-family:Pretendard,'Malgun Gothic',sans-serif;max-width:860px;margin:30px auto;padding:0 20px;color:#1e293b;line-height:1.65}"
            "h1{color:#1e3a8a}h2{border-bottom:2px solid #e2e8f0;padding-bottom:4px;margin-top:28px}"
            "table{border-collapse:collapse;width:100%;margin:10px 0}th,td{border:1px solid #cbd5e1;padding:6px 10px;text-align:left;font-size:14px}"
            "th{background:#eff6ff}.li{margin:3px 0 3px 8px}@media print{body{margin:0}}</style></head><body>"
            + "\n".join(body) + "</body></html>")

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

ss = st.session_state
ss.setdefault("custom", [])
ss.setdefault("pins", {})
ss.setdefault("chat", [("ai", "안녕하세요! 예) '무대를 우측으로, 응급의료센터를 중앙에 배치해줘', '칵테일 바 2개 추가' 처럼 말씀해 주세요.")])
ss.setdefault("history", [])
ss.setdefault("result", None)
ss.setdefault("view", None)
ss.setdefault("pending", None)

# ----------------------------------------------------------------------------- 사이드바 입력
with st.sidebar:
    st.markdown("## ✦ Event ON")
    st.caption("AI 기반 행사 설계·분석 플랫폼")
    st.markdown("### 📝 행사 정보")
    name = st.text_input("행사명", "2025 힐링 페스티벌")
    purpose = st.selectbox("행사 목적", list(PURPOSES))
    c1, c2 = st.columns(2)
    budget = c1.number_input("예산(만원)", 500, 500000, 5000, step=500)
    visitors = c2.number_input("예상 방문객(명)", 200, 100000, 5000, step=500)
    venue = st.selectbox("행사 장소 유형", list(VENUES))
    location = st.text_input("행사장 위치", "야외 종합 운동장 & 잔디 광장")
    c3, c4 = st.columns(2)
    area = c3.number_input("면적(㎡)", 500, 1000000, 50000, step=1000)
    hours = c4.text_input("운영 시간", "10시 - 20시")
    mood = st.selectbox("원하는 분위기", list(MOODS))
    age = st.selectbox("예상 연령대", list(AGES))
    gates = st.selectbox("출입구 수", [2, 4, 6], index=1, format_func=lambda n: f"{n}개")
    n_cand = st.select_slider("탐색할 배치안 수", [500, 1000, 2000, 3000, 5000], value=2000)

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
                location=location, area_m2=int(area), hours=hours, mood=mood, age=age, gates=int(gates))


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
    ss.history.append(dict(label=f"v{len(ss.history) + 1} · {label} ({dt.datetime.now():%H:%M:%S})", result=res))
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
        for n in R["notes"]:
            st.warning(n)

        m = st.columns(5)
        m[0].metric("행사", P["name"])
        m[1].metric("방문객", f"{P['visitors']:,}명")
        m[2].metric("면적", f"{P['area_m2']:,}㎡")
        m[3].metric("종합 점수", f"{R['total']:.1f}점", f"{R['total'] - R['before_total']:+.1f} vs 설계 전")
        m[4].metric("예상 비용", f"{R['cost']['total']:,.0f}만원", f"예산 {R['cost']['budget']:,}만원", delta_color="off")

        # ---- AI 어시스턴트
        st.markdown("##### 🤖 AI 어시스턴트 — 말로 배치를 바꾸거나 부스를 추가하세요")
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
        components.html(build_twin_html(R), height=1330, scrolling=True)

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
            st.info(f"{R['stats']['generated']:,}개 배치안 중 종합 {R['total']:.1f}점 최적안 선정. "
                    f"응급 최대 도달 {fmt_sec(d['t_max'])}, 위험구역 {d['risk_zones']}개소.")

# ----------------------------------------------------------------------------- 프로세스
with tab_wf:
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
    if ss.history:
        R = ss.history[ss.view]["result"]
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
        st.markdown(build_markdown(R))
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ 리포트(HTML, 인쇄→PDF 저장)", build_html(R), file_name="event_on_report.html", mime="text/html")
        d2.download_button("⬇️ 리포트(Markdown)", build_markdown(R), file_name="event_on_report.md", mime="text/markdown")
