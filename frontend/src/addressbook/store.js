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
        overwrite: true,
        // copy of the method from vuex-persistedstate, with shims for the 3 non-JS objects
        getState: function (key, storage, value) {
            var result = undefined;
            try {
                result = (value = storage.getItem(key)) && typeof value !== 'undefined'
                    ? JSON.parse(value)
                    : {
                        usersOrder: [],
                        orgUnitsOrder: [],
                        locationsOrder: [],
                        orgTree: [],
                    };
            } catch (err) {}

            var userMap = result.usersOrder ? result.usersOrder.map(function (el) {
                return [el.id, el];
            }) : [];
            result.users = new Map(userMap);
            var orgUnitMap = result.orgUnitsOrder ? result.orgUnitsOrder.map(function (el) {
                return [el.id, el];
            }) : [];
            result.orgUnits = new Map(orgUnitMap);
            var locationMap = result.locationsOrder ? result.locationsOrder.map(function (el) {
                return [el.id, el];
            }) : [];
            result.locations = new Map(locationMap);

            return result;
        }
    })],
    mutations: {
        updateUsers: function (state, usersList) {
            state.usersOrder = usersList;
            state.users = new Map(state.usersOrder.map(function (el) {
                return [el.id, el];
            }));
        },
        updateLocations: function (state, locationsList) {
            state.locationsOrder = locationsList;
            state.locations = new Map(state.locationsOrder.map(function (el) {
                return [el.id, el];
            }));
        },
        updateOrgTree: function (state, orgTree) {
            state.orgTree = orgTree;
        },
        updateOrgUnits: function (state, orgUnitsList) {
            state.orgUnitsOrder = orgUnitsList;
            state.orgUnits = new Map(state.orgUnitsOrder.map(function (el) {
                return [el.id, el];
            }));
        },
    },
});

export default store
