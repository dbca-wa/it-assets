import '../ieHacks.js';

import Vue from 'vue';
import Vuex from 'vuex';
import VuePaginate from 'vue-paginate';

Vue.use(Vuex);
Vue.use(VuePaginate);
Vue.config.productionTip = (process.env.NODE_ENV === 'production');

import store from './store.js';
import main from './main.vue';


var addressBookApp = function (target, itAssetsUrl, kmiUrl) {
    var options = {
        props: {itAssetsUrl, kmiUrl}
    };

    /* eslint-disable no-new */
    return new Vue({
        store,
        render: function (h) {
            return h(main, options);
        }
    }).$mount(target);
};


export default addressBookApp
