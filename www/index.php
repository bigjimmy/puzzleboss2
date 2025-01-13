<!DOCTYPE html>
<html>
    <head>
        <title>Puzzboss 2000</title>
        <link rel="stylesheet" href="./pb-ui.css">
        <script src="https://cdn.rawgit.com/localForage/localForage/4ce19202/dist/localforage.min.js"></script>
    </head>
    <body>
        <div id = "main">

            <h2>Hello, {{username}}! It is currently {{time}} TIMEMIT.</h2>
            <div id = "status">
                <p>{{roundStats["solved"]}} rounds solved out of {{roundStats["count"]}} open.
                    {{puzzleStats["Solved"]}} puzzles solved out of {{puzzleStats["Count"]}} open ({{puzzleStats["New"]}} new, {{puzzleStats["Being worked"]}} being worked, {{puzzleStats["Critical"]}} critical, {{puzzleStats["Needs eyes"]}} needs eyes, {{puzzleStats["WTF"]}} WTF). Page status: </p>
                <div :class = updateState></div>
            </div>
            <p>Go to: <a href="../pbtools.php" target="_blank">pbtools</a> <a href="../" target="_blank">wiki</a> <a href="./old.php">oldi-ui</a></p>

            <div id= "controls"> 
            <button @click="applyShow(false)">Hide All Rounds</button>
            <button @click="applyShow(true)">Show All Rounds</button>

            Show puzzles:
            <div
                v-for="key in puzzleFilterKeys"
                class="filter"
                @click="toggleKey(key)"
                >
                {{key}} <input type="checkbox" v-model="puzzleFilter[key]"/>
            </div>
            <button @click="applyShowFilter(false)">Hide All Puzzles</button>
            <button @click="applyShowFilter(true)">Show All Puzzles</button>
            <p>Sort puzzles by status: <input type="checkbox" v-model="sortPuzzles"/></p>
            </div>

            <div id = "allrounds" :class = "{'usecolumns': useColumns}">
                <div id = "rounds" :class = "{'usecolumns': useColumns}">
                    <round
                        v-for="round in roundsSorted"
                        :round="round"
                        :showbody="showBody[round.id]"
                        :highlighted="highlight[round.id]"
                        :puzzlefilter="puzzleFilter"
                        :pfk="puzzleFilterKeys"
                        :key="round.id"
                        :scrollspeed="scrollSpeed"
                        :uid="uid"
                        :sortpuzzles="sortPuzzles"
                        :currpuzz="currPuzz"
                        @toggle-body="toggleBody"
                        @please-fetch = "fetchData"
                    ></round>
                </div>
                <div id = "roundshidden" v-if = "roundsSortedHidden.length > 0">
                    <h4>Minimized Rounds</h4>
                    <round
                        v-for="round in roundsSortedHidden"
                        :round="round"
                        :showbody="showBody[round.id]"
                        :highlighted="highlight[round.id]"
                        :puzzlefilter="puzzleFilter"
                        :key="round.id"
                        :pfk="puzzleFilterKeys"
                        :scrollspeed="scrollSpeed"
                        :sortpuzzles="sortPuzzles"
                        :uid="uid"
                        :currpuzz="currPuzz"
                        @toggle-body="toggleBody"
                    ></round>
                </div>
            </div>

            <div>
                <h4>Advanced Settings</h4>
                <p>Use columns display (fixed-height, scroll-to-right) <input type="checkbox" v-model="useColumns"></input></p>
                <p>Scroll speed (default 1) <input type="number" v-model="scrollSpeed" min="1"></input></p>
                <solvesound ref="solveSound"></solvesound>
            </div>

        </div>
    <script type="module">

        import { createApp, ref, useTemplateRef, onMounted, watch } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
        import Round from './round.js'
        import solvesound from './solve-sound.js'

        createApp({
            components: {
                Round,
                solvesound
            },
            computed: {
                
                //
                // This function returns the unhidden rounds.
                //
                roundsSorted() {
                    if(this.data.rounds === undefined) return []

                    return [...this.data.rounds].filter((round) => this.showBody[round.id]);
                },
                
                //
                // This function returns the hidden rounds.
                //
                roundsSortedHidden() {
                    if(this.data.rounds === undefined) return []

                    return [...this.data.rounds].filter((round) => !this.showBody[round.id]);
                }
            },
            setup() {
                
                //
                // Our application stores six pieces of global state:
                // 
                // One is 'data', which is the raw data we get from the PB API.
                // This contains all of the puzzle and round data that we need
                // to display to the user.
                // 
                // Another is 'showBody', which is an array, indexed by round
                // ID, indicating whether or not the list of puzzles is shown
                // for that round. Correspondingly, 'highlight' indicates
                // whether or not to highlight the header (if a round has just
                // been shown or hidden).
                //
                // Settings are stored as well - 'useColumns' selects between
                // one of two flexbox setups for the page; 'scrollSpeed' allows
                // the user to customize how fast clipped names/answers scroll.
                // 
                // The remaining are statistics objects (roundStats,
                // puzzleStats) which track general hunt progress, the current
                // time (to the minute), and the state of the page update
                // indicator (staleTimer, errorTimer, updateState).
                //

                const data = ref([])
                const showBody = ref([])
                const highlight = ref([])
                const puzzleFilterKeys = ref(
                    ['Solved', 'WTF', 'Critical', 'Being worked', 'New', 'Needs eyes', 'Unnecessary']
                )
                const puzzleFilter = ref({
                    'Solved': true, 'WTF': true, 'Critical': true, 'Being worked': true, 'New': true, 'Needs eyes': true, 'Unnecessary': true
                })
                const sortPuzzles = ref(false);
                const roundStats = ref({})
                const puzzleStats = ref({})
                const time = ref("")

                const staleTimer = ref(null);
                const errorTimer = ref(null);
                const updateState = ref("circle stale");

                const useColumns = ref(true);
                const scrollSpeed = ref(1);
                const currPuzz = ref(0);
                const solveSoundRef = useTemplateRef('solveSound');
                
                <?php
                     echo "const username = ref(\"" . $_SERVER['REMOTE_USER'] . "\");";
                ?>
                const uid = ref(0);

                //
                // This function fetches data from an endpoint and updates the
                // stats.
                //
                async function fetchData(firstUpdate = false) {

                    //
                    // Poll the API. We pulse green if the poll is successful,
                    // and set a timer to gray out the page if we don't get new
                    // data in the next 6 seconds. If we're unsuccessful, we
                    // pulse red so that the user doesn't miss it. If we last a
                    // minute without updates, we kill the page, so that a user
                    // never reads stale data for too long.
                    //

                    const url = `./apicall.php?apicall=all`
                    let success = false;
                    let temp = {'rounds': []};
                    try {
                        temp = await (await fetch(url, {cache: "no-store"})).json();
                        data.value = temp;

                        if (firstUpdate) {
                            const url = `./apicall.php?&apicall=solvers`;
                            let solvers = await (await fetch(url)).json();
                            uid.value = solvers.solvers.filter(s => s.name === username.value)[0].id;
                        }

                        const solver_url = `./apicall.php?&apicall=solver&apiparam1=${uid.value}`
                        let solver = await(await fetch(solver_url)).json();

                        currPuzz.value = solver.solver.puzz;

                        success = true;
                    } catch (e) {
                        console.error(e);
                        errorTimer.value = setTimeout(() => {
                            data.value = {'rounds': []};
                        }, 60000);
                    }

                    if (staleTimer.value != null) {
                        clearTimeout(staleTimer.value);
                        staleTimer.value = null;
                    }

                    if (success) {
                        updateState.value = "circle active pulse";
                        setTimeout(() => {
                            updateState.value = "circle active";
                        }, 1000);

                        staleTimer.value = setTimeout(() => {
                            updateState.value = "circle stale";
                        }, 6000);
                        
                        if (errorTimer.value != null) {
                            clearTimeout(errorTimer.value);
                            errorTimer.value = null;
                        }

                    } else {
                        updateState.value = "circle error pulse";
                    }

                    let max_round = data.value.rounds.map(round => round.id)
                                                    .reduce((prev, cur) => Math.max(prev, cur), 0);

                    max_round += 1; // Include the last element. A dictionary
                                    // would be smarter, but hopefully we'll
                                    // never have enough rounds to care.

                    // 
                    // Extend showBody if new rounds appear. Show new rounds
                    // by default.
                    //

                    let showBodyUpdate = showBody.value.slice();
                    let highlightUpdate = highlight.value.slice();
                    while(max_round > showBodyUpdate.length) {
                        showBodyUpdate.push(true);
                        highlightUpdate.push(false);
                    }
                    showBodyUpdate.splice(max_round);
                    highlightUpdate.splice(max_round);

                    showBody.value = showBodyUpdate;
                    highlightUpdate.value = highlightUpdate;

                    //
                    // Calculate statistics to display at top of page. These
                    // are probably somewhat inefficient to be doing every five
                    // seconds, but, well... benefits of Moore's law.
                    //

                    let roundStatsLocal = {'count': 0, 'solved': 0};
                    data.value.rounds.forEach((round) => {
                        roundStatsLocal['count'] += 1;
                        const roundSolved = round.puzzles.filter(puzzle => puzzle.status === 'Solved')
                                                         .filter(puzzle => puzzle.id === round.meta_id)
                                                         .length; 

                        roundStatsLocal['solved'] += roundSolved;

                    });

                    roundStats['unsolved'] = roundStats['count'] - roundStats['solved'];

                    let puzzleStatsLocal = {'Count': 0, 'Solved': 0, 'WTF': 0, 'Critical': 0, 'Being worked': 0, 'New': 0, 'Needs eyes': 0, 'Unnecessary': 0};
                    data.value.rounds.flatMap((round) => {
                        return round.puzzles.map(puzzle => puzzle.status);
                    }).forEach((status) => {
                        puzzleStatsLocal[status] += 1;
                        puzzleStatsLocal['Count'] += 1;
                    })

                    if(puzzleStats.value['Solved'] < puzzleStatsLocal['Solved'] && !firstUpdate) {
                        solveSoundRef.value.playSound();
                    } 

                    roundStats.value = roundStatsLocal;
                    puzzleStats.value = puzzleStatsLocal;

                    time.value = new Date().toLocaleTimeString("en-US", {timeZone: 'America/New_York', weekday: "long", hour: "2-digit", minute: "2-digit" });

                }

                onMounted(async () => {

                    //
                    // Load filters from local storage if present.
                    //

                    const pf = localStorage.getItem("puzzleFilter");
                    if (pf !== null && pf !== undefined) puzzleFilter.value = JSON.parse(pf);

                    const sb = localStorage.getItem("showBody");
                    if (sb !== null && sb !== undefined) showBody.value = JSON.parse(sb);

                    const uc = localStorage.getItem("useColumns");
                    if (uc !== null && uc !== undefined) useColumns.value = JSON.parse(uc);

                    const ss = localStorage.getItem("scrollSpeed");
                    if (ss !== null && ss !== undefined) scrollSpeed.value = JSON.parse(ss);

                    const sp = localStorage.getItem("sortPuzzles");
                    if (sp !== null && sp !== undefined) sortPuzzles.value = JSON.parse(sp);

                    await fetchData(true);
                    setInterval(fetchData, 5000);
                });

                //
                // This function is called from the Round component via the
                // toggle-body event. It toggles the body for a given round,
                // and highlights the header for 500ms.
                //
                function toggleBody(n) {
                    showBody.value[n] = !showBody.value[n];
                    highlight.value[n] = true;
                    setTimeout(() => {
                        highlight.value[n] = false;
                    }, 500);
                }

                //
                // This function toggles the filters for a given key (i.e., 
                // a status of puzzles).
                //
                function toggleKey(k) {
                    puzzleFilter.value[k] = !puzzleFilter.value[k];
                }
                
                //
                // This function implements hide/show all functionality for
                // rounds by filling the showBody array as appropriate.
                //
                function applyShow(which) {
                    showBody.value = Array(showBody.value.length).fill(which);
                }

                //
                // This function implements hide/show all functionality for
                // puzzles by filling the puzzleFilter object as appropriate.
                //
                function applyShowFilter(which) {
                    Object.keys(puzzleFilter.value).forEach((key) => {
                        puzzleFilter.value[key] = which;
                    });
                }

                //
                // This function persists a given key to localStorage.
                //
                function persist(which, update) {
                    localStorage.setItem(which, JSON.stringify(update));
                }

                //
                // Persist the filters across page reloads.
                //

                watch(showBody, update => {
                    persist("showBody", update);
                });

                watch(puzzleFilter, (update) => {
                    persist("puzzleFilter", update);
                }, {'deep': true});

                watch(useColumns, (update) => {
                    persist("useColumns", update);
                });

                watch(scrollSpeed, (update) => {
                    persist("scrollSpeed", update);
                });

                watch(sortPuzzles, (update) => {
                    persist("sortPuzzles", update);
                });

                return {
                    data,
                    showBody, highlight,
                    puzzleFilter, puzzleFilterKeys, sortPuzzles,
                    toggleBody, toggleKey,
                    applyShow, applyShowFilter,
                    roundStats,
                    puzzleStats,
                    time, updateState,
                    fetchData,
                    useColumns, scrollSpeed,
                    uid, username, currPuzz
                }
            },
        }).mount('#main');

    </script>
    </body>
</html>
