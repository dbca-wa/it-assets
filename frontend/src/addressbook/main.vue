<template>
<div id="addressbook_base" class="f6inject">

    <div class="grid-container">
        <div class="grid-x grid-margin-x align-middle align-center">
            <div class="cell auto tabs-title" v-bind:class="{'is-active': true}"><a v-bind:aria-selected="true" >Address list</a></div>
            <div class="cell auto tabs-title"><a>Organisation units</a></div>
            <div class="cell auto tabs-title"><a>Locations</a></div>
        </div>
    </div>

    <addressList v-bind:itAssetsUrl="itAssetsUrl" />

</div>
</template>
<style lang="scss">

.tabs-title {
    text-align: center;
}

.tabs-title > a {
    font-size: 1rem !important;
}
    

</style>
<script>
import 'foundation-sites';
import '../foundation-min.scss';

import addressList from './addressList.vue';


export default {
    name: 'main',
    data: function () {
        return {
        };
    },
    components: {
        addressList
    },
    props: {
        itAssetsUrl: String,
    },
}
</script>
