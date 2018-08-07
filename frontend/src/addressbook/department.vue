<template>
    <div class="callout">
        <h4>
            <strong><a :href="`#?org_id=${unit.id}`">{{ unit.name }}</a></strong>
        </h4>
        <div v-if="hasChildren">
            <ul class="orgList">
                <orgUnit v-for="unit in unit.children" v-bind:key="unit.id" v-bind:unit="unit"></orgUnit>
            </ul>
        </div>
    </div>
</template>
<style lang="scss">
.f6inject {
    .orgList {
        margin: 0;
    }
}
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
    }
}
</script>
