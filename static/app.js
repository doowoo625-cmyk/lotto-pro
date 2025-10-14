
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

function renderBestTable(best_name_ko, rows){
  const root = document.getElementById("tblBest");
  const ths = ['No.','예측 번호 조합','전략'];
  for(let i=1;i<=6;i++){ ths.push('번호','빈도','확률','기준'); }
  let html = '<table class="table"><thead><tr>' + ths.map(t=>`<th>${t}</th>`).join('') + '</tr></thead><tbody>';
  rows.forEach((it, idx)=>{
    let tds = [`<td>${idx+1}</td>`,`<td>${it.numbers.map(pill).join(' ')}</td>`,`<td>${best_name_ko}</td>`];
    const parts = (it.rationale||'').split('|').map(s=>s.trim());
    parts.forEach(seg=>{
      const [num, freq, pct, basis] = seg.split('/');
      tds.push(`<td>${num}</td>`,`<td class="right">${freq}</td>`,`<td class="right">${pct}</td>`,`<td>${basis}</td>`);
    });
    for(let k=parts.length;k<6;k++){ tds.push('<td></td><td></td><td></td><td></td>'); }
    html += '<tr>'+tds.join('')+'</tr>';
  });
  html += '</tbody></table>';
  root.innerHTML = html;
}

function renderWeekly(best3){
  const order = ['균형형','보수형','고위험형'];
  const map = {}; best3.forEach(r=> map[r.name_ko]=r);
  let html = '';
  order.forEach((name, idx)=>{
    const it = map[name];
    html += '<table class="table" style="margin:8px 0">';
    html += `<thead><tr><th>① ${name}</th><th colspan="10" class="subth right">근거</th></tr></thead><tbody>`;
    if (it){
      html += `<tr><td>${it.numbers.map(pill).join(' ')}</td><td colspan="10" class="small">${it.rationale}</td></tr>`;
    }else{
      html += `<tr><td colspan="11">데이터 없음</td></tr>`;
    }
    html += '</tbody></table>';
  });
  document.getElementById('tblWeekly').innerHTML = html;
}

function renderByStrategy(all){
  const order = ['보수형','균형형','고위험형'];
  let html='';
  order.forEach((name, gi)=>{
    html += '<table class="table" style="margin:10px 0">';
    html += `<thead><tr><th>② ${gi+1}. ${name}</th><th class="right">Score</th><th class="right">보상</th><th class="right">승률</th></tr></thead><tbody>`;
    const rows = (all[name]||[]).slice(0,5);
    if (rows.length===0){ html += `<tr><td colspan="4">데이터 없음</td></tr>`; }
    else{
      rows.forEach((it, idx)=>{
        html += `<tr>
          <td>${idx+1}. ${it.numbers.map(pill).join(' ')}</td>
          <td class="right">${it.score}</td>
          <td class="right">${it.reward}</td>
          <td class="right">${it.win}%</td>
        </tr>`;
      });
    }
    html += '</tbody></table>';
  });
  document.getElementById('tblByStrategy').innerHTML = html;
}

async function refreshRecent(){
  const data = await getJSON('/api/recent');
  const items = (data.items||[]).slice(-10).sort((a,b)=> a.draw_no - b.draw_no);
  const sel = document.getElementById('selDraw');
  sel.innerHTML = '<option value="all">최근 10회</option>' + items.map(it=>`<option value="${it.draw_no}">${it.draw_no}회</option>`).join('');
  const render = (filter)=>{
    const list = filter==='all' ? items : items.filter(x=> String(x.draw_no)===filter);
    let html = '<table class="table"><thead><tr><th>회차</th><th>날짜</th>' + 
      '<th colspan="6">번호</th><th class="right">합</th><th class="right">홀</th><th class="right">고번호</th></tr></thead><tbody>';
    list.forEach(it=>{
      const sum = it.numbers.reduce((a,b)=>a+b,0);
      const odd = it.numbers.filter(n=> n%2===1).length;
      const high = it.numbers.filter(n=> n>=23).length;
      const date = it.date || '';
      html += `<tr><td>${it.draw_no}</td><td>${date}</td><td colspan="6">${it.numbers.map(pill).join(' ')}</td><td class="right">${sum}</td><td class="right">${odd}</td><td class="right">${high}</td></tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('tblRecent').innerHTML = html;
  };
  document.getElementById('btnRecent').onclick = ()=> render(sel.value);
  render('all');
}

async function refreshRange(){
  const windowN = parseInt(document.getElementById('selWindow').value||'10',10);
  const data = await getJSON(`/api/range_freq?window=${windowN}`);
  const per = data.per;
  const groups = ['1-10','11-20','21-30','31-40','41-45'];
  let html = '<table class="table"><thead><tr>';
  groups.forEach(g=> html += `<th colspan="2">${g}</th>`);
  html += '</tr><tr class="subth">';
  groups.forEach(g=> html += '<th>번호</th><th>빈도</th>');
  html += '</tr></thead><tbody>';
  const maxRows = 10;
  for(let r=0;r<maxRows;r++){
    html += '<tr>';
    groups.forEach(g=>{
      const keys = Object.keys(per[g]).sort((a,b)=> Number(a)-Number(b));
      const n = keys[r]; const f = n ? per[g][n] : '';
      html += `<td>${n? `<span class="pill ${lottoColor(Number(n))}">${String(n).padStart(2,'0')}</span>`:''}</td><td class="right">${f!==''? f:''}</td>`;
    });
    html += '</tr>';
  }
  html += '<tr class="subth">';
  groups.forEach(g=>{
    const sum = Object.values(per[g]).reduce((a,b)=>a+Number(b),0);
    html += `<td>합계</td><td class="right">${sum}</td>`;
  });
  html += '</tr></tbody></table>';
  document.getElementById('tblRange').innerHTML = html;
}

async function doPredict(){
  const seedVal = document.getElementById('seed').value;
  const countVal = parseInt(document.getElementById('count').value || '5', 10);
  const body = { count: countVal };
  if (seedVal !== '') body.seed = parseInt(seedVal, 10);
  const res = await getJSON('/api/predict', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  renderBestTable(res.best_strategy_name_ko, res.best_strategy_top5);
  renderWeekly(res.best3_by_priority_korean);
  renderByStrategy(res.all_by_strategy_korean);
}

function bindEvents(){
  document.getElementById('btnPredict').addEventListener('click', doPredict);
  document.getElementById('btnRange').addEventListener('click', refreshRange);
}

async function init(){
  bindEvents();
  await refreshTop();
  await refreshRecent();
  await refreshRange();
}
init();
