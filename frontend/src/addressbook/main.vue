<template>
<div id="addressbook_base" class="f6inject">

    <div class="grid-container">
        <div class="grid-x grid-margin-x align-middle align-center small-margin-collapse">
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'addressList'" v-on:click="changeTab('addressList')">Address list</a></div>
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'organisation'" v-on:click="changeTab('organisation')">Organisation</a></div>
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'locations'" v-on:click="changeTab('locations')">Locations</a></div>
        </div>
    </div>

    <addressList ref="addressList" v-bind:addressFilters="addressFilters" v-bind:modal="modals.user" v-on:showModal="showModal" v-on:clearFilters="clearFilters" v-show="currentTab == 'addressList'"/>
    <organisation ref="organisation" v-on:updateFilter="updateFilter" v-bind:modal="modals.orgUnit" v-on:showModal="showModal" v-show="currentTab == 'organisation'" />
    <locations ref="locations" v-on:updateFilter="updateFilter" v-bind:modal="modals.location" v-on:showModal="showModal" v-bind:kmiUrl="kmiUrl" v-bind:visible="currentTab == 'locations'" />
</div>
</template>
<style lang="scss">

.f6inject {
    .tabs-title {
        text-align: center;
    }

    .tabs-title > a {
        font-size: 1rem !important;
    }

    .reveal-overlay.show {
        display: block;
    }

    .reveal-overlay.show .reveal {
        display: block;
    }

    .detailList .grid-x {
        margin-bottom: 0.5em;
    }
}    


</style>
<script>
import '../foundation-min.scss';
import '../leaflet.scss';
import 'foundation-icons/foundation-icons.scss';

import { fetchUsers, fetchLocations, fetchOrgTree, fetchOrgUnits } from './api';

import addressList from './addressList.vue';
import organisation from './organisation.vue';
import locations from './locations.vue';

export default {
    name: 'mainComponent',
    data: function () {
        return {
            currentTab: 'addressList',
            addressFilters: {
                field_id: null,
                name: null,
                value: null,
                mode: null,
            },
            modals: {
                user: null,
                orgUnit: null,
                'location': null,
            },
        };
    },
    components: {
        addressList,
        organisation,
        locations,
    },
    props: {
        itAssetsUrl: String,
        kmiUrl: String,
    },
    methods: {
        update: function () {
            var vm = this;
            // pull the latest locations data from the API, update the store
            fetchLocations(this.itAssetsUrl, function (data) {
                vm.$store.commit('updateLocations', data);
            }, function (error) {
                console.log(error);
            });

            // pull the latest user data from the API, update the store
            fetchUsers(this.itAssetsUrl, function (data) {
                vm.$store.commit('updateUsers', data);
            }, function (error) {
                console.log(error);
            });

            // pull the org structure from the API, update the store
            fetchOrgTree(this.itAssetsUrl, function (data) {
                vm.$store.commit('updateOrgTree', data);
            }, function (error) {
                console.log(error);   
            });
            fetchOrgUnits(this.itAssetsUrl, function (data) {
                vm.$store.commit('updateOrgUnits', data);
            }, function (error) {
                console.log(error);
            });

        },
        changeTab: function (name) {
            this.currentTab = name;
        },
        clearFilters: function (ev) {
            this.addressFilters = {
                field_id: null,
                name: null,
                value: null,
                mode: null
            };
        },
        updateFilter: function (ev) {
            this.currentTab = 'addressList';
            this.addressFilters = ev;
        },
        showModal: function (src_type, src_id) {
            switch (src_type) {
                case 'user':
                    this.showUser(src_id);
                    break;
                case 'orgUnit':
                    this.showOrgUnit(src_id);
                    break;
                case 'location':
                    this.showLocation(src_id);
                    break;
                default:
                    break;
            }
        },
        showUser: function (user_id) {
            this.currentTab = 'addressList';
            this.modals['user'] = this.$store.getters.user(user_id);
            this.modals['orgUnit'] = null;
            this.modals['location'] = null;
        },
        showOrgUnit: function (org_unit_id) {
            this.currentTab = 'organisation';
            this.modals['user'] = null;
            this.modals['orgUnit'] = this.$store.getters.orgUnit(org_unit_id);
            this.modals['location'] = null;
        },
        showLocation: function (location_id) {
            this.currentTab = 'locations';
            this.modals['user'] = null;
            this.modals['orgUnit'] = null;
            this.modals['location'] = this.$store.getters.location(location_id);
        },
    },
    mounted: function () {
        this.update();
    }
}
</script>
