import { ref, watch, watchEffect } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
import AddGeneric from './add-generic.js'
import Consts from './consts.js'

export default {
    props: {
      round: Object,
      showbody: Boolean,
      tagfilter: String,
      puzzlefilter: Object,
      highlighted: Boolean,
      pfk: Object,
      scrollspeed: Number,
      sortpuzzles: Boolean,
      currpuzz: String,
      uid: Number,
      solvers: Object,
      spoil: Boolean,
    },
    emits: ['please-fetch'],
    computed: {

        //
        // This function returns the puzzles which should be displayed based on
        // current filters. 
        //
        filteredPuzzles() {
            const fp = this.round.puzzles.filter(puzzle => this.puzzlefilter[puzzle.status])
                                         .filter(puzzle => !this.tagfilter || (puzzle.tags && puzzle.tags.includes(this.tagfilter)));

            if(!this.sortpuzzles) return fp;

            function pri(puzzle) {
                if (puzzle.ismeta) return -1;

                return Consts.statuses.indexOf(puzzle.status);
            }

            return [...fp].sort((a, b) => {
                return pri(a) - pri(b);
            });
        },
       
        //
        // This function returns the number of puzzles hidden by current
        // filters.
        //
        hiddenCount() {
            return this.round.puzzles.length - 
                this.round.puzzles.filter(puzzle => this.puzzlefilter[puzzle.status])
                                  .filter(puzzle => !this.tagfilter || (puzzle.tags && puzzle.tags.includes(this.tagfilter))).length;
        },

        isSolved() {
            return Consts.isRoundSolved(this.round);
        }
    },
    components: {
       AddGeneric
    },
    setup(props) {

        //
        // This component contains five pieces of state:
        //
        // spoilRound indicates whether or not to display all answers from the
        // given round.
        //
        // scrolling indicates whether the puzzle title is currently scrolling
        // by way of storing the timer for the animation.
        //
        // solved and open are the solved and open puzzle counts for the round,
        // respectively.
        //
        // highlightedPuzzle indicates puzzles which should be highlighted
        // because we just closed a modal associated with it from AddGeneric.
        //

        const spoilRound = ref(false);
        const solved = ref(0);
        const open = ref(0);
        const scrolling = ref(null);
        const highlightedPuzzle = ref({});

        //
        // This function toggles the spoilRound state.
        //
        function toggleSpoil() {
            spoilRound.value = !spoilRound.value;
        }

        //
        // This function scrolls the puzzle title by incrementing scrollLeft.
        //
        function scroll(event, delay) {
            const ct = event.currentTarget;

            //
            // There should only ever be one timer assigned to scrolling.value,
            // but there's definitely a risk of a race condition when the timer
            // has fired, then clearInterval happens on the expired timer, and
            // then a new timer is set. This state should become consistent
            // again when the user hovers/unhovers, but in any case, it's not
            // enough of a risk or problem to be fixed. We skip the timeout
            // when delay is zero though, just in case.
            //
            // N.B. We're clearing a setTimeout with clearInterval. MDN notes:
            //      "It's worth noting that the pool of IDs used by
            //       setInterval() and setTimeout() are shared, which means you
            //       can technically use clearInterval() and clearTimeout()
            //       interchangeably." The more you know.
            //
            if (delay != 0) {
                scrolling.value = setTimeout(() => {
                    scrolling.value = setInterval(() => {
                        ct.scrollLeft += props.scrollspeed;
                    }, 10);
                }, delay);
            } else {
                scrolling.value = setInterval(() => {
                    ct.scrollLeft += props.scrollspeed;
                }, 10);
            }
        }

        //
        // This function cancels the increment and resets the scroll.
        //
        function stopscroll(event) {
            if(scrolling.value !== null) clearInterval(scrolling.value);
            event.currentTarget.scrollLeft = 0;
            scrolling.value = null;
        }

        //
        // This function highlights a puzzle with a given puzzle id (and
        // fires a timer to unhighlight it).
        //
        function highlight(pid, state) {
            highlightedPuzzle.value[pid] = state;
            setTimeout(
                () => {highlightedPuzzle.value[pid] = false}, 750);
        }

        //
        // This function should re-calculate the open/solved values whenever
        // we get an update from the PB API.
        //
        watchEffect(() => {
            open.value = props.round.puzzles.length;
            solved.value = props.round.puzzles.filter(puzzle => {
                return puzzle.status === "Solved";
            }).length;
        });

        return {
            spoilRound, toggleSpoil,
            open, solved,
            scroll, stopscroll, highlight, highlightedPuzzle
        }
    },

    //
    // N.B. The structure of this template is laid out in pb-ui.css.
    //

    template: `
    <div class = "round">
        <div :class = "{'round-header': true, 'solved': isSolved, 'highlighted': highlighted}" @click="$emit('toggle-body', round.id);">
            <p v-if="showbody" class="puzzle-icon">▼</p>
            <p v-if="!showbody" class="puzzle-icon">▶</p>
            <h3 @mouseover="scroll($event, 0)" @mouseout="stopscroll">{{round.name}}</h3>

            <!-- spoiled layout -->
            <p v-if="spoil">({{solved}} solved / {{open}} open)</p>
            <div class="round-header-icons" v-if="spoil">
                <p class="puzzle-icon"><a title='drive folder' :href='round.drive_uri' target="_blank" @click.stop>📂</a></p>
                <AddGeneric type="comments" :puzzle='round' @please-fetch="$emit('please-fetch')"></AddGeneric>
            </div>

            <!-- unspoiled layout -->
            <div class="round-header-column" v-if="!spoil">
                <p>({{solved}} solved / {{open}} open)</p>
                <div class="round-header-icons">
                    <p class="puzzle-icon"><a title='drive folder' :href='round.drive_uri' target="_blank" @click.stop>📂</a></p>
                    <AddGeneric type="comments" :puzzle='round' @please-fetch="$emit('please-fetch')"></AddGeneric>
                </div>
            </div>
            <button v-if="showbody && !spoil" @click.stop="toggleSpoil">{{ spoilRound ? 'Hide' : 'Show' }} Spoilers</button>
        </div>
        <div :class = "{'round-body': true, hiding: !showbody}">
            <div
                v-for='puzzle in filteredPuzzles'
                :key='puzzle.id'
                :class="'puzzle' + (puzzle.ismeta ? ' meta ' : ' ') + (currpuzz === puzzle.name ? ' currpuzz ' : ' ') + puzzle.status.toLowerCase().replace(' ', '') + (highlightedPuzzle[puzzle.id] ? ' ' + highlightedPuzzle[puzzle.id] : '')">
                <div class="puzzle-icons">
                    <AddGeneric type="status" :puzzle='puzzle' :ismeta='puzzle.ismeta' :pfk='pfk' @please-fetch="$emit('please-fetch')" @highlight-me="(s) => highlight(puzzle.id, s)" :solvers="solvers"></AddGeneric>
                    <AddGeneric type="work state" :puzzle='puzzle' @please-fetch="$emit('please-fetch')" :uid="uid" @highlight-me="(s) => highlight(puzzle.id, s)"></AddGeneric>
                    <p :class="{'meta': puzzle.ismeta, 'puzzle-name': true}" @mouseover="scroll($event, 0)" @mouseout="stopscroll"><a :href='puzzle.puzzle_uri' target="_blank">{{puzzle.name}}</a></p>
                    <p class="puzzle-icon"><a title='spreadsheet' :href='puzzle.drive_uri' target="_blank">🗒️</a></p>
                    <p class="puzzle-icon"><a title='discord' :href='puzzle.chat_channel_link' target="_blank">🗣️</a></p>
                    <AddGeneric type="note" :puzzle='puzzle' @please-fetch="$emit('please-fetch')" @highlight-me="(s) => highlight(puzzle.id, s)"></AddGeneric>
                    <AddGeneric type="tags" :puzzle='puzzle' @please-fetch="$emit('please-fetch')" @highlight-me="(s) => highlight(puzzle.id, s)"></AddGeneric>
                </div>
                <p 
                    v-if = "puzzle.answer === null"
                    :class = "{'answer': true, 'spoil': true}">
                    {{ puzzle.name === currpuzz ? 'CURRENT PUZZLE'.padStart(16) : "".padStart(16) }}
                </p>
                <p 
                    v-if = "puzzle.answer !== null"
                    :class = "{'answer': true, 'spoil': spoil || spoilRound, 'done': true}" @mouseover="scroll($event, 300)" @mouseout="stopscroll">
                    {{ puzzle.answer.padStart(16) }}
                </p>
            </div>
            <div
                v-if="hiddenCount > 0"
                class="puzzle">
                <p><i>
                    {{hiddenCount == this.round.puzzles.length ? "No applicable puzzles (" : ""}}{{hiddenCount}}
                    {{hiddenCount == this.round.puzzles.length ? "" : "puzzles"}} hidden by
                    filters{{hiddenCount == this.round.puzzles.length ? ").": "."}}
                    </i></p>
            </div>
        </div>
    </div>  `
  }
  
