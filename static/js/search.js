(function() {
const endpointConfig = JSON.parse(document.getElementById('search-config').textContent);
const input = document.getElementById('searchInput');
const results = document.getElementById('results');
const meta = document.getElementById('searchMeta');
const clearBtn = document.getElementById('clearSearch');
const recentSearchesPanel = document.getElementById('recentSearches');
const recentSearchesList = document.getElementById('recentSearchesList');
const clearRecentSearchesBtn = document.getElementById('clearRecentSearches');
const chips = document.querySelectorAll('.platform-chip');
const filterTopic = document.getElementById('filterTopic');
const filterDifficulty = document.getElementById('filterDifficulty');
const filterPlatform = document.getElementById('filterPlatform');
const filterStatus = document.getElementById('filterStatus');
let activeToken = '';
let debounceTimer = null;
let controller = null;
const RECENT_SEARCHES_KEY = 'dsa_recent_searches_v1';
const MAX_RECENT_SEARCHES = 5;
const platformLabels = {
  leetcode: 'LeetCode',
  gfg: 'GFG',
  cn: 'Coding Ninjas',
  hackerrank: 'HackerRank'
};

function getFilters() {
  return {
    topic_id: filterTopic ? filterTopic.value : '',
    difficulty: filterDifficulty ? filterDifficulty.value : '',
    platform: filterPlatform ? filterPlatform.value : '',
    status: filterStatus ? filterStatus.value : ''
  };
}

function hasActiveFilters() {
  return Object.values(getFilters()).some(Boolean);
}

function setFilterActiveStates() {
  [filterTopic, filterDifficulty, filterPlatform, filterStatus].forEach(filter => {
    if (filter) filter.classList.toggle('active', !!filter.value);
  });
}

function restoreStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('q')) input.value = params.get('q');
  if (filterTopic && params.get('topic_id')) filterTopic.value = params.get('topic_id');
  if (filterDifficulty && params.get('difficulty')) filterDifficulty.value = params.get('difficulty');
  if (filterPlatform && params.get('platform')) filterPlatform.value = params.get('platform');
  if (filterStatus && params.get('status')) filterStatus.value = params.get('status');
  setFilterActiveStates();
}

function buildSearchParams(query) {
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  const filters = getFilters();
  if (filters.topic_id) params.set('topic_id', filters.topic_id);
  if (filters.difficulty) params.set('difficulty', filters.difficulty);
  if (filters.platform) params.set('platform', filters.platform);
  if (filters.status) params.set('status', filters.status);
  return params;
}

function updateUrl(query) {
  const params = buildSearchParams(query);
  const nextUrl = params.toString() ? `?${params}` : window.location.pathname;
  history.replaceState(null, '', nextUrl);
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function badgeClass(color) {
  if (color === 'lc') return 'badge-lc';
  if (color === 'gfg') return 'badge-gfg';
  if (color === 'cn') return 'badge-cn';
  if (color === 'hr') return 'badge-hr';
  return 'badge-link';
}

function currentQuery() {
  const text = input.value.trim();
  return [activeToken, text].filter(Boolean).join(' ');
}

function normalizeRecentSearchText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function loadRecentSearches() {
  try {
    const parsed = JSON.parse(localStorage.getItem(RECENT_SEARCHES_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.filter(item => item && typeof item === 'object') : [];
  } catch (err) {
    return [];
  }
}

function saveRecentSearches(entries) {
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(entries));
  } catch (err) {
    // Ignore storage quota/privacy mode failures and keep the search UI usable.
  }
}

function renderRecentSearches() {
  const recentSearches = loadRecentSearches();
  recentSearchesPanel.hidden = recentSearches.length === 0;
  clearRecentSearchesBtn.hidden = recentSearches.length === 0;

  if (!recentSearches.length) {
    recentSearchesList.innerHTML = '';
    return;
  }

  recentSearchesList.innerHTML = recentSearches.map((entry, index) => {
    const tokenLabel = platformLabels[entry.token] || '';
    const label = tokenLabel && entry.text ? `${tokenLabel}: ${entry.text}` : (entry.text || tokenLabel);
    return `
      <button class="recent-search-chip" type="button" data-index="${index}" role="listitem" aria-label="Repeat recent search ${escapeHtml(label)}">
        <i class="bi bi-clock-history" aria-hidden="true"></i>
        <span class="recent-search-chip-text">${escapeHtml(label)}</span>
      </button>
    `;
  }).join('');
}

function rememberRecentSearch(text, token) {
  const normalizedText = normalizeRecentSearchText(text);
  if (!normalizedText) return;

  const recentSearches = loadRecentSearches();
  const nextEntry = { text: normalizedText, token: token || '' };
  const filtered = recentSearches.filter(entry =>
    !(entry && entry.text && entry.token === nextEntry.token && entry.text.toLowerCase() === normalizedText.toLowerCase())
  );

  filtered.unshift(nextEntry);
  saveRecentSearches(filtered.slice(0, MAX_RECENT_SEARCHES));
  renderRecentSearches();
}

function applyRecentSearch(index) {
  const recentSearches = loadRecentSearches();
  const entry = recentSearches[index];
  if (!entry) return;

  input.value = entry.text || '';
  setActiveChip(entry.token || '');
  input.focus();
  runSearch();
}

function setActiveChip(token) {
  activeToken = token;
  chips.forEach(chip => {
    const isActive = chip.dataset.token === token;
    chip.classList.toggle('active', isActive);
    chip.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
}

function renderEmpty(icon, text) {
  results.innerHTML = `<div class="empty-search" role="status"><i class="bi ${icon}" aria-hidden="true"></i><p>${escapeHtml(text)}</p></div>`;
}

function renderPlatformPrompt() {
  const platform = platformLabels[activeToken] || 'selected platform';
  meta.textContent = `${platform} filter selected`;
  renderEmpty('bi-search-heart', `Type a search term to find ${platform} practice links.`);
}

function renderResults(payload) {
  const count = payload.results.length;
  const platforms = payload.requested_platforms || [];
  meta.textContent = count ? `${count} result${count === 1 ? '' : 's'}${platforms.length ? ' with ' + platforms.join(', ') : ''}` : '';

  if (!input.value.trim() && !hasActiveFilters()) {
    if (activeToken) {
      renderPlatformPrompt();
      return;
    }

    meta.textContent = '';
    renderEmpty('bi-search', 'Start typing to search the DSA sheet.');
    return;
  }

  if (!count) {
    const external = (payload.external_searches || []).map(link =>
      `<a class="q-badge ${badgeClass(link.color)}" href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer" aria-label="Search ${escapeHtml(link.platform)} for your query (opens new tab)">
        <i class="bi bi-box-arrow-up-right" aria-hidden="true"></i>${escapeHtml(link.platform)}
      </a>`
    ).join('');
    results.innerHTML = `<div class="empty-search"><i class="bi bi-search-heart" aria-hidden="true"></i><p>No sheet match found.</p><div class="link-row" style="justify-content:center">${external}</div></div>`;
    return;
  }

  results.innerHTML = payload.results.map(item => {
    const directLinks = (item.links || []).map(link =>
      `<a class="q-badge ${badgeClass(link.color)}" href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer" aria-label="View on ${escapeHtml(link.platform)} (opens new tab)">
        <i class="bi bi-box-arrow-up-right" aria-hidden="true"></i>${escapeHtml(link.platform)}
      </a>`
    ).join('');
    const editorialLinks = (item.editorial_links || []).map(link =>
      `<a class="q-badge badge-link" href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer" aria-label="Read ${escapeHtml(link.label)} (opens new tab)">
        <i class="bi bi-journal-text" aria-hidden="true"></i>${escapeHtml(link.label)}
      </a>`
    ).join('');
    const platformSearches = (item.external_searches || []).map(link =>
      `<a class="q-badge ${badgeClass(link.color)}" href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer" aria-label="Search ${escapeHtml(link.platform)} for this problem (opens new tab)">
        <i class="bi bi-search" aria-hidden="true"></i>${escapeHtml(link.platform)}
      </a>`
    ).join('');
    const topicUrl = `/topic/${encodeURIComponent(item.topic_id)}`;

    return `
      <article class="result-card" role="listitem">
        <div>
          <a href="${topicUrl}" class="result-topic" aria-label="Go to ${escapeHtml(item.topic)} topic page">${escapeHtml(item.topic)}</a>
          <div class="result-name">${escapeHtml(item.problem)}</div>
          <div class="link-row">${directLinks}${editorialLinks}${platformSearches}</div>
        </div>
        <div class="result-actions">
          <a class="topic-open" href="${topicUrl}" title="Open topic" aria-label="Go to ${escapeHtml(item.topic)} topic">
            <i class="bi bi-arrow-right" aria-hidden="true"></i>
          </a>
        </div>
      </article>`;
  }).join('');
}

async function runSearch() {
  const query = currentQuery();
  if (controller) controller.abort();

  if (!input.value.trim() && !hasActiveFilters()) {
    if (activeToken) {
      renderPlatformPrompt();
      return;
    }

    meta.textContent = '';
    renderEmpty('bi-search', 'Start typing to search the DSA sheet.');
    return;
  }

  updateUrl(query);
  controller = new AbortController();
  meta.textContent = 'Searching...';
  meta.setAttribute('aria-busy', 'true');

  try {
    const params = buildSearchParams(query);
    const res = await fetch(`${endpointConfig.searchQuestions}?${params}`, { signal: controller.signal });
    renderResults(await res.json());
    rememberRecentSearch(input.value, activeToken);
    meta.setAttribute('aria-busy', 'false');
  } catch (err) {
    if (err.name !== 'AbortError') {
      meta.textContent = '';
      meta.setAttribute('aria-busy', 'false');
      renderEmpty('bi-wifi-off', 'Search failed. Please try again.');
    }
  }
}

function scheduleSearch() {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(runSearch, 180);
}

input.addEventListener('input', scheduleSearch);
clearBtn.addEventListener('click', () => {
  input.value = '';
  input.focus();
  scheduleSearch();
});
recentSearchesList.addEventListener('click', (event) => {
  const chip = event.target.closest('.recent-search-chip');
  if (!chip) return;
  applyRecentSearch(Number(chip.dataset.index));
});
clearRecentSearchesBtn.addEventListener('click', () => {
  saveRecentSearches([]);
  renderRecentSearches();
});
chips.forEach(chip => {
  chip.addEventListener('click', () => {
    setActiveChip(chip.dataset.token);
    runSearch();
  });
  chip.setAttribute('aria-pressed', 'false');
});
[filterTopic, filterDifficulty, filterPlatform, filterStatus].forEach(filter => {
  if (!filter) return;
  filter.addEventListener('change', () => {
    setFilterActiveStates();
    runSearch();
  });
});

restoreStateFromUrl();
setActiveChip('');
renderRecentSearches();
runSearch();
})();
