
async function getJSON(url, opts={}){
  const r = await fetch(url, opts);
  if (!r.ok){ throw new Error(await r.text()) }
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

async function refreshTop(){
  try{
    const recent = await getJSON('/api/dhlottery/recent?end_no=9999&n=1').catch(()=>null);
    if(recent && recent.items && recent.items.length){
      const last = recent.items[recent.items.length-1];
      document.getElementById("statusRight").innerHTML = `직전(<b>${last.draw_no}</b>): ${last.numbers.map(pill).join(" ")} · 보너스 ${pill(last.bonus)}`;
      const dl = document.getElementById('dlDraws'); const dl2 = document.getElementById('dlDraws2');
      let opts = ''; const end = last.draw_no;
      for(let n=end; n>Math.max(0,end-50); n--){ opts += `<option value="${n}">${n}회</option>`; }
      dl.innerHTML = opts; dl2.innerHTML = opts;
      document.getElementById('inpEndDraw').value = end;
      document.getElementById('inpEndDraw2').value = end;
    }
    document.getElementById("apiStatus").textContent = "정상";
  }catch(e){
    document.getElementById("apiStatus").textContent = "네트워크 확인";
  }
}

function renderBest(nameKo, rows){
  const root = document.getElementById("bestBlock");
  root.innerHTML = "";
  const header = document.createElement("div");
  header.className = "row header-row";
  header.innerHTML = `<div class="mono" style="width:36px">No.</div>
                      <div style="flex:1">예측 번호 조합</div>
                      <div style="width:80px;text-align:center">전략</div>
                      <div class="kv" style="min-width:280px">지표</div>`;
  root.appendChild(header);
  rows.forEach((it, idx)=>{
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `<div class="mono" style="width:36px">${idx+1}</div>
      <div class="pills" style="flex:1">${it.numbers.map(pill).join("")}</div>
      <div style="width:80px;text-align:center">${nameKo}</div>
      <div class="kv" style="min-width:280px">
        <span class="tag">Score ${it.score}</span>
        <span class="tag">R/R ${it.rr}</span>
        <span class="tag">승률 ${it.win}%</span>
      </div>
      <div class="small" style="flex-basis:100%">근거: <b>번호 / 빈도 / 확률(%) / 기준</b> — ${it.rationale}</div>`;
    root.appendChild(row);
  });
}

function renderWeekly(best3){
  const order = ['균형형','보수형','고위험형'];
  const map = {}; best3.forEach(r=> map[r.name_ko]=r);
  const root = document.getElementById('weeklyBlock'); root.innerHTML = '';
  order.forEach(name=>{
    const it = map[name];
    const card = document.createElement('div'); card.className='card';
    card.innerHTML = `<div class="small" style="opacity:.8">${name}</div>
      <div class="pills" style="margin:6px 0 8px">${it.numbers.map(pill).join("")}</div>
      <div class="kv"><span class="tag">Score ${it.score}</span><span class="tag">R/R ${it.rr}</span><span class="tag">승률 ${it.win}%</span></div>
      <div class="small" style="margin-top:8px">근거: <b>번호 / 빈도 / 확률(%) / 기준</b> — ${it.rationale}</div>`;
    root.appendChild(card);
  });
}

function renderByStrategy(all){
  const order = ['보수형','균형형','고위험형'];
  const root = document.getElementById('byStrategyBlock'); root.innerHTML='';
  order.forEach(name=>{
    const group = document.createElement('div'); group.className='card';
    group.innerHTML = `<div class="small" style="opacity:.8">${name}</div>`;
    (all[name]||[]).slice(0,5).forEach((it, idx)=>{
      const row = document.createElement('div'); row.className='row';
      row.innerHTML = `<div class="mono" style="width:36px">${idx+1}</div>
        <div class="pills" style="flex:1">${it.numbers.map(pill).join("")}</div>
        <div class="kv"><span class="tag">Score ${it.score}</span><span class="tag">R/R ${it.rr}</span><span class="tag">승률 ${it.win}%</span></div>`;
      group.appendChild(row);
    });
    root.appendChild(group);
  });
}

async function onRecent(){
  const end = document.getElementById('inpEndDraw').value;
  if(!end) return;
  const data = await getJSON(`/api/dhlottery/recent?end_no=${end}&n=10`);
  const items = (data.items||[]).sort((a,b)=> a.draw_no - b.draw_no);
  const root = document.getElementById('recentBlock'); root.innerHTML='';
  const header = document.createElement('div'); header.className='row header-row';
  header.innerHTML = `<div style="width:70px">회차</div><div style="width:120px">날짜</div><div style="flex:1">번호</div><div class="mono" style="width:60px;text-align:right">합</div><div class="mono" style="width:60px;text-align:right">홀</div><div class="mono" style="width:70px;text-align:right">고번호</div>`;
  root.appendChild(header);
  items.forEach(it=>{
    const sum = it.numbers.reduce((a,b)=>a+b,0), odd=it.numbers.filter(n=>n%2===1).length, high=it.numbers.filter(n=>n>=23).length;
    const row = document.createElement('div'); row.className='row';
    row.innerHTML = `<div style="width:70px">${it.draw_no}</div><div style="width:120px">${it.date||''}</div><div class="pills" style="flex:1">${it.numbers.map(pill).join("")} <span class="small" style="margin-left:6px">보너스 ${pill(it.bonus)}</span></div><div class="mono" style="width:60px;text-align:right">${sum}</div><div class="mono" style="width:60px;text-align:right">${odd}</div><div class="mono" style="width:70px;text-align:right">${high}</div>`;
    root.appendChild(row);
  });
}

async function onRange(){
  const end = document.getElementById('inpEndDraw2').value;
  const n = document.getElementById('selWindow').value;
  if(!end) return;
  const data = await getJSON(`/api/range_freq_by_end?end_no=${end}&n=${n}`);
  const per = data.per;
  const groups = [['1-10','1~10'],['11-20','11~20'],['21-30','21~30'],['31-40','31~40'],['41-45','41~45']];
  const root = document.getElementById('rangeBlock'); root.innerHTML='';
  groups.forEach(([key,label])=>{
    const card = document.createElement('div'); card.className='range-card';
    card.innerHTML = `<div class="range-title">${label}</div>`;
    const grid = document.createElement('div'); grid.className='range-grid';
    Object.keys(per[key]).sort((a,b)=> Number(a)-Number(b)).forEach(n=>{
      const row = document.createElement('div'); row.className='range-row';
      row.innerHTML = `<div>${pill(Number(n))}</div><div class="mono">${per[key][n]}</div>`;
      grid.appendChild(row);
    });
    card.appendChild(grid);
    root.appendChild(card);
  });
}

async function onPredict(){
  const res = await getJSON('/api/predict', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})});
  renderBest(res.best_strategy_name_ko, res.best_strategy_top5);
  renderWeekly(res.best3_by_priority_korean);
  renderByStrategy(res.all_by_strategy_korean);
}

function bind(){
  document.getElementById('btnPredict').addEventListener('click', onPredict);
  document.getElementById('btnRecent').addEventListener('click', onRecent);
  document.getElementById('btnRange').addEventListener('click', onRange);
}

async function init(){
  bind();
  await refreshTop();
  await onRecent();
  await onRange();
}
init();
