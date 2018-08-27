<template>
    <div>
        <div class="grid-container">
            <department v-for="unit in orgTree" v-on:showOrg="showOrg" v-bind:key="unit.id" v-bind:unit="unit"/>
        </div>
        <div class="reveal-overlay show" v-on:click="$emit('showModal', 'orgUnit', null)" v-if="modal">
            <div class="small reveal" v-on:click.stop tabindex="-1">
                <h3>{{ modal.name }}</h3>
                <div class="button-group"><button class="button hollow" v-on:click="setFilter(modal, 'cascade')">List all users (this and all subunits)&nbsp;&nbsp;<i class="fi-filter"></i></button><button class="button hollow" v-on:click="setFilter(modal, 'single')">List users (this unit only)&nbsp;&nbsp;<i class="fi-filter"></i></button></div>
                
                <div class="grid-container full detailList">
                    <div class="grid-x grid-margin-x" v-if="modal.acronym">
                        <div class="cell large-2 large-text-right"><b>Acronym:</b></div>
                        <div class="cell auto">{{ modal.acronym }}</div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.unit_type">
                        <div class="cell large-2 large-text-right"><b>Type:</b></div>
                        <div class="cell auto">{{ modal.unit_type }}</div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modalLocation">
                        <div class="cell large-2 large-text-right"><b>Location:</b></div>
                        <div class="cell auto">
                            <a v-on:click="$emit('showModal', 'location', modalLocation.id)">{{ modalLocation.name }}</a><br/>
                            {{ modalLocation.address }}<br/>
                        </div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.parent">
                        <div class="cell large-2 large-text-right"><b>Parent:</b></div>
                        <div class="cell auto"><a v-on:click="$emit('showModal', 'orgUnit', modal.parent)">{{ $store.getters.orgUnit(modal.parent).name }}<span v-if="$store.getters.orgUnit(modal.parent).acronym"> ({{ $store.getters.orgUnit(modal.parent).acronym }})</span></a></div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.children.length">
                        <div class="cell large-2 large-text-right"><b>Children:</b></div>
                        <div class="cell auto">
                            <ul>
                                <li v-for="org_id in modal.children" v-bind:key="org_id"><a v-on:click="$emit('showModal', 'orgUnit', org_id)">{{ $store.getters.orgUnit(org_id).name }}<span v-if="$store.getters.orgUnit(org_id).acronym"> ({{ $store.getters.orgUnit(org_id).acronym }})</span></a></li>
                            </ul>
                        </div>
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
        modalLocation: function () {
            return (this.modal && this.modal.location) ? this.$store.getters.location(this.modal.location) : null;
        },
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
