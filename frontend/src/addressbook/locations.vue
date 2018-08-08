<template>
    <div class="grid-container" v-show="visible">
        <img v-bind:src="mobileLegend"/>

        <div class="mapbox">
            <l-map ref="map" v-bind:zoom="zoom" v-bind:center="center">
                <l-tile-layer v-bind:url="basemapUrl"/>
                <l-tile-layer v-bind:url="mobileUrl" v-bind:opacity="0.4"/>
                <l-marker v-for="location in locations" v-bind:key="location.id" v-bind:icon="icon" v-bind:lat-lng="location.coords">
                    <l-popup v-bind:content="location.name"></l-popup>
                </l-marker>
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

import { LMap, LTileLayer, LMarker, LPopup } from 'vue2-leaflet';
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
        LPopup,
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
