export default {
    "statuses": ['WTF', 'Critical', 'Needs eyes', 'Being worked', 'Under control', 'New', 'Grind', 'Waiting for HQ', 'Solved', 'Unnecessary'],

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

    "api": ".",
}