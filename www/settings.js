import Consts from './consts.js'

export default {
    props: {
      s: Object,
      statuses: Array
    },
    computed: {
        puzzleFilterKeys() {
            // Use passed statuses prop - component won't render until statuses are loaded
            // Filter out [hidden] since it has its own separate checkbox
            return this.statuses.filter(status => status !== '[hidden]');
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
            // Use passed statuses prop - component won't render until statuses are loaded
            const pf = Object.fromEntries(props.statuses.map((status) => [status, which]));
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
        <div class="toggle-row pills">
            <label :class="{ on: !s.spoilAll }" @click.prevent="$emit('settings-updated', 'spoilAll', !s.spoilAll)">No spoilers</label>
            <label :class="{ on: s.sortPuzzles }" @click.prevent="$emit('settings-updated', 'sortPuzzles', !s.sortPuzzles)"> Sort by status</label>
            <label :class="{ on: s.showSolvedRounds }" @click.prevent="$emit('settings-updated', 'showSolvedRounds', !s.showSolvedRounds)"> Solved rounds</label>
            <label :class="{ on: s.showControls }" @click.prevent="$emit('settings-updated', 'showControls', !s.showControls)">Advanced</label>
        </div>
        <template v-if="s.showControls">
        <hr class="controls-divider" />
        <div id="detailed-controls">
            <div class="controls-section">
                <div
                    v-for="key in puzzleFilterKeys"
                    class="filter"
                    :class="{ active: s.puzzleFilter[key] }"
                    @click="toggleKey(key)"
                    >
                    {{key}} <input type="checkbox" :checked="s.puzzleFilter[key]" @change="toggleKey(key)" @click.stop/>
                </div>
                <span class="filter-action-group">
                    <div class="filter filter-action" @click="applyShowFilter(false)">Hide All</div>
                    <div class="filter filter-action" @click="applyShowFilter(true)">Show All</div>
                </span>
            </div>
            <hr class="controls-divider" />
            <div class="toggle-row pills">
                <label :class="{ on: !s.showTags }" @click.prevent="$emit('settings-updated', 'showTags', !s.showTags)">Hide Tags</label>
                <label :class="{ on: s.showHidden }" @click.prevent="$emit('settings-updated', 'showHidden', !s.showHidden)">Show Hidden Puzzles</label>
                <label :class="{ on: s.useColumns }" @click.prevent="$emit('settings-updated', 'useColumns', !s.useColumns)">Column Mode</label>
                <label>Scroll speed <input type="number" :value="s.scrollSpeed" @input="$emit('settings-updated', 'scrollSpeed', parseFloat($event.target.value))" min="1" style="width: 50px;"></label>
                <slot></slot>
            </div>
        </div>
        </template>
    </div>`
  }
  
