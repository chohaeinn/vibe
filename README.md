# 🎪 Event ON — AI 기반 행사 자동 설계 플랫폼

행사 정보를 입력하면 AI가 **수천 개 배치안을 생성 → 군중 이동 시뮬레이션 → 다목적 최적화 → 최적안 선정(설명가능 AI)** 까지 자동으로 수행하는 Streamlit 대시보드입니다.

## 구성
| 파일 | 역할 |
|---|---|
| `app.py` | Streamlit 메인 화면 (입력, AI 어시스턴트, 히스토리, 탭) |
| `optimizer.py` | 배치안 생성 · 군중 시뮬레이션 · 다목적 최적화(파레토) · XAI · 명령어 해석 |
| `twin.py` | 디지털 트윈 2D/3D 실시간 군중 렌더러 (Canvas + Three.js) |
| `report.py` | 분석 리포트 (Markdown / 인쇄용 HTML) |

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub → Streamlit Cloud 배포
```bash
git init && git add . && git commit -m "Event ON"
git branch -M main
git remote add origin https://github.com/<계정>/event-on.git
git push -u origin main
```
1. https://share.streamlit.io 접속 → GitHub 로그인
2. **New app** → 저장소 / 브랜치 `main` / Main file path `app.py` 선택 → **Deploy**

## 알고리즘 요약
1. **디지털 트윈**: 방문객·예산·목적·분위기·연령으로 구역 수/크기 결정 (예산 초과 시 부스 자동 축소)
2. **배치안 생성**: 무작위 샘플링 75% + 상위안 변이 25% (기본 2,000개, 최대 5,000개)
3. **군중 시뮬레이션**: 출입구→구역 이동 + 구역 체류 군중을 격자 밀집도로 계산
4. **다목적 최적화**: 비상 안전성·동선 효율·접근성·혼잡 분산·공간 활용을 파레토 필터 후 목적/연령 기반 가중합으로 선정
5. **XAI**: 점수 기여도, 후보 대비 순위, 구역별 배치 근거, 채택하지 않은 대안 제시
6. **결과**: 배치도, 설계 전/후 비교, 리포트 다운로드

## AI 어시스턴트 예시 명령
- `무대를 우측으로, 응급의료센터를 중앙에 배치해줘`
- `포토존 2개 추가`

> 모든 수치는 가상 시뮬레이션 기반 추정이며, 실제 시행 전 현장 안전 점검이 필요합니다.
