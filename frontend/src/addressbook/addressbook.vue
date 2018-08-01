<template>
<div id="addressbook_base" class="f6inject">
    <div class="row">
        <div class="small-12 medium-6 large-4 columns">
            <h1>Address Book</h1>
        </div>
        <div class="columns end">
            <div class="callout secondary">
                <p>Recommended web browser is Firefox or Chrome. Information load times may be longer in Internet Explorer.
                Please provide feedback or suggestions for the Address Book to OIM <b><a href="mailto:oimsupport@dbca.wa.gov.au">Service Operations</a></b></p>
                <p><strong><a href="/address-book/organisational-structure/">Lookup Organisation Structure</a></strong> - department structure 
                [Tier 1 (Department), Tier 2, Tier 3, ..., Tier N] can be used to filter and search for staff.<br>
                <i>* Note: To filter or search by Cost Centre, enter the Chart of Accounts entity prefix (e.g. DPaW, ZPA, BGPA, RIA, CPC) and the Cost Centre number e.g. DPaW-890, ZPA-41, BGPA-111, etc. </i></p>
                <p><strong><a href="/locations/">Lookup Office Location</a></strong> - department office location map can be used to filter and search for staff.</p>
                <p><b>Contact <abbr class="glossary" title="Office for Information Management">OIM </abbr><a href="mailto:oimsupport@dbca.wa.gov.au">Service Operations</a> to update manager  (e.g. director general, deputy director general, executive director, director, cost centre manager) approved  information in the Address Book.</b></p>
                <p><i><b>Important Notice:</b> Address Book information supports the department's shared IT common operating environment (Shared IT COE) <a href="/support/identity-and-access-services/">identity and access management</a>. Cost Centre managers are responsible for ensuring the Address Book information is correct for their staff.</i></p>
            </div>
        </div>
    </div>

    <div class="row">
        <input placeholder="Search" v-model="searchQuery" v-on:keyup="search"/> 
    </div>
    <div id="filtering" class="callout warning hide"></div>
    <table cellspacing="0" class="display responsive" role="grid" width="100%">
        <thead>
            <tr>
                <th>Account and Contact Info</th>
                <th>Office Location</th>
                <th>Organisation</th>
            </tr>
        </thead>

        <tr v-if="users.length == 0">
            <div id="loading-icon" class="columns small-12">
                <img src="//static.dbca.wa.gov.au/images/loading.gif"/>
            </div>
        </tr>
        <paginate name="filterUsers" ref="paginator" tag="tbody" v-bind:list="filteredUsers" v-bind:per="10">
            <tr v-for="(user, i) in paginated('filterUsers')" v-bind:key="i">
                <td><img class="float-right" style="height: 6.5rem; width: 6.5rem;" src="//static.dbca.wa.gov.au/images/icons/photo_placeholder.svg" v-bind:data-src="user.photo_url"/>
                    <dl>
                        <dt class="fn" style="margin-bottom: 0; line-height: 1.2;">
                            <a target="_blank" v-bind:href="`/address-book/user-details?email=${ user.email }`">{{ user.name }} <span v-if="user.preferred_name">({{ user.preferred_name }})</span></a>
                        </dt>
                        <dd>
                            <i style="font-size: 90%;">{{ user.title }}</i>
                        </dd>
                        <dd>
                            <ul class="no-bullet shrink">
                                <li v-if="user.phone_landline">
                                    <span>Phone: <a v-bind:href="`tel:${user.phone_landline}`">{{ user.phone_landline }}</a> </span>&nbsp;<span v-if="user.phone_extension">(VoIP ext. <a v-bind:href="`tel:${user.phone_extension}`">{{ user.phone_extension }}</a>)</span> 
                                </li>
                                <li v-if="user.phone_mobile">
                                    Mobile: <a v-bind:href="`tel:${user.phone_mobile}`">{{ user.phone_mobile }}</a>
                                </li>
                                <li class="email"><a v-bind:href="`mailto:${ user.email }`">{{ user.email }}</a></li>
                            </ul>
                        </dd>
                    </dl>
                </td>
                <td class="shrink">
                    <dl v-if="user.location_id">
                        <dt class="fn">
                            <a target="_blank" v-bind:href="`/locations/location-details/?location_id=${ user.location_id }`">{{ user.location_name }}</a>
                        </dt>
                        <dd>
                            <ul class="no-bullet">
                                <li>{{ user.location_address }}</li>
                                <li v-if="user.location_pobox">{{ user.location_pobox }}</li>
                                <li v-if="user.location_phone">Phone: {{ user.location_phone }}</li>
                                <li v-if="user.location_fax">Fax: {{ user.location_fax }}</li>
                            </ul>
                        </dd>
                    </dl>
                </td>
                <td class="shrink">
                    <dl>
                        <dt>
                            {{ user.cc_name }} {{ user.cc_code }}
                        </dt>
                        <dd>
                            <ul class="no-bullet">
                                <li v-for="(unit, i) in user.org_units" v-bind:key="unit.name" v-bind:class="`org_${i}_id`">{{ unit.name }} <span v-if="unit.acronym">({{ unit.acronym }})</span></li>
                            </ul>
                        </dd>
                    </dl>
                </td>
            </tr>
        </paginate>
    </table>
    <paginate-links for="filterUsers" v-bind:classes="{'ul': 'pagination', '.active': 'current'}" v-bind:show-step-links="true" v-bind:limit="4" ></paginate-links> <span v-if="$refs.paginator">Viewing {{ $refs.paginator.pageItemsCount }}</span>
</div>
</template>
<style>

.float-right {
    float: right !important;
}

.nowrap { white-space: nowrap; }
dl, dl dd, ul { margin: 0!important; }
table .shrink * { font-size: 0.7rem }
#loading-icon {
    padding: 2em;
    text-align: center;
}


</style>
<script>
import 'foundation-sites';
//import $ from 'jquery';
import { Search } from 'js-search';
import debounce from 'debounce';

import '../foundation-min.scss';
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
    data: function () {
        return {
            users: [],
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
