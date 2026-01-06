export default {
    props: {
      tags: Array,
      allowAdd: Boolean,
      current: String
    },
    emits: ['update:current', 'complete-transaction'],
    setup(props) {
        function focus() {
            this.$refs["tag-select"].focus();
        }

        return {focus};
    },
    template: `
        <input 
            ref="tag-select"
            list="taglist"
            type="text"
            :value="current"
            @input="$emit('update:current', $event.target.value.toLowerCase())"
            @keyup.enter="$emit('complete-transaction')">
    `
  }