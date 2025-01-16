import { ref, watch, watchEffect } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
import AddGeneric from './add-generic.js'

export default {
    props: {
      round: Object,
      showbody: Boolean,
      puzzlefilter: Object,
      highlighted: Boolean,
      pfk: Object,
      scrollspeed: Number,
      sortpuzzles: Boolean,
      currpuzz: String,
      uid: Number
    },
    emits: ['please-fetch'],
    computed: {

        //
        // This function returns the puzzles which should be displayed based on
        // current filters. 
        //
        filteredPuzzles() {
            const fp = this.round.puzzles.filter(puzzle => this.puzzlefilter[puzzle.status]);
            if(!this.sortpuzzles) return fp;

            const meta_id = this.round.meta_id;

            function pri(puzzle) {
                if (meta_id === puzzle.id) return -1;

                return ['Critical', 'Needs eyes', 'WTF', 'Being worked', 'New', 'Unnecessary', 'Solved'].indexOf(puzzle.status);
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
            return this.round.puzzles.filter(puzzle => !this.puzzlefilter[puzzle.status]).length;
        },
       
        //
        // This function calculates whether the meta has been solved.
        //
        isSolved() {

            return this.round.puzzles.filter(puzzle => puzzle.status === 'Solved')
                                     .filter(puzzle => puzzle.id === this.round.meta_id)
                                     .length > 0; 

        }
    },
    components: {
       AddGeneric
    },
    setup(props) {

        //
        // This component contains five pieces of state:
        //
        // spoilAll indicates whether or not to display all answers from the
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

        const spoilAll = ref(false);
        const solved = ref(0);
        const open = ref(0);
        const scrolling = ref(null);
        const highlightedPuzzle = ref({});

        //
        // This function toggles the spoilAll state.
        //
        function toggleSpoil() {
            spoilAll.value = !spoilAll.value;
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
        function highlight(pid) {
            highlightedPuzzle.value[pid] = true;
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
            spoilAll, toggleSpoil,
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
            <p>({{solved}} solved / {{open}} open)</p>
            <button v-if="showbody" @click.stop="toggleSpoil">{{ spoilAll ? 'Hide' : 'Show' }} Spoilers</button>
        </div>
        <div :class = "{'round-body': true, hiding: !showbody}">
            <div
                v-if="hiddenCount > 0"
                class="puzzle">
                <p><i>{{hiddenCount}} puzzles hidden by filters.</i></p>
            </div>
            <div
                v-for='puzzle in filteredPuzzles'
                :key='puzzle.id'
                :class="'puzzle' + (round.meta_id === puzzle.id ? ' meta ' : ' ') + (currpuzz === puzzle.name ? ' currpuzz ' : ' ') + puzzle.status.toLowerCase().replace(' ', '') + (highlightedPuzzle[puzzle.id] === true ? ' highlighted' : '')">
                <div class="puzzle-icons">
                    <AddGeneric type="status" :puzzle='puzzle' :ismeta='round.meta_id === puzzle.id' :pfk='pfk' @please-fetch="$emit('please-fetch')" @highlight-me="highlight(puzzle.id)"></AddGeneric>
                    <AddGeneric type="work state" :puzzle='puzzle' @please-fetch="$emit('please-fetch')" :uid="uid" @highlight-me="highlight(puzzle.id)"></AddGeneric>
                    <p :class="{'meta': round.meta_id === puzzle.id, 'puzzle-name': true}" @mouseover="scroll($event, 0)" @mouseout="stopscroll"><a :href='puzzle.puzzle_uri' target="_blank">{{puzzle.name}}</a></p>
                    <p class="puzzle-icon"><a title='spreadsheet' :href='puzzle.drive_uri' target="_blank">🗒️</a></p>
                    <p class="puzzle-icon"><a title='discord' :href='puzzle.chat_channel_link' target="_blank">🗣️</a></p>
                    <AddGeneric type="note" :puzzle='puzzle' @please-fetch="$emit('please-fetch')" @highlight-me="highlight(puzzle.id)"></AddGeneric>
                </div>
                <p 
                    v-if = "puzzle.answer === null"
                    :class = "{'answer': true, 'spoil': true}">
                    {{ puzzle.name === currpuzz ? 'CURRENT PUZZLE'.padStart(16) : "".padStart(16) }}
                </p>
                <p 
                    v-if = "puzzle.answer !== null"
                    :class = "{'answer': true, 'spoil': spoilAll, 'done': true}" @mouseover="scroll($event, 300)" @mouseout="stopscroll">
                    {{ puzzle.answer.padStart(16) }}
                </p>
            </div>
        </div>
    </div>  `
  }
  
