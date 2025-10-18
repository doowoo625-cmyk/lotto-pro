// ====== 반드시 파일 최상단에 추가 ======
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// 지갑 확장 콘솔 에러 무시(사이트 기능과 무관)
window.addEventListener('error', (e) => {
  if (e?.message?.includes('Cannot redefine property: ethereum')) e.stopImmediatePropagation();
}, true);

// API 래퍼
const api = {
  async predict() {
    const r = await fetch('/api/predict', { method: 'POST' }); // 서버는 POST/GET 모두 허용(아래 2번 패치)
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
};

// 숫자 → 공색
const ballColor = (n) => {
  if (n <= 10) return 'ball-yellow';
  if (n <= 20) return 'ball-blue';
  if (n <= 30) return 'ball-red';
  if (n <= 40) return 'ball-purple'; // 31~40 보라
  return 'ball-green';               // 41~45 초록
};
const balls = (arr) => `<div class="balls">` + arr.map(n => `<span class="ball ${ballColor(n)}">${n}</span>`).join('') + `</div>`;
const metricText = (x) => `S:${x.score} / R/R:${x.rr ?? x.score} / 승률:${x.win ?? '-'}%`;

// 렌더러들
function renderBestTop5(arr) {
  const el = $('#bestBlock');
  if (!arr || !arr.length) { el.innerHTML = `<div class="empty">예측 데이터를 계산할 수 없습니다.</div>`; return; }
  el.innerHTML = arr.slice(0,5).map((x,i)=>`
    <div class="row item">
      <span class="col-rank">${i+1}위</span>
      <span class="col-combo">${balls(x.numbers)}</span>
      <span class="col-meta tag">${x.name}</span>
      <span class="col-metrics mono">${metricText(x)}</span>
    </div>`).join('');
}
function renderWeekly(best3) {
  const el = $('#weeklyBlock');
  if (!best3 || !best3.length) { el.innerHTML = `<div class="empty">추천 전략을 산출할 수 없습니다.</div>`; return; }
  const sorted = [...best3].sort((a,b)=>b.score-a.score);
  el.innerHTML = sorted.map((x,idx)=>`
    <div class="card strategy-card">
      <div class="row between">
        <div class="tag big">${idx+1}위 · ${x.name}</div>
        <div class="mono">${metricText(x)}</div>
      </div>
      ${balls(x.numbers)}
    </div>`).join('');
}
function renderByStrategy(allBy) {
  const el = $('#byStrategyBlock');
  const order = ['보수형','균형형','고위험형'];
  el.innerHTML = order.map(name=>{
    const arr = allBy?.[name] || [];
    const list = arr.slice(0,5).map((x,i)=>`
      <div class="row item">
        <span class="col-rank">${i+1}위</span>
        <span class="col-combo">${balls(x.numbers)}</span>
        <span class="col-meta tag">${x.name}</span>
        <span class="col-metrics mono">${metricText(x)}</span>
      </div>`).join('');
    return `
      <div class="card">
        <div class="card-title">${name}</div>
        <div class="table-head">
          <div class="row head">
            <span class="col-rank">순위</span>
            <span class="col-combo">조합</span>
            <span class="col-meta">전략</span>
            <span class="col-metrics">근거(Score / R/R / 승률%)</span>
          </div>
        </div>
        <div class="list">${list || '<div class="empty">데이터 없음</div>'}</div>
      </div>`;
  }).join('');
}

// ==== DOM 준비 후 바인딩 ====
document.addEventListener('DOMContentLoaded', () => {
  const statusEl = $('#apiStatus');

  async function boot() {
    statusEl && (statusEl.textContent = '계산 중…');
    try {
      const data = await api.predict();
      renderWeekly(data.best3_by_priority_korean);
      renderByStrategy(data.all_by_strategy_korean);
      renderBestTop5(data.best_strategy_top5);
      statusEl && (statusEl.textContent = '완료');
    } catch (e) {
      console.error(e);
      statusEl && (statusEl.textContent = '오프라인(캐시 없음)');
      renderWeekly([]); renderByStrategy({}); renderBestTop5([]);
    }
  }

  $('#btnPredict')?.addEventListener('click', boot);
  // 첫 진입 자동 1회 렌더
  boot();
});
