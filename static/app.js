async function getJSON(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
function lottoColor(n){
  if (n>=1 && n<=10) return "yellow";
  if (n<=20) return "blue";
  if (n<=30) return "red";
  if (n<=40) return "gray";
  return "green";
}
const pill = (n)=> `<span class="pill ${lottoColor(n)}">${String(n).padStart(2,'0')}</span>`;

let LATEST_DRAW_NO = null;

// 1) 상단 직전 회차 (페이지 접속 시 자동 최신)
async function refreshTop(){
  const last = await getJSON('/api/latest');
  LATEST_DRAW_NO = last.draw_no;
  const right = document.getElementById("statusRight");
  if (right){
    right.innerHTML = `직전(${last.draw_no}회) `
      + last.numbers.map(pill).join(" ")
      + ` 보너스 ${pill(last.bonus)}`;
  }
  // 회차 입력/드롭다운 프리셋
  const dl = document.getElementById('dlDraws'), dl2 = document.getElementById('dlDraws2');
  if (dl && dl2){
    let opts = ''; const end = last.draw_no || 0;
    for(let n=end; n>Math.max(0,end-50); n--){ opts += `<option value="${n}">${n}회</option>`; }
    dl.innerHTML = opts; dl2.innerHTML = opts;
    const inp1 = document.getElementById('inpEndDraw'), inp2 = document.getElementById('inpEndDraw2');
    if (inp1) inp1.value = end;
    if (inp2) inp2.value = end;
  }
}

// 2) 최근 10회 (자동: 직전10 오름차순 / 조회도 오름차순)
async function renderRecent(end_no, n=10){
  const data = await getJSON(`/api/dhlottery/recent?end_no=${end_no}&n=${n}`);
  const items = (data.items||[]).sort((a,b)=> a.draw_no - b.draw_no);
  const root = document.getElementById('recentBlock'); if(!root) return;
  root.innerHTML='';
  const header = `<div class="row header-row"><div style="width:70px">회차</div><div style="width:120px">날짜</div><div style="flex:1">번호</div><div class="mono right60">합</div><div class="mono right60">홀</div><div class="mono right70">고번호</div></div>`;
  root.insertAdjacentHTML('beforeend', header);
  items.forEach(it=>{
    const sum = it.numbers.reduce((a,b)=>a+b,0), odd=it.numbers.filter(n=>n%2===1).length, high=it.numbers.filter(n=>n>=23).length;
    root.insertAdjacentHTML('beforeend', `<div class="row">
      <div style="width:70px">${it.draw_no}</div>
      <div style="width:120px">${it.date||''}</div>
      <div class="pills" style="flex:1">${it.numbers.map(pill).join("")} <span class="small" style="margin-left:6px">보너스 ${pill(it.bonus)}</span></div>
      <div class="mono right60">${sum}</div><div class="mono right60">${odd}</div><div class="mono right70">${high}</div>
    </div>`);
  });
}
async function autoRecent10(){ if (LATEST_DRAW_NO) await renderRecent(LATEST_DRAW_NO, 10); }
async function onRecent(){ const end = Number(document.getElementById('inpEndDraw').value || LATEST_DRAW_NO); if (end) await renderRecent(end, 10); }

// 3) 구간별 번호 빈도 (자동: 직전10 / 상위2·하위1 강조 / 가로 그룹 + 내부 오름)
async function renderRange(end_no, n=10){
  const data = await getJSON(`/api/range_freq_by_end?end_no=${end_no}&n=${n}`);
  const per = data.per, order=['1-10','11-20','21-30','31-40','41-45'], label={ '1-10':'1~10','11-20':'11~20','21-30':'21~30','31-40':'31~40','41-45':'41~45' };
  const totals = order.map(k=>({k,total:Object.values(per[k]).reduce((a,b)=>a+Number(b),0)})).sort((a,b)=>b.total-a.total);
  const top2 = new Set(totals.slice(0,2).map(x=>x.k)), low1=new Set(totals.slice(-1).map(x=>x.k));
  const root = document.getElementById('rangeBlock'); if(!root) return; root.innerHTML='';
  const wrap = document.createElement('div'); wrap.className='h-scroll row-gap';
  order.forEach(k=>{
    const cls = top2.has(k)?'hi-top':(low1.has(k)?'hi-low':'');
    let html = `<div class="range-card"><div class="range-title ${cls}">${label[k]}</div><div class="range-grid">`;
    Object.keys(per[k]).sort((a,b)=>Number(a)-Number(b)).forEach(num=>{
      html += `<div>${pill(Number(num))}</div><div class="mono freq ${cls}">${per[k][num]}</div>`;
    });
    html += `</div></div>`;
    wrap.insertAdjacentHTML('beforeend', html);
  });
  root.appendChild(wrap);
}
async function autoRange10(){ if (LATEST_DRAW_NO) await renderRange(LATEST_DRAW_NO, 10); }
async function onRange(){ const end = Number(document.getElementById('inpEndDraw2').value || LATEST_DRAW_NO); const n = Number(document.getElementById('selWindow').value || 10); if (end) await renderRange(end, n); }

// 4) 예측 번호 조회 (1~5위 가로 정렬)
function renderBestHorizontal(strategyNameKo, rows){
  const root=document.getElementById("bestBlock"); if(!root) return; root.innerHTML="";
  const ranked=[...rows].sort((a,b)=>(b.score??0)-(a.score??0)).slice(0,5);
  const wrap=document.createElement('div'); wrap.className='h-scroll row-gap';
  ranked.forEach((it,idx)=>{
    wrap.insertAdjacentHTML('beforeend', `<div class="card h-card">
      <div class="mono rank-badge">${idx+1}</div>
      <div class="pills">${it.numbers.map(pill).join("")}</div>
      <div class="kv"><span class="tag">Score ${it.score}</span><span class="tag">R/R ${it.rr}</span><span class="tag">승률 ${it.win}%</span></div>
      <div class="small subtle">전략: ${strategyNameKo}</div>
    </div>`);
  });
  root.appendChild(wrap);
}

// 5) 이번 주 추천 전략 (3개, 점수 높은 순, 가로 카드. 카드 내부 가로 정렬)
function renderWeeklyHorizontal(best3){
  const root=document.getElementById('weeklyBlock'); if(!root) return; root.innerHTML='';
  const sorted=[...best3].sort((a,b)=>(b.score??0)-(a.score??0));
  const wrap=document.createElement('div'); wrap.className='h-scroll row-gap';
  sorted.forEach((it,idx)=>{
    const name = it.name_ko || it.name || '전략';
    wrap.insertAdjacentHTML('beforeend', `<div class="card h-card">
      <div class="mono rank-badge">${idx+1}</div>
      <div class="weekly-name">${name}</div>
      <div class="pills weekly-pills">${it.numbers.map(pill).join("")}</div>
      <div class="kv weekly-metrics"><span class="tag">Score ${it.score}</span><span class="tag">R/R ${it.rr}</span><span class="tag">승률 ${it.win}%</span></div>
    </div>`);
  });
  root.appendChild(wrap);
}

// 6) 전략별 추천 (보수형/균형형/고위험형 고정 순서, 각 5세트 가로)
function renderByStrategyHorizontal(all){
  const order=['보수형','균형형','고위험형'];
  const root=document.getElementById('byStrategyBlock'); if(!root) return; root.innerHTML='';
  order.forEach(name=>{
    const group=(all[name]||[]).sort((a,b)=>(b.score??0)-(a.score??0)).slice(0,5);
    let html = `<div class="card"><div class="small" style="opacity:.85">${name}</div><div class="h-scroll row-gap">`;
    group.forEach((it,idx)=>{
      html += `<div class="mini-card">
        <div class="mono rank-dot">${idx+1}</div>
        <div class="pills">${it.numbers.map(pill).join("")}</div>
        <div class="kv"><span class="tag">S ${it.score}</span><span class="tag">R/R ${it.rr}</span><span class="tag">승 ${it.win}%</span></div>
      </div>`;
    });
    html += `</div></div>`;
    root.insertAdjacentHTML('beforeend', html);
  });
}

// Actions
async function onPredict(){
  const res = await getJSON('/api/predict', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})});
  renderBestHorizontal(res.best_strategy_name_ko, res.best_strategy_top5);
  renderWeeklyHorizontal(res.best3_by_priority_korean || []);
  const all=res.all_by_strategy_korean||{}; const sorted={}; Object.keys(all).forEach(k=>sorted[k]=[...all[k]].sort((a,b)=>(b.score??0)-(a.score??0)));
  renderByStrategyHorizontal(sorted);
}
function bind(){
  document.getElementById('btnPredict')?.addEventListener('click', onPredict);
  document.getElementById('btnRecent')?.addEventListener('click', onRecent);
  document.getElementById('btnRange')?.addEventListener('click', onRange);
}
async function init(){
  bind();
  // 페이지 접속 시점마다 자동 최신화(주기 없는 1회 갱신)
  await refreshTop();
  await autoRecent10();
  await autoRange10();
}
init();
