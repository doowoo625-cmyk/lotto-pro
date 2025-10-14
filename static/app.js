
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
  }catch(e){
    document.getElementById("apiStatus").textContent = "오프라인";
  }
  try{
    const recent = await getJSON("/api/recent10");
    const items = recent.items || [];
    let basis = null, last = null;
    if (items.length>0){ basis = items[0]; last = items[items.length-1]; }
    const right = document.getElementById("statusRight");
    if (basis && last){
      right.innerHTML = `기준(<b>${basis.draw_no}</b>): ${basis.numbers.map(pill).join(" ")} | 보너스 ${pill(basis.bonus)} &nbsp;·&nbsp; 직전(<b>${last.draw_no}</b>): ${last.numbers.map(pill).join(" ")} | 보너스 ${pill(last.bonus)}`;
    }else{
      right.textContent = "recent10 데이터가 필요합니다.";
    }
  }catch(e){}
}

function renderStrategyCards(pris){
  const box = document.getElementById("strategyCards");
  box.innerHTML = "";
  pris.forEach((item, idx)=>{
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <h3>#${idx+1} ${item.name}</h3>
      <div class="pills">${item.numbers.map(n=>pill(n)).join("")}</div>
      <div class="kv">
        <span class="tag">Score: <b>${item.score}</b></span>
        <span class="tag">R/R: ${item.rr}</span>
        <span class="tag">추정 승률: ${item.win}%</span>
      </div>
      <div class="table">
        <div class="thead">번호 / 빈도 / 확률(%) / 기준</div>
        <div class="row small">${item.rationale}</div>
      </div>`;
    box.appendChild(el);
  });
}

function renderAll(all){
  const by = document.getElementById("byStrategy");
  by.innerHTML = "";
  Object.keys(all).forEach(k=>{
    const card = document.createElement("div");
    card.className = "card";
    const grid = document.createElement("div");
    grid.className = "cards";
    all[k].forEach((it)=>{
      const inner = document.createElement("div");
      inner.className = "card";
      inner.innerHTML = `
        <h3>${k}</h3>
        <div class="pills">${it.numbers.map(n=>pill(n)).join("")}</div>
        <div class="kv">
          <span class="tag">Score: ${it.score}</span>
          <span class="tag">R/R: ${it.rr}</span>
          <span class="tag">추정 승률: ${it.win}%</span>
        </div>
        <div class="table">
          <div class="thead">번호 / 빈도 / 확률(%) / 기준</div>
          <div class="row small">${it.rationale}</div>
        </div>`;
      grid.appendChild(inner);
    });
    card.appendChild(grid);
    by.appendChild(card);
  });
}

function renderRanges(per, topRanges, bottomRange){
  const order = ["1-10","11-20","21-30","31-40","41-45"];
  const root = document.getElementById("rangeBoard");
  root.innerHTML = "";
  order.forEach(label=>{
    const card = document.createElement("div");
    card.className = "range";
    if (topRanges.includes(label)) card.classList.add("top");
    if (bottomRange===label) card.classList.add("bottom");
    card.innerHTML = `<h4>${label}</h4><div class="grid10"></div>`;
    const grid = card.querySelector(".grid10");
    Object.entries(per[label]).forEach(([n, f])=>{
      const cell = document.createElement("div");
      cell.innerHTML = `${pill(parseInt(n,10))}<div class="small">x${f}</div>`;
      grid.appendChild(cell);
    });
    root.appendChild(card);
  });
}

function renderRecent(items){
  const root = document.getElementById("recent10Board");
  root.innerHTML = "";
  (items||[]).slice(-10).reverse().forEach(it=>{
    const c = document.createElement("div");
    c.className = "recentcard";
    c.innerHTML = `<b>${it.draw_no}회</b> — ${it.numbers.map(pill).join(" ")} | 보너스 ${pill(it.bonus)}`;
    root.appendChild(c);
  });
}

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
  renderStrategyCards(res.priority_sorted);
  renderAll(res.all_candidates);
  renderRanges(res.range_freq, res.top_ranges, res.bottom_range);
}

async function loadRecent10(){
  const r = await getJSON("/api/recent10");
  renderRecent(r.items);
  await refreshTop();
}

document.getElementById("btnPredict").addEventListener("click", doPredict);
document.getElementById("btnLoadRecent10").addEventListener("click", loadRecent10);
refreshTop();
