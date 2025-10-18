window.addEventListener('error', (e) => {
  if (e?.message?.includes('Cannot redefine property: ethereum')) e.stopImmediatePropagation();
}, true);

const api = {
  async predict() {
    const r = await fetch('/api/predict', { method: 'POST' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
};

document.querySelector('#btnPredict')?.addEventListener('click', async () => {
  const status = document.querySelector('#apiStatus');
  if (status) status.textContent = '계산 중…';
  try {
    const data = await api.predict();
    // ① 예측 번호 블록 갱신 (너가 쓰던 렌더 함수 호출)
    renderBestTop5(data.best_strategy_top5);
    // ② 이번 주 추천 전략/전략별 추천도 같은 응답에서 같이 갱신 가능
    renderWeekly(data.best3_by_priority_korean);
    renderByStrategy(data.all_by_strategy_korean);
    if (status) status.textContent = '완료';
  } catch (e) {
    console.error(e);
    if (status) status.textContent = '오프라인';
  }
});


// 숫자 → 공 UI
const ballColor = (n) => {
  if (n >= 1 && n <= 10) return 'ball-yellow';
  if (n >= 11 && n <= 20) return 'ball-blue';
  if (n >= 21 && n <= 30) return 'ball-red';
  if (n >= 31 && n <= 40) return 'ball-purple'; // 요구 사항 반영
  return 'ball-green'; // 41~45
};
const balls = (arr) =>
  `<div class="balls">` +
  arr.map(n => `<span class="ball ${ballColor(n)}">${n}</span>`).join('') +
  `</div>`;

// 공통 렌더
const metricText = (x) => `S:${x.score} / R/R:${x.rr ?? x.score} / 승률:${x.win ?? '-'}%`;

// ① 예측 번호 조회(Top5)
function renderBestTop5(arr) {
  const el = $('#bestBlock');
  if (!arr || !arr.length) {
    el.innerHTML = `<div class="empty">예측 데이터를 계산할 수 없습니다.</div>`;
    return;
  }
  el.innerHTML = arr.slice(0,5).map((x, i) => `
    <div class="row item">
      <span class="col-rank">${i+1}위</span>
      <span class="col-combo">${balls(x.numbers)}</span>
      <span class="col-meta tag">${x.name}</span>
      <span class="col-metrics mono">${metricText(x)}</span>
    </div>
  `).join('');
}

// ② 이번 주 추천 전략(각 전략 1세트, 점수 내림차순 세로)
function renderWeekly(best3) {
  const el = $('#weeklyBlock');
  if (!best3 || !best3.length) {
    el.innerHTML = `<div class="empty">추천 전략을 산출할 수 없습니다.</div>`;
    return;
  }
  // 점수 내림차순
  const sorted = [...best3].sort((a,b)=>b.score-a.score);
  el.innerHTML = sorted.map((x,idx)=>`
    <div class="card strategy-card">
      <div class="row between">
        <div class="tag big">${idx+1}위 · ${x.name}</div>
        <div class="mono">${metricText(x)}</div>
      </div>
      ${balls(x.numbers)}
    </div>
  `).join('');
}

// ③ 전략별 추천 (보수형/균형형/고위험형 각각 5세트)
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
      </div>
    `).join('');
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

// 초기/버튼 핸들러
async function boot(renderOnly = false) {
  $('#apiStatus').textContent = '계산 중…';
  try {
    const data = await api.predict();
    // ② / ③ 는 항상 자동 렌더
    renderWeekly(data.best3_by_priority_korean);
    renderByStrategy(data.all_by_strategy_korean);
    // ① 은 버튼 클릭 시에도 동일 소스 사용 → 여기선 최초 1회도 채워 줌
    renderBestTop5(data.best_strategy_top5);
    $('#apiStatus').textContent = '완료';
  } catch (e) {
    console.error(e);
    $('#apiStatus').textContent = '오프라인(캐시 없음)';
    // 안전 플레이스홀더
    renderWeekly([]);
    renderByStrategy({});
    renderBestTop5([]);
  }
}

$('#btnPredict')?.addEventListener('click', async ()=>{
  $('#apiStatus').textContent = '재계산…';
  try {
    const data = await api.predict();
    renderBestTop5(data.best_strategy_top5);
    $('#apiStatus').textContent = '완료';
  } catch(e) {
    console.error(e);
    $('#apiStatus').textContent = '오프라인';
  }
});

// 부팅
boot();
