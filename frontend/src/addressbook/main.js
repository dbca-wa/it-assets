import Vue from 'vue';
import VuePaginate from 'vue-paginate';

Vue.use(VuePaginate);
Vue.config.productionTip = (process.env.NODE_ENV === 'production');

import main from './main.vue';


var addressBookApp = function (target, itAssetsUrl, kmiUrl) {
    var options = {
        props: {itAssetsUrl, kmiUrl}
    };

    /* eslint-disable no-new */
    return new Vue({
        render: function (h) {
            return h(main, options);
        }
    }).$mount(target);
};


export default addressBookApp
