
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
  // 상태값
  try{
    const h = await getJSON("/api/health");
    const el = document.getElementById("apiStatus");
    if (el) el.textContent = h.ok ? "정상" : "점검 필요";
  }catch(e){}
  // 기준/직전
  try{
    const recent = await getJSON("/api/recent10");
    const items = recent.items || [];
    let basis = null, last = null;
    if (items.length>0){ basis = items[0]; last = items[items.length-1]; }
    const right = document.getElementById("statusRight");
    if (right){
      if (basis && last){
        right.innerHTML = `기준(<b>${basis.draw_no}</b>): ${basis.numbers.map(pill).join(" ")} | 보너스 ${pill(basis.bonus)} &nbsp;·&nbsp; 직전(<b>${last.draw_no}</b>): ${last.numbers.map(pill).join(" ")} | 보너스 ${pill(last.bonus)}`;
      }else{
        right.textContent = "recent10 데이터가 필요합니다.";
      }
    }
  }catch(e){}
}

// ② 이번주 전략 카드 (보수/균형/고위험 각 1세트, 우선순위=Score 높은 순)
function renderStrategyCards(pris){
  const box = document.getElementById("strategyCards") || document.getElementById("priorityList");
  if (!box) return;
  box.innerHTML = "";
  pris.forEach((item, idx)=>{
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <h3>${idx+1}위 · ${item.name}</h3>
      <div class="pills">${item.numbers.map(n=>pill(n)).join("")}</div>
      <div class="kv">
        <span class="tag">Score: <b>${item.score}</b></span>
        <span class="tag">보상·위험비(R/R): ${item.rr}</span>
        <span class="tag">추정 승률: ${item.win}%</span>
      </div>
      <div class="table">
        <div class="thead">번호 / 빈도 / 확률(%) / 기준</div>
        <div class="row small">${item.rationale}</div>
      </div>`;
    box.appendChild(el);
  });
}

// ③ 전략별 추천 (각 5세트)
function renderAll(all){
  const by = document.getElementById("byStrategy") || document.getElementById("allCandidates");
  if (!by) return;
  by.innerHTML = "";
  Object.keys(all).forEach(k=>{
    const card = document.createElement("div");
    card.className = "card";
    const grid = document.createElement("div");
    grid.className = "cards";
    all[k].forEach((it,i)=>{
      const inner = document.createElement("div");
      inner.className = "card";
      inner.innerHTML = `
        <h3>${k} #${i+1}</h3>
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

// ⑥ 구간별 번호 빈도 (개별 번호, 상위2 강조/하위1 흐림, 빈도 숫자 강조)
function renderRanges(per, topRanges, bottomRange){
  const root = document.getElementById("rangeBoard");
  if (!root) return;
  const order = ["1-10","11-20","21-30","31-40","41-45"];
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
      cell.innerHTML = `${pill(parseInt(n,10))}
        <div class="small" style="font-weight:700; background:rgba(250,204,21,.18); padding:2px 6px; border-radius:6px; display:inline-block; margin-top:2px;">
          빈도: <span style="font-weight:800">${f}</span>
        </div>`;
      grid.appendChild(cell);
    });
    root.appendChild(card);
  });
}

// ① 버튼 클릭 시에만 생성
async function doPredict(){
  const seedEl = document.getElementById("seed");
  const countEl = document.getElementById("count");
  const seedVal = seedEl && seedEl.value !== "" ? parseInt(seedEl.value,10) : undefined;
  const countVal = countEl ? parseInt(countEl.value||"5",10) : 5;
  const body = { count: countVal };
  if (seedVal !== undefined) body.seed = seedVal;
  const res = await getJSON("/api/predict", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  renderStrategyCards(res.priority_sorted);  // ②
  renderAll(res.all_candidates);             // ③
  renderRanges(res.range_freq, res.top_ranges, res.bottom_range); // ⑥
}

async function init(){
  await refreshTop();
  const btn = document.getElementById("btnPredict");
  if (btn) btn.addEventListener("click", doPredict);
}

init();
