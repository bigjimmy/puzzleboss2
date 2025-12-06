import { ref, useTemplateRef, watch } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'

//
// This component represents one of three update icons on each puzzle. Much of
// that functionality is shared, so I refactored it into one file. You can
// argue about whether that was a good idea.
//
// There are three kinds of update icons: "note", which updates comments,
// "work state", which updates location and your "currently solving" state, and
// "status", which updates puzzle status (including answers and whether it is a
// meta for the round).
//
export default {
    props: {
    
        // the puzzle from the puzzboss API
        puzzle: Object,
        // the type of update icon
        type: String,

        // the user id of the current user (work state)
        uid: Number,
        
        // whether the puzzle is a meta (status)
        ismeta: Boolean,
        // list of statuses, or "puzzle filter keys" (status)
        pfk: Object
    },
    computed: {
        //
        // Computes the icon to be displayed.
        //
        icon() {
            if (this.type === 'note') return this.puzzle.comments == null ? '➕' : 'ℹ️';
            if (this.type === 'work state') {
                if (this.puzzle.cursolvers !== null && this.puzzle.cursolvers.length !== 0) return '👥';
                if (this.puzzle.xyzloc !== null && this.puzzle.xyzloc.length !== 0) return '📍'
                return '👻';
            }
            if (this.type === 'status') {
                if (this.ismeta) return 'Ⓜ️';
                const map = {'New': '🆕', 'Being worked': '🙇', 'Unnecessary': '🙃', 'WTF': '☢️', 'Critical': '⚠️', 'Solved': '✅', 'Needs eyes': '👀'}
                const ret = map[this.puzzle.status];
                return (ret === undefined) ? '🤡' : ret;
            }
            return '🤡!';
        },
        //
        // Computes the description, or hover text, for the icon.
        //
        description() {
            if (this.type === 'note') return this.puzzle.comments == null ? 'add note' : this.puzzle.comments;
            if (this.type === 'status') {
                var desc = (this.ismeta ? '(Meta) ' : '') + this.puzzle.status;
                if (this.puzzle.xyzloc !== null && this.puzzle.xyzloc.length !== 0) {
                    desc += ` at #${this.puzzle.xyzloc}`;
                }
                return desc;
            }

            var desc = "This puzzle is being worked on";
            if (this.puzzle.xyzloc !== null && this.puzzle.xyzloc.length !== 0) {
                desc += ` at #${this.puzzle.xyzloc}`;
            }
            if (this.puzzle.cursolvers !== null && this.puzzle.cursolvers.length !== 0) {
                desc += ` by ${this.puzzle.cursolvers}`;
            }
            desc += '.';

            if(desc.length === "This puzzle is being worked on.".length) {
                desc = "No active location or solvers on this puzzle.";
            }

            return desc;
        }
    },
    //
    // We emit two events.
    // 
    // please-fetch is propagated to index.html and indicates that we have made
    // a call to the backend which will mutate state, and we should update our
    // page as soon as possible.
    //
    // highlight-me is propagated to round.js and indicates that we have just
    // closed the modal, and should highlight the whole puzzle div to indicate
    // to the user which puzzle they were just editing.
    //
    emits: ['please-fetch', 'highlight-me'],
    setup(props, context) {

        //
        // This component has two pieces of state which is used by all types:
        //
        // showModal indicates whether the dialog box for this component is
        // currently visible to the user.
        //
        // warning displays an error if a POST fails for some reason, or if
        // a user has put in invalid input.
        //
        const showModal = ref(false);
        const warning = ref("");

        //
        // We also have two template refs:
        // 
        // input is used to focus the primary input in the modal (depending on
        // type) when the modal is displayed.
        //
        // puzzle is used to recenter the view on the edited puzzle when the
        // modal closes.
        //
        const input = useTemplateRef('modal-input');
        const puzzle = useTemplateRef('puzzle-tag');

        //
        // stateStrA is shared by all types. It represents comments for "note",
        // location (xyzloc) for "work state", and status for "status". It
        // shadows the true value of the puzzle state until the user commits
        // the change with the save button. 
        //
        const stateStrA = ref("");
        
        //
        // Shadow variables from add-status.js: the current answer and whether
        // the current puzzle is the meta.
        //
        const answer = ref("");
        const isMetaLoc = ref(false);
        
        //
        // Time since last activity (for status modal)
        //
        const timeSinceLastAct = ref("");

        // Force answers to be all uppercase.
        watch(answer, () => {
            answer.value = answer.value.toUpperCase();
        });

        //
        // Shadow variables from add-solvers.js (work state): whether we're
        // currently working on the puzzle, and whether to show that to the
        // user.
        //
        const showStatus = ref(false);
        const currentlyWorking = ref(false);

        //
        // This function toggles modal visibility. If save is true, as is the
        // case when the 'Save' button is selected, then the value is submitted
        // to the back-end if it has been updated.
        //
        async function toggleModal(save) {

            // Global initialization of values.
            showModal.value = !showModal.value;
            warning.value = "";
            showStatus.value = false;
            
            if (showModal.value) {

                //
                // TODO: Maybe force a load of the puzzle here for freshness,
                //       but not hugely urgent IMO.
                //
                // Alternatively, warn the user if the comments have been
                // updated on the back-end while they're performing the update.
                // I suspect this will not be a huge issue either way.
                //

                //
                // Type-specific initalization of state variables.
                //
                if (props.type === 'note') {
                    stateStrA.value = props.puzzle.comments;
                } else if (props.type === 'work state') {
                    stateStrA.value = props.puzzle.xyzloc;

                    const url = `https://importanthuntpoll.org/pb/apicall.php?&apicall=solver&apiparam1=${props.uid}`
                    let solver = await(await fetch(url)).json();

                    currentlyWorking.value = (solver.solver.puzz === props.puzzle.name);
                    showStatus.value = true;
                } else if (props.type === 'status') {
                    stateStrA.value = props.puzzle.status;           
                    isMetaLoc.value = props.ismeta;
                    answer.value = props.puzzle.answer !== null ? props.puzzle.answer : "";
                    
                    // Fetch last activity time
                    try {
                        const lastActUrl = `https://importanthuntpoll.org/pb/apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=lastact`;
                        let lastActData = await(await fetch(lastActUrl)).json();
                        if (lastActData.puzzle && lastActData.puzzle.lastact && lastActData.puzzle.lastact.time) {
                            const lastActTime = new Date(lastActData.puzzle.lastact.time);
                            const now = new Date();
                            const diffMs = now - lastActTime;
                            if (diffMs >= 0) {
                                const diffSec = Math.floor(diffMs / 1000);
                                const hours = Math.floor(diffSec / 3600);
                                const minutes = Math.floor((diffSec % 3600) / 60);
                                const seconds = diffSec % 60;
                                timeSinceLastAct.value = `${hours}h ${minutes}m ${seconds}s ago`;
                            }
                        } else {
                            timeSinceLastAct.value = "";
                        }
                    } catch (e) {
                        console.log("Failed to fetch lastact:", e);
                        timeSinceLastAct.value = "";
                    }
                }

                //
                // N.B. A number of other factors may keep us from successfully
                //      focusing the input right away - the input may not have
                //      rendered yet, or the click will have refocused the
                //      browser back to the <p> tag. The `autofocus` tag, for
                //      whatever reason, works only once. Instead, we'll do the
                //      typical trick of "just do it in a little bit and it
                //      should work most of the time."
                //

                setTimeout(() => { input.value.focus(); }, 100);
            } else if (save) {

                let emitFetch = false;
                let what = '';
                let payload = {};

                //
                // We are worried about updates on a different field for each
                // type - namely, the value in stateStrA. Thus, we can simply
                // read stateStrA and assign it to the appropriate property
                // before fetching the appropriate endpoint.
                //
                if (props.type === 'note') what = 'comments';
                if (props.type === 'work state') what = 'xyzloc';
                if (props.type === 'status') what = 'status';

                //
                // Solved status updates have special handling - we verify the
                // answer is not blank, and then we update the *answer property
                // only*. The database handles updating the status to Solved
                // for us.
                //
                if (props.type === 'status' && stateStrA.value === 'Solved') {
                    if (answer.value === '') {
                        showModal.value = true;
                        warning.value = "ANSWER IS BLANK!!!"

                    } else if (answer.value !== props.puzzle.answer && answer.value !== null) {
                        what = 'answer';
                        payload[what] = answer.value;
                        emitFetch = true;
                    }

                } else if (stateStrA.value !== props.puzzle[what]) {
                    payload[what] = stateStrA.value;
                    emitFetch = true;
                }

                //
                // Hit the backend with the appropriate API parameters.
                //
                const url = `https://importanthuntpoll.org/pb/apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=${what}`;
                if (emitFetch) {
                    try {
                        await fetch(url, {
                            method: 'POST',
                            body: JSON.stringify(payload),
                        });
                        context.emit('please-fetch');
                    } catch (e) {
                        warning.value = "failed to POST; check devtools";
                        console.log(e);
                        showModal.value = true;
                    }
                }

                //
                // We do special handling of the meta location update, since
                // it can be updated at the same time as status, and it hits
                // the round API as a property of the round, rather than the
                // puzzle.
                //
                if (props.type === 'status' && (isMetaLoc.value != props.ismeta)) {
                    const url = `https://importanthuntpoll.org/pb/apicall.php?apicall=round&apiparam1=${props.puzzle.round_id}&apiparam2=meta_id`
                    try {
                        await fetch(url, {
                            method: 'POST',
                            body: JSON.stringify({ "meta_id": isMetaLoc.value ? props.puzzle.id : null }),
                        });
                        if (!emitFetch) context.emit('please-fetch');

                    } catch (e) {
                        warning.value = "failed to POST; check devtools";
                        isMetaLoc.value = props.ismeta;
                        console.log(e);
                        showModal.value = true;
                    }
                }
            }

            //
            // Focus the modal if we closed it!
            //
            if (showModal.value == false) {
                puzzle.value.scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});
                context.emit('highlight-me');
            }
        }

        //
        // "Work state"-specific function. This function marks the user as
        // "currently working" on the given puzzle.
        //
        async function claimCurrentPuzzle() {

            const url = `https://importanthuntpoll.org/pb/apicall.php?apicall=solver&apiparam1=${props.uid}&apiparam2=puzz`
            
            try {
                await fetch(url, {
                    method: 'POST',
                    body: JSON.stringify({ "puzz": props.puzzle.id }),
                });

                context.emit('please-fetch');
                showModal.value = false;

            } catch (e) {
                warning.value = "failed to POST; check devtools";
                console.log(e);
            }

            //
            // Focus the modal if we closed it!
            //
            if (showModal.value == false) {
                puzzle.value.scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});
                context.emit('highlight-me');
            }
        }

        return {
            showModal, toggleModal, warning,
            stateStrA,
            answer, isMetaLoc, timeSinceLastAct,
            showStatus, currentlyWorking, claimCurrentPuzzle
        };
    },

    template: `
    <p class="puzzle-icon" ref="puzzle-tag" :title="description" @click.prevent="toggleModal(false)">{{icon}}</p>
    <dialog v-if='showModal' open>
        <h4>Editing {{type}} for {{puzzle.name}}:</h4>
        <p v-if="warning.length !== 0">{{warning}}</p>

        <!-- work state -->
        <p v-if="puzzle.solvers !== null && type === 'work state'">All solvers: {{puzzle.solvers}}.</p>
                <p v-if="currentlyWorking && showStatus">You are currently working on this puzzle.</p>
        <p v-if="(!currentlyWorking) && showStatus">You are not marked as currently working on this puzzle. Would you like to be? <button @click="claimCurrentPuzzle">Yes</button></p>
        <p v-if="type === 'work state'">Location: <input ref="modal-input" v-model="stateStrA"></input></p>

        <!-- note -->
        <p><textarea v-if="type === 'note'" ref="modal-input" v-model="stateStrA" cols="40" rows="4"></textarea></p>

        <!-- status -->
        <p v-if="type === 'status' && puzzle.sheetcount">Sheets in spreadsheet: {{puzzle.sheetcount}}</p>
        <p v-if="type === 'status' && timeSinceLastAct">Last activity: {{timeSinceLastAct}}</p>
        <p v-if="type === 'status'">Is Meta: <input type="checkbox" v-model="isMetaLoc"></input></p>
        <p v-if="type === 'status'"> Status:
            <select ref="modal-input" class="dropdown" v-model="stateStrA" :disabled="puzzle.status === 'Solved'">
                <option
                    v-for = "k in pfk"
                    :key = "k"
                    :value = "k">
                    {{k}}
                    </option>
            </select>
        </p>
        <p v-if="type === 'status' && stateStrA === 'Solved'">Answer: <input v-model = "answer"></input></p>
        <button @click="toggleModal(false)">Close</button>
        <button @click="toggleModal(true)">Save</button>
    </dialog>
    `
  }
