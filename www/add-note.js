import { ref, useTemplateRef } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'

export default {
    props: {
      puzzle: Object
    },
    emits: ['please-fetch', 'toggle-body'],
    setup(props, context) {

        //
        // This component has two pieces of state:
        //
        // showModal indicates whether the dialog box for this component is
        // currently visible to the user.
        //
        // comments is a local copy of the puzzle's comments, which shadows the
        // true version until a user decides to save their changes.
        //
        // warning displays if a POST fails for some reason.
        //
        const showModal = ref(false);
        const comments = ref("");
        const warning = ref("");

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
            
            if (showModal.value) {
                //
                // TODO: Maybe force a load of the puzzle here for freshness,
                //       but not hugely urgent IMO.
                //
                // Alternatively, warn the user if the comments have been
                // updated on the back-end while they're performing the update.
                // I suspect this will not be a huge issue either way.
                //

                comments.value = props.puzzle.comments;

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

                const url = `./apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=comments`
                
                if(comments.value !== props.puzzle.comments) {
                    
                    try {
                        await fetch(url, {
                            method: 'POST',
                            body: JSON.stringify({ "comments": comments.value }),
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

        return {
            showModal, toggleModal, warning,
            comments
        };
    },

    template: `
    <p :title="puzzle.comments == null ? 'add note' : puzzle.comments " @click.prevent="toggleModal(false)">{{puzzle.comments == null ? '➕' : 'ℹ️'}}</p>
    <dialog v-if='showModal' open>
        <h4>Editing note for {{puzzle.name}}:</h4>
        <p>{{warning}}</p>
        <textarea ref="modal-input" v-model="comments"></textarea><br/>
        <button @click="toggleModal(false)">Close</button>
        <button @click="toggleModal(true)">Save</button>
    </dialog>
    `
  }
  
