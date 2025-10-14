
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

async function refreshStatus(){
  // health
  try{
    const h = await getJSON("/api/health");
    document.getElementById("apiStatus").textContent = h.ok ? "정상" : "점검 필요";
  }catch(e){
    document.getElementById("apiStatus").textContent = "오프라인";
  }
  // basis & recent last from recent10
  try{
    const recent = await getJSON("/api/recent10");
    const items = recent.items || [];
    let basis = null, last = null;
    if (items.length>0){
      basis = items[0]; last = items[items.length-1];
    }else{
      const fallback = await getJSON("/api/last_draw");
      basis = fallback; last = fallback;
    }
    const right = document.getElementById("statusRight");
    right.innerHTML = `기준 회차(<b>${basis.draw_no}</b>): ${basis.numbers.map(pill).join(" ")} | 보너스 ${pill(basis.bonus)} &nbsp;·&nbsp; 직전 회차(<b>${last.draw_no}</b>): ${last.numbers.map(pill).join(" ")} | 보너스 ${pill(last.bonus)}`;
    // also seed inputs with last
    document.getElementById("inpDrawNo").value = last.draw_no || 0;
    document.getElementById("inpNumbers").value = (last.numbers||[]).join(",");
    document.getElementById("inpBonus").value = last.bonus || 0;
  }catch(e){}
}

function renderPriority(list){
  const box = document.getElementById("priorityList");
  box.innerHTML = "";
  list.forEach((item, idx)=>{
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
      </div>
    `;
    box.appendChild(el);
  });
}

function renderAll(all){
  const box = document.getElementById("allCandidates");
  box.innerHTML = "";
  Object.keys(all).forEach(k=>{
    const group = document.createElement("div");
    group.innerHTML = `<h3>${k}</h3>`;
    const grid = document.createElement("div");
    grid.className = "cards";
    all[k].forEach((it)=>{
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="pills">${it.numbers.map(n=>pill(n)).join("")}</div>
        <div class="kv">
          <span class="tag">Score: ${it.score}</span>
          <span class="tag">R/R: ${it.rr}</span>
          <span class="tag">추정 승률: ${it.win}%</span>
        </div>
        <div class="table">
          <div class="thead">번호 / 빈도 / 확률(%) / 기준</div>
          <div class="row small">${it.rationale}</div>
        </div>
      `;
      grid.appendChild(card);
    });
    group.appendChild(grid);
    box.appendChild(group);
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
  renderPriority(res.priority_sorted);
  renderAll(res.all_candidates);
  renderRanges(res.range_freq, res.top_ranges, res.bottom_range);
}

async function saveLast(){
  const draw_no = parseInt(document.getElementById("inpDrawNo").value||"0",10);
  const numbers = document.getElementById("inpNumbers").value.split(",").map(s=>parseInt(s.trim(),10)).filter(n=>!isNaN(n));
  const bonus = parseInt(document.getElementById("inpBonus").value||"0",10);
  await getJSON("/api/last_draw", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({draw_no, numbers, bonus})
  });
  await refreshStatus();
  alert("저장 완료");
}
async function loadRecent10(){
  const r = await getJSON("/api/recent10");
  console.log("recent10", r);
  alert("최근10 불러오기 완료. 예측을 다시 실행하세요.");
}

document.getElementById("btnPredict").addEventListener("click", doPredict);
document.getElementById("btnSaveLast").addEventListener("click", saveLast);
document.getElementById("btnLoadRecent10").addEventListener("click", loadRecent10);
refreshStatus();
