<?php
require_once('puzzlebosslib.php');
?>
<!DOCTYPE html>
<html>
    <head>
        <title>Puzzboss 2000</title>
        <link rel="stylesheet" href="./pb-ui.css">
        <script src="https://cdn.rawgit.com/localForage/localForage/4ce19202/dist/localforage.min.js"></script>
    </head>
    <body>
        <div id = "main">

            <div class="info-box">
                <div class="info-box-header" @click="showHuntInfo = !showHuntInfo">
                    <span class="collapse-icon" :class="{ collapsed: !showHuntInfo }">▼</span>
                    <h3>Hunt Status</h3>
                </div>
                <div class="info-box-content" v-show="showHuntInfo" v-cloak>
                    <h2 style="margin-top: 0;">Hello, {{username}}! It is currently {{time}} TIMEMIT.</h2>
                    <div id = "status">
                        <p>{{roundStats["solved"]}} rounds solved out of {{roundStats["count"]}} open.
                            {{puzzleStats["Solved"]}} puzzles solved out of {{puzzleStats["Count"]}} open. Page status: </p>
                        <div :class = updateState></div>
                    </div>
                    <?php
                    // Render navbar with special styling for index.php
                    $navbar = render_navbar('index');
                    // Add inline style to the nav-links div
                    $navbar = str_replace('<div class="nav-links">', '<div class="nav-links" style="margin-top: 15px;">', $navbar);
                    echo $navbar;
                    ?>
                </div>
            </div>

            <div class="info-box" v-if="settings && statuses && statuses.length > 0">
                <div class="info-box-header" @click="showSettings = !showSettings">
                    <span class="collapse-icon" :class="{ collapsed: !showSettings }">▼</span>
                    <h3>Search and Settings</h3>
                </div>
                <div class="info-box-content" v-show="showSettings">
                    <div id="settings-bar">
                        <div id="tag-search">
                            <label>Tag search:</label>
                            <tagselect v-model:current="tagFilter" :allowAdd="false" :tags="[]"></tagselect>
                        </div>
                        <settings :s="settings" :statuses="statuses" @settings-updated="updateSetting">
                            <solvesound ref="solveSound"></solvesound>
                        </settings>
                    </div>
                </div>
            </div>

            <div id = "allrounds" :class = "{'usecolumns': useColumns}">
                <div id = "rounds" :class = "{'usecolumns': useColumns}">
                    <round
                        v-for="round in roundsSorted"
                        :round="round"
                        :settings="settings"
                        :showbody="showBody[round.id]"
                        :highlighted="highlight[round.id]"
                        :tagfilter="tagFilter"
                        :key="round.id"
                        :uid="uid"
                        :isadmin="isAdmin"
                        :currpuzz="currPuzz"
                        :solvers="solvers"
                        :initialpuzz="initialPuzz"
                        :hints="data.hints || []"
                        :username="username"
                        @toggle-body="toggleBody"
                        @please-fetch="fetchData"
                        @route-shown="clearInitPuzz"
                    ></round>
                </div>
                <div id = "roundshidden" v-if = "roundsSortedHidden.length > 0">
                    <h4>Minimized Rounds</h4>
                    <round
                        v-for="round in roundsSortedHidden"
                        :round="round"
                        :settings="settings"
                        :showbody="showBody[round.id]"
                        :highlighted="highlight[round.id]"
                        :tagfilter="tagFilter"
                        :key="round.id"
                        :uid="uid"
                        :isadmin="isAdmin"
                        :currpuzz="currPuzz"
                        :initialpuzz="initialPuzz"
                        :hints="data.hints || []"
                        :username="username"
                        @toggle-body="toggleBody"
                        @please-fetch="fetchData"
                        @route-shown="clearInitPuzz"
                    ></round>
                </div>
            </div>

            <datalist id="taglist">
                <option
                    v-for="tag in tags"
                    :key="tag.id"
                    :value="tag.name">
                </option>
            </datalist>

        </div>
    <script type="module">

        import { createApp, ref, useTemplateRef, onMounted, watch } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
        import Round from './round.js';
        import solvesound from './solve-sound.js';
        import Consts from './consts.js';
        import { onFetchSuccess, onFetchFailure } from './pb-utils.js';
        import tagselect from './tag-select.js';
        import Settings from './settings.js';

        // Wait for status metadata (emoji, names) to load before mounting.
        // Without this, computed icons show 🤡 until the next data poll.
        await Consts.ready;

        createApp({
            components: {
                Round,
                solvesound,
                tagselect,
                Settings,
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
                },

                //
                // This function returns the useColumns setting value
                //
                useColumns() {
                    return this.settings?.useColumns || false;
                },
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

                const data = ref({rounds: []});
                const settings = ref(null);
                const showBody = ref([]);
                const highlight = ref([]);

                const roundStats = ref({});
                const puzzleStats = ref({});
                const time = ref("");

                const staleTimer = ref(null);
                const errorTimer = ref(null);
                const updateState = ref("circle stale");
                
                const currPuzz = ref("0");
                const initialPuzz = ref(null);

                const solveSoundRef = useTemplateRef('solveSound');

                //
                // Get authenticated username (with test mode support)
                //
                <?php
                $auth_solver = getauthenticatedsolver();
                echo "const username = ref(\"" . $auth_solver->name . "\");";
                $is_pt = checkpriv("puzztech", $auth_solver->id) ? 'true' : 'false';
                $is_pb = checkpriv("puzzleboss", $auth_solver->id) ? 'true' : 'false';
                ?>
                const uid = ref(<?php echo $auth_solver->id; ?>);
                const isAdmin = ref(<?php echo $is_pt; ?> || <?php echo $is_pb; ?>);
                const solvers = ref(null);

                const tags = ref([]);
                const tagFilter = ref("");
                const statuses = ref([]);

                const showHuntInfo = ref(true);
                const showSettings = ref(true);

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

                    // Statuses will be merged after huntinfo loads in firstUpdate

                    const url = `${Consts.api}/apicall.php?apicall=all`
                    let success = false;
                    let temp = {'rounds': []};
                    try {
                        temp = await (await fetch(url, {cache: "no-store"})).json();
                        data.value = temp;

                        if (firstUpdate) {
                            const url = `${Consts.api}/apicall.php?&apicall=solvers`;
                            const solversData = await (await fetch(url)).json();
                            solvers.value = solversData.solvers;
                            uid.value = solversData.solvers.filter(s => s.name === username.value)[0].id;

                            //
                            // Read tags once at first update. This could be moved
                            // out of the if block if we find that new tags are
                            // being created more often than people reload.
                            //
                            const tags_url = `${Consts.api}/apicall.php?&apicall=tags`;
                            const tagsData = await (await fetch(tags_url)).json();
                            tags.value = tagsData.tags;

                            //
                            // Fetch statuses from huntinfo for the settings filter
                            //
                            const huntinfo_url = `${Consts.api}/apicall.php?&apicall=huntinfo`;
                            const huntinfoData = await (await fetch(huntinfo_url)).json();
                            if (huntinfoData.statuses && Array.isArray(huntinfoData.statuses)) {
                                statuses.value = huntinfoData.statuses.map(s => s.name);

                                // Now that statuses are loaded, populate puzzleFilter
                                if (settings.value) {
                                    if (!settings.value.puzzleFilter) {
                                        settings.value.puzzleFilter = {};
                                    }
                                    // Add all statuses to filter (visible except [hidden])
                                    statuses.value.forEach(status => {
                                        if (!(status in settings.value.puzzleFilter)) {
                                            settings.value.puzzleFilter[status] = (status !== '[hidden]');
                                        }
                                    });
                                } else {
                                    console.error('settings.value is null/undefined when trying to populate puzzleFilter');
                                }
                            } else {
                                console.error('huntinfo did not return valid statuses array');
                            }
                        }

                        const solver_url = `${Consts.api}/apicall.php?&apicall=solver&apiparam1=${uid.value}`
                        let solver = await(await fetch(solver_url)).json();

                        currPuzz.value = solver.solver.puzz;

                        success = true;
                        onFetchSuccess();
                    } catch (e) {
                        console.error(e);
                        if (onFetchFailure()) return;
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
                    // by default, unless they are solved and showSolvedRounds is false.
                    //

                    let showBodyUpdate = showBody.value.slice();
                    let highlightUpdate = highlight.value.slice();

                    // Build a map of round ID to solved status
                    const roundSolvedMap = {};
                    data.value.rounds.forEach((round) => {
                        roundSolvedMap[round.id] = Consts.isRoundSolved(round);
                    });

                    while(max_round > showBodyUpdate.length) {
                        const roundId = showBodyUpdate.length;
                        const isSolved = roundSolvedMap[roundId] || false;
                        // Show round by default unless it's solved and showSolvedRounds is false
                        const shouldShow = !isSolved || settings.value.showSolvedRounds;
                        showBodyUpdate.push(shouldShow);
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
                        roundStatsLocal['solved'] += Consts.isRoundSolved(round) ? 1 : 0;
                    });

                    roundStats['unsolved'] = roundStats['count'] - roundStats['solved'];

                    let puzzleStatsLocal = Object.fromEntries([['Count', 0]].concat(Consts.statuses.map((status) => [status, 0])));
                    data.value.rounds.flatMap((round) => {
                        return round.puzzles.map(puzzle => puzzle.status);
                    }).forEach((status) => {
                        puzzleStatsLocal[status] += 1;
                        puzzleStatsLocal['Count'] += 1;
                    })

                    if(puzzleStats.value['Solved'] < puzzleStatsLocal['Solved'] && !firstUpdate) {
                        if (solveSoundRef.value) {
                            solveSoundRef.value.playSound();
                        }
                    } 

                    roundStats.value = roundStatsLocal;
                    puzzleStats.value = puzzleStatsLocal;

                    time.value = new Date().toLocaleTimeString("en-US", {timeZone: 'America/New_York', weekday: "long", hour: "2-digit", minute: "2-digit" });

                }

                onMounted(async () => {

                    //
                    // Load modal to pop from route if available.
                    //
                    // N.B. This occurs before we fetch data, meaning that it
                    //      is okay to reference this prop in the mounted()
                    //      call of the children, because puzzles have not yet
                    //      mounted.
                    //
                    const params = new URLSearchParams(document.location.search);
                    const puzz = parseInt(params.get("puzzle"), 10);
                    const what = params.get("what");

                    if (!isNaN(puzz) && what) initialPuzz.value = { puzz, what };

                    //
                    // Load filters from local storage if present.
                    //
                    let s = localStorage.getItem("settings");
                    if (s != null && s !== undefined) {
                        s = JSON.parse(s);
                    } else {
                        s = {};
                    }

                    //
                    // Add defaults if new settings have been introduced.
                    // Skip puzzleFilter (index 0) - will be initialized after statuses load
                    //
                    Consts.settings.forEach((setting, index) => {
                        if(s[setting] === null || s[setting] === undefined) {
                            if (index === 0) {
                                // puzzleFilter - initialize as empty object, will be populated after statuses load
                                s[setting] = {};
                            } else {
                                s[setting] = structuredClone(Consts.defaults[index]);
                            }
                        }
                    });

                    // Don't merge statuses here - will be done after huntinfo loads in firstUpdate

                    settings.value = s;

                    const sb = localStorage.getItem("showBody");
                    if (sb !== null && sb !== undefined) showBody.value = JSON.parse(sb);

                    await fetchData(true);

                    // Apply showSolvedRounds setting to override localStorage values for solved rounds
                    if (!settings.value.showSolvedRounds && data.value.rounds.length > 0) {
                        let showBodyUpdate = showBody.value.slice();
                        data.value.rounds.forEach((round) => {
                            const isSolved = Consts.isRoundSolved(round);
                            if (isSolved) {
                                showBodyUpdate[round.id] = false;
                            }
                        });
                        showBody.value = showBodyUpdate;
                    }
                    setInterval(fetchData, 5000);
                });

                function clearInitPuzz() {
                    // clear tags for reload
                    window.history.pushState("", "", ".");
                }

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
                // This function implements hide/show all functionality for
                // rounds by filling the showBody array as appropriate.
                //
                function applyShow(which) {
                    showBody.value = Array(showBody.value.length).fill(which);
                }

                //
                // This function persists a given key to localStorage.
                //
                function persist(which, update) {
                    localStorage.setItem(which, JSON.stringify(update));
                }

                //
                // This function updates settings and persists the
                // update to localStorage.
                //
                function updateSetting(s, value) {
                    settings.value[s] = value;
                    persist("settings", settings.value);
                }

                //
                // Persist the filters across page reloads.
                //

                watch(showBody, update => {
                    persist("showBody", update);
                });

                //
                // Watch for changes to showSolvedRounds setting and update showBody accordingly
                //
                watch(() => settings.value?.showSolvedRounds, (newVal) => {
                    if (data.value.rounds.length === 0) return;

                    let showBodyUpdate = showBody.value.slice();
                    data.value.rounds.forEach((round) => {
                        const isSolved = Consts.isRoundSolved(round);
                        if (isSolved) {
                            // If round is solved, show/hide based on showSolvedRounds setting
                            showBodyUpdate[round.id] = newVal;
                        }
                    });
                    showBody.value = showBodyUpdate;
                });

                return {
                    data,
                    showBody, highlight, toggleBody,
                    roundStats, puzzleStats,
                    fetchData, time, updateState,
                    uid, username, isAdmin, tags, solvers,
                    currPuzz, initialPuzz, clearInitPuzz,
                    tags, tagFilter,
                    settings, statuses, updateSetting,
                    showHuntInfo, showSettings
                }
            },
        }).mount('#main');

    </script>
    </body>
</html>
