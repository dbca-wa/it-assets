<template>
    <div class="grid-container">
        <img v-bind:src="mobileLegend"/>

        <div class="mapbox">
            <l-map v-bind:zoom="zoom" v-bind:center="center">
                <l-tile-layer v-bind:url="basemapUrl"/>
                <l-tile-layer v-bind:url="mobileUrl" opacity="0.4"/>
            </l-map>
        </div>
    </div>
</template>
<style lang="scss">
.f6inject {
    .mapbox {
        height: 70vh;
    }
}

</style>
<script>

import { LMap, LTileLayer, LMarker } from 'vue2-leaflet';
import L from 'leaflet';

import 'leaflet/dist/leaflet.css';

import mobileLegend from './assets/mobile_legend.png';


export default {
    name: 'locations',
    components: {
        LMap,
        LTileLayer,
        LMarker
    },
    data: function () {
        return {
            zoom: 5,
            center: L.latLng(-24.966, 123.750),
            basemapUrl: null,
            mobileUrl: null,
            mobileLegend,
        };
    },
    props: {
        itAssetsUrl: String,
        kmiUrl: String,
    },
    methods: {
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
