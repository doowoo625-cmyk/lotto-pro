// Lotto v2.1 client-side engine
let draws = []; // {회차, 날짜, 번호1..번호6, 보너스}

function parseCSV(text){
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(',');
  const rows = [];
  for(let i=1;i<lines.length;i++){
    if(!lines[i].trim()) continue;
    const cols = lines[i].split(',').map(s=>s.trim());
    const rec = Object.fromEntries(header.map((h,idx)=>[h, cols[idx]]));
    ['번호1','번호2','번호3','번호4','번호5','번호6','보너스','회차'].forEach(k=> rec[k] = +rec[k]);
    rows.push(rec);
  }
  return rows.sort((a,b)=>a.회차-b.회차);
}

function ballClass(n){
  if(n<=10) return 'yellow';
  if(n<=20) return 'blue';
  if(n<=30) return 'red';
  if(n<=40) return 'gray';
  return 'green';
}

function ballHTML(n){
  return `<span class="ball ${ballClass(n)}">${n}</span>`;
}

function sum(nums){ return nums.reduce((a,b)=>a+b,0); }
function oddCount(nums){ return nums.filter(n=>n%2===1).length; }
function highCount(nums,cut){ return nums.filter(n=>n>=cut).length; }

function renderRoundDropdown(){
  const sel = document.getElementById('roundDropdown');
  sel.innerHTML = '';
  const unique = [...new Set(draws.map(d=>d.회차))].sort((a,b)=>b-a);
  unique.forEach(r=>{
    const opt = document.createElement('option');
    opt.value = r; opt.textContent = r;
    sel.appendChild(opt);
  });
}

function showRecent10(fromRound){
  const target = document.getElementById('recentTable');
  target.innerHTML = '';
  if(!draws.length){ target.textContent='데이터가 없습니다.'; return; }
  let idx = draws.findIndex(d=>d.회차===fromRound);
  if(idx===-1){ // if exact round not found, select latest
    idx = draws.length-1;
  }
  const start = Math.max(0, idx-9);
  const slice = draws.slice(start, idx+1).reverse();
  const html = [`<table><thead><tr><th>회차</th><th>날짜</th><th>번호</th><th>합</th><th>홀</th><th>고번호</th></tr></thead><tbody>`];
  const highCut = +document.getElementById('highCut').value || 23;
  slice.forEach(d=>{
    const nums = [d.번호1,d.번호2,d.번호3,d.번호4,d.번호5,d.번호6].sort((a,b)=>a-b);
    const balls = nums.map(ballHTML).join('');
    html.push(`<tr><td>${d.회차}</td><td>${d.날짜}</td><td>${balls}</td><td>${sum(nums)}</td><td>${oddCount(nums)}</td><td>${highCount(nums, highCut)}</td></tr>`);
  });
  html.push(`</tbody></table>`);
  target.innerHTML = html.join('');
}

function buildWeights(){
  // frequency of each number 1..45 across dataset
  const freq = Array(46).fill(0);
  draws.forEach(d=>{
    [d.번호1,d.번호2,d.번호3,d.번호4,d.번호5,d.번호6].forEach(n=>{ if(n>=1 && n<=45) freq[n]++; });
  });
  // avoid zero weight: add 1 smoothing
  const weights = freq.map(f=>f+1);
  return weights;
}

function pickWeighted(weights){
  // sample 6 unique numbers 1..45 without replacement based on weights
  const pool = Array.from({length:45}, (_,i)=>i+1);
  const w = pool.map(n=>weights[n]);
  const chosen = [];
  for(let k=0;k<6;k++){
    const total = w.reduce((a,b)=>a+b,0);
    let r = Math.random()*total;
    let idx=0;
    while(r>=w[idx]){ r-=w[idx]; idx++; }
    chosen.push(pool[idx]);
    // remove chosen
    pool.splice(idx,1);
    w.splice(idx,1);
  }
  return chosen.sort((a,b)=>a-b);
}

function pickRandom(){
  const pool = Array.from({length:45}, (_,i)=>i+1);
  const chosen = [];
  for(let i=0;i<6;i++){
    const idx = Math.floor(Math.random()*pool.length);
    chosen.push(pool.splice(idx,1)[0]);
  }
  return chosen.sort((a,b)=>a-b);
}

function renderPredictions(list){
  const wrap = document.getElementById('predictions');
  wrap.innerHTML = '';
  const highCut = +document.getElementById('highCut').value || 23;
  list.forEach((nums, i)=>{
    const balls = nums.map(ballHTML).join('');
    const meta = `합 ${sum(nums)} · 홀 ${oddCount(nums)} · 고번호 ${highCount(nums, highCut)}`;
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<h3>#${i+1}</h3><div>${balls}</div><div class="meta">${meta}</div>`;
    wrap.appendChild(card);
  });
}

// Event wiring
document.getElementById('fileInput').addEventListener('change', async (e)=>{
  const file = e.target.files[0];
  if(!file) return;
  const text = await file.text();
  draws = parseCSV(text);
  document.getElementById('loadStatus').textContent = `불러오기 완료: ${draws.length}회`;
  renderRoundDropdown();
  if(draws.length) showRecent10(draws[draws.length-1].회차);
});

document.getElementById('loadSample').addEventListener('click', async ()=>{
  const res = await fetch('../data/sample_results.csv');
  const text = await res.text();
  draws = parseCSV(text);
  document.getElementById('loadStatus').textContent = `샘플 로드: ${draws.length}회`;
  renderRoundDropdown();
  showRecent10(draws[draws.length-1].회차);
});

document.getElementById('generateBtn').addEventListener('click', ()=>{
  const mode = [...document.querySelectorAll('input[name="mode"]')].find(r=>r.checked).value;
  const n = Math.min(20, Math.max(1, +document.getElementById('comboCount').value||5));
  let results = [];
  if(mode==='weighted'){
    const w = buildWeights();
    for(let i=0;i<n;i++) results.push(pickWeighted(w));
  }else{
    for(let i=0;i<n;i++) results.push(pickRandom());
  }
  renderPredictions(results);
});

document.getElementById('searchRound').addEventListener('click', ()=>{
  const r = +document.getElementById('queryRound').value;
  if(!r){ alert('회차를 입력하세요'); return; }
  showRecent10(r);
});

document.getElementById('goDropdown').addEventListener('click', ()=>{
  const sel = document.getElementById('roundDropdown');
  const r = +sel.value;
  showRecent10(r);
});

document.getElementById('calcFreq').addEventListener('click', ()=>{
  const s = +document.getElementById('startRound').value;
  const e = +document.getElementById('endRound').value;
  renderFreq(s,e);
});

function renderFreq(startRound, endRound){
  const target = document.getElementById('freqResult');
  target.innerHTML = '';
  if(!draws.length){ target.textContent='데이터가 없습니다.'; return; }
  const subset = draws.filter(d => 
    (!startRound || d.회차>=startRound) && (!endRound || d.회차<=endRound)
  );
  if(!subset.length){ target.textContent='해당 구간의 데이터가 없습니다.'; return; }

  const buckets = { '1-9':0, '10-19':0, '20-29':0, '30-39':0, '40-45':0 };
  let totalBalls = 0;
  subset.forEach(d=>{
    [d.번호1,d.번호2,d.번호3,d.번호4,d.번호5,d.번호6].forEach(n=>{
      if(n>=1 && n<=9) buckets['1-9']++;
      else if(n<=19) buckets['10-19']++;
      else if(n<=29) buckets['20-29']++;
      else if(n<=39) buckets['30-39']++;
      else buckets['40-45']++;
      totalBalls++;
    });
  });

  const wrap = document.createElement('div');
  wrap.className = 'grid';
  Object.entries(buckets).forEach(([k,v])=>{
    const card = document.createElement('div');
    card.className = 'freq-card';
    const pct = (v/totalBalls*100).toFixed(1);
    card.innerHTML = `<div class="freq-title">${k}</div>
      <div>출현: <b>${v}</b> <span class="badge">${pct}%</span></div>
      <div class="small">총 공: ${totalBalls}, 표본 회차: ${subset.length}</div>`;
    wrap.appendChild(card);
  });
  target.appendChild(wrap);
}
