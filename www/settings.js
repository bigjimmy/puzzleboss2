import Consts from './consts.js'

export default {
    props: {
      s: Object
    },
    computed: {
        puzzleFilterKeys() {
            return Consts.statuses;
        }
    },
    emits: ['settings-updated'],
    setup(props, context) {

        //
        // This function toggles the filters for a given key (i.e., 
        // a status of puzzles).
        //
        function toggleKey(k) {
            const pf = Object.assign({}, props.s.puzzleFilter);
            pf[k] = !pf[k];
            context.emit('settings-updated', 'puzzleFilter', pf);
        }

        //
        // This function implements hide/show all functionality for
        // puzzles by filling the puzzleFilter object as appropriate.
        //
        function applyShowFilter(which) {
            const pf = Object.fromEntries(Consts.statuses.map((status) => [status, which]));
            context.emit('settings-updated', 'puzzleFilter', pf);
        }

        return {
            toggleKey, applyShowFilter, 
        }
    },

    //
    // N.B. The structure of this template is laid out in pb-ui.css.
    //

    template: `
    <div id="control-bar">
        <p>Spoil all puzzles: <input type="checkbox" :checked="s.spoilAll" @change="$emit('settings-updated', 'spoilAll', !s.spoilAll)" /> |
           Sort puzzles by status: <input type="checkbox" :checked="s.sortPuzzles" @change="$emit('settings-updated', 'sortPuzzles', !s.sortPuzzles)" /> |
           Show tags: <input type="checkbox" :checked="s.showTags" @change="$emit('settings-updated', 'showTags', !s.showTags)" /> &nbsp; &nbsp; &nbsp;
           <button @click="$emit('settings-updated', 'showControls', !s.showControls)">{{s.showControls ? 'Hide ' : 'Show '}}advanced controls</button>
        </p>
        <div v-if="s.showControls" id="detailed-controls"> 
        <div>
            Show puzzles:
            <div
                v-for="key in puzzleFilterKeys"
                class="filter"
                @click="toggleKey(key)"
                >
                {{key}} <input type="checkbox" :checked="s.puzzleFilter[key]" @change="toggleKey(key)" @click.stop/>
            </div>
            <button @click="applyShowFilter(false)">Hide All Puzzles</button>
            <button @click="applyShowFilter(true)">Show All Puzzles</button>
        </div>
        <br/>
        <div>
            <p>Use columns display (fixed-height, scroll-to-right) <input type="checkbox" :checked="s.useColumns" @change="$emit('settings-updated', 'useColumns', !s.useColumns)"></input></p>
            <p>Scroll speed (default 1) <input type="number" :value="s.scrollSpeed" @input="$emit('settings-updated', 'scrollSpeed', parseFloat($event.target.value))" min="1"></input></p>
        </div>
        <div>
        </div>
    </div>`
  }
  
