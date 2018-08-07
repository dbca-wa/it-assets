<template>
    <div class="grid-container">
        <department v-for="unit in orgUnits" v-bind:key="unit.id" v-bind:unit="unit"/>
    </div>
</template>
<style lang="scss">

</style>
<script>
import department from './department.vue';

import { fetchOrg } from './api';

export default {
    name: 'organisation',
    components: {
        department,
    },
    data: function () {
        return {
            orgUnits: []
        };
    },
    props: {
        itAssetsUrl: String,
    },
    methods: {
        update: function () {
            var vm = this;
            fetchOrg(this.itAssetsUrl, function (data) {
                vm.orgUnits = data;
            }, function (error) {
                console.log(error);
            });
        },
    },
    mounted: function () {
        var vm = this;
        vm.update();
    },
}
</script>
