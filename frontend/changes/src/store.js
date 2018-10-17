import Vuex from 'vuex'
import Vue from 'vue'

Vue.use(Vuex)
var store = new Vuex.Store({
    state: {
        itsystems:[],
        requestors: [],
        standardchanges:[],
    },
    mutations: {
        SETITSYSTEMS(state, a) {
            var data = [];
            for (var i = 0; i < a.length; i++){
                var code = a[i].substr(0,4);
                var name = a[i].substr(4);
                data.push({'id': code, 'name': name});
            }
            state.itsystems = data;
        },
        SETREQUESTORS(state, a) {
            state.requestors = a;
        },
        SETSTANDARDCHANGES(state, standardchanges) {
            state.standardchanges = standardchanges;
        },
    },
    actions: {
        fetchItsystems(context) {
            $.get("/api/options/?list=itsystem",function(data){
                context.commit('SETITSYSTEMS',data.objects);
            });
        },
        fetchRequestors(context) {
            $.get("/api/users/fast/?minimal=true&active=True",function(data){
                context.commit('SETREQUESTORS',data.objects);
            });
        },
        fetchStandardchanges(context) {
            $.get("/api/v2/standardchange/",function(data){
                context.commit('SETSTANDARDCHANGES',data);
            });
        },
    },
    getters:{
        itsystems: state => {
            return state.itsystems;
        },
        requestors: state => {
            return state.requestors;
        },
        standardchanges: (state) =>  {
            return state.standardchanges;
        },
    }
});

export default store;
