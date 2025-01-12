import { ref, watch, watchEffect } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
import AddNote from './add-note.js'
import AddStatus from './add-status.js'
import AddSolvers from './add-solvers.js'

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
       AddNote,
       AddStatus,
       AddSolvers
    },
    setup(props) {

        //
        // This component contains four pieces of state:
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

        const spoilAll = ref(false);
        const solved = ref(0);
        const open = ref(0);
        const scrolling = ref(null);

        //
        // This function toggles the spoilAll state.
        //
        function toggleSpoil() {
            spoilAll.value = !spoilAll.value;
        }

        //
        // This function scrolls the puzzle title by incrementing scrollLeft.
        //
        function scroll(event) {
            const ct = event.currentTarget;
            scrolling.value = setInterval(() => {
                ct.scrollLeft += props.scrollspeed;
            }, 10);
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
            scroll, stopscroll
        }
    },

    //
    // N.B. The structure of this template is laid out in pb-ui.css.
    //

    template: `
    <div class = "round">
        <div :class = "{'round-header': true, 'solved': isSolved, 'highlighted': highlighted}" @click="$emit('toggle-body', round.id);">
            <h3>{{round.name}}</h3>
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
                :class="'puzzle' + (round.meta_id === puzzle.id ? ' meta ' : ' ') + (currpuzz === puzzle.name ? ' currpuzz ' : ' ') + puzzle.status.toLowerCase().replace(' ', '')">
                <div class="puzzle-icons">
                    <AddStatus :puzzle='puzzle' :ismeta='round.meta_id === puzzle.id' :pfk='pfk' @please-fetch="$emit('please-fetch')"></AddStatus>
                    <p :class="{'meta': round.meta_id === puzzle.id, 'puzzle-name': true}" @mouseover="scroll" @mouseout="stopscroll"><a :href='puzzle.puzzle_uri' target="_blank">{{puzzle.name}}</a></p>
                    <p><a title='spreadsheet' :href='puzzle.drive_uri' target="_blank">🗒️</a></p>
                    <p><a title='discord' :href='puzzle.chat_channel_link' target="_blank">🗣️</a></p>
                    <AddSolvers :puzzle='puzzle' @please-fetch="$emit('please-fetch')" :uid="uid"></AddSolvers>
                    <AddNote :puzzle='puzzle' @please-fetch="$emit('please-fetch')"></AddNote>
                </div>
                <p 
                    v-if = "puzzle.answer === null"
                    :class = "{'answer': true, 'spoil': true}">
                    {{ puzzle.name === currpuzz ? 'CURRENT PUZZLE'.padStart(16) : "".padStart(16) }}
                </p>
                <p 
                    v-if = "puzzle.answer !== null"
                    :class = "{'answer': true, 'spoil': spoilAll, 'done': true}" @mouseover="scroll" @mouseout="stopscroll">
                    {{ puzzle.answer.padStart(16) }}
                </p>
            </div>
        </div>
    </div>  `
  }
  
