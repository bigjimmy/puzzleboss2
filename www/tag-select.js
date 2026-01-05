export default {
    props: {
      tags: Array,
      allowAdd: Boolean,
      current: String
    },
    emits: ['update:current'],
    setup(props) {
        return {};
    },
    template: `<input type="text"
                :value="current"
                @input="$emit('update:current', $event.target.value.toLowerCase())">`
  }