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
    },
});

export default store
