<!DOCTYPE html>
<template>
    <div class="request">
        <navigation></navigation>
        <div class="container" style="overflow:visible;">
            <h1>Make a request</h1>
            <div class="well" style="overflow:visible;">
                <form name="requestForm" @submit.prevent="processForm">
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Request Title</label>
                            </div>
                            <div class="col-sm-9">
                                <input id="title" v-model="title" class="form-control" name="title" type="text" required/>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Description</label>
                            </div>
                            <div class="col-sm-9">
                                <textarea id="description" v-model="description" class="form-control" name="description" :rows="4"/>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Requestor</label>
                            </div>
                            <div class="col-sm-9">
                                <select ref="requestor" class="form-control" v-model="requestor" id="requestor" style="width:100%;" required>
                                    <option v-for="requestor in requestors" :value="requestor.pk">{{requestor.name }}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Approver</label>
                            </div>
                            <div class="col-sm-9">
                                <select ref="approver" class="form-control" v-model="approver" id="approver" style="width:100%;" required>
                                    <option v-for="requestor in requestors" :value="requestor.pk">{{requestor.name }}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Implementor</label>
                            </div>
                            <div class="col-sm-9">
                                <select ref="implementor" class="form-control" v-model="implementor" id="implementor" style="width:100%;">
                                    <option v-for="requestor in requestors" :value="requestor.pk">{{requestor.name }}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Urgency</label>
                            </div>
                            <div class="col-sm-9">
                                <select ref="urgency" class="form-control" v-model="urgency" id="urgency" style="width:100%;" required>
                                    <option v-for="urgency in urgencies" :value="urgency.id">{{urgency.name}}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Change Type</label>
                            </div>
                            <div class="col-sm-9">
                                <select ref="changetype" class="form-control" v-model="changetype" id="changetype" style="width:100%;" required>
                                    <option v-for="change in changes" :value="change.id">{{change.name}}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="row" v-show="changetype == '1'">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Standard Change</label>
                            </div>
                            <div class="col-sm-9">
                                <select ref="standardchange" class="form-control" v-model="standardchange" id="standardchange" style="width:100%;">
                                    <option v-for="standard in standardchanges" :value="standard.id">{{standard.name}}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >IT System</label>
                            </div>
                            <div class="col-sm-9">
                                <select ref="itsystem" class="browser-default" v-model="itsystem" id="itsystem" style="width:100%;">
                                    <option>System not listed</option>
                                    <option v-for="system in itsystems" :value="system.id">{{system.name}}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="row" v-if="itsystem == 'System not listed'">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Alternate IT System</label>
                            </div>
                            <div class="col-sm-9">
                                <input type="text" class="form-control" palceholder="System Name" name="altsystem" v-model="altsystem" id="altsystem"/>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Change Start Date</label>
                            </div>
                            <div class="col-sm-3">
                                <div class="input-group date" id="changeDate">
                                    <input type="text" class="form-control" placeholder="DD/MM/YYYY HH:MM" v-model="changeDate" @blur="validateDates()">
                                    <span class="input-group-addon">
                                        <span class="glyphicon glyphicon-calendar"></span>
                                    </span>
                                </div>
                            </div>
                            <div class='col-sm-1'></div>
                            <div class="col-sm-2">
                                <label >Change End Date</label>
                            </div>
                            <div class="col-sm-3">
                                <div class="input-group date" id="changeDateEnd">
                                    <input type="text" class="form-control" placeholder="DD/MM/YYYY HH:MM" v-model="changeDateEnd" @blur="validateDates()">
                                    <span class="input-group-addon">
                                        <span class="glyphicon glyphicon-calendar"></span>
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Outage</label>
                            </div>
                            <div class="col-sm-9">
                                <input type="checkbox" name="outage" v-model="outage" value="Outage">
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Implementation</label>
                            </div>
                            <div class="col-sm-9">
                                <textarea id="implementation" v-model="implementation" class="form-control" name="implementation" :rows="4"/>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Implementation Documents</label>
                            </div>
                            <div class="col-sm-9">
                                <input type="file" name="impDocs" id="impDocs" />
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Broadcast</label>
                            </div>
                            <div class="col-sm-9">
                                <textarea id="broadcast" v-model="broadcast" class="form-control" name="broadcast" :rows="4"/>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="small-12 medium-12 large-4 columns">
                            <div class="col-sm-2">
                                <label >Notes</label>
                            </div>
                            <div class="col-sm-9">
                                <textarea id="notes" v-model="notes" class="form-control" name="notes" :rows="4"/>
                            </div>
                        </div>
                    </div>
                    <div class="row" v-if="errorString">
                        <div class="alert alert-danger" id="error" role="alert">{{ errorString }}</div>
                    </div>
                    <div class="row">
                        <button type="submit" class="btn btn-primary" style="width:180px;background-color:#4286f4;font-weight:bold;">Submit Request</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</template>

<script>
import navigation from './components/navigation.vue'
import {select2, datetimepicker} from "./hooks.js";
import moment,{ relativeTimeRounding } from 'moment'
import JQuery from 'jquery'
import { mapGetters } from 'vuex'

let $ = JQuery

export default {
    name:'request',
    el: '#requests',
    components : {
        'navigation': navigation
    },
    data: function() {
        let vm = this;
        return {
            requestor: '',
            approver:'',
            implementor:'',
            title:'',
            description:'',
            changetype:'',
            standardchange:'',
            itsystem:'',
            altsystem: '',
            urgency: '',
            outage:'',
            implementation: '',
            broadcast:'',
            notes: '',
            errorString: '',
            changes:{},
            urgencies:{},
            changeDate: null,
            changeDateEnd: null,
            datepickerOptions:{
                format: 'DD/MM/YYYY HH:mm',
                showClear:true,
                useCurrent:true,
                keepInvalid:true,
                allowInputToggle:true,
                stepping:5
            },
            datepickerOptions2:{
                format: 'DD/MM/YYYY HH:mm',
                showClear:true,
                useCurrent:false,
                keepInvalid:true,
                allowInputToggle:true,
                stepping:5
            },

        }
    },
    computed: {
        ...mapGetters([
          'requestors',
          'itsystems',
          'standardchanges',
        ]),
        
    },
    filters: {
        
    },
    props: {

    },
    methods: {
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
            if(vm.validateForm()){
                //Form valid, send to API to save.
                var submitData = {
                    title : vm.title,
                    description: vm.description,
                    requestor: vm.requestor,
                    approver: vm.approver,
                    implementor: vm.implementor,
                    urgency: vm.urgency,
                    changeType: vm.changetype,
                    itSystem: vm.itsystem,
                    altSystem: vm.altsystem,
                    changeStart: vm.changeDate,
                    changeEnd: vm.changeDateEnd,
                    implementation: vm.implementation,
                    broadcast: vm.broadcast,
                    notes: vm.notes
                }
                if(!vm.outage){
                    submitData.outage = false;
                } else {
                    submitData.outage = true;
                }

                $.ajaxSetup({
                    beforeSend: function(xhr){
                        xhr.setRequestHeader('X-CSRFToken', vm.getCookie('csrftoken'))
                    },
                });
                
                $.ajax({
                    url: "/api/v2/changerequest/",
                    method: 'POST',
                    type: 'POST',
                    // data: submitData,
                    data: JSON.stringify(submitData),
                    dataType: 'json',
                    contentType: 'application/json',
                    processData: false,
                    crossDomain: true,
                    xhrFields: {
                        withCredentials: true
                    },
                    success: function(data, stat, xhr) {
                        //Main data sent, now the file must be uploaded.
                        if(document.getElementById('impDocs').files.length > 0){
                            var fileData = new FormData();
                            fileData.append('csrfmiddlewaretoken', vm.getCookie('csrftoken'));
                            fileData.append('id', data.id);
                            // fileData.append('file', document.getElementById('impDocs').files);
                            $.each($('#impDocs')[0].files, function(i, file){
                                fileData.append('file', file);
                            });
                            console.log(fileData);
                            $.ajax({
                                url: "/api/v2/changerequest/" + data.id,
                                method: 'PUT',
                                data: fileData,
                                contentType: false,
                                processData: false,
                                success: function(data, stat, xhr){
                                    console.log("successfully uploaded form and file.")
                                }
                            }) 
                            
                            
                        } else {
                            console.log("Successfully uploaded form, no file to upload.")
                        }
                        
                    },
                    error: function(xhr, stat, err) {
                        console.log('POST error');
                        console.log((xhr.responseJSON && xhr.responseJSON.msg) ? xhr.responseJSON.msg : '"'+err+'" response when communicating with server.');
                    }
                });
            } else {
                console.log("Form was invalid");
            }
        },
        validateForm: function(){
            let vm = this;
            vm.errorString = null;
            var isValid = true;
            if(!vm.title || vm.title == ''|| !vm.requestor || vm.requestor == '' || !vm.approver || vm.approver == '' ||
             !vm.changetype || vm.changetype == '' || !vm.urgency || vm.urgency == ''){
                isValid = false;
                vm.errorString = "A required field is not filled out. please check your form."
                return isValid;
            }
            if(vm.changeDate && vm.changeDateEnd){
                isValid = this.validateDates();
            }
            return isValid;
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
        fetchActiveLink: function(){
            var ch = document.getElementById('newrequestlink');
            ch.classList.add('active');
        },
        fetchChanges: function(){
            this.changes[0] = {'id': 0, 'name':'Normal'};
            this.changes[1] = {'id': 1, 'name':'Standard'};
            this.changes[2] = {'id': 2, 'name':'Emergency'};
        },
        fetchUrgencies: function(){
            this.urgencies[0] = {'id': 0, 'name': 'Low'};
            this.urgencies[1] = {'id': 1, 'name': 'Medium'};
            this.urgencies[2] = {'id': 2, 'name': 'High'};
        },
        fetchSystems: function(){
            let vm =this;
            if (vm.itsystems.length == 0) {
                vm.$store.dispatch("fetchItsystems");
            }
        },
        fetchRequestors: function(){
            let vm =this;
            if (vm.requestors.length == 0) {
                vm.$store.dispatch("fetchRequestors");
            }
        },
        fetchStandardChanges: function(){
            let vm = this;
            if (vm.standardchanges.length == 0){
                vm.$store.dispatch("fetchStandardchanges");
            }
        },
        addEventListeners: function(){
            let vm = this;
            // Set the it systems selector
            $(vm.$refs.itsystem).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.itsystem = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.itsystem = "";
            }); 
            // Set the changes selector
            $(vm.$refs.changetype).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.changetype = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.changetype = "";
            });
            // Set the requestor selector
            $(vm.$refs.requestor).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.requestor = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.requestor = "";
            }); 
            // Set the approver selector
            $(vm.$refs.approver).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.approver = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.approver = "";
            }); 
            // Set the implementor selector
            $(vm.$refs.implementor).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.implementor = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.implementor = "";
            });
            // Set the urgency selector
            $(vm.$refs.urgency).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.urgency = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.urgency = "";
            });
            // Set the standardchange selector
            $(vm.$refs.standardchange).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.standardchange = selected.val();
                for (var i = 0; i < vm.standardchanges.length; i++){
                    var sc = vm.standardchanges[i]
                    if(sc.id == vm.standardchange){
                        $(vm.$refs.title).val(sc.name);
                        vm.title = sc.name;
                        $(vm.$refs.description).val(sc.description);
                        vm.description = sc.description;
                        $(vm.$refs.approver).val(sc.approver);
                        $(vm.$refs.approver).trigger('change');
                        vm.approver = sc.approver;
                        //it_system is the pk
                        //need to get the system_id from api from that.
                        $.get("/api/itsystems/?pk=" + sc.it_system,function(data){
                            $(vm.$refs.itsystem).val(data.objects[0].system_id);
                            $(vm.$refs.itsystem).trigger('change');
                            vm.itsystem = data.objects[0].system_id;
                        });
                        return;
                    }
                }
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.standardchange = "";
            });
        },
    },
    mounted: function(){
        let vm = this;
        vm.fetchActiveLink();
        vm.changeStartPicker = $('#changeDate').datetimepicker(vm.datepickerOptions);
        vm.changeEndPicker = $('#changeDateEnd').datetimepicker(vm.datepickerOptions2);
        vm.changeStartPicker.on("dp.change", function(e){
            vm.changeEndPicker.data("DateTimePicker").minDate(e.date);
            vm.changeDate = moment(e.date).format('DD/MM/YYYY HH:mm');
        });
        vm.changeEndPicker.on("dp.change", function(e){
            vm.changeDateEnd = moment(e.date).format('DD/MM/YYYY HH:mm');
        });
        
        vm.fetchChanges();
        vm.fetchUrgencies();
        vm.fetchRequestors();
        vm.fetchStandardChanges();
        vm.fetchSystems();
        vm.addEventListeners();

    }
};

</script>

<style lang='css'>
textarea{
    resize: none;
}
</style>