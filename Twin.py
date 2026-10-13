# -*- coding: utf-8 -*-
"""디지털 트윈 렌더러: 최적화 결과(JSON)를 받아 아이소메트릭 3D / 2D 평면 + 실시간 군중 시뮬레이션 HTML 생성."""
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
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:12px}
.card h4{font-size:13px;font-weight:800;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.wrap{position:relative;width:100%;background:#1e293b;border-radius:10px;overflow:hidden}
#wrap{aspect-ratio:1.85}
#wrap2{aspect-ratio:1.6}
.wrap canvas,.wrap .c3{position:absolute;inset:0;width:100%;height:100%}
.c3{cursor:grab;background:linear-gradient(#e0f2fe,#f8fafc)}
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
let yaw=.55,pitch=.72,zoom3=1,drag=false,lx=0,ly=0;
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
  const sp=labelSprite(z.icon+' '+z.name,z.color); const ww=Math.min(44,Math.max(20,z.name.length*3+12)); sp.scale.set(ww,ww*150/640,1); sp.position.set(0,top+4,0); g.add(sp);
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
    const sp=labelSprite('🚪 '+g.name,'#1e293b'); sp.scale.set(24,24*150/640,1); sp.position.set(x,13,zz); G3.add(sp); });
  Z().forEach(buildZone3);
  $('zlist').innerHTML=Z().map(z=>`<span style="--c:${z.color}">${z.icon} ${z.name}</span>`).join(''); $('zCnt').textContent='('+Z().length+'개)';
}
function initR3(){
  const el=$('c3'); try{ R3=new THREE.WebGLRenderer({antialias:true}); }catch(e){ R3=null; is3d=false; $('hint').textContent='이 브라우저는 3D를 지원하지 않아 2D로 표시합니다'; return; }
  el.appendChild(R3.domElement);
  S3=new THREE.Scene(); S3.add(new THREE.AmbientLight(0xffffff,.82)); const dl=new THREE.DirectionalLight(0xffffff,.65); dl.position.set(-60,120,50); S3.add(dl);
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
  hm.style.display=v3?'none':'block'; $('b3d').className=v3?'on':''; $('b2d').className=v3?'':'on'; $('hint').style.display=v3?'block':'none'; $('bHeat3').style.display=v3?'inline-block':'none';
  if(v3) size3(); }
function togHeat3(){ heat3=!heat3; $('bHeat3').className=heat3?'on':''; }
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
