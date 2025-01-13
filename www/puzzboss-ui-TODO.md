feature requests

- [general] quick-add note functionality (need to make an API call to the backend)
- [general] quick-update status functionality (should be similar to quick-add note)
- [ayz] THIS IS A DUMB FEATURE but I really want a "play a custom, locally-stored noise when the number of solved puzzles goes up".
- [mehtank] what happens with rounds of drastically varying lengths? (alan: I forget. hunts like doing stupid things like Hydra/Infinite.)

finishing touches:
- maybe put emoji in the filter row? might be too cluttered
- emoji in the "n puzzles filtered" to indicate round status. actually, a round status would generally be good... but clutter
- additional colors for different status, probably

testing:

- needs testing on Firefox
- needs testing on Safari
- needs testing on mobile (not a priority)

bugs: 

done:

- [general] display location where the puzzle is being worked on, if any (in hover text on status)
- [mehtank] day of week in header
- [general] filter by puzzle status (global checkboxes, pass the state down to the Round component and filter at the puzzle level with a v-if)
- [general] persist filter state across refreshes
- [mehtank] all collapsed rounds get stacked up in a single column somewhere (alan: this should be easy to do given that showBody lives in the main component.)
- hovers on the discord link, the sheets link, the puzzle link, and the status icon
- needs testing with actual PB backend (ask Benoc to specify a CORS policy of '*')
- need to get rid of this max-height transition (pb-ui.css .hideable) or make it cleverer... it's almost certainly going to screw us at some point because it sets a maximum height. (replaced with a highlight)