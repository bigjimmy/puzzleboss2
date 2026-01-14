const statuses = ['WTF', 'Critical', 'Needs eyes', 'Being worked', 'Under control', 'New', 'Grind', 'Waiting for HQ', 'Solved', 'Unnecessary'];
export default {
    statuses,

    //
    // Must be in the same order as statuses.
    //

    "emoji": ['☢️', '⚠️', '👀', '🙇', '🤝', '🆕', '⛏️', '⌛', '✅', '🙃'],

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

    "settings": ["puzzleFilter", "useColumns", "scrollSpeed", "sortPuzzles", "showControls", "spoilAll", "showTags"],

    //
    // Default values of available settings.
    //

    "defaults": [
        // puzzleFilter
        Object.fromEntries(statuses.map((status) => [status, true])),
        // useColumns
        false,
        // scrollSpeed
        1,
        // sortPuzzles
        true,
        // showControls
        false,
        // spoilAll
        false,
        // showTags
        true],

    "api": ".",
}