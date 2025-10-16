// ===== Helpers =====
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

// ===== Global latest draw cache =====
let LATEST_DRAW_NO = null;

// ===== Top status (직전 회차 자동 최신화) =====
async function refreshTop(){
  try{
    const last = await getJSON('/api/latest');      // 최신 회차 1회 호출
    LATEST_DRAW_NO = last.draw_no;

    const right = document.getElementById("statusRight");
    if (right){
      right.innerHTML = `직전(${last.draw_no}회) `
        + last.numbers.map(pill).join(" ")
        + ` 보너스 ${pill(last.bonus)}`;
    }

    // 입력/드롭다운에 최신 회차 세팅
    const dl = document.getElementById('dlDraws');
    const dl2 = document.getElementById('dlDraws2');
    if (dl && dl2){
      let opts = ''; const end = last.draw_no || 0;
      for(let n=end; n>Math.max(0,end-50); n--){ opts += `<option value="${n}">${n}회</option>`; }
      dl.innerHTML = opts; dl2.innerHTML = opts;

      const inp1 = document.getElementById('inpEndDraw');
      const inp2 = document.getElementById('inpEndDraw2');
      if (inp1) inp1.value = end;
      if (inp2) inp2.value = end;
    }

    const apiEl = document.getElementById("apiStatus");
    if (apiEl) apiEl.textContent = "정상";
  }catch(e){
    const apiEl = document.getElementById("apiStatus");
    if (apiEl) apiEl.textContent = "네트워크 확인";
  }
}

// ===== 예측 번호 조회 (Top5 가로 정렬) =====
function renderBestHorizontal(strategyNameKo, rows){
  const root = document.getElementById("bestBlock");
  if (!root) return;
  root.innerHTML = "";

  // 점수 높은 순(=우선순위 오름: 1위가 가장 좋음)
  const ranked = [...rows].sort((a,b)=> (b.score ?? 0) - (a.score ?? 0)).slice(0,5);

  const wrap = document.createElement('div');
  wrap.className = 'h-scroll row-gap';

  ranked.forEach((it, idx)=>{
    const card = document.createElement('div');
    card.className = 'card h-card';
    card.innerHTML = `
      <div class="mono rank-badge">${idx+1}</div>
      <div class="pills">${it.numbers.map(pill).join("")}</div>
      <div class="kv">
        <span class="tag">Score ${it.score}</span>
        <span class="tag">R/R ${it.rr}</span>
        <span class="tag">승률 ${it.win}%</span>
      </div>
      <div class="small subtle">전략: ${strategyNameKo}</div>
      <div class="small" style="margin-top:6px">
        근거: <b>번호 / 빈도 / 확률(%) / 기준</b> — ${it.rationale||''}
      </div>`;
    wrap.appendChild(card);
  });
  root.appendChild(wrap);
}

// ===== 이번 주 추천 전략 (3개 가로, 우선순위 오름) =====
function renderWeeklyHorizontal(best3){
  const root = document.getElementById('weeklyBlock');
  if (!root) return;
  root.innerHTML = '';

  // 점수 높은 순으로 정렬 (1위→2위→3위 가로)
  const sorted = [...best3].sort((a,b)=> (b.score ?? 0) - (a.score ?? 0));

   // 세로로 쌓기
  const stack = document.createElement('div');
  stack.className = 'weekly-stack';

  sorted.forEach((it, idx)=>{
    const name = it.name_ko || it.name || '전략';

    // 카드 1개 = 한 줄 가로 정렬(랭크 뱃지 / 전략명 / 번호 / 지표)
    const card = document.createElement('div');
    card.className = 'card weekly-row';

 card.innerHTML = `
      <div class="mono rank-badge">${idx+1}</div>
      <div class="weekly-name">${name}</div>
      <div class="pills weekly-pills">${it.numbers.map(pill).join("")}</div>
      <div class="kv weekly-metrics">
        <span class="tag">Score ${it.score}</span>
        <span class="tag">R/R ${it.rr}</span>
        <span class="tag">승률 ${it.win}%</span>
      </div>
    `;

    stack.appendChild(card);
  });

  root.appendChild(stack);
}
// ===== 전략별 추천 (각 5세트, 내부 오름정렬, 그룹 가로 스크롤) =====
function renderByStrategyHorizontal(all){
  const order = ['보수형','균형형','고위험형'];
  const root = document.getElementById('byStrategyBlock'); 
  if(!root) return;
  root.innerHTML='';

  order.forEach(name=>{
    const outer = document.createElement('div');
    outer.className='card';
    outer.innerHTML = `<div class="small" style="opacity:.85">${name}</div>`;

    // 각 그룹 5세트, 점수 높은 순
    const wrap = document.createElement('div'); 
    wrap.className='h-scroll row-gap';
    const rows = (all[name]||[]).sort((a,b)=> (b.score??0)-(a.score??0)).slice(0,5);

    rows.forEach((it, idx)=>{
      const card = document.createElement('div'); 
      card.className='mini-card';
      card.innerHTML = `
        <div class="mono rank-dot">${idx+1}</div>
        <div class="pills">${it.numbers.map(pill).join("")}</div>
        <div class="kv">
          <span class="tag">S ${it.score}</span>
          <span class="tag">R/R ${it.rr}</span>
          <span class="tag">승 ${it.win}%</span>
        </div>`;
      wrap.appendChild(card);
    });

    outer.appendChild(wrap);
    root.appendChild(outer);
  });
}

// ===== 최근 10회 결과 (자동 기본: 직전 10개, 오름차순) =====
async function autoRecent10(){
  const end = LATEST_DRAW_NO || (document.getElementById('inpEndDraw')?.value);
  if(!end) return;
  await renderRecent(Number(end), 10);
}
async function renderRecent(end_no, n){
  const root = document.getElementById('recentBlock'); 
  if (!root) return;
  root.innerHTML = '<div class="small subtle">최근 10회 불러오는 중…</div>';

  const data = await getJSON(`/api/dhlottery/recent?end_no=${end_no}&n=${n}`);
  const items = (data.items||[]).sort((a,b)=> a.draw_no - b.draw_no);

  root.innerHTML='';
  const header = document.createElement('div'); 
  header.className='row header-row';
  header.innerHTML = `
    <div style="width:70px">회차</div>
    <div style="width:120px">날짜</div>
    <div style="flex:1">번호</div>
    <div class="mono right60">합</div>
    <div class="mono right60">홀</div>
    <div class="mono right70">고번호</div>`;
  root.appendChild(header);

  items.forEach(it=>{
    const sum = it.numbers.reduce((a,b)=>a+b,0);
    const odd = it.numbers.filter(n=>n%2===1).length;
    const high = it.numbers.filter(n=>n>=23).length;
    const row = document.createElement('div'); 
    row.className='row';
    row.innerHTML = `
      <div style="width:70px">${it.draw_no}</div>
      <div style="width:120px">${it.date||''}</div>
      <div class="pills" style="flex:1">
        ${it.numbers.map(pill).join("")}
        <span class="small" style="margin-left:6px">보너스 ${pill(it.bonus)}</span>
      </div>
      <div class="mono right60">${sum}</div>
      <div class="mono right60">${odd}</div>
      <div class="mono right70">${high}</div>`;
    root.appendChild(row);
  });
}

// ===== 구간별 번호 빈도 (자동 기본 10회, 상위2/하위1 강조) =====
async function autoRange10(){
  const end = LATEST_DRAW_NO || (document.getElementById('inpEndDraw2')?.value);
  if(!end) return;
  await renderRange(Number(end), 10);
}
async function renderRange(end_no, n){
  const root = document.getElementById('rangeBlock'); 
  if(!root) return;
  root.innerHTML = '<div class="small subtle">구간별 빈도 계산 중…</div>';

  const data = await getJSON(`/api/range_freq_by_end?end_no=${end_no}&n=${n}`);
  const per = data.per; // { '1-10':{num:cnt,...}, ... }

  // 그룹 총합 계산 → 상위 2, 하위 1 식별
  const groupsOrder = ['1-10','11-20','21-30','31-40','41-45'];
  const totals = groupsOrder.map(g=>({ key:g, total: Object.values(per[g]).reduce((a,b)=>a+Number(b),0)}));
  const sortedTotals = [...totals].sort((a,b)=> b.total - a.total);
  const top2keys = new Set(sortedTotals.slice(0,2).map(x=>x.key));
  const bottom1keys = new Set(sortedTotals.slice(-1).map(x=>x.key));

  const labelMap = {'1-10':'1~10','11-20':'11~20','21-30':'21~30','31-40':'31~40','41-45':'41~45'};

  root.innerHTML='';
  const wrap = document.createElement('div'); 
  wrap.className='h-scroll row-gap';

  groupsOrder.forEach(key=>{
    const card = document.createElement('div'); 
    card.className='range-card';
    const stateClass = top2keys.has(key) ? 'hi-top' : (bottom1keys.has(key) ? 'hi-low' : '');
    card.innerHTML = `<div class="range-title ${stateClass}">${labelMap[key]}</div>`;

    const grid = document.createElement('div'); 
    grid.className='range-grid';

    Object.keys(per[key]).sort((a,b)=> Number(a)-Number(b)).forEach(num=>{
      const row = document.createElement('div'); 
      row.className='range-row';
      // 강조: 해당 그룹의 빈도 숫자에만 스타일
      row.innerHTML = `<div>${pill(Number(num))}</div><div class="mono freq ${stateClass}">${per[key][num]}</div>`;
      grid.appendChild(row);
    });

    card.appendChild(grid);
    wrap.appendChild(card);
  });
  root.appendChild(wrap);
}

// ===== Actions / Buttons =====
async function onPredict(){
  const res = await getJSON('/api/predict', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({})
  });
  renderBestHorizontal(res.best_strategy_name_ko, res.best_strategy_top5);
  renderWeeklyHorizontal(res.best3_by_priority_korean || []);

  const all = res.all_by_strategy_korean || {};
  const sortedAll = {};
  Object.keys(all).forEach(k=>{
    sortedAll[k] = [...all[k]].sort((a,b)=> (b.score??0)-(a.score??0));
  });
  renderByStrategyHorizontal(sortedAll);
}

async function onRecent(){
  const end = Number(document.getElementById('inpEndDraw').value || LATEST_DRAW_NO);
  if (!end) return;
  await renderRecent(end, 10);
}

async function onRange(){
  const end = Number(document.getElementById('inpEndDraw2').value || LATEST_DRAW_NO);
  const n = Number(document.getElementById('selWindow').value || 10);
  if (!end) return;
  await renderRange(end, n);
}

// ===== Bind & Init =====
function bind(){
  document.getElementById('btnPredict')?.addEventListener('click', onPredict);
  document.getElementById('btnRecent')?.addEventListener('click', onRecent);
  document.getElementById('btnRange')?.addEventListener('click', onRange);
}

async function init(){
  bind();
  await refreshTop();                 // 1) 직전 회차
  setTimeout(()=>{ autoRecent10().catch(()=>{}); }, 150); // 2) 최근 10회 자동(오름차순)
  setTimeout(()=>{ autoRange10().catch(()=>{}); }, 300);  // 3) 구간 빈도 자동(10회, 강조)
}
init();
