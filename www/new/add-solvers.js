import { ref, useTemplateRef } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'

export default {
    props: {
      puzzle: Object,
      uid: Number
    },
    computed: {
        icon() {
            if (this.puzzle.cursolvers !== null && this.puzzle.cursolvers.length !== 0) {
                return '👥';
            }

            if (this.puzzle.xyzloc !== null && this.puzzle.xyzloc.length !== 0) {
                return '📍';
            }

            return '👻';

        },
        description() {
            var desc = "This puzzle is being worked on";

            if (this.puzzle.xyzloc !== null && this.puzzle.xyzloc.length !== 0) {
                desc += ` at ${this.puzzle.xyzloc}`;
            }

            if (this.puzzle.cursolvers !== null && this.puzzle.cursolvers.length !== 0) {
                desc += ` by ${this.puzzle.cursolvers}`;
            }

            desc += '.';

            if(desc.length === "This puzzle is being worked on.".length) {
                desc = "No active location or solvers on this puzzle.";
            }

            return desc;
        }
    },
    emits: ['please-fetch', 'toggle-body'],
    setup(props, context) {

        //
        // This component has two pieces of state:
        //
        // showModal indicates whether the dialog box for this component is
        // currently visible to the user.
        //
        // xyzloc is a local copy of the puzzle's location, which shadows the
        // true version until a user decides to save their changes.
        //
        // warning displays if a POST fails for some reason.
        //
        const showModal = ref(false);
        const xyzloc = ref("");
        const warning = ref("");
        const showStatus = ref(false);
        const currentlyWorking = ref(false);

        //
        // Template ref to focus the textarea on selection.
        //
        const input = useTemplateRef('modal-input');

        //
        // This function toggles modal visibility. If save is true, as is the
        // case when the 'Save' button is selected, then the value is submitted
        // to the back-end if it has been updated.
        //
        async function toggleModal(save) {
            showModal.value = !showModal.value;
            warning.value = "";
            showStatus.value = false;
            
            if (showModal.value) {
                //
                // TODO: Maybe force a load of the puzzle here for freshness,
                //       but not hugely urgent IMO.
                //
                // Alternatively, warn the user if the comments have been
                // updated on the back-end while they're performing the update.
                // I suspect this will not be a huge issue either way.
                //

                xyzloc.value = props.puzzle.xyzloc;

                const url = `https://importanthuntpoll.org/pb/apicall.php?&apicall=solver&apiparam1=${props.uid}`
                let solver = await(await fetch(url)).json();

                showStatus.value = true;

                currentlyWorking.value = (solver.solver.puzz === props.puzzle.name);

                //
                // N.B. A number of other factors may keep us from successfully
                //      focusing the input right away - the input may not have
                //      rendered yet, or the click will have refocused the
                //      browser back to the <p> tag. The `autofocus` tag, for
                //      whatever reason, works only once. Instead, we'll do the
                //      typical trick of "just do it in a little bit and it
                //      should work most of the time."
                //

                setTimeout(() => { input.value.focus(); }, 100);
            } else if (save) {


                //
                // Write the data to the backend.
                //

                const url = `https://importanthuntpoll.org/pb/apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=xyzloc`
                
                if(xyzloc.value !== props.puzzle.xyzloc) {
                    
                    try {
                        await fetch(url, {
                            method: 'POST',
                            body: JSON.stringify({ "xyzloc": xyzloc.value }),
                        });

                        context.emit('please-fetch');

                    } catch (e) {
                        warning.value = "failed to POST; check devtools";
                        console.log(e);
                        showModal.value = true;
                    }
                }

            }
        }

        async function claimCurrentPuzzle() {

            //
            // Write the data to the backend.
            //

            const url = `https://importanthuntpoll.org/pb/apicall.php?apicall=solver&apiparam1=${props.uid}&apiparam2=puzz`
            
            
            try {
                await fetch(url, {
                    method: 'POST',
                    body: JSON.stringify({ "puzz": props.puzzle.id }),
                });

                context.emit('please-fetch');
                showModal.value = false;

            } catch (e) {
                warning.value = "failed to POST; check devtools";
                console.log(e);
            }


        }

        return {
            showModal, toggleModal, warning,
            xyzloc,
            showStatus, currentlyWorking, claimCurrentPuzzle
        };
    },

    template: `
    <p :title="description" @click.prevent="toggleModal(false)">{{icon}}</p>
    <dialog v-if='showModal' open>
        <h4>Work log for {{puzzle.name}}:</h4>
        <p>{{description}}</p>
        <p v-if="puzzle.solvers !== null">All solvers: {{puzzle.solvers}}.</p>
        <p v-if="warning.length !== 0">{{warning}}</p>
        <p v-if="currentlyWorking && showStatus">You are currently working on this puzzle.</p>
        <p v-if="(!currentlyWorking) && showStatus">You are not marked as currently working on this puzzle. Would you like to be? <button @click="claimCurrentPuzzle">Yes</button></p>
        <p>Location: <input ref="modal-input" v-model="xyzloc"></input></p>
        <button @click="toggleModal(false)">Close</button>
        <button @click="toggleModal(true)">Save</button>
    </dialog>
    `
  }
  
