<template>
<div id="addressbook_base" class="f6inject">

    <div class="grid-container">
        <div class="grid-x grid-margin-x align-middle align-center small-margin-collapse">
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'addressList'" v-on:click="changeTab('addressList')">Address list</a></div>
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'organisation'" v-on:click="changeTab('organisation')">Organisation</a></div>
            <div class="cell auto tabs-title"><a v-bind:aria-selected="currentTab == 'locations'" v-on:click="changeTab('locations')">Locations</a></div>
        </div>
    </div>

    <addressList v-bind:itAssetsUrl="itAssetsUrl" v-show="currentTab == 'addressList'"/>
    <organisation v-bind:itAssetsUrl="itAssetsUrl" v-show="currentTab == 'organisation'" />
    <locations v-bind:itAssetsUrl="itAssetsUrl" v-bind:kmiUrl="kmiUrl" v-show="currentTab == 'locations'" />
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
}    

</style>
<script>
import 'foundation-sites';
import '../foundation-min.scss';
import 'foundation-icons/foundation-icons.scss';

import addressList from './addressList.vue';
import organisation from './organisation.vue';
import locations from './locations.vue';

export default {
    name: 'mainComponent',
    data: function () {
        return {
            currentTab: 'addressList',
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
        changeTab: function (name) {
            this.currentTab = name;
        }
    }
}
</script>
