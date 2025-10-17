// static/app.js  (v3.4-final)
async function getJSON(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

// 동행복권 공 색상 (동행복권 기준)
function lottoColor(n){
  if (n>=1 && n<=10) return "yellow";
  if (n<=20) return "blue";
  if (n<=30) return "red";
  if (n<=40) return "purple";
  return "green";
}
const pill = (n)=> `<span class="pill ${lottoColor(n)}">${String(n).padStart(2,'0')}</span>`;

let LATEST_DRAW_NO = null;

// ----------------------------
// 상단 상태: 직전 회차 자동 최신화
// ----------------------------
async function refreshTop(){
  const statusEl = document.getElementById('apiStatus');
  try {
    statusEl && (statusEl.textContent = '연결 확인 중…');
    const last = await getJSON('/api/latest');
    LATEST_DRAW_NO = last.draw_no;

    const right = document.getElementById("statusRight");
    if (right){
      right.innerHTML = `직전(${last.draw_no}회) `
        + last.numbers.map(pill).join(" ")
        + ` 보너스 ${pill(last.bonus)}`;
    }

    // 회차 입력/드롭다운 프리셋
    const dl1 = document.getElementById('dlDraws');
    const dl2 = document.getElementById('dlDraws2');
    const end = last.draw_no || 0;
    if (dl1 && dl2){
      let opts = '';
      for(let n=end; n>Math.max(0,end-200); n--){ // 최근 200회 프리셋
        opts += `<option value="${n}">${n}회</option>`;
      }
      dl1.innerHTML = opts;
      dl2.innerHTML = opts;
    }
    const inp1 = document.getElementById('inpEndDraw');
    const inp2 = document.getElementById('inpEndDraw2');
    if (inp1) inp1.value = end;
    if (inp2) inp2.value = end;

    statusEl && (statusEl.textContent = '정상');
  } catch (e) {
    statusEl && (statusEl.textContent = '캐시 표시 중');
  }
}

// ------------------------------------
// ④ 최근 10회 결과: 기본 자동 + 조회 동작
// - 표시는 "최신이 위(상단), 아래로 과거" = 내림차순 표시
// - 각 행은 회차/날짜/번호(공) 가로 정렬
// ------------------------------------
async function renderRecent(end_no, n=10){
  const data = await getJSON(`/api/dhlottery/recent?end_no=${end_no}&n=${n}`);
  // API는 오름차순으로 주기 쉬움 → 화면엔 최신 위로 보이게 역정렬(내림차순)
  const items = (data.items||[]).sort((a,b)=> b.draw_no - a.draw_no);

  const root = document.getElementById('recentBlock');
  if(!root) return;
  root.innerHTML='';
  const header = `
    <div class="row header-row">
      <div class="w70">회차</div>
      <div class="w120">날짜</div>
      <div class="flex1">번호</div>
      <div class="mono w60 right">합</div>
      <div class="mono w60 right">홀</div>
      <div class="mono w70 right">고번호</div>
    </div>`;
  root.insertAdjacentHTML('beforeend', header);

  items.forEach(it=>{
    const sum = it.numbers.reduce((a,b)=>a+b,0);
    const odd = it.numbers.filter(n=>n%2===1).length;
    const high = it.numbers.filter(n=>n>=23).length;
    root.insertAdjacentHTML('beforeend', `
      <div class="row">
        <div class="w70">${it.draw_no}</div>
        <div class="w120">${it.date||''}</div>
        <div class="pills flex1">
          ${it.numbers.map(pill).join("")}
          <span class="small" style="margin-left:6px">보너스 ${pill(it.bonus)}</span>
        </div>
        <div class="mono w60 right">${sum}</div>
        <div class="mono w60 right">${odd}</div>
        <div class="mono w70 right">${high}</div>
      </div>
    `);
  });
}
async function autoRecent10(){ if (LATEST_DRAW_NO) await renderRecent(LATEST_DRAW_NO, 10); }
async function onRecent(){
  const end = Number(document.getElementById('inpEndDraw')?.value || LATEST_DRAW_NO);
  if (end) await renderRecent(end, 10);
}

// ------------------------------------
// ⑤ 구간별 번호 빈도: 기본 자동 + 조회 동작
// - 그룹(1~10, 11~20, …)은 가로 배치
// - 그룹 내 번호는 오름차순
// - 상위2/하위1 강조
// ------------------------------------
async function renderRange(end_no, n=10){
  const data = await getJSON(`/api/range_freq_by_end?end_no=${end_no}&n=${n}`);
  const per = data.per;
  const order=['1-10','11-20','21-30','31-40','41-45'];
  const label={ '1-10':'1~10','11-20':'11~20','21-30':'21~30','31-40':'31~40','41-45':'41~45' };

  // 상/하위 구간 계산
  const totals = order.map(k=>({k,total:Object.values(per[k]).reduce((a,b)=>a+Number(b),0)}))
                      .sort((a,b)=>b.total-a.total);
  const top2 = new Set(totals.slice(0,2).map(x=>x.k));
  const low1 = new Set(totals.slice(-1).map(x=>x.k));

  const root = document.getElementById('rangeBlock');
  if(!root) return;
  root.innerHTML='';
  const wrap = document.createElement('div');
  wrap.className='h-scroll row-gap';

  order.forEach(k=>{
    const cls = top2.has(k)?'hi-top':(low1.has(k)?'hi-low':'');
    let html = `<div class="range-card">
      <div class="range-title ${cls}">${label[k]}</div>
      <div class="range-grid">`;
    Object.keys(per[k]).sort((a,b)=>Number(a)-Number(b)).forEach(num=>{
      html += `<div>${pill(Number(num))}</div><div class="mono freq ${cls}">${per[k][num]}</div>`;
    });
    html += `</div></div>`;
    wrap.insertAdjacentHTML('beforeend', html);
  });
  root.appendChild(wrap);
}
async function autoRange10(){ if (LATEST_DRAW_NO) await renderRange(LATEST_DRAW_NO, 10); }
async function onRange(){
  const end = Number(document.getElementById('inpEndDraw2')?.value || LATEST_DRAW_NO);
  const n   = Number(document.getElementById('selWindow')?.value || 10);
  if (end) await renderRange(end, n);
}

// ------------------------------------
// ① 예측 번호 뽑기
// - 1~5위 "세로 오름차순" 정렬
// - 한 줄: [순위 | 조합 | 전략 | 근거(score/RR/승률)]
// - 순위마다 전략은 달라도 됨 (전체 후보 중 상위 5 추출)
// ------------------------------------
function lineRow(rank, nums, strategyName, score, rr, win){
  return `
    <div class="line-row">
      <div class="rank-col mono">${rank}</div>
      <div class="pills">${nums.map(pill).join("")}</div>
      <div class="strategy-col">${strategyName||''}</div>
      <div class="kv">
        <span class="tag">Score ${score}</span>
        <span class="tag">R/R ${rr}</span>
        <span class="tag">승률 ${win}%</span>
      </div>
    </div>
  `;
}
function renderPredictVertical(top5){
  const root=document.getElementById("bestBlock");
  if(!root) return;
  root.innerHTML = ''; // 세로 리스트
  top5.forEach((it, idx)=>{
    root.insertAdjacentHTML('beforeend', lineRow(
      idx+1, it.numbers, it.name_ko || it.name || '전략',
      it.score, it.rr, it.win
    ));
  });
}

async function onPredict(){
  // 백엔드 응답: best_strategy_top5, best3_by_priority_korean, all_by_strategy_korean
  const res = await getJSON('/api/predict', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({})  // seed/count는 백엔드 기본값 사용
  });

  // (A) 전체 후보 중 점수 상위 5개(전략 섞여도 OK)
  const pool = [];
  const all = res.all_by_strategy_korean || {};
  Object.keys(all).forEach(k=> all[k].forEach(x=> pool.push({...x})));
  pool.sort((a,b)=>(b.score??0)-(a.score??0));
  const top5 = pool.slice(0,5);
  renderPredictVertical(top5);

  // (B) ② 이번 주 추천 전략 (요청과 충돌 없으므로 유지: 3전략 상위 1세트씩 가로)
  renderWeeklyHorizontal(res.best3_by_priority_korean || []);

  // (C) ③ 전략별 추천: 각 전략 내 1~5위 "세로" + 한 줄 가로 배치
  renderByStrategyVertical(all);
}

// ------------------------------------
// ② 이번 주 추천 전략 (3개, 점수 높은 순, 가로 카드 그대로 유지)
// ------------------------------------
function renderWeeklyHorizontal(best3){
  const root=document.getElementById('weeklyBlock'); if(!root) return; root.innerHTML='';
  const sorted=[...best3].sort((a,b)=>(b.score??0)-(a.score??0));
  const wrap=document.createElement('div'); wrap.className='h-scroll row-gap';
  sorted.forEach((it,idx)=>{
    const name = it.name_ko || it.name || '전략';
    wrap.insertAdjacentHTML('beforeend', `
      <div class="card h-card">
        <div class="mono rank-badge">${idx+1}</div>
        <div class="weekly-name">${name}</div>
        <div class="pills weekly-pills">${it.numbers.map(pill).join("")}</div>
        <div class="kv weekly-metrics">
          <span class="tag">Score ${it.score}</span>
          <span class="tag">R/R ${it.rr}</span>
          <span class="tag">승률 ${it.win}%</span>
        </div>
      </div>
    `);
  });
  root.appendChild(wrap);
}

// ------------------------------------
// ③ 전략별 추천: 보수형→균형형→고위험형 세로 정렬,
//   각 전략 내부는 1~5위 세로, 한 줄 가로 구성
// ------------------------------------
function renderByStrategyVertical(all){
  const order=['보수형','균형형','고위험형'];
  const root=document.getElementById('byStrategyBlock'); if(!root) return; root.innerHTML='';

  order.forEach(name=>{
    const group=(all[name]||[]).sort((a,b)=>(b.score??0)-(a.score??0)).slice(0,5);
    let html = `<div class="card">
      <div class="group-title">${name}</div>`;
    group.forEach((it, idx)=>{
      html += lineRow(idx+1, it.numbers, name, it.score, it.rr, it.win);
    });
    html += `</div>`;
    root.insertAdjacentHTML('beforeend', html);
  });
}

// ----------------------------
// 바인딩 & 초기화
// ----------------------------
function bind(){
  document.getElementById('btnPredict')?.addEventListener('click', onPredict);
  document.getElementById('btnRecent') ?.addEventListener('click', onRecent);
  document.getElementById('btnRange')  ?.addEventListener('click', onRange);
}
async function init(){
  bind();
  // 접속 시점에 한 번만 최신화
  await refreshTop();
  await autoRecent10();
  await autoRange10();
}
init();
