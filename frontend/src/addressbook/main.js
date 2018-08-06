import Vue from 'vue';
import VuePaginate from 'vue-paginate';

Vue.use(VuePaginate);
Vue.config.productionTip = (process.env.NODE_ENV === 'production');

import addressbook from './addressbook.vue';


var addressBookApp = function (target, itAssetsUrl) {
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
