import { ref } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'
import Consts from './consts.js'

//
// Shared hint submission form used by both status.php (inside a <dialog>)
// and add-generic.js (inline in the status editing modal).
//
// Props supply the puzzle context and queue size; emits notify the parent
// on submit/cancel so it can close the container and refresh data.
//

export default {
    props: {
        puzzleName: String,
        puzzleId: Number,
        username: String,
        queueSize: Number
    },
    emits: ['submitted', 'cancelled'],
    setup(props, { emit }) {
        const hintText = ref('')

        async function submit() {
            if (!hintText.value.trim()) return
            try {
                await fetch(`${Consts.api}/apicall.php?apicall=hints`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        puzzle_id: props.puzzleId,
                        solver: props.username,
                        request_text: hintText.value.trim()
                    })
                })
                hintText.value = ''
                emit('submitted')
            } catch (e) {
                console.error('Failed to submit hint:', e)
                alert('Failed to submit hint request')
            }
        }

        return { hintText, submit }
    },
    template: `
        <div>
            <h5>Request Hint for {{puzzleName}}</h5>
            <p class="hint-modal-info">
                This will be hint #{{queueSize + 1}} in the queue.
                Describe what you've tried and where you're stuck.
            </p>
            <textarea v-model="hintText" class="hint-textarea" rows="4"
                      placeholder="We have tried... and are stuck on..."></textarea>
            <div class="modal-actions">
                <button class="btn-secondary" @click="$emit('cancelled')">Cancel</button>
                <button @click="submit()" :disabled="!hintText.trim()">Add to Queue</button>
            </div>
        </div>
    `
}
