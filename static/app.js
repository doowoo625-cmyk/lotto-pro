// ===== 헬퍼 & 확장 에러 가드 =====
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// 지갑 확장 충돌 콘솔 소음 차단(사이트 기능과 무관)
window.addEventListener('error', (e) => {
  if (e?.message?.includes('Cannot redefine property: ethereum')) e.stopImmediatePropagation();
}, true);

// ===== API =====
const api = {
  async predict() {
    const r = await fetch('/api/predict', { method: 'POST' }); // 버튼 클릭시에만 호출
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
  `<div class="balls">` +
  arr.map(n => `<span class="ball ${ballColor(n)}">${n}</span>`).join('') +
  `</div>`;

const metricText = (x) => `S:${x.score} / R/R:${x.rr ?? x.score} / 승률:${x.win ?? '-'}%`;

// 백엔드 명칭 → 화면 표시명 맵핑(균형형→전략형)
const nameDisplay = (name) => (name === '균형형' ? '전략형' : name);

// ===== 렌더러 =====

// ① 예측 번호 Top5 — “가장 추천하는 단일 전략”만 사용
//    규칙: 각 전략 리스트의 1위(score 최대)를 비교해서 가장 높은 전략 1개 선택 → 그 전략의 Top5 표시
function renderBestTop5FromBestStrategy(allBy) {
  const el = $('#bestBlock');
  const candidates = [
    allBy?.['보수형']?.[0],
    allBy?.['균형형']?.[0],
    allBy?.['고위험형']?.[0],
  ].filter(Boolean);

  if (!candidates.length) {
    el.innerHTML = `<div class="empty">예측 데이터를 계산할 수 없습니다.</div>`;
    return;
  }
  // 최고 점수 전략 선택
  candidates.sort((a, b) => b.score - a.score);
  const bestStrategyName = candidates[0].name; // 보수형/균형형/고위험형
  const bestList = (allBy?.[bestStrategyName] || []).slice(0, 5);

  el.innerHTML = bestList.map((x, i) => `
    <div class="row item">
      <span class="col-rank">${i+1}위</span>
      <span class="col-combo">${balls(x.numbers)}</span>
      <span class="col-meta tag">${nameDisplay(x.name)}</span>
      <span class="col-metrics mono">${metricText(x)}</span>
    </div>
  `).join('');
}

// ② 이번 주 추천 전략 (각 전략 1세트, 점수 내림차순 → 카드 세로)
function renderWeekly(best3) {
  const el = $('#weeklyBlock');
  if (!best3 || !best3.length) {
    el.innerHTML = `<div class="empty">추천 전략을 산출할 수 없습니다.</div>`;
    return;
  }
  const sorted = [...best3].sort((a,b)=>b.score-a.score);
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

// ③ 전략별 추천 — 보수형 → 전략형(=균형형) → 고위험형, 각 1~5위 세로, 행 가로 정렬
function renderByStrategy(allBy) {
  const el = $('#byStrategyBlock');
  const orderBackend = ['보수형','균형형','고위험형'];          // 데이터 키 순서
  const orderDisplay = ['보수형','전략형','고위험형'];            // 화면 표시 순서

  el.innerHTML = orderBackend.map((key, idx)=>{
    const arr = allBy?.[key] || [];
    const list = arr.slice(0,5).map((x,i)=>`
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

// ===== 초기 바인딩 (초기 자동 조회 없음: 버튼 클릭 시에만 조회) =====
document.addEventListener('DOMContentLoaded', () => {
  const statusEl = $('#apiStatus');

  async function runPredict() {
    statusEl && (statusEl.textContent = '계산 중…');
    try {
      const data = await api.predict(); // 한 번의 호출로 3개 섹션 모두 채움
      // ① 가장 추천하는 ‘단일 전략’의 Top5
      renderBestTop5FromBestStrategy(data.all_by_strategy_korean);
      // ② 이번 주 추천 전략(근거 = 백엔드 계산값 그대로)
      renderWeekly(data.best3_by_priority_korean);
      // ③ 전략별 추천(보수형 → 전략형 → 고위험형)
      renderByStrategy(data.all_by_strategy_korean);

      statusEl && (statusEl.textContent = '완료');
    } catch (e) {
      console.error(e);
      statusEl && (statusEl.textContent = '오프라인(응답 없음)');
    }
  }

  $('#btnPredict')?.addEventListener('click', runPredict); // 클릭할 때마다 재조회
});
