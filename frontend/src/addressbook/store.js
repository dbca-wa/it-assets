import Vue from 'vue';
import Vuex from 'vuex';
import createPersistedState from 'vuex-persistedstate';
Vue.use(Vuex);

const store = new Vuex.Store({
    state: {
        users: new Map(),
        usersOrder: [],
        orgUnits: new Map(),
        orgUnitsOrder: [],
        locations: new Map(),
        locationsOrder: [],
    },
    getters: {
        usersList: function (state) {
            if (state.users instanceof Map) {
                return state.usersOrder.map(function (el) {
                    return state.users.get(el); 
                });
            }
            return [];
        },
        user: function (state) { 
            return function (id) {
                return state.users.get(id);
            };
        },
        locationsList: function (state) {
            if (state.users instanceof Map) {
                return state.locationsOrder.map(function (el) {
                    return state.locations.get(el); 
                });
            }
            return [];
        },
        'location': function (state) { 
            return function (id) {
                return state.locations.get(id);
            };
        },
    },
    plugins: [createPersistedState({
        key: 'oim_addressbook',
        paths: [],
        overwrite: true,
        getState: function (key, storage, value) {
            var result = undefined;
            try {
                result = (value = storage.getItem(key)) && typeof value !== 'undefined'
                ? JSON.parse(value)
                : undefined;
            } catch (err) {}
            
            if (result) {
                result.users = new Map(result.users);
                result.orgUnits = new Map(result.orgUnits);
                result.locations = new Map(result.locations);
            }
            console.log('getState');
            console.log(result);
            return result;
        },
        setState: function (key, state, storage) {
            // dumb shim to serialize Maps to JSON
            // we have to do this because JS Objects only support using string as a key
            var result = {
                users: state.users instanceof Map ? [...state.users.entries()] : [],
                usersOrder: state.usersOrder,
                orgUnits: state.orgUnits instanceof Map ? [...state.orgUnits.entries()] : [],
                orgUnitsOrder: state.orgUnitsOrder,
                locations: state.locations instanceof Map ? [...state.locations.entries()] : [],
                locationsOrder: state.locationsOrder,
            };
            console.log('setState');
            console.log(result);
            return storage.setItem(key, JSON.stringify(result));
        },
    })],
    mutations: {
        updateUsers: function (state, usersList) {
            state.usersOrder = usersList.map(function(el) {
                return el.id;
            });
            var toRemove = new Set(Object.keys(state.users));
            usersList.forEach(function (el) {
                toRemove.delete(el.id);
                state.users.set(el.id, el);
            });
            toRemove.forEach(function (el) {
                state.users.delete(el);
            });
        },
        updateLocations: function (state, locationsList) {
            state.locationsOrder = locationsList.map(function(el) {
                return el.id;
            });
            var toRemove = new Set(Object.keys(state.locations));
            locationsList.forEach(function (el) {
                toRemove.delete(el.id);
                state.locations.set(el.id, el);
            });
            toRemove.forEach(function (el) {
                state.locations.delete(el);
            });
        },
        
    },
});

export default store
