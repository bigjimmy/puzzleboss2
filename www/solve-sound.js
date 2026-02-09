import { ref, watch, useTemplateRef } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js'

export default {
    props: {},
    setup(props, context) {

        const ps = ref(false);
        const warning = ref("");
        const customFileExists = ref(false);

        const fileInputRef = useTemplateRef("fileInput");

        function updateExists() {
            localforage.getItem('soundfile').then((blob) => {
                customFileExists.value = (!!blob);
            });
        }
        
        //
        // This function persists a given key to localStorage.
        //
        function persist(which, update) {
            localStorage.setItem(which, JSON.stringify(update));
        }

        //
        // This function plays sound.
        //
        async function playSound() {
            if(!ps.value) return;
            try {
                const blob = await localforage.getItem('soundfile');
                if (!blob) throw "no custom sound";
                const aud = new Audio(URL.createObjectURL(blob));
                aud.play();
            } catch {
                var audio = new Audio('https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3');
                audio.play();
            }
        }

        async function storeSound(event) {
            if(event.target.files[0].type.indexOf('audio/') !== 0) {
                warning.value = 'Not an audio file...';
                return;
            }
            await localforage.setItem('soundfile', event.target.files[0]);
            warning.value = 'File set';
            fileInputRef.value.value = null;
            updateExists();
        }

        async function deleteSound(){
            await localforage.setItem('soundfile', null);
            updateExists();
        }

        watch(ps, (update) => {
            persist("playSound", update);
        });

        const psl = localStorage.getItem("playSound");
        if (psl !== null && psl !== undefined) ps.value = JSON.parse(psl);

        updateExists();

        return {
            ps, playSound, storeSound, warning, customFileExists, deleteSound
        }
    },

    template: `
    <label :class="{ on: ps }" @click.prevent="ps = !ps">🔊 Solve sound
        <template v-if="ps">
            <input type="file" class="sound-file-input" ref="fileInput" @click.stop @change="storeSound" accept="audio/*"/>
            <span v-if="warning" @click.stop>{{warning}}</span>
            <button v-if="customFileExists" @click.stop="deleteSound">Clear</button>
        </template>
    </label>
    `
}
  
