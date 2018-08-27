import Vue from 'vue';
import Vuex from 'vuex';
import createPersistedState from 'vuex-persistedstate';
Vue.use(Vuex);

const store = new Vuex.Store({
    state: {
        users: new Map(),
        usersOrder: [],
        orgTree: [],
        orgUnits: new Map(),
        orgUnitsOrder: [],
        locations: new Map(),
        locationsOrder: [],
    },
    getters: {
        usersList: function (state) {
            return state.usersOrder;
        },
        user: function (state) { 
            return function (id) {
                return state.users.get(id);
            };
        },
        locationsList: function (state) {
            return state.locationsOrder;
        },
        'location': function (state) { 
            return function (id) {
                return state.locations.get(id);
            };
        },
        orgTree: function (state) {
            return state.orgTree;
        },
        orgUnitsList: function (state) {
            return state.orgUnitsOrder;
        },
        orgUnit: function (state) {
            return function (id) {
                return state.orgUnits.get(id);
            };
        },
    },
    plugins: [createPersistedState({
        key: 'oim_addressbook',
        paths: [],
    })],
    mutations: {
        updateUsers: function (state, usersList) {
            state.usersOrder = usersList;
            state.users = new Set(state.usersOrder.map(function (el) {
                return [el.id, el];
            }));
        },
        updateLocations: function (state, locationsList) {
            state.locationsOrder = locationsList;
            state.locations = new Set(state.locationsOrder.map(function (el) {
                return [el.id, el];
            }));
        },
        updateOrgTree: function (state, orgTree) {
            state.orgTree = orgTree;
        },
        updateOrgUnits: function (state, orgUnitsList) {
            state.orgUnitsOrder = orgUnitsList;
            state.orgUnits = new Set(state.orgUnitsOrder.map(function (el) {
                return [el.id, el];
            }));
        },
    },
});

export default store
