"use strict";
// NOTE: some global constants are set in the base template.
const geoserver_wmts_url = geoserver_url + "/gwc/service/wmts?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&tilematrix=gda94:{z}&tilecol={x}&tilerow={y}";
const geoserver_wmts_url_base = geoserver_wmts_url + "&format=image/jpeg";
const geoserver_wmts_url_overlay = geoserver_wmts_url + "&format=image/png";

// Define baselayer tile layers.
const mapboxStreets = L.tileLayer(
  geoserver_wmts_url_base + "&layer=public:mapbox-streets",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);

// Define overlay tile layers.
const dbcaRegions = L.tileLayer(
  geoserver_wmts_url_overlay + "&layer=cddp:kaartdijin-boodja-public_CPT_DBCA_REGIONS",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const dbcaDistricts = L.tileLayer(
  geoserver_wmts_url_overlay + "&layer=cddp:kaartdijin-boodja-public_CPT_DBCA_DISTRICTS",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);

// Function to define hover effect for location points.
function locationHover(feature, layer) {
  layer.bindTooltip(
    feature.properties.name,
    { className: "leaflet-tooltip-wide" }
  );
  layer.bindPopup(`<a href="?q=${feature.properties.ascender_desc}">${feature.properties.name}</a><br>
${feature.properties.ascender_desc}<br>
${feature.properties.phone}`);
}

// Define a clustered layer for DBCA locations, and a GeoJSON layer to contain the data.
const locationsClustered = L.markerClusterGroup();
const dbcaLocations = L.geoJSON(
  null,  // Initially empty.
  {
    onEachFeature: locationHover
  },
);

// Function to get location data and populate the layer.
function queryLocationsData() {
  $.ajax({
    dataType: "json",
    url: location_features_url,
    data: { format: "geojson" },
    success: function (data) {
      // Add the device data to the GeoJSON layer.
      dbcaLocations.addData(data);
      // Add DBCA locations layer to the map display and zoom to their bounds.
      locationsClustered.addLayer(dbcaLocations);
      map.addLayer(locationsClustered);
      map.fitBounds(dbcaLocations.getBounds());
    },
  });
};
// Immediately run the function once to get data.
queryLocationsData();

// Define map.
const map = L.map("map", {
  crs: L.CRS.EPSG4326,  // WGS 84
  center: [-31.96, 115.87],
  minZoom: 4,
  maxZoom: 18,
  layers: [mapboxStreets, dbcaRegions],  // Sets default selections.
  attributionControl: false,
});

// Define layer groups.
const baseMaps = {
  "Place names": mapboxStreets,
};
const overlayMaps = {
  "DBCA regions": dbcaRegions,
  "DBCA districts": dbcaDistricts,
};

// Define layer control.
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Define scale bar
L.control.scale({ maxWidth: 500, imperial: false }).addTo(map);

// Move the map div inside the #locations-tab-pane div and redraw it.
// https://stackoverflow.com/a/63319084/14508
const mapDiv = document.getElementById("map");
const mapResizeObserver = new ResizeObserver(() => {
  map.invalidateSize();
});
document.getElementById("locations-tab-pane").appendChild(mapDiv);
mapResizeObserver.observe(mapDiv);
