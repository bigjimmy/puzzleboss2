<?php
require('puzzlebosslib.php');

$uid = getauthenticateduser();
$allowed = checkpriv("puzztech", $uid);

if (!$allowed) {
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Activity Log - Access Denied</title>
  <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="status-page">
<div class="status-header">
  <h1>ACCESS DENIED</h1>
</div>
<?= render_navbar() ?>
<p>Access to this page is restricted to users with the <strong>puzztech</strong> role. Contact puzzleboss or puzztech for assistance.</p>
</body>
</html>
<?php
  exit(2);
}
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Activity Log</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
  <style>
    body.status-page #app .activity-table table { width: 100%; }
    .activity-table th, .activity-table td { padding: 4px 8px; border-bottom: 1px solid var(--border-light); text-align: left; }
    .activity-table .col-time { white-space: nowrap; }
    .activity-table td.col-time { font-family: var(--font-mono); }
    .field-label { font-weight: bold; font-size: 0.85em; margin-bottom: 2px; }
    .filter-row { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; margin: 8px 0; }
    .filter-row > div { display: flex; flex-direction: column; gap: 2px; }
    .loading { opacity: 0.5; }
    .system-solver { color: var(--text-secondary); font-style: italic; }
    .help-table { width: 100%; border-collapse: collapse; }
    .help-table th, .help-table td { padding: 4px 8px; border-bottom: 1px solid var(--border-light); text-align: left; vertical-align: top; }
    .help-table th { white-space: nowrap; }
    .help-table code { font-family: var(--font-mono); font-size: 0.9em; }
    .help-table .type-legacy { color: var(--text-secondary); font-style: italic; }
  </style>
</head>
<body class="status-page">
<div id="app">
<div class="status-header">
  <h1>Activity Log</h1>
</div>

<?= render_navbar() ?>

<div class="info-box">
  <div class="info-box-header" @click="showHelp = !showHelp">
    <span class="collapse-icon" :class="{ collapsed: !showHelp }">▼</span>
    <h3>Help</h3>
  </div>
  <div class="info-box-content" v-show="showHelp">
    <p>The activity log tracks all actions across the hunt. Use the filters below to narrow results by type, source, solver, or puzzle. Results are ordered most-recent-first.</p>

    <div class="field-label" style="margin-top: 10px;">Activity Types</div>
    <table class="help-table">
      <thead>
        <tr><th>Type</th><th>Meaning</th><th>Example</th></tr>
      </thead>
      <tbody>
        <tr><td><code>create</code></td><td>Puzzle created</td><td>New puzzle added via bookmarklet or admin page</td></tr>
        <tr><td><code>revise</code></td><td>Sheet edited</td><td>Solver edits the puzzle's Google Sheet</td></tr>
        <tr><td><code>comment</code></td><td>Comment or tag changed</td><td>Puzzleboss updates a puzzle's note or tags</td></tr>
        <tr><td><code>solve</code></td><td>Puzzle solved</td><td>Correct answer submitted</td></tr>
        <tr><td><code>change</code></td><td>Puzzle field changed</td><td>Location, round, name, meta status, or sheet URL updated</td></tr>
        <tr><td><code>status</code></td><td>Puzzle status changed</td><td>Status set to "Needs eyes", "Being worked", etc.</td></tr>
        <tr><td><code>assignment</code></td><td>Solver assigned to puzzle</td><td>Solver joins or is assigned to a puzzle</td></tr>
        <tr><td><code>interact</code></td><td class="type-legacy">Legacy — undifferentiated activity</td><td class="type-legacy">Pre-existing rows from before the type taxonomy was refined</td></tr>
      </tbody>
    </table>

    <div class="field-label" style="margin-top: 10px;">Sources</div>
    <table class="help-table">
      <thead>
        <tr><th>Source</th><th>Meaning</th></tr>
      </thead>
      <tbody>
        <tr><td><code>puzzleboss</code></td><td>Action taken through the Puzzleboss web UI or REST API</td></tr>
        <tr><td><code>bigjimmybot</code></td><td>Automatic action by the BigJimmy polling bot (sheet edits, auto-assignments)</td></tr>
      </tbody>
    </table>

    <div class="field-label" style="margin-top: 10px;">Tips</div>
    <ul style="margin: 4px 0; padding-left: 20px;">
      <li>Solver <em>"system"</em> (ID 100) represents automated actions not tied to a specific person.</li>
      <li>Filters are preserved in the URL — bookmark or share a filtered view directly.</li>
      <li>Column visibility settings are saved in your browser's local storage.</li>
    </ul>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showFilters = !showFilters">
    <span class="collapse-icon" :class="{ collapsed: !showFilters }">▼</span>
    <h3>Search Filters</h3>
  </div>
  <div class="info-box-content" v-show="showFilters">
    <div class="field-label">Type</div>
    <div class="controls-section">
      <div class="filter" v-for="t in allTypes" :key="t" :class="{ active: selectedTypes.includes(t) }" @click="toggleType(t)">{{ t }} <input type="checkbox" :checked="selectedTypes.includes(t)" @click.stop /></div>
      <div class="filter-action-group"><div class="filter filter-action" @click="selectAllTypes">Select All</div><div class="filter filter-action" @click="selectNoTypes">Select None</div></div>
    </div>

    <div class="field-label" style="margin-top: 10px;">Source</div>
    <div class="controls-section">
      <div class="filter" v-for="s in allSources" :key="s" :class="{ active: selectedSources.includes(s) }" @click="toggleSource(s)">{{ s }} <input type="checkbox" :checked="selectedSources.includes(s)" @click.stop /></div>
      <div class="filter-action-group"><div class="filter filter-action" @click="selectAllSources">Select All</div><div class="filter filter-action" @click="selectNoSources">Select None</div></div>
    </div>

    <div class="filter-row" style="margin-top: 10px;">
      <div>
        <label class="field-label">Solver</label>
        <input type="text" list="solverlist" v-model="solverInput" @change="onSolverChange" placeholder="Type solver name...">
        <datalist id="solverlist">
          <option v-for="s in solvers" :key="s.id" :value="s.name">{{ s.name }}</option>
        </datalist>
      </div>
      <div>
        <label class="field-label">Puzzle</label>
        <input type="text" list="puzzlelist" v-model="puzzleInput" @change="onPuzzleChange" placeholder="Type puzzle name...">
        <datalist id="puzzlelist">
          <option v-for="p in puzzles" :key="p.id" :value="p.name">{{ p.name }}</option>
        </datalist>
      </div>
      <div>
        <label class="field-label">Rows</label>
        <select v-model="limit">
          <option value="50">50</option>
          <option value="100">100</option>
          <option value="200">200</option>
          <option value="500">500</option>
        </select>
      </div>
      <div>
        <button @click="fetchActivity" :disabled="isLoading">Search</button>
      </div>
    </div>
  </div>
</div>

<div class="info-box column-visibility">
  <div class="info-box-header" @click="showColumnVisibility = !showColumnVisibility">
    <span class="collapse-icon" :class="{ collapsed: !showColumnVisibility }">▼</span>
    <h3>Column Visibility</h3>
  </div>
  <div class="info-box-content" v-show="showColumnVisibility">
    <div class="controls-section">
      <div class="filter" :class="{ active: visibleColumns.time }" @click="visibleColumns.time = !visibleColumns.time">Time <input type="checkbox" :checked="visibleColumns.time" @click.stop /></div>
      <div class="filter" :class="{ active: visibleColumns.type }" @click="visibleColumns.type = !visibleColumns.type">Type <input type="checkbox" :checked="visibleColumns.type" @click.stop /></div>
      <div class="filter" :class="{ active: visibleColumns.source }" @click="visibleColumns.source = !visibleColumns.source">Source <input type="checkbox" :checked="visibleColumns.source" @click.stop /></div>
      <div class="filter" :class="{ active: visibleColumns.puzzle }" @click="visibleColumns.puzzle = !visibleColumns.puzzle">Puzzle <input type="checkbox" :checked="visibleColumns.puzzle" @click.stop /></div>
      <div class="filter" :class="{ active: visibleColumns.solver }" @click="visibleColumns.solver = !visibleColumns.solver">Solver <input type="checkbox" :checked="visibleColumns.solver" @click.stop /></div>
      <div class="filter-action-group"><div class="filter filter-action" @click="showAllColumns">Show All</div><div class="filter filter-action" @click="hideAllColumns">Hide All</div></div>
    </div>
  </div>
</div>

<div class="info-box activity-table" :class="{ loading: isLoading }">
  <p v-if="!hasSearched"><em>Use the filters above and click Search to view activity.</em></p>
  <p v-else-if="results.length === 0 && !isLoading"><em>No activity found matching your filters.</em></p>
  <table v-else-if="results.length > 0">
    <thead>
    <tr>
      <th class="col-time" :class="{ 'hidden-column': !visibleColumns.time }">Time</th>
      <th :class="{ 'hidden-column': !visibleColumns.type }">Type</th>
      <th :class="{ 'hidden-column': !visibleColumns.source }">Source</th>
      <th :class="{ 'hidden-column': !visibleColumns.puzzle }">Puzzle</th>
      <th :class="{ 'hidden-column': !visibleColumns.solver }">Solver</th>
    </tr>
    </thead>
    <tbody>
    <tr v-for="row in results" :key="row.id">
      <td class="col-time" :class="{ 'hidden-column': !visibleColumns.time }">{{ formatTime(row.time) }}</td>
      <td :class="{ 'hidden-column': !visibleColumns.type }">{{ row.type }}</td>
      <td :class="{ 'hidden-column': !visibleColumns.source }">{{ row.source }}</td>
      <td :class="{ 'hidden-column': !visibleColumns.puzzle }">{{ row.puzzle_name || '—' }}</td>
      <td :class="{ 'hidden-column': !visibleColumns.solver }">
        <span v-if="row.solver_id === 100" class="system-solver">system</span>
        <span v-else>{{ row.solver_name || ('ID:' + row.solver_id) }}</span>
      </td>
    </tr>
    </tbody>
  </table>
  <p v-if="results.length > 0">
    <small>{{ results.length }} result(s) returned.</small>
    <small v-if="hasMore" style="color: var(--text-secondary);"> More results exist — increase the row limit or narrow your filters.</small>
  </p>
</div>

</div>

<script>
const { createApp } = Vue;

createApp({
  data() {
    return {
      showHelp: false,
      showFilters: true,
      showColumnVisibility: false,
      allTypes: ['create', 'revise', 'comment', 'interact', 'solve', 'change', 'status', 'assignment'],
      allSources: ['puzzleboss', 'bigjimmybot'],
      selectedTypes: [],
      selectedSources: [],
      solverInput: '',
      puzzleInput: '',
      selectedSolverId: null,
      selectedPuzzleId: null,
      limit: '50',
      solvers: [],
      puzzles: [],
      results: [],
      hasMore: false,
      isLoading: false,
      hasSearched: false,
      visibleColumns: {
        time: true,
        type: true,
        source: true,
        puzzle: true,
        solver: true,
      },
    }
  },
  mounted() {
    this.loadColumnVisibility();
    if (this.hasUrlFilters()) {
      this.restoreFiltersFromUrl();
    } else {
      this.selectedTypes = [...this.allTypes];
      this.selectedSources = [...this.allSources];
    }
    // Load datalists; once both are ready, resolve names and auto-search
    Promise.all([this.loadSolvers(), this.loadPuzzles()]).then(() => {
      this.resolveNamesFromIds();
      this.fetchActivity();
    });
  },
  watch: {
    visibleColumns: {
      handler() { this.saveColumnVisibility(); },
      deep: true,
    },
  },
  methods: {
    loadSolvers() {
      return fetch('apicall.php?apicall=solvers')
        .then(r => r.json())
        .then(data => {
          if (data && data.solvers) {
            this.solvers = data.solvers;
          }
        })
        .catch(e => console.error('Failed to load solvers:', e));
    },
    loadPuzzles() {
      return fetch('apicall.php?apicall=all')
        .then(r => r.json())
        .then(data => {
          if (data && data.rounds) {
            const puzzles = [];
            data.rounds.forEach(round => {
              if (round.puzzles) {
                round.puzzles.forEach(p => puzzles.push({ id: p.id, name: p.name }));
              }
            });
            this.puzzles = puzzles;
          }
        })
        .catch(e => console.error('Failed to load puzzles:', e));
    },
    onSolverChange() {
      const match = this.solvers.find(s => s.name === this.solverInput);
      this.selectedSolverId = match ? match.id : null;
    },
    onPuzzleChange() {
      const match = this.puzzles.find(p => p.name === this.puzzleInput);
      this.selectedPuzzleId = match ? match.id : null;
    },
    fetchActivity() {
      this.isLoading = true;
      this.hasSearched = true;

      const params = new URLSearchParams();
      params.set('apicall', 'activitysearch');
      if (this.selectedTypes.length > 0) params.set('types', this.selectedTypes.join(','));
      if (this.selectedSources.length > 0) params.set('sources', this.selectedSources.join(','));
      if (this.selectedSolverId) params.set('solver_id', this.selectedSolverId);
      if (this.selectedPuzzleId) params.set('puzzle_id', this.selectedPuzzleId);
      params.set('limit', this.limit);

      this.syncFiltersToUrl();

      fetch('apicall.php?' + params.toString())
        .then(r => r.json())
        .then(data => {
          if (data && data.activity) {
            this.results = data.activity;
            this.hasMore = !!data.has_more;
          } else {
            this.results = [];
            this.hasMore = false;
          }
        })
        .catch(e => {
          console.error('Activity search failed:', e);
          this.results = [];
        })
        .finally(() => { this.isLoading = false; });
    },
    formatTime(isoStr) {
      if (!isoStr) return '—';
      const d = new Date(isoStr);
      const pad = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    },
    toggleType(t) {
      const idx = this.selectedTypes.indexOf(t);
      if (idx === -1) this.selectedTypes.push(t);
      else this.selectedTypes.splice(idx, 1);
    },
    selectAllTypes() { this.selectedTypes = [...this.allTypes]; },
    selectNoTypes() { this.selectedTypes = []; },
    toggleSource(s) {
      const idx = this.selectedSources.indexOf(s);
      if (idx === -1) this.selectedSources.push(s);
      else this.selectedSources.splice(idx, 1);
    },
    selectAllSources() { this.selectedSources = [...this.allSources]; },
    selectNoSources() { this.selectedSources = []; },
    showAllColumns() {
      Object.keys(this.visibleColumns).forEach(k => { this.visibleColumns[k] = true; });
    },
    hideAllColumns() {
      Object.keys(this.visibleColumns).forEach(k => { this.visibleColumns[k] = false; });
    },
    loadColumnVisibility() {
      try {
        const saved = localStorage.getItem('activityPageColumnVisibility');
        if (saved) Object.assign(this.visibleColumns, JSON.parse(saved));
      } catch (e) { console.error('Failed to load column visibility:', e); }
    },
    saveColumnVisibility() {
      try {
        localStorage.setItem('activityPageColumnVisibility', JSON.stringify(this.visibleColumns));
      } catch (e) { console.error('Failed to save column visibility:', e); }
    },
    restoreFiltersFromUrl() {
      const p = new URLSearchParams(window.location.search);
      if (p.has('types')) this.selectedTypes = p.get('types').split(',').filter(t => this.allTypes.includes(t));
      if (p.has('sources')) this.selectedSources = p.get('sources').split(',').filter(s => this.allSources.includes(s));
      if (p.has('solver_id')) this.selectedSolverId = parseInt(p.get('solver_id')) || null;
      if (p.has('puzzle_id')) this.selectedPuzzleId = parseInt(p.get('puzzle_id')) || null;
      if (p.has('limit') && ['50','100','200','500'].includes(p.get('limit'))) this.limit = p.get('limit');
    },
    syncFiltersToUrl() {
      const p = new URLSearchParams();
      // Preserve assumedid for dev/test mode
      const current = new URLSearchParams(window.location.search);
      if (current.has('assumedid')) p.set('assumedid', current.get('assumedid'));
      if (this.selectedTypes.length > 0) p.set('types', this.selectedTypes.join(','));
      if (this.selectedSources.length > 0) p.set('sources', this.selectedSources.join(','));
      if (this.selectedSolverId) p.set('solver_id', this.selectedSolverId);
      if (this.selectedPuzzleId) p.set('puzzle_id', this.selectedPuzzleId);
      if (this.limit !== '50') p.set('limit', this.limit);
      const qs = p.toString();
      const newUrl = window.location.pathname + (qs ? '?' + qs : '');
      history.replaceState(null, '', newUrl);
    },
    hasUrlFilters() {
      const p = new URLSearchParams(window.location.search);
      return p.has('types') || p.has('sources') || p.has('solver_id') || p.has('puzzle_id');
    },
    resolveNamesFromIds() {
      if (this.selectedSolverId) {
        const match = this.solvers.find(s => s.id === this.selectedSolverId);
        if (match) this.solverInput = match.name;
      }
      if (this.selectedPuzzleId) {
        const match = this.puzzles.find(p => p.id === this.selectedPuzzleId);
        if (match) this.puzzleInput = match.name;
      }
    },
  },
}).mount('#app');
</script>
</body>
</html>
