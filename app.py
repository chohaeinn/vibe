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
        st.markdown("#### 점수 산정 기준과 근거")
        st.markdown(
            "점수는 현장 실측이나 법정 안전 인증 점수가 아니라, 앱 내부 시뮬레이션 지표를 0~100으로 정규화한 상대 평가값입니다. "
            "동일한 평가 함수를 모든 후보 배치안에 적용하고, 행사 목적·연령대에 따라 항목별 가중치를 조정합니다."
        )
        st.dataframe(pd.DataFrame([
            {"평가 항목": "비상 안전성", "기본 가중치": "25%", "계산 지표": "응급의료센터 추정 도달시간, 의료센터-출입구 거리, 최근접 출입구 거리"},
            {"평가 항목": "동선 효율성", "기본 가중치": "20%", "계산 지표": "다른 구역 관통률, 출입구-구역 평균 거리"},
            {"평가 항목": "접근성", "기본 가중치": "15%", "계산 지표": "안내센터·화장실·휴게공간 최근접 거리"},
            {"평가 항목": "혼잡도 분산", "기본 가중치": "25%", "계산 지표": "격자별 최대 추정 밀도, 상위 5% 격자 인원 집중도"},
            {"평가 항목": "공간 활용성", "기본 가중치": "15%", "계산 지표": "시설 점유율, 시설 간 최근접 거리"},
        ]), hide_index=True, use_container_width=True)
        st.caption("가중 종합점수는 각 항목 점수×실제 가중치의 합입니다. 실제 가중치는 행사 목적·연령대에 따라 조정됩니다. 응급 도달시간은 단순 거리 기반 추정이며 실제 보행 속도·장애물·군중 흐름을 완전히 반영하지 않습니다.")
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

