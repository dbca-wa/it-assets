// The Vue build version to load with the `import` command
// (runtime-only or standalone) has been set in webpack.base.conf with an alias.
import Vue from 'vue';
import resource from 'vue-resource';
import VueRouter from 'vue-router';
import VModal from 'vue-js-modal';
import 'bootstrap/dist/css/bootstrap.css';
import 'bootstrap-vue/dist/bootstrap-vue.css';
import 'pretty-checkbox/dist/pretty-checkbox.min.css';
import 'pretty-checkbox-vue/dist/pretty-checkbox-vue.min.js';
import PrettyCheckBox from 'pretty-checkbox-vue';
import BootstrapVue from 'bootstrap-vue';
import request from './request';
import viewRequest from './requestdetail';
import viewChanges from './requestlist';
import App from './App';
import store from './store';
var css = require('./hooks-css.js');
Vue.use(BootstrapVue);
Vue.use(VueRouter);
Vue.use(resource);
Vue.use(VModal);
Vue.use(PrettyCheckBox);

require('custom-event-polyfill');

const routes = [
    {
        path: '/change/request',
        component: request,
        name: 'request'
    },
    {
        path:'/change/request/:camefrom/:id',
        component: viewRequest,
        name: 'detail',
    },
    {
        path: '/changes/',
        component: viewChanges,
        name: 'list',
    }
];

const router = new VueRouter({
  routes,
  mode: 'history',
});

new Vue({
    router,
}).$mount('#menu');

const app = new Vue({
    router,
    store,
    components:{
        alert
    },
    watch:{
        $route:function () {
            let vm =this;
        }
    },
    computed:{
    },
    render: h => h(App)
}).$mount('#app');