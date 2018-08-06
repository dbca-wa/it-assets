<template>
<div>
    <div id="filtering" class="callout warning hide"></div>

    <div class="grid-container">
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
            <img src="//static.dbca.wa.gov.au/images/loading.gif"/>
        </div>

        <div class="contact grid-x grid-padding-x align-middle" v-for="(user, i) in paginated('filterUsers')" v-bind:key="i">
            <div class="cell medium-shrink small-2">
                <a target="_blank" v-bind:href="`/address-book/user-details?email=${ user.email }`">
                    <img class="float-left" style="height: 4rem; width: 4rem;" src="//static.dbca.wa.gov.au/images/icons/photo_placeholder.svg" />
                </a>
            </div>
            <div class="cell auto">
                <ul class="no-bullet shrink">

                    <li><a target="_blank" v-bind:href="`/address-book/user-details?email=${ user.email }`"><b>{{ user.name }} <span v-if="user.preferred_name">({{ user.preferred_name }})</span></b></a></li>
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
                    <li v-if="user.location_id"><b>Loc:</b>&nbsp;<a target="_blank" v-bind:href="`/locations/location-details/?location_id=${ user.location_id }`">{{ user.location_name }}</a></li>
                    <li v-if="user.org_primary"><b>Unit:</b>&nbsp;{{ user.org_primary.name }}<span v-if="user.org_primary.acronym">&nbsp;({{ user.org_primary.acronym }})</span></li>
                    <li v-if="user.org_secondary"><b>Dep:</b>&nbsp;{{ user.org_secondary.name }}<span v-if="user.org_secondary.acronym">&nbsp;({{ user.org_secondary.acronym }})</span></li>
                </ul>
            </div>
            <div class="cell shrink show-for-small-only"> 
                <a v-bind:href="`tel:${user.phone_landline}`" class="button hollow">📞</a>
                <a v-bind:href="`mailto:${ user.email }`" class="button hollow">🖂</a>
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
</div>
</template>
<style lang="scss">

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
dl, dl dd, ul { margin: 0!important; }
table .shrink * { font-size: 0.7rem }

.loading-icon {
    padding: 2em;
    text-align: center;
}


</style>
<script>
//import $ from 'jquery';
import { Search } from 'js-search';
import debounce from 'debounce';

import { fetchUsers } from './api';


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
            users: [],
            perPageChoices: [10, 25, 50, 100],
            perPage: 25,
            searchQuery: '',
            paginate: ['filterUsers'],
        };
    },
    props: {
        itAssetsUrl: String,
    },
    computed: {
        filteredUsers: function () {
            return this.users.filter(function(el) {return el.visible});
        }
    },
    methods: {
        update: function () {
            var vm = this;
            fetchUsers(this.itAssetsUrl, function (data) {
                searchDB.addDocuments(data);
                vm.users = data;
            }, function(error) {
                console.log(error);
            });
        },
        search: debounce( function () {
            var vm = this;
            if (!vm.searchQuery) {
                vm.users.forEach(function (el) {
                    el.visible = true;
                });
            } else {
                var query = searchDB.search(vm.searchQuery).map( function (el) {
                    return el.id;  
                });
                vm.users.forEach( function (el) {
                    el.visible = query.indexOf(el.id) != -1;
                } );
            }
        }, 100 ),
    },
    mounted: function () {
        var vm = this;
        vm.update();
    }
}
</script>
