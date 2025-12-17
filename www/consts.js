export default {
    "statuses": ['Solved', 'WTF', 'Critical', 'Being worked', 'Under control', 'New', 'Needs eyes', 'Grind', 'Waiting for HQ', 'Unnecessary'],

    //
    // Must be in the same order as statuses.
    //

    "emoji": ['✅', '☢️', '⚠️', '🙇', '🤝', '🆕', '👀', '⛏️', '⌛', '🙃'],

    //
    // We consider a round solved when all its metas have been solved.
    //

    isRoundSolved(round) {
        const metas = round.puzzles.filter(puzzle => puzzle.ismeta);
        return (metas.length > 0) &&
               (metas.filter(puzzle => puzzle.status !== 'Solved').length === 0);
        
    }
}