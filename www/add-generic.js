import { ref, useTemplateRef, watch } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
import TagSelect from './tag-select.js';
import Consts from './consts.js';

//
// This component represents one of three update icons on each puzzle. Much of
// that functionality is shared, so I refactored it into one file. You can
// argue about whether that was a good idea.
//
// There are five kinds of update icons:
//
// round:
// - "comments": updates a round's comments
//
// puzzle:
// - "note": updates a puzzle's comments
// - "workstate": updates location and your currently solving state
// - "status": updates puzzle status (including answer, meta)
// - "tags" (WIP): updates puzzle tags
//

export default {
    components: {
        TagSelect
    },
    props: {
    
        // the puzzle or round from the puzzboss API
        puzzle: Object,
        // the type of update icon
        type: String,

        // the user id of the current user (work state)
        uid: Number,
        
        // whether the puzzle is a meta (status)
        ismeta: Number,
        // list of solvers,
        solvers: Object,

        // the initially opened dialog
        initialpuzz: Object
    },
    computed: {
        //
        // Computes the icon to be displayed.
        //
        icon() {
            if (this.type === 'workstate') {
                if (this.puzzle.cursolvers !== null && this.puzzle.cursolvers.length !== 0) return '👥';
                if (this.puzzle.xyzloc !== null && this.puzzle.xyzloc.length !== 0) return '📍'
                return '👻';
            }
            if (this.type === 'status') {
                if (this.ismeta) return 'Ⓜ️';
                const idx = Consts.statuses.indexOf(this.puzzle.status);
                return (idx === -1) ? '🤡' : Consts.emoji[idx];
            }
            if ((this.type === 'note') || (this.type === 'comments')) {
                return ((this.puzzle.comments === null) || (this.puzzle.comments.length === 0)) ? 
                        '➕' : '📝'
            }
            if (this.type === 'tags') {
                return '🏷️';
            }
            return '🤡!';
        },
        //
        // Computes the description, or hover text, for the icon.
        //
        description() {
            if ((this.type === 'note') || (this.type === 'comments')) {
                return ((this.puzzle.comments == null) || (this.puzzle.comments.length == 0)) ? 
                    'add note' : this.puzzle.comments;
            }

            if (this.type === 'status') {
                var desc = (this.ismeta ? '(Meta) ' : '') + this.puzzle.status;
                if (this.puzzle.xyzloc !== null && this.puzzle.xyzloc.length !== 0) {
                    desc += ` at #${this.puzzle.xyzloc}`;
                }
                return desc;
            }

            if (this.type === 'tags') {
                return ((this.puzzle.tags) && this.puzzle.tags.length > 0) ? this.puzzle.tags : 'no tags!';
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
        },
        //
        // Return the puzzle keys.
        //
        pfk() {
            return Consts.statuses;
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
    // route-shown is propagated to index.html and indicates that the route
    // initially specified when the page loaded was shown.
    //
    emits: ['please-fetch', 'highlight-me', 'route-shown'],
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
        // stateStrA is shared by all types. It represents comments for
        // "note/comments", location (xyzloc) for "work state", and status for
        // "status". It shadows the true value of the puzzle state until the
        // user commits the change with the save button. 
        //
        const stateStrA = ref("");
        
        //
        // Shadow variables from add-status.js: the current answer and whether
        // the current puzzle is the meta.
        //
        const answer = ref("");
        const isMetaLoc = ref(false);
        
        //
        // Last activity (for status modal)
        //
        const lastActInfo = ref("");
        const lastActTime = ref("");
        
        //
        // Contains the next tag to be added to the list, if any.
        //
        const nextTag = ref("");

        // Force answers to be all uppercase.
        watch(answer, () => {
            answer.value = answer.value.toUpperCase();
        });

        // Force all new tags to conform to regex.
        watch(nextTag, () => {
            const tagRegex = /[^a-zA-Z0-9_-]/i
            nextTag.value = nextTag.value.replace(tagRegex, "");
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
                if ((props.type === 'note') || (props.type === 'comments')) {
                    stateStrA.value = props.puzzle.comments;
                } else if (props.type === 'workstate') {
                    stateStrA.value = props.puzzle.xyzloc;

                    const url = `${Consts.api}/apicall.php?&apicall=solver&apiparam1=${props.uid}`
                    let solver = await(await fetch(url)).json();

                    currentlyWorking.value = (solver.solver.puzz === props.puzzle.name);
                    showStatus.value = true;
                } else if (props.type === 'status') {
                    stateStrA.value = props.puzzle.status;           
                    isMetaLoc.value = props.ismeta != 0 ? true : false;
                    answer.value = props.puzzle.answer !== null ? props.puzzle.answer : "";
                    
                    // Fetch last activity information
                    try {
                        const lastActUrl = `${Consts.api}/apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=lastact`;
                        let lastActData = await(await fetch(lastActUrl)).json();
                        if (lastActData.lastact && lastActData.lastact.time) {
                            const lastActDate = new Date(lastActData.lastact.time);
                            const now = new Date();
                            const diffMs = now - lastActDate;
                            if (diffMs >= 0) {
                                const diffSec = Math.floor(diffMs / 1000);
                                const hours = Math.floor(diffSec / 3600);
                                const minutes = Math.floor((diffSec % 3600) / 60);
                                const seconds = diffSec % 60;
                                lastActTime.value = `${hours}h ${minutes}m ${seconds}s ago`;

                                const activity = lastActData.lastact.type[0].toUpperCase() + lastActData.lastact.type.slice(1);
                                const solvers = props.solvers.filter(s => s.id === lastActData.lastact.solver_id);
                                const solver = solvers.length > 0 ? ` by ${solvers[0].name}`: '';
                                lastActInfo.value = `${activity}${solver},`;
                            }
                        } else {
                            lastActInfo.value = "";
                            lastActTime.value = "";
                        }
                    } catch (e) {
                        console.log("Failed to fetch lastact:", e);
                        lastActInfo.value = "";
                        lastActTime.value = "";
                    }
                } else if (props.type === 'tags') {
                    stateStrA.value = props.puzzle.tags ? props.puzzle.tags.split(",") : [];
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
                if ((props.type === 'note') || (props.type === 'comments')) {
                    what = 'comments';
                }

                if (props.type === 'workstate') what = 'xyzloc';
                if (props.type === 'status') what = 'status';
                if (props.type === 'tags') what = 'tags';

                const url = (props.type === 'comments') ?
                    `${Consts.api}/apicall.php?apicall=round&apiparam1=${props.puzzle.id}&apiparam2=${what}` :
                    `${Consts.api}/apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=${what}` ;

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
                        payload['answer'] = answer.value;
                        emitFetch = true;
                    }

                //
                // Tags have very special handling!
                //

                } else if (props.type === 'tags') {
                    const oldTags = props.puzzle.tags ? props.puzzle.tags.split(",") : [];
                    const addTags = stateStrA.value.filter(tag => !oldTags.includes(tag));
                    const removeTags = oldTags.filter(tag => !stateStrA.value.includes(tag));

                    try {
                        await Promise.all(addTags.map(async (tag) => {
                            payload[what] = {add: tag};
                            await fetch(url, {
                                method: 'POST',
                                body: JSON.stringify(payload),
                            });
                        }));
                        await Promise.all(removeTags.map(async (tag) => {
                            payload[what] = {remove: tag};
                            await fetch(url, {
                                method: 'POST',
                                body: JSON.stringify(payload),
                            });
                        }));
                        context.emit('please-fetch');
                    } catch (e) {
                        warning.value = "failed to POST; check devtools";
                        console.log(e);
                        showModal.value = true;
                    }
                } else if (stateStrA.value !== props.puzzle[what]) {
                    payload[what] = stateStrA.value;
                    emitFetch = true;
                }

                //
                // Hit the backend with the appropriate API parameters.
                //

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
                // it can be updated at the same time as status.
                //
                if (props.type === 'status' && (isMetaLoc.value !== (props.ismeta != 0 ? true : false ))) {
                    const url = `${Consts.api}/apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=ismeta`
                    try {
                        await fetch(url, {
                            method: 'POST',
                            body: JSON.stringify({ "ismeta": isMetaLoc.value }),
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
                context.emit('highlight-me', save ? 'saved' : 'closed');
            }
        }

        //
        // "Work state"-specific function. This function marks the user as
        // "currently working" on the given puzzle.
        //
        async function claimCurrentPuzzle() {

            const url = `${Consts.api}/apicall.php?apicall=solver&apiparam1=${props.uid}&apiparam2=puzz`
            
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
                context.emit('highlight-me', 'saved');
            }
        }

        function updateTags(tag, add) {
            if (tag === "") return;

            stateStrA.value = stateStrA.value.filter(stateTag => stateTag !== tag);
            if (add) {
                stateStrA.value.push(tag);
                nextTag.value = "";
            }
        }

        return {
            showModal, toggleModal, warning,
            stateStrA,
            answer, isMetaLoc, lastActInfo, lastActTime,
            nextTag, updateTags,
            showStatus, currentlyWorking, claimCurrentPuzzle
        };
    },
    mounted() {
        if ((this.initialpuzz) &&
            (this.puzzle.id === this.initialpuzz.puzz) &&
            (this.type === this.initialpuzz.what) &&
            (!this.showModal.value)) {

            this.toggleModal(false);
            this.$emit("route-shown");
        }
    },

    template: `
    <p class="puzzle-icon" ref="puzzle-tag" :title="description" @keydown.enter="toggleModal(false)" @click.stop="toggleModal(false)" tabindex="0">{{icon}}</p>
    <dialog v-if='showModal' open @click.stop @keydown.esc="toggleModal(false)">
        <h4>Editing {{type}} for {{puzzle.name}}:</h4>
        <p v-if="warning.length !== 0">{{warning}}</p>

        <!-- work state -->
        <p v-if="puzzle.solvers !== null && type === 'workstate'">All solvers: {{puzzle.solvers}}.</p>
                <p v-if="currentlyWorking && showStatus">You are currently working on this puzzle.</p>
        <p v-if="(!currentlyWorking) && showStatus">You are not marked as currently working on this puzzle. Would you like to be? <button @click="claimCurrentPuzzle">Yes</button></p>
        <p v-if="type === 'workstate'">Location: <input ref="modal-input" v-model="stateStrA"></input></p>

        <!-- note/comments -->
        <p v-if="type === 'note' || type === 'comments'"><textarea ref="modal-input" v-model="stateStrA" cols="40" rows="4"></textarea></p>

        <!-- tags (WIP) -->
        <p v-if="type === 'tags'">Current tags:</p>
        <ul v-if="type === 'tags'">
            <li
                v-for="tag in stateStrA"
                key="tag">
                {{tag}}
                <p
                    tabindex="0"
                    class="puzzle-icon"
                    title="remove"
                    @click="updateTags(tag, false)"
                    @keydown.enter="updateTags(tag, false)"
                >🗑️</p>
            </li>
        </ul>
        <p v-if="type === 'tags'">
            Add tag:
            <TagSelect
                ref="modal-input"
                v-model:current="nextTag"
                @complete-transaction="updateTags(nextTag, true)">
            </TagSelect>
            <span
                tabindex="0"
                class="puzzle-icon"
                title="add"
                @click="updateTags(nextTag, true)"
                @keydown.enter="updateTags(nextTag, true)"
            >➕</span>
        </p>

        <!-- status -->
        <p v-if="type === 'status'">
            <em v-if="puzzle.sheetcount">Sheets in spreadsheet: </em>
            {{puzzle.sheetcount ? puzzle.sheetcount : ''}}
            <br v-if="lastActTime"/>
            <em v-if="lastActTime">Last activity:</em>
            {{lastActInfo ? lastActInfo : ''}}
            <br v-if="lastActInfo"/>
            {{lastActTime ? lastActTime : ''}}
        </p>
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
        <button @click.stop="toggleModal(false)">Close</button>
        <button @click.stop="toggleModal(true)">Save</button>
    </dialog>
    `
  }
