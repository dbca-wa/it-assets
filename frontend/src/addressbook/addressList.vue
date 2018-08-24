<template>
<div>
    <div id="filtering" class="callout warning hide"></div>

    <div class="grid-container">
        <div class="contact-header grid-x grid-padding-x align-middle" v-if="addressFilters.field_id">
            <div class="cell shrink">
                Filtering by: {{ addressFilters.name }}
            </div>
            <div class="cell auto">
                <button class="button hollow" v-on:click="$emit('clearFilters')">Clear filter</button>
            </div>
        </div>
        <div class="contact-header grid-x grid-padding-x">
            <div class="cell shrink">
                <label>
                    Show
                    <select class="contact-per-page" v-model="perPage">
                        <option v-for="pp in perPageChoices" v-bind:key="pp" v-bind:value="pp">{{ pp }}</option>
                    </select>
                    entries
                </label>
            </div>
            <div class="cell auto">

            </div>
            <div class="cell shrink">
                <label>
                    Search:
                    <input type="text" class="contact-search" placeholder="Name, title, location..." v-model="searchQuery" v-on:keyup="search"/> 
                </label>
            </div>
        </div>
    </div>


    <paginate name="filterUsers" ref="paginator" tag="div" class="contact-list grid-container" v-bind:list="filteredUsers" v-bind:per="perPage">

        <div class="contact grid-x grid-padding-x align-middle align-center cell" v-if="paginated('filterUsers').length == 0">
            <img v-if="usersList.length == 0" v-bind:src="loadingImg"/>
            <span v-else>No users match your query. Try removing some filters.</span>
        </div>

        <div class="contact grid-x grid-padding-x align-middle" v-for="(user, i) in paginated('filterUsers')" v-bind:key="i">
            <div class="cell medium-shrink small-2">
                <a v-on:click="showModal(true, user)">
                    <img class="float-left" style="width: 4rem;" v-bind:src="user.photo_url" />
                </a>
            </div>
            <div class="cell auto">
                <ul class="no-bullet shrink">

                    <li><a v-on:click="showModal(true, user)"><b>{{ user.name }} <span v-if="user.preferred_name">({{ user.preferred_name }})</span></b></a></li>
                    <li><i style="font-size: 90%;">{{ user.title }}</i></li>
                </ul>
            </div>
            <div class="cell auto show-for-medium details">
                <ul class="no-bullet shrink">
                    <li><a v-bind:href="`mailto:${ user.email }`">{{ user.email }}</a></li>
                    <li v-if="user.phone_landline"><b>Ph:</b>&nbsp;<a v-bind:href="`tel:${user.phone_landline}`">{{ user.phone_landline }}</a><span v-if="user.phone_extension">&nbsp;(VoIP ext. <a v-bind:href="`tel:${user.phone_extension}`">{{ user.phone_extension }}</a>)</span></li>
                    <li v-if="user.phone_mobile"><b>Mob:</b>&nbsp;<a v-bind:href="`tel:${user.phone_mobile}`">{{ user.phone_mobile }}</a></li>
                </ul>
            </div>
            <div class="cell auto show-for-large details">
                <ul class="no-bullet shrink">
                    <li v-if="user.location_id"><b>Loc:</b>&nbsp;<a target="_blank" v-bind:href="`#?location_id=${ user.location_id }`">{{ user.location_name }}</a></li>
                    <li v-if="user.org_primary"><b>Unit:</b>&nbsp;{{ user.org_primary.name }}<span v-if="user.org_primary.acronym">&nbsp;({{ user.org_primary.acronym }})</span></li>
                    <li v-if="user.org_secondary"><b>Grp:</b>&nbsp;{{ user.org_secondary.name }}<span v-if="user.org_secondary.acronym">&nbsp;({{ user.org_secondary.acronym }})</span></li>
                </ul>
            </div>
            <div class="cell shrink show-for-small-only side-controls"> 
                <div class="button-group">
                    <a v-bind:href="`tel:${user.phone_landline}`" class="button hollow"><i class="fi-telephone"></i></a>
                    <a v-bind:href="`mailto:${ user.email }`" class="button hollow"><i class="fi-mail"></i></a>
                </div>
            </div>
        </div>


    </paginate>
    <div class="grid-container">
        <div class="contact grid-x grid-padding-x">
            <div class="cell shrink">
                 <span v-if="$refs.paginator">Viewing {{ $refs.paginator.pageItemsCount }}</span>
            </div>
            <div class="cell auto">

            </div>
            <div class="cell shrink">
                <paginate-links for="filterUsers" v-bind:classes="{'ul': 'pagination', '.active': 'current'}" v-bind:show-step-links="true" v-bind:limit="4" ></paginate-links>
            </div>
        </div>
    </div>

    <div class="reveal-overlay" v-on:click="showModal(false)" v-bind:class="{show: modalVisible}">
        <div class="small reveal" v-on:click.stop tabindex="-1" v-if="modalUser">
            <h3>{{ modalUser.name }}</h3>
            <p><i>{{ modalUser.title }}</i></p>
            <button class="close-button" type="button" v-on:click="showModal(false)"><span aria-hidden="true">×</span></button>
        </div>
    </div>
</div>
</template>
<style lang="scss">

.f6inject {
    .float-right {
        float: right !important;
    }

    .details {
        font-size: 0.85rem;
    }

    .contact-header {
        background-color: #e6e6e6;
        border: 1px solid #e6e6e6;

        .contact-per-page, .contact-search {
            display: inline-block;
            margin: 0 0.5em;
        }
        
        .contact-per-page {
            width: 6em;
        }

        .contact-search {
            width: 12em;
        }

        .button, .button:hover {
            background-color: white;
            margin-bottom: 0;
        }
    }


    .contact-list {

    }

    .contact-list .contact {
        padding: 0.5em 0;
        border: 1px solid #f1f1f1;
    }

    .contact-list .contact:nth-child(2n) {
        background-color: #f1f1f1;
    }

    .nowrap { white-space: nowrap; }
    table .shrink * { font-size: 0.7rem }

    .loading-icon {
        padding: 2em;
        text-align: center;
    }

    .cell ul {
        margin-bottom: 0;
    }

    .side-controls .button-group {
        margin-bottom: 0;
        .button {
            font-size: 1.1rem;
        }
    }


}

</style>
<script>
import { mapGetters } from 'vuex';
import { Search } from 'js-search';
import debounce from 'debounce';

import { fetchUsers } from './api';

import loadingImg from './assets/loading.gif';


var searchDB = new Search('id');
var searchKeys = [
    'name', 'preferred_name', 'email', 'username', 'title', 'employee_id',
    'phone_landline', 'phone_extension', 'phone_mobile',
    'location_name', 'cc_code', 'cc_name', 'org_search',
];
searchKeys.forEach(function (key) {
    searchDB.addIndex(key);
});


export default {
    name: 'addressList',
    data: function () {
        return {
            perPageChoices: [10, 25, 50, 100],
            perPage: 25,
            searchQuery: '',
            paginate: ['filterUsers'],
            loadingImg,
            modalUser: {},
            modalVisible: false,
        };
    },
    props: {
        addressFilters: Object,
    },
    computed: {
        // used to render the list of users
        filteredUsers: function () {
            return this.usersList.filter(function(el) {return el.visible});
        },
         // bind to getters in store.js
        ...mapGetters([
            'usersList'
        ]),
    },
    methods: {
        updateVisible: function () {
            var vm = this;
            var query = null;
           
            // get a list of IDs that match the current search term (if exists)
            if (vm.searchQuery) {
                query = searchDB.search(vm.searchQuery).map(function (el) {
                    return el.id;
                });
            } else {
                query = vm.usersList.map(function (el) {
                    return el.id;
                });
            }
    
            // apply address filter as a callback function.
            // address filter should have these properties:
            // - field_id: property name on the user object to match on
            // - name: string to show at the top next to "Filtering by:"
            // - value: value to match with
            // - mode: modifier to indicate a special type of match

            // here's one for a basic match-by-value
            var check_func = function (el) {
                return vm.addressFilters.field_id ? el[vm.addressFilters.field_id] == vm.addressFilters.value : true;
            };

            // add specific filter overrides for more complex lookups
            // this one searches inside the org_units list for a match
            if ((vm.addressFilters.mode == 'cascade') && (vm.addressFilters.field_id == 'org_id')) {
                check_func = function (el) {
                    return el.org_units.findIndex(function (fl) {
                        return fl.id == vm.addressFilters.value;
                    }) != -1;
                };
            }

            vm.usersList.forEach(function (el) {
                el.visible = check_func(el);
                el.visible &= query.includes(el.id);
            });
        },
        // flip the user modal on and off
        showModal: function (state, user) {
            if (user) {
                this.modalUser = user;
            }
            this.modalVisible = state;
        },
        // if the current search term changes, update the visible status of each record
        search: debounce( function () {
            this.updateVisible();
        }, 100 ),
    },
    watch: {
        addressFilters: function (val, oldVal) {
            // if the current address filter changes, update the visible status of each record
            this.updateVisible();
        },
        usersList: function (val, oldVal) {
            // when the user list changes, update the search index
            searchDB.addDocuments(val);
        }
    },
    mounted: function () {
        // on first mount, update the search index with the current user list
        searchDB.addDocuments(this.usersList);
    }
}
</script>
