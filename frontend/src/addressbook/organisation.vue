<template>
    <div>
        <div class="grid-container">
            <department v-for="unit in orgUnits" v-on:showOrg="showOrg" v-bind:key="unit.id" v-bind:unit="unit"/>
        </div>
        <div class="reveal-overlay" v-on:click="showModal(false)" v-bind:class="{show: modalVisible}">
            <div class="small reveal" v-on:click.stop tabindex="-1" v-if="modalOrgUnit">
                <h3>{{ modalOrgUnit.name }}</h3>
                <div class="button-group"><button class="button hollow" v-on:click="setFilter(modalOrgUnit, 'cascade')">Show all users&nbsp;&nbsp;<i class="fi-filter"></i></button><button class="button hollow" v-on:click="setFilter(modalOrgUnit, 'single')">Show users just in this unit&nbsp;&nbsp;<i class="fi-filter"></i></button></div>
                <div class="grid-container">
                    <div class="grid-x grid-padding-x" v-if="modalOrgUnit.address">
                        <div class="cell large-2 medium-auto large-text-right"><b>Address:</b></div>
                        <div class="cell auto">[placeholder]</div>
                    </div>
                </div>
                <button class="close-button" type="button" v-on:click="showModal(false)"><span aria-hidden="true">×</span></button>
            </div>
        </div>
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
            orgUnits: [],
            modalOrgUnit: null,
            modalVisible: false,
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
        showOrg: function (ev) {
            return this.showModal(true, ev);
        },
        showModal: function (state, org) {
            if (org) {
                this.modalOrgUnit = org;
            }
            this.modalVisible = state;
        },
        setFilter: function (org, mode) {
            this.showModal(false);
            this.$emit('updateFilter', {
                field_id: 'org_id',
                name: org.name,
                value: org.id,
                mode: mode
            });
        },
    },
    mounted: function () {
        var vm = this;
        vm.update();
    },
}
</script>
