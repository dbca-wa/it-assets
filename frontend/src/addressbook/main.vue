<template>
<div id="addressbook_base" class="f6inject">

    <div class="grid-container">
        <div class="grid-x grid-margin-x align-middle align-center small-margin-collapse">
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'addressList'" v-on:click="changeTab('addressList')">Address list</a></div>
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'organisation'" v-on:click="changeTab('organisation')">Organisation</a></div>
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'locations'" v-on:click="changeTab('locations')">Locations</a></div>
        </div>
    </div>

    <addressList ref="addressList" v-bind:addressFilters="addressFilters" v-on:clearFilters="clearFilters" v-show="currentTab == 'addressList'"/>
    <organisation ref="organisation" v-bind:itAssetsUrl="itAssetsUrl" v-on:updateFilter="updateFilter" v-show="currentTab == 'organisation'" />
    <locations ref="locations" v-on:updateFilter="updateFilter" v-bind:kmiUrl="kmiUrl" v-bind:visible="currentTab == 'locations'" />
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
}    


</style>
<script>
import '../foundation-min.scss';
import '../leaflet.scss';
import 'foundation-icons/foundation-icons.scss';

import { fetchUsers, fetchLocations } from './api';

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
    },
    mounted: function () {
        this.update();
    }
}
</script>
