'use strict';
// NOTE: some global constants are set in the base template.
const geoserver_wms_url = `${geoserver_url}/ows`;
const geoserver_wmts_url = `${geoserver_url}/gwc/service/wmts?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=mercator&tilematrix=mercator:{z}&tilecol={x}&tilerow={y}`;
const geoserver_wmts_url_overlay = `${geoserver_wmts_url}&format=image/png`;

// Define tile layers.
const openStreetMap = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png');
const dbcaRegions = L.tileLayer(`${geoserver_wmts_url_overlay}&layer=cddp:kaartdijin-boodja-public_CPT_DBCA_REGIONS`, {
  opacity: 0.75,
});
const dbcaDistricts = L.tileLayer(`${geoserver_wmts_url_overlay}&layer=cddp:kaartdijin-boodja-public_CPT_DBCA_DISTRICTS`, {
  opacity: 0.75,
});

// Function to define hover effect for location points.
function locationHover(feature, layer) {
  layer.bindTooltip(feature.properties.name, { className: 'leaflet-tooltip-wide' });
  layer.bindPopup(`<a href="?q=${feature.properties.ascender_desc}">${feature.properties.name}</a><br>
${feature.properties.ascender_desc}<br>
${feature.properties.phone}`);
}

// Define a clustered layer for DBCA locations, and a GeoJSON layer to contain the data.
const locationsClustered = L.markerClusterGroup();
const dbcaLocations = L.geoJSON(
  null, // Initially empty.
  {
    onEachFeature: locationHover,
  }
);

function queryLocationsData() {
  // Query the API endpoint for device data.
  fetch(location_features_url + '?format=geojson')
    // Parse the response as JSON.
    .then((resp) => resp.json())
    // Replace the data in the tracked devices layer.
    .then(function (data) {
      // Add the device data to the GeoJSON layer.
      dbcaLocations.addData(data);
      // Add DBCA locations layer to the map display and zoom to their bounds.
      locationsClustered.addLayer(dbcaLocations);
      map.addLayer(locationsClustered);
      map.fitBounds(dbcaLocations.getBounds());
    });
}

// Immediately run the function once to get data.
queryLocationsData();

// Define map.
const map = L.map('map', {
  // crs: L.CRS.EPSG4326, // WGS 84
  center: [-31.96, 115.87],
  minZoom: 5,
  maxZoom: 18,
  layers: [openStreetMap, dbcaRegions], // Sets default selections.
  attributionControl: false,
});

// Define layer groups.
const baseMaps = {
  'Place names': openStreetMap,
};
const overlayMaps = {
  'DBCA regions': dbcaRegions,
  'DBCA districts': dbcaDistricts,
};

// Define layer control.
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Define scale bar
L.control.scale({ maxWidth: 500, imperial: false }).addTo(map);

// Move the map div inside the #locations-tab-pane div and redraw it.
// https://stackoverflow.com/a/63319084/14508
const mapDiv = document.getElementById('map');
const mapResizeObserver = new ResizeObserver(() => {
  map.invalidateSize();
});
document.getElementById('locations-tab-pane').appendChild(mapDiv);
mapResizeObserver.observe(mapDiv);
