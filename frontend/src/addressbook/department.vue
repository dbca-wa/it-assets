<template>
    <div class="callout">
        <h4>
            <strong><a :href="`#?org_id=${unit.id}`">{{ unit.name }}</a></strong>
            <span v-if="hasChildren" v-on:click="toggle"><i v-if="open" class="fi-minus">-</i><i v-else class="fi-plus">+</i></span>
        </h4>
        <div v-if="hasChildren" v-show="open">
            <ul>
                <orgUnit v-for="unit in unit.children" :key="unit.id" :unit="unit"></orgUnit>
            </ul>
        </div>
    </div>
</template>
<style lang="scss">

</style>
<script>
import orgUnit from './orgUnit.vue';

export default {
    name: 'department',
    components: {
        orgUnit
    },
    data: function () {
        return {
            open: false,
        };
    },
    props: {
        unit: Object,
    },
    computed: {
        hasChildren: function () {
            return this.unit.children && this.unit.children.length;
        }
    },
    methods: {
        toggle: function () {
            if (this.hasChildren) {
                this.open = !this.open;
            }
        }
    }
}
</script>
