<!DOCTYPE html>
<html>
<head>
    <title>Hunt Status Overview</title>
    <link rel="stylesheet" href="./pb-ui.css">
<style>
  body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #e8e8e8;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        
        h1, h2, h3 {
            color: #00d9ff;
            text-shadow: 0 0 10px rgba(0, 217, 255, 0.3);
        }
        
        .status-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .status-header h1 {
            margin: 0;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stats-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(0, 217, 255, 0.2);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        
        .stats-card h3 {
            margin-top: 0;
            border-bottom: 1px solid rgba(0, 217, 255, 0.3);
            padding-bottom: 10px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            overflow: hidden;
        }
        
        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        th {
            background: rgba(0, 217, 255, 0.15);
            color: #00d9ff;
            font-weight: 600;
        }
        
        tr:hover {
            background: rgba(0, 217, 255, 0.05);
        }
        
        .puzzle-table {
            margin-bottom: 30px;
        }
        
        .puzzle-table table {
            font-size: 0.9em;
        }
        
        a {
            color: #00d9ff;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
            color: #5ce1ff;
        }
        
        .meta-row {
            background: rgba(128, 128, 128, 0.2) !important;
        }
        
        .new-row {
            background: rgba(0, 255, 200, 0.15) !important;
        }
        
        .critical-row {
            background: rgba(255, 50, 100, 0.25) !important;
        }
        
        select, input[type="text"] {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(0, 217, 255, 0.3);
            color: #e8e8e8;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 0.85em;
        }
        
        select:focus, input[type="text"]:focus {
            outline: none;
            border-color: #00d9ff;
            box-shadow: 0 0 5px rgba(0, 217, 255, 0.3);
        }
        
        button, input[type="submit"] {
            background: linear-gradient(135deg, #00d9ff 0%, #0099cc 100%);
            border: none;
            color: #1a1a2e;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.85em;
            transition: all 0.2s;
        }
        
        button:hover, input[type="submit"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 217, 255, 0.3);
        }
        
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }
        
        .section-header h2 {
            margin: 0;
        }
        
        .badge {
            background: rgba(0, 217, 255, 0.2);
            color: #00d9ff;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
        }
        
        footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            text-align: center;
            color: #888;
        }
        
        .inline-form {
            display: inline-flex;
            gap: 5px;
            align-items: center;
        }
        
        .solver-col {
            max-width: 120px;
            white-space: normal;
            word-break: break-word;
            font-size: 0.85em;
        }
        
        .tags-col {
            max-width: 150px;
            white-space: normal;
            word-break: break-word;
            font-size: 0.85em;
        }
        
        .saving {
            opacity: 0.6;
            pointer-events: none;
        }
        
        .flash {
            animation: flash-green 0.5s ease-out;
        }
        
        @keyframes flash-green {
            0% { background: rgba(0, 255, 100, 0.4); }
            100% { background: transparent; }
        }
        
        .nav-links {
            margin-bottom: 20px;
        }
        
        .nav-links a {
            margin-right: 15px;
            padding: 8px 16px;
            background: rgba(0, 217, 255, 0.1);
            border-radius: 6px;
            transition: all 0.2s;
        }
        
        .nav-links a:hover {
            background: rgba(0, 217, 255, 0.2);
            text-decoration: none;
        }

        .collapsible-header {
            cursor: pointer;
            user-select: none;
        }
        
        .collapsible-header:hover {
            opacity: 0.8;
        }
        
        .collapse-icon {
            display: inline-block;
            transition: transform 0.2s;
            margin-right: 8px;
        }
        
        .collapse-icon.collapsed {
            transform: rotate(-90deg);
        }
    </style>
</head>
<body>
    <div id="app">
        <div class="status-header">
            <h1>Hunt Status Overview</h1>
            <div :class="updateState"></div>
        </div>
        
        <div class="nav-links">
            <a href="./index.php">Main Dashboard</a>
            <a href="./pbtools.php" target="_blank">PB Tools</a>
            <a href="../" target="_blank">Wiki</a>
        </div>

        <div class="stats-grid">
            <div class="stats-card">
                <h3>Hunt Progress</h3>
                <table>
                    <tr>
                        <th></th>
                        <th>Opened</th>
                        <th>Solved</th>
                        <th>Unsolved</th>
                    </tr>
                    <tr>
                        <th>Rounds</th>
                        <td>{{ stats.totalRounds }}</td>
                        <td>{{ stats.solvedRounds }}</td>
                        <td>{{ stats.totalRounds - stats.solvedRounds }}</td>
                    </tr>
                    <tr>
                        <th>Puzzles</th>
                        <td>{{ stats.totalPuzzles }}</td>
                        <td>{{ stats.solvedPuzzles }}</td>
                        <td>{{ stats.totalPuzzles - stats.solvedPuzzles }}</td>
                    </tr>
                </table>
            </div>
            
            <div class="stats-card">
                <h3>Status Breakdown</h3>
                <table>
                    <tr>
                        <th>Status</th>
                        <th>Count</th>
                    </tr>
                    <tr v-for="status in displayStatuses" :key="status">
                        <td>{{ status }}</td>
                        <td>{{ statusCounts[status] || 0 }}</td>
                    </tr>
                </table>
            </div>
        </div>

        <div class="puzzle-table">
            <div class="section-header collapsible-header" @click="showNoLoc = !showNoLoc">
                <h2>
                    <span class="collapse-icon" :class="{ collapsed: !showNoLoc }">▼</span>
                    Unsolved Puzzles Missing Location
                </h2>
                <span class="badge">{{ noLocPuzzles.length }} puzzles</span>
            </div>
            <table v-show="showNoLoc">
                <tr>
                    <th>Status</th>
                    <th>Meta</th>
                    <th>Name</th>
                    <th>Doc</th>
                    <th>Chat</th>
                    <th>Sheet</th>
                    <th>Solvers (current)</th>
                    <th>Solvers (all time)</th>
                    <th>Tags</th>
                    <th>Comment</th>
                    <th></th>
                </tr>
                <tr v-for="puzzle in noLocPuzzles" 
                    :key="puzzle.id" 
                    :class="getPuzzleRowClass(puzzle)"
                    :id="'puzzle-' + puzzle.id">
                    <td>
                        <a :href="'editpuzzle.php?pid=' + puzzle.id" target="_blank">
                            {{ puzzle.status }}
                        </a>
                    </td>
                    <td>{{ puzzle.ismeta ? '✓' : '' }}</td>
                    <td><a :href="puzzle.puzzle_uri" target="_blank">{{ puzzle.name }}</a></td>
                    <td><a :href="puzzle.drive_uri" target="_blank">Doc</a></td>
                    <td><a :href="puzzle.chat_channel_link" target="_blank">Chat</a></td>
                    <td>{{ puzzle.sheetcount || 0 }}</td>
                    <td class="solver-col">{{ puzzle.cursolvers }}</td>
                    <td class="solver-col">{{ puzzle.solvers }}</td>
                    <td class="tags-col">{{ formatTags(puzzle.tags) }}</td>
                    <td class="inline-form">
                        <input type="text" 
                               v-model="commentEdits[puzzle.id]" 
                               :placeholder="puzzle.comments || ''"
                               @keyup.enter="updateComment(puzzle.id)">
                        <button @click="updateComment(puzzle.id)" :disabled="saving[puzzle.id]">
                            {{ saving[puzzle.id] ? '...' : 'Save' }}
                        </button>
                    </td>
                    <td></td>
                </tr>
            </table>
        </div>

        <div class="puzzle-table">
            <div class="section-header collapsible-header" @click="showSheetDisabled = !showSheetDisabled">
                <h2>
                    <span class="collapse-icon" :class="{ collapsed: !showSheetDisabled }">▼</span>
                    Puzzles Without Sheet Tracking Enabled
                </h2>
                <span class="badge">{{ sheetDisabledPuzzles.length }} puzzles</span>
            </div>
            <table v-show="showSheetDisabled">
                <tr>
                    <th>Round</th>
                    <th>Name</th>
                    <th>Sheet Link</th>
                </tr>
                <tr v-for="puzzle in sheetDisabledPuzzles" :key="puzzle.id">
                    <td>{{ getRoundName(puzzle.id) }}</td>
                    <td><a :href="puzzle.puzzle_uri" target="_blank">{{ puzzle.name }}</a></td>
                    <td><a :href="puzzle.drive_uri" target="_blank">Open Sheet</a></td>
                </tr>
            </table>
        </div>

        <div class="puzzle-table">
            <div class="section-header collapsible-header" @click="showOverview = !showOverview">
                <h2>
                    <span class="collapse-icon" :class="{ collapsed: !showOverview }">▼</span>
                    Total Hunt Overview
                </h2>
                <span class="badge">{{ workOnPuzzles.length }} puzzles</span>
            </div>
            <table v-show="showOverview">
                <tr>
                    <th>Status</th>
                    <th>Round</th>
                    <th>Meta</th>
                    <th>Name</th>
                    <th>Doc</th>
                    <th>Chat</th>
                    <th>Sheet</th>
                    <th>Solvers (current)</th>
                    <th>Solvers (all time)</th>
                    <th>Tags</th>
                    <th>Location</th>
                    <th>Comment</th>
                    <th></th>
                </tr>
                <tr v-for="puzzle in workOnPuzzles" 
                    :key="puzzle.id"
                    :class="getPuzzleRowClass(puzzle)"
                    :id="'puzzle-overview-' + puzzle.id">
                    <td class="inline-form">
                        <select v-model="statusEdits[puzzle.id]" @change="updateStatus(puzzle.id)">
                            <option v-for="status in selectableStatuses" :key="status" :value="status">
                                {{ status }}
                            </option>
                        </select>
                    </td>
                    <td>{{ getRoundName(puzzle.id) }}</td>
                    <td>{{ puzzle.ismeta ? '✓' : '' }}</td>
                    <td><a :href="puzzle.puzzle_uri" target="_blank">{{ puzzle.name }}</a></td>
                    <td><a :href="puzzle.drive_uri" target="_blank">Doc</a></td>
                    <td><a :href="puzzle.chat_channel_link" target="_blank">Chat</a></td>
                    <td>{{ puzzle.sheetcount || 0 }}</td>
                    <td class="solver-col">{{ puzzle.cursolvers }}</td>
                    <td class="solver-col">{{ puzzle.solvers }}</td>
                    <td class="tags-col">{{ formatTags(puzzle.tags) }}</td>
                    <td>{{ puzzle.xyzloc }}</td>
                    <td class="inline-form">
                        <input type="text" 
                               v-model="commentEdits[puzzle.id]" 
                               :placeholder="puzzle.comments || ''"
                               @keyup.enter="updateComment(puzzle.id)">
                        <button @click="updateComment(puzzle.id)" :disabled="saving[puzzle.id]">
                            {{ saving[puzzle.id] ? '...' : 'Save' }}
                        </button>
                    </td>
                    <td></td>
                </tr>
            </table>
        </div>
        
        <footer>
            <a href="index.php">Puzzleboss Home</a> | 
            Last updated: {{ lastUpdate }}
        </footer>
    </div>

    <script type="module">
        import { createApp, ref, computed, onMounted, watch } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
        import Consts from './consts.js'

        <?php
            require('puzzlebosslib.php');
            $uid = getauthenticateduser();
            echo "const currentUid = " . json_encode($uid) . ";";
        ?>

        createApp({
            setup() {
                const data = ref({ rounds: [] })
                const statuses = ref([])
                const updateState = ref('circle stale')
                const lastUpdate = ref('')
                const staleTimer = ref(null)
                
                const showNoLoc = ref(true)
                const showSheetDisabled = ref(true)
                const showOverview = ref(true)
                
                const commentEdits = ref({})
                const statusEdits = ref({})
                const saving = ref({})
                
                // Statuses excluded from count table
                const excludedFromCount = ['[hidden]', 'Solved']
                // Statuses excluded from work-on list
                const excludedFromWorkOn = ['[hidden]', 'Unnecessary', 'Solved']
                // Statuses excluded from dropdown
                const excludedFromDropdown = ['Solved', '[hidden]']
                
                const stats = computed(() => {
                    let totalRounds = 0
                    let solvedRounds = 0
                    let totalPuzzles = 0
                    let solvedPuzzles = 0
                    
                    data.value.rounds.forEach(round => {
                        totalRounds++
                        let roundMetas = 0
                        let roundMetasSolved = 0
                        
                        round.puzzles.forEach(puzzle => {
                            if (puzzle.status === '[hidden]') return
                            totalPuzzles++
                            if (puzzle.status === 'Solved') {
                                solvedPuzzles++
                                if (puzzle.ismeta) roundMetasSolved++
                            }
                            if (puzzle.ismeta) roundMetas++
                        })
                        
                        if (roundMetas > 0 && roundMetas === roundMetasSolved) {
                            solvedRounds++
                        }
                    })
                    
                    return { totalRounds, solvedRounds, totalPuzzles, solvedPuzzles }
                })
                
                const statusCounts = computed(() => {
                    const counts = {}
                    data.value.rounds.forEach(round => {
                        round.puzzles.forEach(puzzle => {
                            if (puzzle.status === '[hidden]') return
                            counts[puzzle.status] = (counts[puzzle.status] || 0) + 1
                        })
                    })
                    return counts
                })
                
                const displayStatuses = computed(() => {
                    return statuses.value.filter(s => !excludedFromCount.includes(s))
                })
                
                const selectableStatuses = computed(() => {
                    return statuses.value.filter(s => !excludedFromDropdown.includes(s))
                })
                
                const allPuzzles = computed(() => {
                    const puzzles = []
                    data.value.rounds.forEach(round => {
                        round.puzzles.forEach(puzzle => {
                            if (puzzle.status !== '[hidden]') {
                                puzzles.push({ ...puzzle, roundName: round.name })
                            }
                        })
                    })
                    return puzzles
                })
                
                const noLocPuzzles = computed(() => {
                    return allPuzzles.value.filter(p => 
                        !p.xyzloc && p.status !== 'Solved'
                    )
                })
                
                const workOnPuzzles = computed(() => {
                    return allPuzzles.value.filter(p =>
                        !excludedFromWorkOn.includes(p.status)
                    )
                })

                const sheetDisabledPuzzles = computed(() => {
                    return allPuzzles.value.filter(p =>
                        (p.sheetenabled === 0 || p.sheetenabled === false) &&
                        p.status !== 'Solved'
                    )
                })
                
                function getRoundName(puzzleId) {
                    for (const round of data.value.rounds) {
                        for (const puzzle of round.puzzles) {
                            if (puzzle.id === puzzleId) return round.name
                        }
                    }
                    return ''
                }
                
                function getPuzzleRowClass(puzzle) {
                    if (puzzle.status === 'Critical') return 'critical-row'
                    if (puzzle.ismeta && puzzle.status !== 'Critical') return 'meta-row'
                    if (puzzle.status === 'New' && !puzzle.ismeta) return 'new-row'
                    return ''
                }
                
                function formatTags(tags) {
                    if (!tags || !Array.isArray(tags) || tags.length === 0) return ''
                    return tags.map(t => t.name).join(', ')
                }
                
                async function fetchData() {
                    try {
                        const response = await fetch('./apicall.php?apicall=all', { cache: 'no-store' })
                        const newData = await response.json()
                        data.value = newData
                        
                        // Initialize status edits for new puzzles
                        newData.rounds.forEach(round => {
                            round.puzzles.forEach(puzzle => {
                                if (statusEdits.value[puzzle.id] === undefined) {
                                    statusEdits.value[puzzle.id] = puzzle.status
                                }
                            })
                        })
                        
                        // Update status indicator
                        if (staleTimer.value) clearTimeout(staleTimer.value)
                        updateState.value = 'circle active pulse'
                        setTimeout(() => updateState.value = 'circle active', 1000)
                        staleTimer.value = setTimeout(() => updateState.value = 'circle stale', 6000)
                        
                        lastUpdate.value = new Date().toLocaleTimeString('en-US', {
                            timeZone: 'America/New_York',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        })
                    } catch (e) {
                        console.error('Fetch error:', e)
                        updateState.value = 'circle error pulse'
                    }
                }
                
                async function fetchStatuses() {
                    try {
                        const response = await fetch('./apicall.php?apicall=all')
                        const data = await response.json()
                        // Get statuses from huntinfo or use defaults
                        if (data.statuses) {
                            statuses.value = data.statuses
                        } else {
                            statuses.value = Consts.statuses
                        }
                    } catch (e) {
                        statuses.value = Consts.statuses
                    }
                }
                
                async function updateComment(puzzleId) {
                    const comment = commentEdits.value[puzzleId]
                    if (comment === undefined || comment === '') return
                    
                    saving.value[puzzleId] = true
                    try {
                        await fetch(`./apicall.php?apicall=puzzle&apiparam1=${puzzleId}&apiparam2=comments`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ comments: comment })
                        })
                        
                        // Flash the row
                        const row = document.getElementById('puzzle-' + puzzleId) || 
                                    document.getElementById('puzzle-overview-' + puzzleId)
                        if (row) {
                            row.classList.add('flash')
                            setTimeout(() => row.classList.remove('flash'), 500)
                        }
                        
                        // Clear the input and refresh
                        commentEdits.value[puzzleId] = ''
                        await fetchData()
                    } catch (e) {
                        console.error('Update error:', e)
                        alert('Failed to update comment')
                    }
                    saving.value[puzzleId] = false
                }
                
                async function updateStatus(puzzleId) {
                    const status = statusEdits.value[puzzleId]
                    
                    saving.value[puzzleId] = true
                    try {
                        await fetch(`./apicall.php?apicall=puzzle&apiparam1=${puzzleId}&apiparam2=status`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: status })
                        })
                        
                        // Flash the row
                        const row = document.getElementById('puzzle-overview-' + puzzleId)
                        if (row) {
                            row.classList.add('flash')
                            setTimeout(() => row.classList.remove('flash'), 500)
                        }
                        
                        await fetchData()
                    } catch (e) {
                        console.error('Update error:', e)
                        alert('Failed to update status')
                    }
                    saving.value[puzzleId] = false
                }
                
                onMounted(async () => {
                    await fetchStatuses()
                    await fetchData()
                    setInterval(fetchData, 5000)
                })
                
                return {
                    data,
                    stats,
                    statusCounts,
                    displayStatuses,
                    selectableStatuses,
                    noLocPuzzles,
                    sheetDisabledPuzzles,
                    workOnPuzzles,
                    updateState,
                    lastUpdate,
                    showNoLoc,
                    showSheetDisabled,
                    showOverview,
                    commentEdits,
                    statusEdits,
                    saving,
                    getRoundName,
                    getPuzzleRowClass,
                    formatTags,
                    updateComment,
                    updateStatus
                }
            }
        }).mount('#app')
    </script>
</body>
</html>
