
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
    const last = await getJSON('/api/latest');
    document.getElementById("statusRight").innerHTML =
      `직전(${last.draw_no}회) ` + last.numbers.map(pill).join(" ") + ` 보너스 ${pill(last.bonus)}`;
    const dl = document.getElementById('dlDraws'); const dl2 = document.getElementById('dlDraws2');
    if (dl && dl2){
      let opts = ''; const end = last.draw_no;
      for(let n=end; n>Math.max(0,end-50); n--){ opts += `<option value="${n}">${n}회</option>`; }
      dl.innerHTML = opts; dl2.innerHTML = opts;
      const inp1 = document.getElementById('inpEndDraw'); const inp2 = document.getElementById('inpEndDraw2');
      if (inp1 && !inp1.value) inp1.value = end;
      if (inp2 && !inp2.value) inp2.value = end;
    }
    const apiEl = document.getElementById("apiStatus");
    if (apiEl) apiEl.textContent = "정상";
  }catch(e){
    const apiEl = document.getElementById("apiStatus");
    if (apiEl) apiEl.textContent = "네트워크 확인";
  }
}
