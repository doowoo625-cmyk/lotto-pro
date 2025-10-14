
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
    const h = await getJSON("/api/health");
    document.getElementById("apiStatus").textContent = h.ok ? "정상" : "점검 필요";
  }catch(e){}
  try{
    const recent = await getJSON("/api/recent");
    const items = recent.items || [];
    const right = document.getElementById("statusRight");
    if (items.length>0){
      const last = items[items.length-1];
      right.innerHTML = `직전(<b>${last.draw_no}</b>): ${last.numbers.map(pill).join(" ")} | 보너스 ${pill(last.bonus)}`;
    }else{
      right.textContent = "직전 회차 데이터가 없습니다.";
    }
  }catch(e){}
}

function renderBestStrategy(best_name_ko, top5){
  const root = document.getElementById("bestStrategyBlock");
  root.innerHTML = "";
  const card = document.createElement("div");
  card.className = "card";
  let html = `<h3>가장 추천하는 전략: <b>${best_name_ko}</b></h3>`;
  html += `<div class="table"><div class="thead"># / 조합 / Score · R/R · 추정승률</div>`;
  top5.forEach((it, idx)=>{
    html += `<div class="row" style="display:flex;align-items:center;gap:12px;margin:6px 0;">
      <div style="width:28px;">${idx+1}위</div>
      <div class="pills" style="flex:1 1 auto">${it.numbers.map(pill).join("")}</div>
      <div class="right kv" style="min-width:260px">
        <span class="tag">Score ${it.score}</span>
        <span class="tag">R/R ${it.rr}</span>
        <span class="tag">승률 ${it.win}%</span>
      </div>
    </div>
    <div class="small" style="margin-left:40px;opacity:.9">근거: <b>번호 / 빈도 / 확률(%) / 기준</b> — ${it.rationale}</div>`;
  });
  html += `</div>`;
  card.innerHTML = html;
  root.appendChild(card);
}

function renderWeekly(best3){
  const root = document.getElementById("weeklyTop3");
  root.innerHTML = "";
  best3.forEach((it, i)=>{
    const c = document.createElement("div");
    c.className = "card";
    c.innerHTML = `
      <h3>${i+1}번 ${it.name_ko}</h3>
      <div class="pills">${it.numbers.map(pill).join("")}</div>
      <div class="kv">
        <span class="tag">Score ${it.score}</span>
        <span class="tag">R/R ${it.rr}</span>
        <span class="tag">승률 ${it.win}%</span>
      </div>
      <div class="small">근거: <b>번호 / 빈도 / 확률(%) / 기준</b> — ${it.rationale}</div>`;
    root.appendChild(c);
  });
}

function renderByStrategy(all){
  const root = document.getElementById("byStrategy");
  root.innerHTML = "";
  const order = ["보수형","균형형","고위험형"];
  order.forEach(name=>{
    const group = document.createElement("div");
    group.className = "card";
    group.innerHTML = `<h3>${order.indexOf(name)+1}. ${name}</h3>`;
    const grid = document.createElement("div");
    grid.className = "cards";
    (all[name]||[]).slice(0,5).forEach((it, idx)=>{
      const inner = document.createElement("div");
      inner.className = "card";
      inner.innerHTML = `
        <h3>#${idx+1}</h3>
        <div class="pills">${it.numbers.map(pill).join("")}</div>
        <div class="kv">
          <span class="tag">Score ${it.score}</span>
          <span class="tag">R/R ${it.rr}</span>
          <span class="tag">승률 ${it.win}%</span>
        </div>
        <div class="small">근거: <b>번호 / 빈도 / 확률(%) / 기준</b> — ${it.rationale}</div>`;
      grid.appendChild(inner);
    });
    group.appendChild(grid);
    root.appendChild(group);
  });
}

async function refreshRecent(){
  const data = await getJSON("/api/recent");
  const items = (data.items||[]).slice(-10);
  items.sort((a,b)=> a.draw_no - b.draw_no);
  const sel = document.getElementById("selDraw");
  sel.innerHTML = `<option value="all">전체(최근 10회)</option>` + items.map(it=>`<option value="${it.draw_no}">${it.draw_no}회</option>`).join("");
  const board = document.getElementById("recentBoard");
  function render(filter){
    board.innerHTML = "";
    const list = filter==="all" ? items : items.filter(x=> String(x.draw_no)===filter);
    list.forEach(it=>{
      const c = document.createElement("div");
      c.className = "card";
      c.innerHTML = `<b>${it.draw_no}회</b> — ${it.numbers.map(pill).join(" ")} | 보너스 ${pill(it.bonus)}`;
      board.appendChild(c);
    });
  }
  sel.onchange = (e)=> render(e.target.value);
  render("all");
}

async function refreshRange(){
  const winSel = document.getElementById("selWindow");
  const windowN = parseInt(winSel.value||"10",10);
  const data = await getJSON(`/api/range_freq?window=${windowN}`);
  const per = data.per, top2 = data.top2, bottom = data.bottom;
  const root = document.getElementById("rangeBoard");
  root.innerHTML = "";
  const order = ["1-10","11-20","21-30","31-40","41-45"];
  order.forEach(label=>{
    const card = document.createElement("div");
    card.className = "range";
    if (top2.includes(label)) card.classList.add("top");
    if (bottom===label) card.classList.add("bottom");
    card.innerHTML = `<h4>${label}</h4><div class="grid10"></div>`;
    const grid = card.querySelector(".grid10");
    Object.entries(per[label]).forEach(([n, f])=>{
      const row = document.createElement("div");
      row.style.display = "flex"; row.style.alignItems = "center"; row.style.justifyContent = "space-between";
      row.innerHTML = `<div>${pill(parseInt(n,10))}</div><div class="small" style="font-weight:800">빈도 ${f}</div>`;
      grid.appendChild(row);
    });
    root.appendChild(card);
  });
}
document.getElementById("selWindow").addEventListener("change", refreshRange);

async function doPredict(){
  const seedVal = document.getElementById("seed").value;
  const countVal = parseInt(document.getElementById("count").value || "5", 10);
  const body = { count: countVal };
  if (seedVal !== "") body.seed = parseInt(seedVal, 10);
  const res = await getJSON("/api/predict", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  renderBestStrategy(res.best_strategy_name_ko, res.best_strategy_top5);
  renderWeekly(res.best3_by_priority_korean);
  renderByStrategy(res.all_by_strategy_korean);
  await refreshRange();
}

async function init(){
  await refreshTop();
  await refreshRecent();
  await refreshRange();
  document.getElementById("btnPredict").addEventListener("click", doPredict);
}
init();
