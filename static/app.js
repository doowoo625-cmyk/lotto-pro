// === 이번 주 추천 전략: 세로 카드(1→3) + 카드 내부 가로 정렬 ===
function renderWeeklyHorizontal(best3){
  const root = document.getElementById('weeklyBlock');
  if (!root) return;
  root.innerHTML = '';

  // 점수 높은 순 (1→3위)
  const sorted = [...best3].sort((a,b)=> (b.score ?? 0) - (a.score ?? 0));

  // 세로로 쌓기
  const stack = document.createElement('div');
  stack.className = 'weekly-stack';

  sorted.forEach((it, idx)=>{
    const name = it.name_ko || it.name || '전략';

    // 카드 1개 = 한 줄 가로 정렬(랭크 뱃지 / 전략명 / 번호 / 지표)
    const card = document.createElement('div');
    card.className = 'card weekly-row';

    card.innerHTML = `
      <div class="mono rank-badge">${idx+1}</div>
      <div class="weekly-name">${name}</div>
      <div class="pills weekly-pills">${it.numbers.map(pill).join("")}</div>
      <div class="kv weekly-metrics">
        <span class="tag">Score ${it.score}</span>
        <span class="tag">R/R ${it.rr}</span>
        <span class="tag">승률 ${it.win}%</span>
      </div>
    `;

    stack.appendChild(card);
  });

  root.appendChild(stack);
}
