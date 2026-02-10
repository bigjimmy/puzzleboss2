import { onFetchSuccess, onFetchFailure } from './pb-utils.js';

// Status data - must be loaded from huntinfo, no fallback
let statusData = [];

// Fetch huntinfo on module load - REQUIRED for app to function
fetch('./apicall.php?apicall=huntinfo')
    .then(r => r.json())
    .then(data => {
        if (data.statuses && Array.isArray(data.statuses)) {
            statusData = data.statuses;
            onFetchSuccess();
        } else {
            console.error('huntinfo did not return valid statuses array');
        }
    })
    .catch(e => {
        onFetchFailure();
        console.error('FATAL: Failed to load huntinfo for status metadata:', e);
    });

export default {
    // Status names in display order
    get statuses() {
        return statusData.map(s => s.name);
    },

    // Emoji array (parallel to statuses)
    get emoji() {
        return statusData.map(s => s.emoji);
    },

    // Get emoji for a specific status name
    getEmoji(name) {
        const s = statusData.find(x => x.name === name);
        return s ? s.emoji : '❓';
    },

    // Get text code for a specific status name
    getText(name) {
        const s = statusData.find(x => x.name === name);
        return s ? s.text : '?';
    },

    //
    // We consider a round solved when all its metas have been solved.
    //

    isRoundSolved(round) {
        const metas = round.puzzles.filter(puzzle => puzzle.ismeta);
        return (metas.length > 0) &&
               (metas.filter(puzzle => puzzle.status !== 'Solved').length === 0);

    },

    //
    // List of available settings.
    //

    "settings": ["puzzleFilter", "useColumns", "scrollSpeed", "sortPuzzles", "showControls", "spoilAll", "showTags", "showHidden", "showSolvedRounds"],

    //
    // Default values of available settings.
    //

    get defaults() {
        return [
            // puzzleFilter - all statuses visible except [hidden]
            Object.fromEntries(this.statuses.map((status) => [status, status !== '[hidden]'])),
            // useColumns
            false,
            // scrollSpeed
            1,
            // sortPuzzles
            true,
            // showControls
            false,
            // spoilAll
            true,
            // showTags
            true,
            // showHidden
            false,
            // showSolvedRounds
            false
        ];
    },

    "api": ".",
}
