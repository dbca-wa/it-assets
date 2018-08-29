<template>
    <div v-show="visible">
        <div class="grid-container">
            <img v-bind:src="mobileLegend"/>

            <div class="mapbox">
                <l-map ref="map" v-bind:zoom="zoom" v-bind:center="center">
                    <l-tile-layer v-bind:url="basemapUrl"/>
                    <l-tile-layer v-bind:url="mobileUrl" v-bind:opacity="0.4"/>
                    <l-marker v-for="location in mapLocations" v-bind:key="location.id" v-bind:icon="icon" v-bind:lat-lng="location.coords" v-on:click="$emit('showModal', 'location', location.id)">
                        <l-tooltip v-bind:content="location.name"></l-tooltip>
                    </l-marker>
                </l-map>
            </div>
        </div>
        <div class="reveal-overlay show" v-on:click="$emit('showModal', 'location', null)" v-if="modal">
            <div class="small reveal" v-on:click.stop tabindex="-1">
                <h3>{{ modal.name }}</h3>
                <div><button class="button hollow" v-on:click="setFilter(modal, 'single')">List all users&nbsp;&nbsp;<i class="fi-filter"></i></button></div>
                <div class="grid-container full detailList">
                    <div class="grid-x grid-margin-x" v-if="modal.address">
                        <div class="cell large-2 large-text-right"><b>Address:</b></div>
                        <div class="cell auto" v-if="modal.coords"><a target="_blank" v-bind:href="`https://www.google.com/maps/search/?api=1&query=${modal.coords.lat},${modal.coords.lng}`">{{ modal.address }}</a></div>
                        <div class="cell auto" v-else>
                            {{ modal.address }}
                        </div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.phone">
                        <div class="cell large-2 large-text-right"><b>Phone:</b></div>
                        <div class="cell auto">{{ modal.phone }}</div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.fax">
                        <div class="cell large-2 large-text-right"><b>Fax:</b></div>
                        <div class="cell auto">{{ modal.fax }}</div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.email">
                        <div class="cell large-2 large-text-right"><b>Email:</b></div>
                        <div class="cell auto">{{ modal.email }}</div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.info_url">
                        <div class="cell large-2 large-text-right"><b>Website:</b></div>
                        <div class="cell auto"><a v-bind:href="modal.info_url">Link</a></div>
                    </div>
                    <div class="grid-x grid-margin-x" v-if="modal.bandwidth_url">
                        <iframe class="prtg cell auto" v-bind:src="modal.bandwidth_url"/>
                    </div>
                </div>
                <button class="close-button" type="button" v-on:click="$emit('showModal', 'location', null)"><span aria-hidden="true">×</span></button>
            </div>
        </div>
    </div>
</template>
<style lang="scss">
.f6inject {
    .mapbox {
        height: 70vh;
    }

    .prtg {
        width: 100%;
        height: 384px;
        margin-top: 1em;
    }
}

</style>
<script>

import { mapGetters } from 'vuex';
import { LMap, LTileLayer, LMarker, LTooltip } from 'vue2-leaflet';
import L from 'leaflet';

//import 'leaflet/dist/leaflet.css';

import mobileLegend from './assets/mobile_legend.png';
import iconUrl from './assets/pin.svg';


export default {
    name: 'locations',
    components: {
        LMap,
        LTileLayer,
        LMarker,
        LTooltip,
    },
    data: function () {
        return {
            zoom: 5,
            center: L.latLng(-24.966, 123.750),
            icon: new L.Icon({
                iconUrl: `${this.itAssetsUrl}/static${iconUrl}`,
                iconSize: [32, 32],
                iconAnchor: [16, 32],
                popupAnchor: [0, -20],
            }),
            basemapUrl: null,
            mobileUrl: null,
            mobileLegend,
        };
    },
    props: {
        itAssetsUrl: String,
        kmiUrl: String,
        visible: Boolean,
        modal: Object,
    },
    watch: {
        // the map widget will only listen for changes in window size. 
        // need to load in the widget's visibility as a property and simulate a window resize on change.
        visible: function (val, oldVal) {
            if (val) {
                this.$nextTick(function () {
                    this.$refs.map.mapObject.invalidateSize();
                });
            }
        },
        modal: function (val, oldVal) {
            if (val && val.coords) {
                this.$refs.map.mapObject.setView(val.coords, 13);
            }
        },
    },
    computed: {
        mapLocations: function () {
            return this.locationsList.filter(function (el) {
                return el.coords;
            });
        },
        // bind to getters in store.js
        ...mapGetters([
            'locationsList'
        ]),
    },
    methods: {
        setFilter: function (location, mode) {
            this.$emit('showModal', 'location', null);
            this.$emit('updateFilter', {
                field_id: 'location.id',
                name: location.name,
                value: location.id,
                mode: mode
            });
        },
        getTileUrl: function (name) {
            return `${this.kmiUrl}?Layer=${name}&TileMatrixSet=mercator&Service=WMTS&Request=GetTile&Version=1.0.0&format=image/png&TileMatrix=mercator:{z}&TileRow={y}&TileCol={x}`;
        }
    },
    mounted: function () {
        this.basemapUrl = this.getTileUrl('public:mapbox-outdoors');
        this.mobileUrl = this.getTileUrl('dpaw:telstra_gcm_4g_3g');
    }
}
</script>
