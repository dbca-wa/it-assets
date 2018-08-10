<template>
    <li class="orgUnit button-group">
        <button class="button small hollow" v-bind:href="`#?org_id=${unit.id}`">{{ unit.name }}</button>
        <button v-if="hasChildren" class="button small hollow" v-on:click="toggle"><i v-if="hasChildren" v-bind:class="{'fi-minus': open, 'fi-plus': !open}"></i></button>
        <ul v-if="hasChildren" v-show="open">
            <orgUnit v-for="child in unit.children" v-bind:key="child.id" v-bind:unit="child" />
        </ul>
    </li>
</template>
<style lang="scss">

.f6inject {
    .orgUnit {
        flex-wrap: wrap;
        margin-bottom: 2px
    }

    .orgUnit ul {
        margin-bottom: 0;
    }

    .orgUnit.button-group .button {
        flex: 0 1 auto;
    }
}
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
