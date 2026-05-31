(function() {
const config = JSON.parse(document.getElementById('leaderboard-config').textContent);
const CURRENT_USER_ID = config.currentUserId;
const endpointConfig = {
  publicProfileBase: config.publicProfileBase,
  compareBase: config.compareBase
};
let activeMode = 'cscore';
let currentPage = 1;
let totalPages = 1;
let currentUserRank = null;
let isLoading = false;
let leaderboardController = null;

function escapeHTML(str) {
  if (typeof str !== 'string' && typeof str !== 'number') return '';
  str = String(str);
  return str.replace(/[&<>"']/g, function(c) {
    return '&#' + c.charCodeAt(0) + ';';
  });
}

function safeURL(url) {
  if (!url) return '';
  try {
    const u = new URL(url);
    return (u.protocol === 'http:' || u.protocol === 'https:') ? u.href : '';
  } catch { return ''; }
}

function getScoreLabel(mode) {
  if (mode === 'cscore') return 'C-Score';
  if (mode === 'questions') return 'Solved';
  if (mode === 'rating') return 'Rating';
  if (mode === 'college') return 'College Score';
  return '';
}

function getScoreClass(mode) {
  if (mode === 'rating') return 'rating-mode';
  if (mode === 'questions') return 'questions-mode';
  if (mode === 'college') return 'college-mode';
  return '';
}

function avatarHTML(entry, size = 36) {
  if (entry.profile_photo) {
    return `<img src="${safeURL(entry.profile_photo)}" alt="${escapeHTML(entry.name)}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
  }
  return escapeHTML((entry.name || '?')[0].toUpperCase());
}

function renderLeaderboardError(error) {
  const message = error && error.message ? error.message : 'Error loading leaderboard data.';
  currentPage = 1;
  totalPages = 1;
  currentUserRank = null;
  document.getElementById('lbBody').innerHTML = `<tr><td colspan="5" class="loading">${escapeHTML(message)}</td></tr>`;
  renderPagination();
}

async function loadLeaderboard(page = 1) {
  if (leaderboardController) leaderboardController.abort();

  const controller = new AbortController();
  leaderboardController = controller;
  isLoading = true;
  
  document.getElementById('lbBody').innerHTML = '<tr><td colspan="5" class="loading" aria-label="Loading leaderboard data">Loading...</td><tr>';
  
  try {
    const url = `/api/leaderboard?mode=${activeMode}&page=${page}&per_page=20&current_user_id=${CURRENT_USER_ID || ''}`;
    const response = await fetch(url, { signal: controller.signal });
    const data = await response.json();

    if (leaderboardController !== controller) return;

    if (!response.ok) {
      throw new Error(data.error || data.message || `Leaderboard request failed (${response.status})`);
    }

    if (!Array.isArray(data.entries)) {
      throw new Error('Leaderboard response was missing entries.');
    }
    
    totalPages = Number(data.total_pages) || 1;
    currentPage = Number(data.page) || page;
    currentUserRank = data.current_user_rank || null;
    
    renderTable(data.entries, activeMode);
    renderPagination();
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (leaderboardController !== controller) return;
    console.error('Error loading leaderboard:', error);
    renderLeaderboardError(error);
  } finally {
    if (leaderboardController === controller) {
      leaderboardController = null;
      isLoading = false;
    }
  }
}

function renderTable(entries, mode) {
  const body = document.getElementById('lbBody');
  const isCollegeMode = mode === 'college';
  
  if (entries.length === 0) {
    body.innerHTML = `<tr><td colspan="5"><div class="loading">No users yet. Be the first to join!</div></td></tr>`;
    return;
  }
  
  let html = '';
  entries.forEach((e, i) => {
    const rank = e.rank;
    const isMe = e.user_id === CURRENT_USER_ID;
    const rankClass = rank === 1 ? 'top-1' : rank === 2 ? 'top-2' : rank === 3 ? 'top-3' : '';
    const rankIcon = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
    
    let score = 0;
    if (mode === 'cscore') score = e.c_score;
    else if (mode === 'questions') score = e.total_solved;
    else if (mode === 'rating') score = e.lc_rating;
    else if (mode === 'college') score = e.c_score;
    
    const profileURL = !isCollegeMode && e.user_id
      ? endpointConfig.publicProfileBase.replace('__USER_ID__', encodeURIComponent(e.user_id))
      : '';
    const nameHTML = isCollegeMode
      ? `${escapeHTML(e.college)}`
      : `<a href="${profileURL}" aria-label="View profile of ${escapeHTML(e.name)}">${escapeHTML(e.name)}</a>${isMe ? '<span class="me-tag" aria-label="This is you">YOU</span>' : ''}`;
    
    const subtitleHTML = isCollegeMode
      ? `${e.member_count} coder${e.member_count === 1 ? '' : 's'} · Top: ${escapeHTML(e.top_user?.name || 'N/A')}`
      : (escapeHTML(e.college) || '—');
    
    const dsaHTML = `<span class="stat-badge dsa">${e.dsa_done} / 450</span>`;
    
    const compareHTML = (CURRENT_USER_ID && !isMe && e.user_id)
      ? `<a class="pagination-btn" style="margin-left:8px" href="${endpointConfig.compareBase.replace('__USER_ID__', encodeURIComponent(e.user_id))}" aria-label="Compare with ${escapeHTML(e.name)}">Compare</a>`
      : '';

    const platformHTML = isCollegeMode
      ? `<span class="stat-badge lc">Solved ${e.total_solved}</span>`
      : `${e.lc_total ? `<span class="stat-badge lc" aria-label="LeetCode: ${e.lc_total} solved">LC ${e.lc_total}</span> ` : ''}
         ${e.gfg_total ? `<span class="stat-badge gfg" aria-label="GFG: ${e.gfg_total} solved">GFG ${e.gfg_total}</span> ` : ''}
         ${e.cn_total ? `<span class="stat-badge cn" aria-label="Coding Ninjas: ${e.cn_total} solved">CN ${e.cn_total}</span> ` : ''}
         ${e.hr_total ? `<span class="stat-badge hr" aria-label="HackerRank: ${e.hr_total} solved">HR ${e.hr_total}</span>` : ''}`;
    
    html += `
      <tr class="${isMe ? 'me-row' : ''}">
        <td class="rank-cell ${rankClass}" aria-label="Rank ${rank}">${rankIcon}</td>
        <td>
          <div class="user-cell">
            <div class="user-cell-avatar" aria-label="Avatar for ${escapeHTML(e.name)}">${avatarHTML(e)}</div>
            <div class="user-cell-info">
              <div class="user-cell-name">${nameHTML}</div>
              <div class="user-cell-college">${subtitleHTML}</div>
            </div>
          </div>
        </td>
        <td class="score-cell ${getScoreClass(mode)}" aria-label="${getScoreLabel(mode)}: ${score}">${score}</td>
        <td>${dsaHTML}</td>
        <td>${platformHTML} ${compareHTML}</td>
      </tr>`;
  });
  
  if (CURRENT_USER_ID && currentUserRank && !entries.some(e => e.user_id === CURRENT_USER_ID)) {
    const targetPage = Math.ceil(currentUserRank / 20);
    html += `<tr class="current-user-pinned me-row">
      <td colspan="5" style="text-align: center; padding: 12px;">
        <i class="bi bi-pin-angle-fill" style="color: var(--accent);" aria-hidden="true"></i> 
        You are ranked #${escapeHTML(currentUserRank)} in this category. 
        <a href="?page=${targetPage}" aria-label="Go to page ${targetPage} where your rank appears">Go to your rank →</a>
      </td>
    </tr>`;
  }
  
  body.innerHTML = html;
}

function renderPagination() {
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const pageInfo = document.getElementById('pageInfo');
  
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;
  pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
  
  prevBtn.setAttribute('aria-label', currentPage <= 1 ? 'Previous page (disabled)' : 'Go to previous page');
  nextBtn.setAttribute('aria-label', currentPage >= totalPages ? 'Next page (disabled)' : 'Go to next page');
}

function switchTab(mode) {
  activeMode = mode;
  currentPage = 1;
  
  document.querySelectorAll('.lb-tab').forEach(tab => {
    tab.classList.remove('active');
    tab.setAttribute('aria-selected', 'false');
  });
  const activeTab = document.querySelector(`.lb-tab[data-mode="${mode}"]`);
  activeTab.classList.add('active');
  activeTab.setAttribute('aria-selected', 'true');
  
  loadLeaderboard(1);
}

document.getElementById('prevBtn').addEventListener('click', () => {
  if (currentPage > 1) loadLeaderboard(currentPage - 1);
});

document.getElementById('nextBtn').addEventListener('click', () => {
  if (currentPage < totalPages) loadLeaderboard(currentPage + 1);
});

document.querySelectorAll('.lb-tab').forEach(tab => {
  tab.addEventListener('click', function() {
    switchTab(this.dataset.mode);
  });
});

loadLeaderboard(1);
})();
