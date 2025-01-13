import { ref, watch, useTemplateRef } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'

export default {
    props: {
      puzzle: Object,
      ismeta: Boolean,
      pfk: Object
    },
    emits: ['please-fetch'],
    computed: {
        calculateIcon() {
            if (this.ismeta) return 'Ⓜ️'
            switch(this.puzzle.status) {
            case 'New':
                return '🆕'
                
            case 'Being worked':
                return '🙇'
                
            case 'Unnecessary':
                return '😶‍🌫️'

            case 'WTF':
                return '☢️'

            case 'Critical':
                return '⚠️'

            case 'Solved':
                return '✅'
                
            case 'Needs eyes':
                return '👀'

            default:
                return '🤡'
            }
        }
    },
    setup(props, context) {

        //
        // This component has five pieces of state:
        //
        // showModal indicates whether the dialog box for this component is
        // currently visible to the user.
        //
        // status and answer are local copies of the puzzle's status/answer,
        // which shadow the true version until a user decides to save their
        // changes.
        //
        // isMetaLoc performs a similar role for the "is meta" checkbox, which
        // behaves slightly differently (since "is meta" is a property of the
        // round object).
        // 
        // warning is used for input validation.
        //

        const showModal = ref(false);
        const status = ref("");
        const answer = ref("");
        const warning = ref("");
        const isMetaLoc = ref(false);

        //
        // Template ref to focus the select on selection.
        //
        const input = useTemplateRef('modal-input');

        //
        // Force answers to be all uppercase.
        //

        watch(answer, () => {
            answer.value = answer.value.toUpperCase();
        });

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
                // Alternatively, warn the user if the status has been updated
                // on the back-end while they're performing the update. I
                // suspect this will not be a huge issue either way.
                //

                status.value = props.puzzle.status;
                answer.value = props.puzzle.answer !== null ? props.puzzle.answer : "";
                isMetaLoc.value = props.ismeta;
                if (props.puzzle.status === 'Solved') {
                    warning.value = `If you're sure you want to change a solved puzzle's status,
                                     click the gear to use the old PB interface.`               
                }

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
                // If we're solved, just write the answer. Otherwise, write the
                // status if updated.
                //
                // TODO: Consider disabling updates if puzzle is solved.
                //

                let emitFetch = false;
                
                if (status.value === 'Solved') {
                    if (answer.value === '') {
                        showModal.value = true;
                        warning.value = "ANSWER IS BLANK!!!"

                    } else if (answer.value !== props.puzzle.answer && answer.value !== null) {

                        //
                        // N.B. This is ugly but we'll live.
                        //

                        const url = `./apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=answer`
                        
                        try {
                            await fetch(url, {
                                method: 'POST',
                                body: JSON.stringify({ "answer": answer.value }),
                            });

                            emitFetch = true;

                        } catch (e) {
                            warning.value = "failed to POST; check devtools";
                            console.log(e);
                            showModal.value = true;
                        }
                    }

                } else {
                    if (status.value !== props.puzzle.status) {

                        const url = `./apicall.php?apicall=puzzle&apiparam1=${props.puzzle.id}&apiparam2=status`

                        try {
                            await fetch(url, {
                                method: 'POST',
                                body: JSON.stringify({ "status": status.value }),
                            });

                            emitFetch = true;

                        } catch (e) {
                            warning.value = "failed to POST; check devtools";
                            console.log(e);
                            showModal.value = true;
                        }
                    }
                }

                if (isMetaLoc.value ^ props.ismeta) {

                    const url = `./apicall.php?apicall=round&apiparam1=${props.puzzle.round_id}&apiparam2=meta_id`

                    try {
                        await fetch(url, {
                            method: 'POST',
                            body: JSON.stringify({ "meta_id": isMetaLoc.value ? props.puzzle.id : null }),
                        });

                        emitFetch = true;

                    } catch (e) {

                        warning.value = "failed to POST; check devtools";
                        isMetaLoc.value = props.ismeta;
                        console.log(e);
                        showModal.value = true;
                    }

                }

                if(emitFetch) context.emit('please-fetch');

            }
        }

        return {
            showModal, toggleModal,
            status, answer, warning, isMetaLoc
        };
    },

    template: `
    <p :title="puzzle.status + ((puzzle.xyzloc === null || puzzle.xyzloc.length === 0) ? '' : ' at #' + puzzle.xyzloc)" @click.prevent="toggleModal(false)">{{calculateIcon}}</p>
    <dialog v-if='showModal' open>
        <h4>Editing status for {{puzzle.name}}:</h4>
        <p>{{warning}}</p>
        <p>Is Meta: <input type="checkbox" v-model="isMetaLoc"></input></p>
        <p> Status:
            <select ref="modal-input" class="dropdown" v-model="status" :disabled="puzzle.status === 'Solved'">
                <option
                    v-for = "k in pfk"
                    :key = "k"
                    :value = "k">
                    {{k}}
                    </option>
            </select>
        </p>
        <p v-if="status === 'Solved'">Answer: <input v-model = "answer"></input></p>
        <button @click="toggleModal(false)">Close</button>
        <button @click="toggleModal(true)">Save</button>
    </dialog>
    `
  }
  
