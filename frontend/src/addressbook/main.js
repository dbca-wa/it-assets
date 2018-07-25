import Vue from 'vue';
import VuePaginate from 'vue-paginate';

Vue.use(VuePaginate);

import addressbook from './addressbook.vue';


var addressBookApp = function (target, itAssetsUrl) {
    Vue.config.productionTip = (process.env.NODE_ENV === 'production');
    
    if (!itAssetsUrl) {
        itAssetsUrl = process.env.IT_ASSETS_URL || '';
    }

    var options = {
        props: {itAssetsUrl}
    };

    /* eslint-disable no-new */
    return new Vue({
        render: function (h) {
            return h(addressbook, options);
        }
    }).$mount(target);
};


export default addressBookApp
