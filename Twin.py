# -*- coding: utf-8 -*-
"""디지털 트윈 렌더러: 최적화 결과(JSON)를 받아 2D/3D 실시간 군중 시뮬레이션 HTML 생성."""
import json

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
.grid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:12px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:12px}
.card h4{font-size:13px;font-weight:800;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.wrap{position:relative;width:100%;aspect-ratio:1.6;background:#1e293b;border-radius:10px;overflow:hidden}
.wrap canvas,.wrap .c3{position:absolute;inset:0;width:100%;height:100%}
.c3{display:none}
.legend{position:absolute;left:8px;bottom:8px;background:rgba(255,255,255,.92);border-radius:8px;padding:6px 9px;font-size:10px;font-weight:700;display:grid;grid-template-columns:repeat(2,auto);gap:2px 10px;z-index:5}
.legend i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px}
.tl{display:flex;align-items:center;gap:8px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:6px 10px;margin-bottom:8px;font-size:12px;font-weight:700}
.tl input{flex:1;accent-color:#2563eb}
.tm{background:#2563eb;color:#fff;border-radius:16px;padding:2px 10px;font-size:12px;min-width:56px;text-align:center}
.kpi{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-bottom:8px}
.kpi div{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:6px 8px;font-size:11px;color:#64748b;font-weight:700}
.kpi b{display:block;font-size:15px;color:#0f172a}
.hl{font-size:11px;color:#64748b;font-weight:700;display:flex;justify-content:space-around;margin-top:6px}
</style></head><body>
<div class="bar">
  <button id="bMode" class="on" onclick="setMode('after')">✦ AI 최적 배치</button>
  <button id="bModeB" onclick="setMode('before')">설계 전(기존) 배치</button>
  <span style="flex:1"></span>
  <button id="bPlay" onclick="togSim()">⏸ 시뮬레이션 정지</button>
  <button id="bRain" class="warn" onclick="togRain()">🌧️ 우천</button>
  <button id="bEmg" class="danger" onclick="togEmg()">🚨 응급환자 발생</button>
  <button id="b3d" onclick="tog3d()">🧊 3D</button>
  <span class="badge" id="status">실시간 군중 시뮬레이션</span>
</div>
<div class="tl">⏰ 시간대
  <button id="bTl" onclick="togTl()">▶ 재생</button>
  <input type="range" id="tSl" min="10" max="20" step="1" value="14" oninput="setTime(+this.value)">
  <span class="tm" id="tTxt">14:00</span><span id="tDesc" style="color:#64748b;font-weight:600"></span>
</div>
<div class="grid">
  <div class="card"><h4><span>🗺️ 디지털 트윈 배치도 <span id="verTxt" style="color:#64748b;font-weight:600"></span></span><span class="badge" id="peopleTxt"></span></h4>
    <div class="wrap" id="wrap">
      <canvas id="cv"></canvas><canvas id="hm" style="opacity:.8;pointer-events:none"></canvas><canvas id="pp" style="pointer-events:none"></canvas>
      <div class="c3" id="c3"></div>
      <div class="legend" id="legend"></div>
    </div>
  </div>
  <div class="card"><h4><span>🔥 실시간 군중 밀집도</span><span class="badge" id="envTxt">일반 상태</span></h4>
    <div class="wrap"><canvas id="hm2"></canvas></div>
    <div class="hl"><span style="color:#10b981">🟢 원활(&lt;0.25)</span><span style="color:#eab308">🟡 보통</span><span style="color:#f97316">🟠 혼잡(≥0.5)</span><span style="color:#ef4444">🔴 위험(≥0.9)</span></div>
    <div style="font-size:10px;color:#94a3b8;margin-top:4px;text-align:center">단위: 명/㎡ · 구역 체류 + 출입구 이동 군중 반영</div>
    <div class="kpi" style="margin-top:10px">
      <div>현재 최대 밀도<b id="kPeak">-</b></div><div>혼잡 구역 비율<b id="kBott">-</b></div>
      <div>응급 최대 도달<b id="kMed">-</b></div><div>위험 구역<b id="kRisk">-</b></div>
    </div>
  </div>
</div>
<script>
const D = __DATA__;
const WW=160, WH=100, GX=40, GY=25;
let mode='after', sim=true, rain=false, emg=null, tHour=14, tlTimer=null, is3d=false;
const cv=document.getElementById('cv'), hm=document.getElementById('hm'), pp=document.getElementById('pp'), hm2=document.getElementById('hm2');
const cx=cv.getContext('2d'), hx=hm.getContext('2d'), px=pp.getContext('2d'), h2=hm2.getContext('2d');
const wrap=document.getElementById('wrap');
let W=0,H=0,S=1;
const Z=()=> mode==='after'?D.zones:D.before_zones;
const mpu=D.mpu, cellArea=(WW/GX)*(WH/GY)*mpu*mpu;
const NAG=320; let agents=[]; let raindrops=[];
let heat=new Float32Array(GX*GY);

document.getElementById('legend').innerHTML=
 [['#8b5cf6','공연'],['#3b82f6','체험'],['#f59e0b','푸드'],['#10b981','휴게'],['#ef4444','응급의료'],['#0ea5e9','안내'],['#06b6d4','화장실'],['#ec4899','사용자'],['#64748b','출입구']]
 .map(a=>`<span><i style="background:${a[0]}"></i>${a[1]}</span>`).join('');

function resize(){
  W=wrap.clientWidth; H=wrap.clientHeight; S=W/WW;
  [cv,hm,pp,hm2].forEach(c=>{c.width=W;c.height=H});
  drawBase(); if(is3d) build3d();
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
  agents=[]; for(let i=0;i<NAG;i++){ const a={}; spawn(a); const z=Z()[a.zone]; const t=Math.random(); a.x=a.x+(a.tx-a.x)*t; a.y=a.y+(a.ty-a.y)*t; a.active=i<NAG*factor(tHour); agents.push(a);}
  raindrops=[]; for(let i=0;i<110;i++) raindrops.push({x:Math.random()*W,y:Math.random()*H,l:7+Math.random()*10,v:6+Math.random()*6});
}
function inside(a,z){ return a.x>=z.x-2&&a.x<=z.x+z.w+2&&a.y>=z.y-2&&a.y<=z.y+z.h+2; }
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
  // 근접 반발(군중 분산)
  for(let i=0;i<agents.length;i+=2){ const a=agents[i]; if(!a.active) continue; const b=agents[(i*7+3)%agents.length]; if(!b.active) continue;
    const dx=a.x-b.x, dy=a.y-b.y, d=Math.hypot(dx,dy); if(d>0&&d<1.2){ a.x+=dx/d*.1; a.y+=dy/d*.1; } }
  if(emg){ const meds=Z().filter(z=>z.type==='medical'); let best=null,bd=1e9;
    meds.forEach(m=>{const d=Math.hypot(m.x+m.w/2-emg.x,m.y+m.h/2-emg.y); if(d<bd){bd=d;best=m;}});
    emg.target=best;
    if(best&&bd>1.5){ emg.x+=(best.x+best.w/2-emg.x)/bd*.9; emg.y+=(best.y+best.h/2-emg.y)/bd*.9; emg.trail.push([emg.x,emg.y]);
      document.getElementById('status').textContent='🚑 응급 이송 중… 의료센터까지 '+(bd*mpu).toFixed(0)+'m';
    } else if(best){ document.getElementById('status').textContent='✅ 의료센터 도착 · 이송 소요 '+Math.round(emg.t0?((performance.now()-emg.t0)/1000):0)+'초(시뮬레이션)'; } }
  raindrops.forEach(r=>{r.y+=r.v;r.x-=1;if(r.y>H){r.y=0;r.x=Math.random()*W}});
}
function updateHeat(){
  const n=Math.floor(NAG*factor(tHour)); const per=D.params.visitors*.5/Math.max(1,n)*(factor(tHour)/1.0);
  const g=new Float32Array(GX*GY);
  agents.forEach(a=>{ if(!a.active) return; const ix=Math.min(GX-1,Math.max(0,Math.floor(a.x/(WW/GX)))), iy=Math.min(GY-1,Math.max(0,Math.floor(a.y/(WH/GY)))); g[iy*GX+ix]+=per; });
  // 3x3 평활화
  const o=new Float32Array(GX*GY);
  for(let y=0;y<GY;y++)for(let x=0;x<GX;x++){ let s=0,c=0; for(let j=-1;j<=1;j++)for(let i=-1;i<=1;i++){const xx=x+i,yy=y+j; if(xx>=0&&xx<GX&&yy>=0&&yy<GY){const w=(i==0&&j==0)?2:1; s+=g[yy*GX+xx]*w; c+=w;}} o[y*GX+x]=s/c/cellArea; }
  for(let k=0;k<o.length;k++) heat[k]=heat[k]*.85+o[k]*.15;
}
function heatColor(d){ if(d<.12) return null; if(d<.25) return 'rgba(16,185,129,.45)'; if(d<.5) return 'rgba(234,179,8,.6)'; if(d<.9) return 'rgba(249,115,22,.72)'; return 'rgba(239,68,68,.85)'; }
function drawHeat(ctx){ ctx.clearRect(0,0,W,H);
  if(ctx===h2){ ctx.fillStyle='#0f172a'; ctx.fillRect(0,0,W,H); drawZonesLite(ctx); }
  const cw=W/GX, ch=H/GY; let peak=0,hot=0,act=0;
  for(let y=0;y<GY;y++)for(let x=0;x<GX;x++){ const d=heat[y*GX+x]; peak=Math.max(peak,d); if(d>=.12) act++; if(d>=.5) hot++; const c=heatColor(d); if(c){ ctx.fillStyle=c; ctx.fillRect(x*cw,y*ch,cw+.5,ch+.5);} }
  return [peak,hot,act];
}
function drawZonesLite(ctx){ Z().forEach(z=>{ ctx.strokeStyle='rgba(255,255,255,.35)'; ctx.lineWidth=1; ctx.strokeRect(z.x*S,z.y*S,z.w*S,z.h*S); }); }
function drawBase(){
  const T=D.theme; cx.clearRect(0,0,W,H);
  cx.fillStyle=rain?T.groundRain:T.ground; cx.fillRect(0,0,W,H);
  if(T.kind==='outdoor'){ cx.fillStyle='rgba(0,0,0,.14)'; for(let x=6;x<W;x+=26){cx.beginPath();cx.arc(x,7,11,0,7);cx.fill();cx.beginPath();cx.arc(x,H-7,11,0,7);cx.fill();} }
  else { cx.strokeStyle='rgba(0,0,0,.12)'; cx.lineWidth=1; for(let x=0;x<W;x+=W/16){cx.beginPath();cx.moveTo(x,0);cx.lineTo(x,H);cx.stroke();} for(let y=0;y<H;y+=H/10){cx.beginPath();cx.moveTo(0,y);cx.lineTo(W,y);cx.stroke();} }
  // 출입구→구역 보행 통로
  cx.strokeStyle=T.path; cx.globalAlpha=.55; cx.lineCap='round'; cx.lineWidth=Math.max(3,S*1.2);
  const g0=D.gates[0]; Z().forEach(z=>{ if(z.type==='stage'||z.type==='info'||z.type==='medical'){ cx.beginPath(); cx.moveTo(g0.x*S,g0.y*S); cx.lineTo((z.x+z.w/2)*S,(z.y+z.h/2)*S); cx.stroke(); } });
  cx.globalAlpha=1;
  Z().forEach(z=>{ const x=z.x*S,y=z.y*S,w=z.w*S,h=z.h*S;
    cx.fillStyle='rgba(0,0,0,.25)'; cx.fillRect(x+2,y+2,w,h);
    cx.fillStyle=z.color; cx.beginPath(); cx.roundRect(x,y,w,h,5); cx.fill(); cx.strokeStyle='#fff'; cx.lineWidth=1.3; cx.stroke();
    cx.fillStyle='#fff'; cx.textAlign='center'; cx.font='bold '+Math.max(9,Math.min(12,w/9))+'px Pretendard,sans-serif';
    cx.fillText(z.icon+' '+z.name,x+w/2,y+h/2+4,w-4); });
  D.gates.forEach(g=>{ cx.fillStyle='#1e293b'; cx.beginPath(); cx.arc(g.x*S,g.y*S,7,0,7); cx.fill(); cx.strokeStyle='#fff'; cx.lineWidth=1.5; cx.stroke();
    cx.fillStyle='#fff'; cx.font='bold 9px Pretendard'; cx.textAlign='center'; cx.fillText('🚪',g.x*S,g.y*S+3);
    cx.fillStyle='#fff'; cx.fillText(g.name,g.x*S,g.y*S+(g.y>50?-11:17)); });
}
function drawPeople(){ px.clearRect(0,0,W,H);
  let c=0; agents.forEach(a=>{ if(!a.active) return; c++; px.fillStyle=rain?'#93c5fd':'#fff'; px.strokeStyle='rgba(0,0,0,.35)'; px.lineWidth=.6; px.beginPath(); px.arc(a.x*S,a.y*S,2.4,0,7); px.fill(); px.stroke(); });
  document.getElementById('peopleTxt').textContent='시뮬레이션 군중 '+c+'개체 ≈ '+Math.round(D.params.visitors*.5*factor(tHour)).toLocaleString()+'명';
  if(emg){ px.strokeStyle='#ef4444'; px.lineWidth=3; px.setLineDash([6,5]);
    if(emg.target){ px.beginPath(); px.moveTo(emg.x*S,emg.y*S); px.lineTo((emg.target.x+emg.target.w/2)*S,(emg.target.y+emg.target.h/2)*S); px.stroke(); }
    px.setLineDash([]); px.fillStyle='#ef4444'; px.beginPath(); px.arc(emg.x*S,emg.y*S,7+Math.sin(performance.now()/120)*1.5,0,7); px.fill();
    px.fillStyle='#fff'; px.font='bold 10px Pretendard'; px.textAlign='center'; px.fillText('🚑 응급',emg.x*S,emg.y*S-11); }
  if(rain){ px.strokeStyle='rgba(147,197,253,.55)'; px.lineWidth=1.1; raindrops.forEach(r=>{px.beginPath();px.moveTo(r.x,r.y);px.lineTo(r.x-2,r.y+r.l);px.stroke();}); }
}
let last=performance.now(), kt=0;
function loop(now){ const dt=(now-last)/1000; last=now;
  if(sim){ step(dt); }
  updateHeat(); const r=drawHeat(hx); hm.style.opacity=.75; drawHeat(h2); drawPeople();
  kt+=dt; if(kt>.4){ kt=0; document.getElementById('kPeak').textContent=r[0].toFixed(2)+' 명/㎡'; document.getElementById('kBott').textContent=(r[2]?Math.round(100*r[1]/r[2]):0)+'%';
    const de=mode==='after'?D.detail:D.before_detail; document.getElementById('kMed').textContent=Math.round(de.t_max)+'초'; document.getElementById('kRisk').textContent=de.risk_zones+'개소'; }
  requestAnimationFrame(loop);
}
function setMode(m){ mode=m; document.getElementById('bMode').className=m==='after'?'on':''; document.getElementById('bModeB').className=m==='before'?'on':'';
  document.getElementById('verTxt').textContent=m==='after'?'· AI 최적 배치(종합 '+D.total.toFixed(1)+'점)':'· 설계 전(종합 '+D.before_total.toFixed(1)+'점)';
  heat.fill(0); initAgents(); emg=null; drawBase(); if(is3d) build3d(); document.getElementById('status').textContent='실시간 군중 시뮬레이션'; }
function togSim(){ sim=!sim; document.getElementById('bPlay').textContent=sim?'⏸ 시뮬레이션 정지':'▶ 시뮬레이션 시작'; }
function togRain(){ rain=!rain; const b=document.getElementById('bRain'); b.className='warn'+(rain?' on':''); b.textContent=rain?'🌧️ 우천(ON)':'🌧️ 우천'; document.getElementById('envTxt').textContent=rain?'🌧️ 우천: 무대 쪽으로 대피':'일반 상태'; agents.forEach(a=>{ if(!rain&&!a.leaving) setTarget(a); }); drawBase(); }
function togEmg(){ const b=document.getElementById('bEmg');
  if(emg){ emg=null; b.className='danger'; b.textContent='🚨 응급환자 발생'; document.getElementById('status').textContent='실시간 군중 시뮬레이션'; return; }
  const Zs=Z().filter(z=>z.type!=='medical'); const z=Zs[Math.floor(Math.random()*Zs.length)];
  emg={x:z.x+z.w/2,y:z.y+z.h+2,trail:[],t0:performance.now(),target:null}; b.className='danger on'; b.textContent='🚨 응급 해제'; sim=true; document.getElementById('bPlay').textContent='⏸ 시뮬레이션 정지'; }
function setTime(h){ tHour=h; document.getElementById('tSl').value=h; document.getElementById('tTxt').textContent=h+':00'; document.getElementById('tDesc').textContent=descT(h); }
function togTl(){ const b=document.getElementById('bTl'); if(tlTimer){clearInterval(tlTimer);tlTimer=null;b.textContent='▶ 재생';} else { b.textContent='⏸ 일시정지'; tlTimer=setInterval(()=>{ let n=tHour+1; if(n>20)n=10; setTime(n); },2500); } }
// ---- 3D ----
let sc3,cam3,ren3,grp3,rotY=0.6,rotX=0.9,drag=false,lx=0,ly=0;
function tog3d(){ is3d=!is3d; const el=document.getElementById('c3'); el.style.display=is3d?'block':'none'; [cv,hm,pp].forEach(c=>c.style.display=is3d?'none':'block');
  document.getElementById('b3d').textContent=is3d?'🗺️ 2D':'🧊 3D'; document.getElementById('b3d').className=is3d?'on':''; if(is3d) build3d(); }
function build3d(){
  const el=document.getElementById('c3'); el.innerHTML=''; const w=el.clientWidth,h=el.clientHeight;
  sc3=new THREE.Scene(); sc3.background=new THREE.Color(D.theme.bg3d);
  cam3=new THREE.PerspectiveCamera(45,w/h,.1,2000); ren3=new THREE.WebGLRenderer({antialias:true}); ren3.setSize(w,h); el.appendChild(ren3.domElement);
  sc3.add(new THREE.AmbientLight(0xffffff,.75)); const dl=new THREE.DirectionalLight(0xffffff,.8); dl.position.set(60,120,60); sc3.add(dl);
  grp3=new THREE.Group(); sc3.add(grp3);
  const gm=new THREE.Mesh(new THREE.PlaneGeometry(WW,WH),new THREE.MeshLambertMaterial({color:new THREE.Color(D.theme.g3d)})); gm.rotation.x=-Math.PI/2; grp3.add(gm);
  Z().forEach(z=>{ const hgt=z.ht*(z.type==='stage'?1:1); const m=new THREE.Mesh(new THREE.BoxGeometry(z.w,hgt,z.h),new THREE.MeshLambertMaterial({color:new THREE.Color(z.color)}));
    m.position.set(z.x+z.w/2-WW/2,hgt/2,z.y+z.h/2-WH/2); grp3.add(m); });
  D.gates.forEach(g=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(2.2,2.2,9,16),new THREE.MeshLambertMaterial({color:0x334155})); m.position.set(g.x-WW/2,4.5,g.y-WH/2); grp3.add(m); });
  agents.forEach(a=>{ if(!a.active) return; });
  ren3.domElement.onmousedown=e=>{drag=true;lx=e.clientX;ly=e.clientY};
  window.onmouseup=()=>drag=false;
  ren3.domElement.onmousemove=e=>{ if(!drag)return; rotY+=(e.clientX-lx)*.01; rotX=Math.min(1.5,Math.max(.2,rotX+(e.clientY-ly)*.01)); lx=e.clientX; ly=e.clientY; };
  (function r(){ if(!is3d) return; requestAnimationFrame(r); if(!drag) rotY+=.002; const R=190; cam3.position.set(Math.sin(rotY)*Math.cos(rotX)*R,Math.sin(rotX)*R,Math.cos(rotY)*Math.cos(rotX)*R); cam3.lookAt(0,0,0); ren3.render(sc3,cam3); })();
}
window.addEventListener('resize',resize);
setTime(14); setMode('after'); resize(); initAgents(); requestAnimationFrame(loop);
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
