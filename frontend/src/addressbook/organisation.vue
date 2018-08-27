<template>
    <div>
        <div class="grid-container">
            <department v-for="unit in orgTree" v-on:showOrg="showOrg" v-bind:key="unit.id" v-bind:unit="unit"/>
        </div>
        <div class="reveal-overlay show" v-on:click="$emit('showModal', 'orgUnit', null)" v-if="modal">
            <div class="small reveal" v-on:click.stop tabindex="-1">
                <h3>{{ modal.name }}</h3>
                <div class="button-group"><button class="button hollow" v-on:click="setFilter(modal, 'cascade')">Show all users&nbsp;&nbsp;<i class="fi-filter"></i></button><button class="button hollow" v-on:click="setFilter(modal, 'single')">Show users just in this unit&nbsp;&nbsp;<i class="fi-filter"></i></button></div>
                <div class="grid-container">
                    <div class="grid-x grid-padding-x" v-if="modal.address">
                        <div class="cell large-2 medium-auto large-text-right"><b>Address:</b></div>
                        <div class="cell auto">[placeholder]</div>
                    </div>
                </div>
                <button class="close-button" type="button" v-on:click="$emit('showModal', 'orgUnit', null)"><span aria-hidden="true">×</span></button>
            </div>
        </div>
    </div>
</template>
<style lang="scss">

</style>
<script>
import { mapGetters } from 'vuex';

import department from './department.vue';

export default {
    name: 'organisation',
    components: {
        department,
    },
    data: function () {
        return {
            orgUnits: [],
        };
    },
    props: {
        modal: Object,
    },
    computed: {
        // bind to getters in store.js
        ...mapGetters([
            'orgTree'
        ]),
    },
    methods: {
        showOrg: function (ev) {
            console.log(ev);
            this.$emit('showModal', 'orgUnit', ev);
        },
        setFilter: function (org, mode) {
            this.$emit('showModal', 'orgUnit', null);
            this.$emit('updateFilter', {
                field_id: 'org_unit.id',
                name: org.name,
                value: org.id,
                mode: mode
            });
        },
    },
    mounted: function () {
    },
}
</script>
