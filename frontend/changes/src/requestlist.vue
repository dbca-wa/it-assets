<template lang="html">
 <div class="request">
    <navigation></navigation>
    <div class="container" style="overflow:visible;">
        <h1>Changes</h1>
        <div class="row">
            <div class="col-lg-12">
                <div class="well" style="overflow: visible;">
                    <div class="row" style="margin-bottom:10px;">
                        <div class="col-md-4">
                            <label for="">Date From</label>
                            <div class="input-group date" id="change-date-from">
                            <input type="text" class="form-control" placeholder="DD/MM/YYYY" v-model="filterDateFrom">
                            <span class="input-group-addon">
                                <span class="glyphicon glyphicon-calendar"></span>
                            </span>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <label for="">Date To</label>
                            <div class="input-group date" id="change-date-to">
                            <input type="text" class="form-control"  placeholder="DD/MM/YYYY" v-model="filterDateTo">
                            <span class="input-group-addon">
                                <span class="glyphicon glyphicon-calendar"></span>
                            </span>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-2">
                            <label>Urgency</label>
                            <div id="urgency">
                                <select ref="urgency" class="form-control" v-model="urgencyno" style="width:100%;">
                                    <option value=99>All</option>
                                    <option value=0>Low</option>
                                    <option value=1>Medium</option>
                                    <option value=2>High</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-2">
                            <label>Status</label>
                            <div id="status">
                                <select ref="status" class="form-control" v-model="statusno" style="width:100%;">
                                    <option value=99>All</option>
                                    <option value=0>Open</option>
                                    <option value=1>Approved</option>
                                    <option value=2>Complete</option>
                                    <option value=3>Rejected</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-2" style="display:none;" ref="my_changes" id="my-changes">
                            <label id="my-changes-label">My Changes</label>
                            <div id="checkbox">
                                <p-check class="p-switch p-fill" v-model="mychanges" v-on:change="changeschecked()"/>
                            </div>
                        </div>
                    </div>
                    <div class="row" style="margin-top:20px;">
                        <div class="col-lg-12">
                            <datatable ref="changes_table" id="changes-table" :dtOptions="dtOptions" :dtHeaders="dtHeaders"></datatable>
                        </div>
                        <modal name="detailModal" height="auto"
                            transition="nice-modal-fade"
                            :resizeable="false"
                            :delay="100"
                            :scrollable="true"
                            :draggable="false">
                            <div class="detailModal-content" align="center">
                                <h1 id="ModalTitle">Change Request # {{currentId}}</h1>
                                <div align="left" style="padding:15px;">
                                    <div class = "row">
                                        <div class="col-sm-8">
                                            Title: {{ title }}
                                        </div>
                                        <div class="col-sm-4">
                                            Status: {{ status }}
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-12">
                                            Description: {{ description }}
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-12">
                                            System: {{ itsystem }}
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-6">
                                            Start: {{ start }}
                                        </div>
                                        <div class="col-sm-2"/>
                                        <div class="col-sm-4">
                                        End: {{ end }}
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-6">
                                            Urgency: {{ urgency }}
                                        </div>
                                        <div class="col-sm-2"/>
                                        <div class="col-sm-4">
                                            Change Type: {{ changetype }}
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-4">
                                            Requestor: {{ requestor }}
                                        </div>
                                        <div class="col-sm-4">
                                            Approver: {{ approver }}
                                        </div>
                                        <div class="col-sm-4">
                                            Implementor: {{ implementor }}
                                        </div>
                                    </div>
                                </div>
                                <div align="left" style="margin-bottom:20px; margin-left:20px;">
                                    <button type="button" v-on:click="editChange()" class="btn btn-primary" style="width:80px;font-weight:bold;">View</button>
                                </div>
                            </div>
                        </modal>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
</template>


<script>
import navigation from './components/navigation.vue'
import {$,datetimepicker,moment,select2} from "./hooks.js"
import datatable from './utils/datatable.vue'
import { mapGetters } from 'vuex'
export default {
    name:'request',
    el: '#requestslist',
    components:{
        datatable,
        'navigation' : navigation
    },
    created(){
        let vm = this;
        vm.retrieveUser();
    },
    data:function () {
        let vm =this;
        return {
            dtOptions:{
                responsive: true,
                serverSide:true,
                processing:true,
                searchDelay: 500,
                ajax: {
                    url: "/api/v2/changerequest/",
                    method: 'GET',
                    dataSrc: 'results',
                    data :function (d) {
                        if (vm.filterDateFrom) {
                            d.filterfrom = vm.filterDateFrom;
                        }
                        if (vm.filterDateTo) {
                            d.filterto = vm.filterDateTo;
                        }
                        if(vm.urgencyno){
                            d.urgency = vm.urgencyno;
                        }
                        if(vm.statusno){
                            d.status = vm.statusno;
                        }
                        if(vm.mychanges || vm.isLoading){
                            d.mychanges = true;
                        }
                    }
                },
                columns:[
                    {
                    data:'id',
                    orderable: true,
                    mRender: function(data, type, full){
                        var column = "<a href='#' class='showModal' data-rate=\"__RATE__\" >" + data + "</a></td>";
                        column = column.replace(/__RATE__/g, data);
                        return column;
                    }
                    
                },  {
                    data: 'status',
                    orderable: true,
                    mRender: function(data, type, full) {
                        if (data || data == 0){
                           var status = data;
                            if (status == 0){
                                return "Open";
                            } else if (status == 1){
                                return "Approved";
                            } else if (status == 2){
                                return "Complete";
                            } else {
                                return "Rejected";
                            } 
                        } else {
                            return "";
                        }
                        
                    }
                }, {
                    data: 'title',
                }, {
                    data: 'it_system',
                    orderable: true,
                    mRender: function(data, type, full){
                        if(data){
                            return full.it_system.name;
                        } else if (full.alternate_system){
                            return full.alternate_system;
                        } else {
                            return "";
                        }
                    }
                }, {
                    data: 'change_start',
                    orderable: true,
                    mRender: function(data, type, full) {
                        if (data) {
                            return moment(full.change_start).format("DD/MM/YYYY HH:mm");
                        }
                        else {
                            return "";
                        }
                    }
                }, {
                    data: 'urgency',
                    orderable: true,
                    mRender: function(data, type, full) {
                        if (data || data == 0) {
                            if (data == 0){
                                return "Low";
                            } else if (data == 1){
                                return "Medium";
                            } else {
                                return "High";
                            }
                        }
                        else {
                            return "";
                        }
                    }
                }, {
                    data: 'editable',
                    orderable: false,
                    mRender: function(data, type, full) {
                        if (data){
                            if (vm.userpk == full.requestor.id){
                                var column = "<a href='/change/request/1/\__RATE__\'>Edit</a></td>";
                                column = column.replace(/__RATE__/g, full.id);
                                return column;
                            } else if(vm.userpk == full.approver.id) {
                                var column = "<a href='/change/request/1/\__RATE__\'>Approve/Reject</a></td>";
                                column = column.replace(/__RATE__/g, full.id);
                                return column;
                            } else if (vm.userpk == full.implementor.id){
                                var column = "<a href='/change/request/1/\__RATE__\'>Complete</a></td>";
                                column = column.replace(/__RATE__/g, full.id);
                                return column;
                            } else {
                                return "";
                            }
                        } else {
                            return "";
                        }

                    }
                }
                ],language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
            },
            dtHeaders: ['ID', 'Status', 'Title', 'IT System', 'Start Date', 'Urgency', 'Actions'],
            userpk: '',
            filterDateFrom: null,
            filterDateTo: null,
            currentId: '',
            title:'',
            description:'',
            status:'',
            itsystem:'',
            start:'',
            end:'',
            urgency:'',
            changetype:'',
            requestor:'',
            approver:'',
            implementor:'',
            datepickerOptions:{
                format: 'DD/MM/YYYY',
                showClear:true,
                useCurrent:false,
                keepInvalid:true,
                allowInputToggle:true
            },
            filterDateFrom:"",
            filterDateTo:"",
            urgencyno: '',
            urgencysel: '',
            statusno:'',
            statussel:'',
            mychanges: false,
            isLoading: true,
        }
    },
    watch:{
    },
    computed:{
    },
    methods:{
        changeschecked: function(){
            let vm = this;
            vm.$refs.changes_table.vmDataTable.ajax.reload();
        },
        editChange: function(){
            let vm = this;
            location.href = "/change/request/1/" + vm.currentId;
        },
        getCookie: function(name) {
            var cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                var cookies = document.cookie.split(';');
                for (var i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },
        processForm: function(){
            let vm = this;
        },
        validateDates: function(){
            let vm = this;
            var isValid = true;
            vm.errorString = null;
            if(!vm.changeDateEnd){
                isValid = false;
                return isValid;
            }
            if(moment(vm.changeDate, "DD/MM/YYYY HH:mm").isAfter(moment(vm.changeDateEnd, "DD/MM/YYYY HH:mm"))){
                isValid = false;
                vm.errorString = "Dates are invalid. Please ensure that the start date and time is before the end date and time."
                return isValid;
            }
            return isValid;
        },
        retrieveUser: function(){
            // Gets the current user.
            let vm = this;
            $.ajax({
                url: "/api/profile/",
                method: 'GET',
                success: function(data, stat, xhr){
                    vm.userpk = data.objects[0].pk;
                    vm.mychanges = true;
                    document.getElementById('my-changes').style.display = "block";
                },
                error: function(data, stat, xhr){
                    console.log("Not logged in.");
                }
            });
        },
        fetchActiveLink: function(){
            var ch = document.getElementById('changeslink');
            ch.classList.add('active');
        },
        fetchSystems: function(){
            let vm =this;
            if (vm.itsystems.length == 0) {
                vm.$store.dispatch("fetchItsystems");
            }
        },
        fetchRequestors: function(){
            let vm =this;
            
        },
        fetchStandardChanges: function(){
            let vm = this;
            
        },
        addEventListeners: function(){
            let vm = this;
            vm.dateToPicker.on('dp.change', function(e){
                if (vm.dateToPicker.data('DateTimePicker').date()) {
                    vm.filterDateTo =  e.date.format('DD/MM/YYYY');
                    vm.$refs.changes_table.vmDataTable.ajax.reload();
                }
                else if (vm.dateToPicker.data('date') === "") {
                    vm.filterDateTo = "";
                    vm.$refs.changes_table.vmDataTable.ajax.reload();
                }

             });

            vm.dateFromPicker.on('dp.change',function (e) {
                if (vm.dateFromPicker.data('DateTimePicker').date()) {
                    vm.filterDateFrom = e.date.format('DD/MM/YYYY');
                    vm.dateToPicker.data("DateTimePicker").minDate(e.date);
                    vm.$refs.changes_table.vmDataTable.ajax.reload();
                }
                else if (vm.dateFromPicker.data('date') === "") {
                    vm.filterDateFrom = "";
                    vm.$refs.changes_table.vmDataTable.ajax.reload();
                }

            });
            // Set the urgency selector
            $(vm.$refs.urgency).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.urgencysel = selected.select2('data')[0].text;
                vm.urgencyno = selected.val();
                vm.$refs.changes_table.vmDataTable.ajax.reload();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.urgencysel = "";
                vm.urgencyno = "";
                vm.$refs.changes_table.vmDataTable.ajax.reload();
            });
            // Set the status selector
            $(vm.$refs.status).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.statussel = selected.select2('data')[0].text;
                vm.statusno = selected.val();
                vm.$refs.changes_table.vmDataTable.ajax.reload();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.statussel = "";
                vm.statusno = "";
                vm.$refs.changes_table.vmDataTable.ajax.reload();
            });
            vm.$refs.changes_table.vmDataTable.on('click','.showModal', function(e) {
                e.preventDefault();
                vm.currentId = e.currentTarget.innerText;
                //Show modal
                console.log('showing modal...');
                $.ajax({
                    url: "/api/v2/changerequest/" + vm.currentId + '/',
                    method: 'GET',
                    type: 'GET',
                    contentType: false,
                    success: function(data, stat, xhr){
                        vm.title = data.title;
                        vm.description = data.description;
                        vm.start = moment(data.change_start).format("DD/MM/YYYY HH:mm");
                        vm.end = moment(data.change_end).format("DD/MM/YYYY HH:mm");
                        vm.requestor = data.requestor.name;
                        vm.approver = data.approver.name;
                        vm.implementor = data.implementor.name;

                        if(data.it_system){
                            vm.itsystem = data.it_system.name;
                        } else {
                            vm.itsystem = data.alternate_system;
                        }

                        if(data.status == 0){
                            vm.status = 'Open';
                        } else if (data.status == 1){
                            vm.status = 'Approved';
                        } else if (data.status == 2){
                            vm.status = 'Complete';
                        } else {
                            vm.status = 'Rejected';
                        }

                        if(data.urgency == 0){
                            vm.urgency = 'Low';
                        } else if (data.urgency == 1){
                            vm.urgency = 'Medium';
                        } else {
                            vm.urgency = 'High';
                        }

                        if (data.change_type == 0){
                            vm.changetype = 'Normal';
                        } else if (data.change_type == 1){
                            vm.changetype = "Standard";
                        } else {
                            vm.changetype = "Emergency";
                        }

                        vm.$modal.show('detailModal');
                    }
                });
            });
            vm.isLoading = false;
        },
    },
    mounted:function () {
        let vm = this;
        vm.fetchActiveLink();
        vm.dateFromPicker = $('#change-date-from').datetimepicker(vm.datepickerOptions);
        vm.dateToPicker = $('#change-date-to').datetimepicker(vm.datepickerOptions);
        vm.addEventListeners();


        
    }

}
</script>

<style lang="css">
    .text-warning{
        color:#f0ad4e;
    }
    @media print {
        .col-md-3 {
            width: 25%;
            float:left;
        }

        a[href]:after {
           content: none !important;
        }

        #print-btn {
            display: none !important;
        }
    }
</style>
