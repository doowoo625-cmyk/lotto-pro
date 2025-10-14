
async function getJSON(url, opts={}){
  const r = await fetch(url, opts);
  if (!r.ok){ throw new Error(await r.text()) }
  return await r.json();
}

function fmtNums(arr){ return arr.join(", "); }

async function refreshStatus(){
  try{
    const h = await getJSON("/api/health");
    document.getElementById("apiStatus").textContent = h.ok ? "정상" : "점검 필요";
  }catch(e){
    document.getElementById("apiStatus").textContent = "오프라인";
  }
  try{
    const last = await getJSON("/api/last_draw");
    document.getElementById("drawNo").textContent = last.draw_no;
    document.getElementById("lastNums").textContent = fmtNums(last.numbers);
    document.getElementById("bonusNum").textContent = last.bonus;
    document.getElementById("inpDrawNo").value = last.draw_no;
    document.getElementById("inpNumbers").value = last.numbers.join(",");
    document.getElementById("inpBonus").value = last.bonus;
  }catch(e){
    console.error(e);
  }
}

function renderPriority(list){
  const box = document.getElementById("priorityList");
  box.innerHTML = "";
  list.forEach((item, idx)=>{
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <h3>#${idx+1} ${item.name}</h3>
      <div class="grid">
        <div>추천 번호</div><div class="pills">${item.numbers.map(n=>`<span class="pill">${n}</span>`).join("")}</div>
        <div>score</div><div>${item.score}</div>
        <div>근거</div><div>${item.rationale}</div>
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
        <div class="pills">${it.numbers.map(n=>`<span class="pill">${n}</span>`).join("")}</div>
        <div>score: ${it.score}</div>
        <div style="opacity:.85;font-size:12px">${it.rationale}</div>
      `;
      grid.appendChild(card);
    });
    group.appendChild(grid);
    box.appendChild(group);
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
}

async function saveLast(){
  const draw_no = parseInt(document.getElementById("inpDrawNo").value||"0",10);
  const numbers = document.getElementById("inpNumbers").value.split(",").map(s=>parseInt(s.trim(),10)).filter(n=>!isNaN(n));
  const bonus = parseInt(document.getElementById("inpBonus").value||"0",10);
  const res = await getJSON("/api/last_draw", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({draw_no, numbers, bonus})
  });
  await refreshStatus();
  alert("저장 완료");
}

document.getElementById("btnPredict").addEventListener("click", doPredict);
document.getElementById("btnSaveLast").addEventListener("click", saveLast);
refreshStatus();
