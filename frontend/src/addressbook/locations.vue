<template>
    <div>
        <div class="grid-container" v-show="visible">
            <img v-bind:src="mobileLegend"/>

            <div class="mapbox">
                <l-map ref="map" v-bind:zoom="zoom" v-bind:center="center">
                    <l-tile-layer v-bind:url="basemapUrl"/>
                    <l-tile-layer v-bind:url="mobileUrl" v-bind:opacity="0.4"/>
                    <l-marker v-for="location in locations" v-bind:key="location.id" v-bind:icon="icon" v-bind:lat-lng="location.coords" v-on:click="showModal(true, location)">
                        <l-tooltip v-bind:content="location.name"></l-tooltip>
                    </l-marker>
                </l-map>
            </div>
        </div>
        <div class="reveal-overlay" v-on:click="showModal(false)" v-bind:class="{show: modalVisible}">
            <div class="small reveal" v-on:click.stop tabindex="-1" v-if="modalLocation">
                <h3>{{ modalLocation.name }}</h3>
                <div><button class="button hollow" v-on:click="setFilter(modalLocation, 'single')">Show all users&nbsp;&nbsp;<i class="fi-filter"></i></button></div>
                <div class="grid-container">
                    <div class="grid-x grid-padding-x" v-if="modalLocation.address">
                        <div class="cell large-2 medium-auto large-text-right"><b>Address:</b></div>
                        <div class="cell auto"><a target="_blank" v-bind:href="`https://www.google.com/maps/search/?api=1&query=${modalLocation.coords.lat},${modalLocation.coords.lng}`">{{ modalLocation.address }}</a></div>
                    </div>
                    <div class="grid-x grid-padding-x" v-if="modalLocation.phone">
                        <div class="cell large-2 medium-auto large-text-right"><b>Phone:</b></div>
                        <div class="cell auto">{{ modalLocation.phone }}</div>
                    </div>
                    <div class="grid-x grid-padding-x" v-if="modalLocation.fax">
                        <div class="cell large-2 medium-auto large-text-right"><b>Fax:</b></div>
                        <div class="cell auto">{{ modalLocation.fax }}</div>
                    </div>
                    <div class="grid-x grid-padding-x" v-if="modalLocation.email">
                        <div class="cell large-2 medium-auto large-text-right"><b>Email:</b></div>
                        <div class="cell auto">{{ modalLocation.email }}</div>
                    </div>
                    <div class="grid-x grid-padding-x" v-if="modalLocation.info_url">
                        <div class="cell large-2 medium-auto large-text-right"><b>Website:</b></div>
                        <div class="cell auto"><a v-bind:href="modalLocation.info_url">Link</a></div>
                    </div>
                    <div class="grid-x grid-padding-x" v-if="modalLocation.bandwidth_url">
                        <iframe class="prtg" v-bind:src="modalLocation.bandwidth_url"/>
                    </div>
                </div>
                <button class="close-button" type="button" v-on:click="showModal(false)"><span aria-hidden="true">×</span></button>
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

import { LMap, LTileLayer, LMarker, LTooltip } from 'vue2-leaflet';
import L from 'leaflet';

//import 'leaflet/dist/leaflet.css';

import { fetchLocations } from './api';
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
            locations: [],
            zoom: 5,
            center: L.latLng(-24.966, 123.750),
            icon: new L.Icon({
                iconUrl,
                iconSize: [32, 32],
                iconAnchor: [16, 32],
                popupAnchor: [0, -20],
            }),
            basemapUrl: null,
            mobileUrl: null,
            mobileLegend,
            modalLocation: null,
            modalVisible: false,
        };
    },
    props: {
        itAssetsUrl: String,
        kmiUrl: String,
        visible: Boolean,
    },
    watch: {
        visible: function (val, oldVal) {
            if (val) {
                this.$nextTick(function () {
                    this.$refs.map.mapObject.invalidateSize();
                });
            }
        },
    },
    methods: {
        update: function() {
            var vm = this;
            fetchLocations(this.itAssetsUrl, function (data) {
                vm.locations = data;
            }, function (error) {
                console.log(error);
            });
        },
        showModal: function (state, loc) {
            if (loc) {
                this.modalLocation = loc;
            }
            this.modalVisible = state;
        },
        setFilter: function (location, mode) {
            this.showModal(false);
            this.$emit('updateFilter', {
                field_id: 'location_id',
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
        this.update();
    }
}
</script>
