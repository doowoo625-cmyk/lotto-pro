// static/app.js
async function getJSON(url, opts={}){ const r = await fetch(url, opts); if(!r.ok){ throw new Error(await r.text()) } return await r.json(); }
function lottoColor(n){ if(n>=1&&n<=10) return "yellow"; if(n<=20) return "blue"; if(n<=30) return "red"; if(n<=40) return "gray"; return "green"; }
const pill=(n)=>`<span class="pill ${lottoColor(n)}">${String(n).padStart(2,'0')}</span>`;

async function refreshTop(){
  try{
    const last = await getJSON('/api/latest');
    document.getElementById("statusRight").innerHTML =
      `직전(${last.draw_no}회) ` + last.numbers.map(pill).join(" ") + ` 보너스 ${pill(last.bonus)}`;
    const dl = document.getElementById('dlDraws'); const dl2 = document.getElementById('dlDraws2');
    if (dl && dl2){
      let opts = ''; const end = last.draw_no || 0;
      for(let n=end; n>Math.max(0,end-50); n--){ opts += `<option value="${n}">${n}회</option>`; }
      dl.innerHTML = opts; dl2.innerHTML = opts;
      const inp1 = document.getElementById('inpEndDraw'); const inp2 = document.getElementById('inpEndDraw2');
      if (inp1 && !inp1.value) inp1.value = end;
      if (inp2 && !inp2.value) inp2.value = end;
    }
    const apiEl = document.getElementById("apiStatus"); if(apiEl) apiEl.textContent = "정상";
  }catch(e){
    const apiEl = document.getElementById("apiStatus"); if(apiEl) apiEl.textContent = "네트워크 확인";
  }
}

// ✅ 초기 로딩에서는 상단만 로드. 아래 두 기능은 버튼 클릭 시에만 실행.
// async function onRecent(){ ... }   // (기존 함수 유지)
// async function onRange(){ ... }    // (기존 함수 유지)
// async function onPredict(){ ... }  // (기존 함수 유지)
// function bind(){ ... }             // (기존 함수 유지에서 init시 onRecent/onRange 자동 호출 삭제)

async function init(){
  bind();
  await refreshTop();   // 상단만
  // ❌ 자동 onRecent(); onRange(); 제거
}
init();
