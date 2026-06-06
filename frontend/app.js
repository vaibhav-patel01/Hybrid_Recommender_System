const API_BASE = 'http://127.0.0.1:8000';

// ── DOM Elements ──────────────────────────────────────────
const views = {
    home: document.getElementById('home-view'),
    details: document.getElementById('details-view'),
    recommendations: document.getElementById('recommendations-view')
};
const grids = {
    anime: document.getElementById('anime-grid'),
    manhwa: document.getElementById('manhwa-grid'),
    similar: document.getElementById('similar-grid'),
    recs: document.getElementById('rec-grid')
};

// Nav search (shown on details & recs view)
const navSearch    = document.getElementById('nav-search');
const searchInput  = document.getElementById('search-input');
const searchDropdown = document.getElementById('search-dropdown');
const navLimit = document.getElementById('nav-limit');

// Hero search (shown on home view)
const heroSearchInput    = document.getElementById('hero-search-input');
const heroSearchDropdown = document.getElementById('hero-search-dropdown');
const heroLimit = document.getElementById('hero-limit');

// Sync the two limit dropdowns so they always match
navLimit.addEventListener('change', (e) => heroLimit.value = e.target.value);
heroLimit.addEventListener('change', (e) => navLimit.value = e.target.value);

// ── Navigation ────────────────────────────────────────────
function goHome(pushHistory = true) {
    views.details.classList.add('hidden');
    views.recommendations.classList.add('hidden');
    views.home.classList.remove('hidden');

    navSearch.classList.add('hidden-search');
    heroSearchInput.value = '';
    searchInput.value = '';
    closeAllDropdowns();
    window.scrollTo(0, 0);

    if (pushHistory) window.history.pushState({ view: 'home' }, '', window.location.pathname);
}

function showDetailsView(id, pushHistory = true) {
    views.home.classList.add('hidden');
    views.recommendations.classList.add('hidden');
    views.details.classList.remove('hidden');

    navSearch.classList.remove('hidden-search');
    closeAllDropdowns();
    window.scrollTo(0, 0);

    if (pushHistory) window.history.pushState({ view: 'details', id: id }, '', `?id=${id}`);
}

function showRecommendationsView(id, title, pushHistory = true) {
    views.home.classList.add('hidden');
    views.details.classList.add('hidden');
    views.recommendations.classList.remove('hidden');

    navSearch.classList.remove('hidden-search');
    closeAllDropdowns();
    window.scrollTo(0, 0);

    if (pushHistory) window.history.pushState({ view: 'recommendations', id, title }, '', `?rec=${id}`);
}

function closeAllDropdowns() {
    searchDropdown.classList.add('hidden');
    heroSearchDropdown.classList.add('hidden');
}

// ── Home Data ─────────────────────────────────────────────
async function loadHome() {
    try {
        const res  = await fetch(`${API_BASE}/`);
        const data = await res.json();
        grids.anime.innerHTML   = data.animes.map(createCardHTML).join('');
        grids.manhwa.innerHTML  = data.manhwa.map(createCardHTML).join('');
    } catch (err) {
        console.error('Failed to load home data:', err);
    }
}

// ── Card HTML ─────────────────────────────────────────────
function createCardHTML(item) {
    return `
        <div class="card" onclick="loadDetails(${item.id})">
            <img src="${item.coverImage}" alt="${item.title}" loading="lazy">
            <div class="card-title">${item.title}</div>
        </div>`;
}

// ── Search Logic ──────────────────────────────────────────
function makeSearchHandler(inputEl, dropdownEl) {
    let timer;
    inputEl.addEventListener('input', (e) => {
        const q = e.target.value.trim();
        clearTimeout(timer);
        if (q.length < 2) { dropdownEl.classList.add('hidden'); return; }
        timer = setTimeout(() => doSearch(q, inputEl, dropdownEl), 300);
    });
}

async function doSearch(q, inputEl, dropdownEl) {
    try {
        const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        const results = data.search_result;
        dropdownEl.innerHTML = '';

        if (!results || Object.keys(results).length === 0) {
            dropdownEl.innerHTML = '<div class="search-item" style="color:#666;cursor:default">No results found</div>';
        } else {
            for (const [title, id] of Object.entries(results)) {
                const div = document.createElement('div');
                div.className = 'search-item';
                div.textContent = title;
                div.onclick = () => {
                    inputEl.value = title;
                    closeAllDropdowns();
                    // Route directly to the recommendations grid
                    loadRecommendations(id, title);
                };
                dropdownEl.appendChild(div);
            }
        }
        dropdownEl.classList.remove('hidden');
    } catch (err) {
        console.error('Search failed:', err);
    }
}

// Close dropdowns when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) closeAllDropdowns();
});

// Wire up both search inputs
makeSearchHandler(searchInput, searchDropdown);
makeSearchHandler(heroSearchInput, heroSearchDropdown);

// ── Recommendations (Search Results) ──────────────────────
async function loadRecommendations(id, title, pushHistory = true) {
    showRecommendationsView(id, title, pushHistory);

    document.getElementById('rec-target-title').textContent = title;
    grids.recs.innerHTML = '<p style="color:#666; grid-column: 1/-1; text-align: center; padding: 2rem 0;">Processing vector space matches...</p>';

    // Grab the limit requested by the user
    const limit = navLimit.value;

    try {
        const res = await fetch(`${API_BASE}/recommend/${id}?limit=${limit}`);
        const data = await res.json();

        const results = data.recommendations || data.similar || data;

        if (results && results.length > 0) {
            grids.recs.innerHTML = results.map(createCardHTML).join('');
        } else {
            grids.recs.innerHTML = '<p style="color:#666; grid-column: 1/-1; text-align: center; padding: 2rem 0;">No recommendations found for this title.</p>';
        }
    } catch (err) {
        console.error('Failed to load recommendations:', err);
        grids.recs.innerHTML = '<p style="color:#ef4444; grid-column: 1/-1; text-align: center; padding: 2rem 0;">Error fetching recommendations.</p>';
    }
}

// ── Details ───────────────────────────────────────────────
async function loadDetails(id, pushHistory = true) {
    showDetailsView(id, pushHistory);

    document.getElementById('detail-title').textContent = 'Loading...';
    document.getElementById('detail-description').textContent = 'Fetching data...';
    grids.similar.innerHTML = '';

    try {
        const res  = await fetch(`${API_BASE}/info/${id}`);
        const data = await res.json();

        if (data.detail && data.detail.length > 0) {
            const info = data.detail[0];

            document.getElementById('detail-title').textContent       = info.title;
            document.getElementById('detail-description').innerHTML   = info.description || 'No description available.';
            document.getElementById('detail-cover').src               = info.coverImage;

            const banner = document.getElementById('details-banner');
            banner.style.backgroundImage = (info.bannerImage && !info.bannerImage.includes('unavailable'))
                ? `url('${info.bannerImage}')` : `url('${info.coverImage}')`;

            // 1. Expanded Meta Tags
            const adultBadge = info.isAdult ? `<span class="meta-tag adult-badge">18+ Explicit</span>` : '';

            let mediaTags = `<span class="meta-tag">${info.type || 'UNKNOWN'}</span>`;
            if (info.format && info.format !== info.type) {
                mediaTags += `<span class="meta-tag">${info.format}</span>`;
            }

            let lengthTag = '';
            if (info.type === 'ANIME') {
                if (info.episodes && info.episodes > 0) {
                    lengthTag = `<span class="meta-tag">${info.episodes} EPS</span>`;
                }
            } else {
                let readParts = [];
                if (info.chapters && info.chapters > 0) readParts.push(`${info.chapters} CH`);
                if (info.volumes && info.volumes > 0) readParts.push(`${info.volumes} VOL`);
                if (readParts.length > 0) {
                    lengthTag = `<span class="meta-tag">${readParts.join(' • ')}</span>`;
                }
            }

            const scoreText = info.averageScore ? `⭐${Number(info.averageScore).toFixed(1)}/100` : 'No Rating';
            const statsText = info.stats ? `<span class="stats-text">(Rated by ${info.stats.toLocaleString()} users)</span>` : '';

            document.getElementById('detail-meta').innerHTML = `
                ${adultBadge}
                ${mediaTags}
                ${lengthTag}
                <span class="meta-tag">${info.status || 'UNKNOWN'}</span>
                ${info.seasonYear ? `<span class="meta-tag">${info.seasonYear}</span>` : ''}
                <span class="meta-tag score-tag">${scoreText}</span>
                ${statsText}
            `;

            // 2. Extra Info: Studios and Trailer
            const studioList = (info.studios && info.studios.length > 0)
                ? info.studios.slice(0, 2).join(', ')
                : 'Unknown Studio';

            const trailerHtml = (info.trailer && info.trailer !== 'trailer unavailable')
                ? `<a href="${info.trailer}" target="_blank" class="trailer-link">Watch Trailer ↗</a>`
                : `<span class="no-trailer">No Trailer</span>`;

            document.getElementById('detail-extra').innerHTML = `
                <span class="studio-text">🎬 <strong>Studio:</strong> ${studioList}</span>
                <span class="trailer-divider">|</span>
                ${trailerHtml}
            `;

            // 3. Genres
            let genres = [];
            if (info.genres && info.genres.includes('[')) {
                genres = info.genres.replace(/[\[\]']/g, '').split(',').map(s => s.trim());
            } else if (info.genres) {
                genres = [info.genres];
            }
            document.getElementById('detail-genres').innerHTML =
                genres.map(g => `<span class="genre-badge">${g}</span>`).join('');

            // 4. Deep Tags (Limit to top 12)
            if (info.tags && Array.isArray(info.tags)) {
                document.getElementById('detail-tags').innerHTML = info.tags
                    .slice(0, 12)
                    .map(t => `<span class="tag-badge">#${t.toLowerCase()}</span>`)
                    .join('');
            } else {
                document.getElementById('detail-tags').innerHTML = '';
            }
        }

        grids.similar.innerHTML = (data.similar && data.similar.length > 0)
            ? data.similar.map(createCardHTML).join('')
            : '<p style="color:#666">No recommendations found.</p>';

    } catch (err) {
        console.error('Failed to load details:', err);
        document.getElementById('detail-title').textContent = 'Error Loading Details';
        document.getElementById('detail-description').textContent = 'Check if your backend server is running.';
    }
}

// ── Back / Forward Routing ────────────────────────────────
window.addEventListener('popstate', (e) => {
    const state = e.state;
    if (!state || state.view === 'home') goHome(false);
    else if (state.view === 'details' && state.id) loadDetails(state.id, false);
    else if (state.view === 'recommendations' && state.id) loadRecommendations(state.id, state.title, false);
});

// ── Boot ──────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    window.history.replaceState({ view: 'home' }, '', window.location.pathname);
    navSearch.classList.add('hidden-search');
    loadHome();
});