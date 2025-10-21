// ===== 헬퍼 & 확장 에러 가드 =====
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// 브라우저 지갑 확장 충돌 소음 차단(기능 무관)
window.addEventListener('error', (e) => {
  if (e?.message?.includes('Cannot redefine property: ethereum')) e.stopImmediatePropagation();
}, true);

// ===== API =====
const api = {
  async predict() {
    const url = `/api/predict?u=${Date.now()}`; // 캐시 회피 (매 클릭 재조회)
    const r = await fetch(url, {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-store' }
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
};

// ===== 공 UI =====
const ballColor = (n) => {
  if (n <= 10) return 'ball-yellow';
  if (n <= 20) return 'ball-blue';
  if (n <= 30) return 'ball-red';
  if (n <= 40) return 'ball-purple'; // 31~40 보라
  return 'ball-green';               // 41~45 초록
};
const balls = (arr) =>
  `<div class="balls">` + arr.map(n => `<span class="ball ${ballColor(n)}">${n}</span>`).join('') + `</div>`;

// 근거 표시: 정확 계산 (백엔드 값 활용)
function metricText(x) {
  const reward = Number(x.reward ?? 0);
  const risk   = Number(x.risk   ?? 0);
  const score  = Number(x.score  ?? 0);
  const win    = (x.win ?? '-');
  const rr     = risk > 0 ? (reward / risk).toFixed(3) : '∞';
  return `S:${score} / R/R:${rr} / 승률:${win}%`;
}

// 백엔드 명칭 → 화면 표시명 맵핑(균형형→전략형)
const nameDisplay = (name) => (name === '균형형' ? '전략형' : name);

// ===== 렌더러 =====

// ① 예측 번호 Top5 — “가장 추천하는 단일 전략”만 사용
//   규칙: 각 전략 1위(score 최대) 비교 → 가장 높은 전략 1개 선택 → 그 전략의 Top5 출력
function renderBestTop5FromBestStrategy(allBy) {
  const el = $('#bestBlock');
  const cands = [
    allBy?.['보수형']?.[0],
    allBy?.['균형형']?.[0],
    allBy?.['고위험형']?.[0],
  ].filter(Boolean);
  if (!cands.length) { el.innerHTML = `<div class="empty">예측 데이터를 계산할 수 없습니다.</div>`; return; }
  cands.sort((a,b)=> (b.score ?? 0) - (a.score ?? 0));
  const bestName = cands[0].name;                       // 보수형/균형형/고위험형
  const bestList = (allBy?.[bestName] || []).slice(0,5);

  el.innerHTML = bestList.map((x,i)=>`
    <div class="row item">
      <span class="col-rank">${i+1}위</span>
      <span class="col-combo">${balls(x.numbers)}</span>
      <span class="col-meta tag">${nameDisplay(x.name)}</span>
      <span class="col-metrics mono">${metricText(x)}</span>
    </div>
  `).join('');
}
const url = `/api/predict?u=${Date.now()}`; // 캐시 회피
fetch(url, { method: 'POST', cache: 'no-store', headers: { 'Cache-Control': 'no-store' }})

// ② 이번 주 추천 전략 (각 전략 1세트, 점수 내림차순 → 카드 세로)
function renderWeekly(best3) {
  const el = $('#weeklyBlock');
  if (!best3 || !best3.length) { el.innerHTML = `<div class="empty">추천 전략을 산출할 수 없습니다.</div>`; return; }
  const sorted = [...best3].sort((a,b)=> (b.score ?? 0) - (a.score ?? 0));
  el.innerHTML = sorted.map((x,idx)=>`
    <div class="card strategy-card">
      <div class="row between">
        <div class="tag big">${idx+1}위 · ${nameDisplay(x.name)}</div>
        <div class="mono">${metricText(x)}</div>
      </div>
      ${balls(x.numbers)}
    </div>
  `).join('');
}

// ③ 전략별 추천 — 보수형 → 전략형(=균형형) → 고위험형 (가로 배치), 각 1~5위는 세로, 각 행은 가로 정렬
function renderByStrategy(allBy) {
  const el = $('#byStrategyBlock');
  const orderBackend = ['보수형','균형형','고위험형'];  // 데이터 키 순서(가로 나열)
  const orderDisplay = ['보수형','전략형','고위험형'];

  el.innerHTML = orderBackend.map((key, idx)=>{
    const arr = (allBy?.[key] || []).slice(0,5); // 1~5위 (이미 점수 내림차순 가정)
    const list = arr.map((x,i)=>`
      <div class="row item">
        <span class="col-rank">${i+1}위</span>
        <span class="col-combo">${balls(x.numbers)}</span>
        <span class="col-meta tag">${nameDisplay(x.name)}</span>
        <span class="col-metrics mono">${metricText(x)}</span>
      </div>
    `).join('');
    return `
      <div class="card">
        <div class="card-title">${orderDisplay[idx]}</div>
        <div class="table-head">
          <div class="row head">
            <span class="col-rank">순위</span>
            <span class="col-combo">조합</span>
            <span class="col-meta">전략</span>
            <span class="col-metrics">근거(Score / R/R / 승률%)</span>
          </div>
        </div>
        <div class="list">${list || '<div class="empty">데이터 없음</div>'}</div>
      </div>
    `;
  }).join('');
}

// ===== 바인딩 (초기 자동 조회 없음: 버튼 클릭 시마다 재조회) =====
document.addEventListener('DOMContentLoaded', () => {
  const statusEl = $('#apiStatus');

  async function runPredict() {
    statusEl && (statusEl.textContent = '계산 중…');
    try {
      const data = await api.predict(); // 매 클릭마다 새 요청
      // ① 단일 ‘최고’ 전략 Top5
      renderBestTop5FromBestStrategy(data.all_by_strategy_korean);
      // ② 이번 주 추천 전략
      renderWeekly(data.best3_by_priority_korean);
      // ③ 전략별 추천(보수형 → 전략형 → 고위험형 가로 배치)
      renderByStrategy(data.all_by_strategy_korean);
      statusEl && (statusEl.textContent = '완료');
    } catch (e) {
      console.error(e);
      statusEl && (statusEl.textContent = '오프라인(응답 없음)');
    }
  }

  $('#btnPredict')?.addEventListener('click', runPredict); // 클릭할 때마다 재조회
});
