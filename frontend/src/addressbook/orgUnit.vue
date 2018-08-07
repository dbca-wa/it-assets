<template>
    <div>
        <li class="org_unit">
            <a v-bind:href="`#?org_id=${unit.id}`">{{ unit.name }}</a>
            <span v-if="hasChildren" v-on:click="toggle"><i v-if="open" class="fi-minus">-</i><i v-else class="fi-plus">+</i></span>
        </li>
        <ul v-if="hasChildren" v-show="open">
            <orgUnit v-for="child in unit.children" v-bind:key="unit.id" v-bind:unit="child" />
        </ul>
    </div>
</template>
<style lang="scss">

</style>
<script>


export default {
    name: 'orgUnit',
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
