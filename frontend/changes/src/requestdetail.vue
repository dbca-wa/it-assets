<!DOCTYPE html>
<template>
    <div class="request">
        <navigation></navigation>
        <div class="container" style="overflow:visible;" v-if="id">
            <h1>Change Request #{{ id }}</h1>
            <div style="overflow:visible;">
                <form name="requestForm" id="requestForm" @submit.prevent="processForm">
                    <div class="small-12 medium-12 large-4 columns">
                        <div class="row">
                            <div class="col-sm-8">
                                <div class="well">
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>Title</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <input v-if="reqUser || appUser" class="form-control" v-model="title" style="width:100%;background-color:white;"/>
                                            <input v-else v-model="title" style="width:100%;" class="form-control" disabled/>
                                        </div>
                                        <div class="col-sm-1">
                                            <label>Status</label>
                                        </div>
                                        <div class="col-sm-2">
                                            <input v-model="status" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                        <div class="col-sm-2">
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>Description</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <textarea v-if="reqUser || appUser" v-model="description" class="form-control" style="width:100%;" :rows="4"/>
                                            <textarea v-else v-model="description" class="form-control" style="width:100%;" disabled :rows="4"/>
                                        </div>
                                        <div class="col-sm-2">
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>IT System</label>
                                        </div>
                                        <div class="col-sm-6">
                                            <div id="itsystem" style="display:none;">
                                                <select ref="itsystem" class="browser-default" v-model="itsystem" style="width:100%;">
                                                    <option>System not listed</option>
                                                    <option v-for="system in itsystems" :value="system.id">{{system.name}}</option>
                                                </select>
                                            </div>
                                            <div v-if="(reqUser || appUser)"/>
                                            <input v-else-if="itSystem" v-model="itSystem" class="form-control" style="width:100%;" disabled/>
                                            <input v-else-if="(reqUser || appUser) && itSystem=='System not listed'" class="form-control" v-model="altSystem" id="altsystem" style="width:100%;" />
                                            <input v-else v-model="altSystem" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-sm-4">
                                <div class="well">
                                    <div class="row">
                                        <div class="col-sm-4">
                                            <label>Start</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <div style="display:none;" class="input-group date" id="changeStart" >
                                                <input type="text" class="form-control" placeholder="DD/MM/YYYY HH:MM" name="changeStart" v-model="changeStart" @blur="validateDates()">
                                                <span class="input-group-addon">
                                                    <span class="glyphicon glyphicon-calendar"/>
                                                </span>
                                            </div>
                                            <input v-if="editable == false" v-model="changeStart" class="form-control" style="width:80%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-4">
                                            <label>End</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <div style="display:none;" class="input-group date" id="changeEnd">
                                                <input type="text" class="form-control" placeholder="DD/MM/YYYY HH:MM" name="changeEnd" v-model="changeEnd" @blur="validateDates()">
                                                <span class="input-group-addon">
                                                    <span class="glyphicon glyphicon-calendar"/>
                                                </span>
                                            </div>
                                            <input v-if="editable == false" v-model="changeEnd" class="form-control" style="width:80%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-4">
                                            <label>Submitted</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <input v-model="submissionDate" class="form-control" style="width:80%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row" id="approved" style="display:none;">
                                        <div class="col-sm-4">
                                            <label>Approved</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <input v-model="approved" class="form-control" style="width:80%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row" id="completed" style="display:none;">
                                        <div class="col-sm-4">
                                            <label>Completed</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <input v-model="dateCompleted" class="form-control" style="width:80%;" disabled/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row" style="margin-top:40px;">
                            <div class="col-sm-8">
                                <div class="well">
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>Urgency</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <div id="urgency" style="display:none;">
                                                <select  ref="urgency" class="form-control" v-model="urgencyno" style="width:100%;">
                                                    <option v-for="urgency in urgencies" :value="urgency.id">{{urgency.name}}</option>
                                                </select>
                                            </div>
                                            <div v-if="reqUser || appUser" />
                                            <input v-else v-model="urgency" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                        <div class="col-sm-6"/>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>Change Type</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <div id="changetype" style="display:none;">
                                                <select ref="changetype" class="form-control" v-model="changetypeno" style="width:100%;">
                                                    <option v-for="change in changes" :value="change.id">{{change.name}}</option>
                                                </select>
                                            </div>
                                            <div v-if="reqUser || appUser" />
                                            <input v-else v-model="changeType" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                        <div class="col-sm-6"/>
                                    </div>
                                    <div class="row" id="standardchangerow" style="display:none;">
                                        <div class="col-sm-2">
                                            <label>Standard Change</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <select ref="standardchange" class="form-control" v-model="standardchange" id="standardchange" style="width:100%;">
                                                <option v-for="standard in standardchanges" :value="standard.id">{{standard.name}}</option>
                                            </select>
                                        </div>
                                        <div class="col-sm-6"/>
                                    </div>
                                    <div class="row" id="approvedby" style="display:none;">
                                        <div class="col-sm-2">
                                            <label>Approval Method</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <input v-model="approvedby" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                        <div class="col-sm-6"/>
                                    </div>
                                </div>
                            </div>
                            <div class="col-sm-4">
                                <div class="well">
                                    <div class="row">
                                        <div class="col-sm-4">
                                            <label>Requestor</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <div id="requestor" style="display:none;">
                                                <select ref="requestor" class="form-control" v-model="reqpk"  style="width:100%;">
                                                    <option v-for="requestor in requestors" :value="requestor.pk">{{requestor.name }}</option>
                                                </select>
                                            </div>
                                            <div v-if="reqUser || appUser"/>
                                            <input v-else v-model="requestor" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-4">
                                            <label>Approver</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <div id="approver" style="display:none;">
                                                <select ref="approver" class="form-control" v-model="apppk" style="width:100%;" required>
                                                    <option v-for="requestor in requestors" :value="requestor.pk">{{requestor.name }}</option>
                                                </select>
                                            </div>
                                            <div v-if="reqUser || appUser"/>
                                            <input v-else v-model="approver" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-4">
                                            <label>Implementor</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <div id="implementor" style="display:none;">
                                                <select ref="implementor" class="form-control" v-model="imppk" style="width:100%;">
                                                    <option v-for="requestor in requestors" :value="requestor.pk">{{requestor.name }}</option>
                                                </select>
                                            </div>
                                            <div v-if="editable"/>
                                            <input v-else v-model="implementor" class="form-control" style="width:100%;" disabled/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row" style="margin-top:40px;">
                            <div class="col-sm-8">
                                <div class="well">
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>Implementation</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <textarea v-if="editable" v-model="implementation" class="form-control" style="width:100%;" :rows="4"/>
                                            <textarea v-else v-model="implementation" class="form-control" style="width:100%;" disabled :rows="4"/>
                                        </div>
                                        <div class="col-sm-2">
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>Notes</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <textarea v-if="editable" v-model="notes" class="form-control" style="width:100%;" :rows="4"/>
                                            <textarea v-else v-model="notes" class="form-control" style="width:100%;" disabled :rows="4"/>
                                        </div>
                                        <div class="col-sm-2">
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-2">
                                            <label>Broadcast</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <textarea v-if="editable" v-model="broadcast" class="form-control" style="width:100%;" :rows="4"/>
                                            <textarea v-else v-model="broadcast" class="form-control" style="width:100%;" disabled :rows="4"/>
                                        </div>
                                        <div class="col-sm-2">
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-sm-4">
                                <div class="well">
                                    <div class="row">
                                        <div class="col-sm-8">
                                            <label>Outage</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <input v-if="editable" type="checkbox" v-model="outage" style="width:100%;"/>
                                            <input v-else type="checkbox" v-model="outage" style="width:100%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-8">
                                            <label>Unexpected Issues</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <input v-if="impUser" type="checkbox" v-model="unexpectedIssues" style="width:100%;"/>
                                            <input v-else type="checkbox" v-model="unexpectedIssues" style="width:100%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-8">
                                            <label>Caused Issues</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <input v-if="editable" type="checkbox" v-model="causedIssues" style="width:100%;" />
                                            <input v-else type="checkbox" v-model="causedIssues" style="width:100%;" disabled/>
                                        </div>
                                    </div>
                                    <div class="row" v-if="editable">
                                        <div class="col-sm-4">
                                            <label>Document Upload</label>
                                        </div>
                                        <div class="col-sm-8">
                                            <input type="file" ref="impDocs" name="impDocs" style="width:100%;" id="impDocs" @change="fileSelected()"/>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-sm-8">
                                            <label>Implementation Documents</label>
                                        </div>
                                        <div class="col-sm-4">
                                            <a :href="implementationDocs" style="width:100%;">Download</a>
                                        </div>
                                    </div>
                                </div>
                                <div class="well" v-if="(changesmade) || (changesmade == false && ((appUser && status == 'Open')|| (impUser && status == 'Approved')))">
                                    <div class="row" style="text-align:center;">
                                        <button v-if="editable && changesmade" type="submit" class="btn btn-primary" style="width:180px;background-color:#4286f4;font-weight:bold;">Save</button>
                                        <button v-if="changesmade == false && appUser && status == 'Open'" type="button" v-on:click="reject()" class="btn btn-danger" style="width:170px;font-weight:bold;">Reject Request</button>
                                        <button v-if="changesmade == false && appUser && status == 'Open'" type="button" v-on:click="approve()" class="btn btn-success" style="width:170px;font-weight:bold;">Approve Request</button>
                                        <button v-if="changesmade == false && impUser && status == 'Approved'" type="button" v-on:click="complete()" class="btn btn-success" style="width:180px;font-weight:bold;">Complete Request</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </form>
            </div>
        </div>
        <div v-else>
            <h1>No matching change request found.</h1>
        </div>
        <modal name="approvalModal"
            transition="nice-modal-fade"
            :min-width="600"
            :min-height="250"
            :resizeable="false"
            :delay="100"
            :draggable="false">
            <div class="approvalModal-content" align="center">
                <h1>Approval notes</h1>
                <textarea name="approvalnotes" ref="approvalnotes" v-model="approvalnotes" class="form-control" style="width:80%;display:block;margin-bottom:20px;" :rows="4"/>
                <button type="button" v-on:click="closeModal()" class="btn btn-danger" style="width:180px;font-weight:bold;">Cancel</button>
                <button type="button" v-on:click="approveNotes()" class="btn btn-success" style="width:180px;font-weight:bold;">Approve</button>
                
            </div>
        </modal>

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
    el: '#request',
    components: {
        'navigation': navigation
    },
    data: function() {
        let vm = this;
        return {
            id: '',
            camefrom: '',
            requestor:'',
            approver:'',
            implementor:'',
            title:'',
            description:'',
            changeType:'',
            changes: {},
            urgency:'',
            urgencies: {},
            submissionDate:'',
            dateCompleted: '',
            changeStart:null,
            changeEnd:null,
            itSystem:'',
            itsystemno:'',
            altSystem:'',
            outage:'',
            implementation:'',
            implementationDocs:'',
            broadcast:'',
            notes:'',
            status:'',
            unexpectedIssues:'',
            causedIssues:'',
            approved: '',
            approvedby: '',
            userpk:'',
            reqpk:'',
            apppk:'',
            imppk:'',
            approvalnotes: '',
            changesmade: false,
            editable: false,
            reqUser: false,
            appUser: false,
            impUser: false,
            isLoading: true,

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
        fileSelected: function(){
            let vm = this;
            vm.changesmade = true;
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
        approve: function(){
            let vm = this;
            vm.$modal.show('approvalModal');
        },
        approveNotes: function(){
            let vm = this;
            vm.closeModal();
            var statusChange = {
                status: 1,
                approvalnotes: vm.approvalnotes,
                camefrom: vm.camefrom
            }
            vm.updateChange(statusChange);
        },
        closeModal: function(){
            this.$modal.hide('approvalModal');
        },
        reject: function(){
            let vm = this;
            var statusChange = {
                status: 3,
            }
            vm.updateChange(statusChange);
        },
        complete: function(){
            let vm = this;
            var statusChange = {
                status: 2,
            }
            vm.updateChange(statusChange);
        },
        updateChange: function(newData){
            let vm = this;
            $.ajaxSetup({
                beforeSend: function(xhr){
                    xhr.setRequestHeader('X-CSRFToken', vm.getCookie('csrftoken'))
                },
            });
            $.ajax({
                url: "/api/v2/changerequest/" + vm.id + '/',
                data: JSON.stringify(newData),
                dataType: 'json',
                contentType: 'application/json',
                method: 'PUT',
                success: function(data, stat, xhr){
                    if (newData.status == 1){
                        vm.status = "Approved";
                        vm.retrieveApproval();
                    } else if (newData.status == 2 || newData.status == 3){
                        if(newData.status == 2){
                            vm.status = "Complete";
                            vm.dateCompleted = moment().format("DD/MM/YYYY HH:mm");
                            document.getElementById('completed').style.display = 'block';
                        } else if (newData.status == 3){
                            vm.status = "Rejected";
                        }
                        vm.editable = false;
                        vm.reqUser = false;
                        vm.appUser = false;
                        vm.impUser = false;
                        document.getElementById('changeStart').style.display = "none";
                        document.getElementById('changeEnd').style.display = "none";
                        $('#urgency').hide();
                        $('#changetype').hide();
                        $('#standardchangerow').hide();
                        $('#itsystem').hide();
                        $('#requestor').hide();
                        $('#approver').hide();
                        $('#implementor').hide();
                    }
                    vm.changesmade = false;
                    vm.checkUser();
                },
                error: function(data, stat, xhr){
                    console.log("Not found");
                }
            });;
        },
        processForm: function(){
            let vm = this;
            var startdate = moment(vm.changeStart);
            var enddate = moment(vm.changeEnd);

            var data = {
                title : vm.title,
                description: vm.description,
                itsystem: vm.itsystem,
                altsystem: vm.altSystem,
                changestart: startdate,
                changeend: enddate,
                urgency: vm.urgencyno,
                changetype: vm.changetypeno,
                requestor: vm.reqpk,
                approver: vm.apppk,
                implementor: vm.imppk,
                implementation: vm.implementation,
                notes: vm.notes,
                broadcast: vm.broadcast,
                outage: vm.outage,
                unexpectedissues: vm.unexpectedIssues,
                causedissues: vm.causedIssues,
            }
            vm.updateChange(data);

            if(document.getElementById('impDocs').files.length > 0){
                vm.uploadFile(function(newImpDocs){
                    //Clear the file input. Reset the download link.
                    vm.implementationDocs = newImpDocs;
                    vm.$refs.impDocs.value = "";
                });
            }
        },
        uploadFile: function(callback){
            let vm = this;
            var fileData = new FormData();
            fileData.append('csrfmiddlewaretoken', vm.getCookie('csrftoken'));
            fileData.append('id', vm.id);
            // fileData.append('file', document.getElementById('impDocs').files);
            $.each($('#impDocs')[0].files, function(i, file){
                fileData.append('file', file);
            });
            console.log(fileData);
            $.ajax({
                url: "/api/v2/changerequest/" + vm.id,
                method: 'PUT',
                data: fileData,
                contentType: false,
                processData: false,
                success: function(data, stat, xhr){
                    callback(data.implementation_docs);
                }
            }) 
        },
        validateDates: function(){

        },
        checkUser: function(){
            // Compares the current user to the requestor, approver and implementor.
            // As long as this change is not completed, then changes can be made.
            let vm = this;
            vm.editable = false;
            vm.reqUser = false;
            vm.appUser = false;
            vm.impUser = false;
            if(vm.status != 'Complete' && vm.status != 'Rejected'){
                if (vm.userpk == vm.reqpk){
                    vm.editable = true;
                    vm.reqUser = true;
                }
                if (vm.userpk == vm.apppk){
                    vm.editable = true;
                    vm.appUser = true;
                }
                if (vm.userpk == vm.imppk){
                    vm.editable = true;
                    vm.impUser = true;
                }
                if (vm.reqUser || vm.appUser){
                    document.getElementById('changeStart').style = "display:";
                    document.getElementById('changeEnd').style = "display:";
                    document.getElementById('urgency').style.display = 'block';
                    document.getElementById('changetype').style.display = 'block';
                    document.getElementById('itsystem').style.display = 'block';
                    document.getElementById('requestor').style.display = 'block';
                    document.getElementById('approver').style.display = 'block';
                    document.getElementById('implementor').style.display = 'block';
                } else if(vm.impUser) {
                    document.getElementById('changeStart').style = "display:";
                    document.getElementById('changeEnd').style = "display:";
                    document.getElementById('implementor').style.display = 'block';
                    document.getElementById('urgency').style.display = 'none';
                    document.getElementById('changetype').style.display = 'none';
                    document.getElementById('itsystem').style.display = 'none';
                    document.getElementById('requestor').style.display = 'none';
                    document.getElementById('approver').style.display = 'none';
                    document.getElementById('standardchangerow').style.display = 'none';
                } else {
                    document.getElementById('changeStart').style.display = "none";
                    document.getElementById('changeEnd').style.display = "none";
                    document.getElementById('urgency').style.display = 'none';
                    document.getElementById('changetype').style.display = 'none';
                    document.getElementById('itsystem').style.display = 'none';
                    document.getElementById('requestor').style.display = 'none';
                    document.getElementById('approver').style.display = 'none';
                    document.getElementById('implementor').style.display = 'none';
                    document.getElementById('standardchangerow').style.display = 'none';
                }
            }
        },
        loadDropDowns: function(){
            // This is only used when requestor or approver is used.
            // Reason being that implementors cannot make changes to the
            // requested change itself, just to the implementation aspects.
            let vm = this;
            vm.urgencies[0] = {'id': 0, 'name': 'Low'};
            vm.urgencies[1] = {'id': 1, 'name': 'Medium'};
            vm.urgencies[2] = {'id': 2, 'name': 'High'};

            vm.changes[0] = {'id': 0, 'name':'Normal'};
            vm.changes[1] = {'id': 1, 'name':'Standard'};
            vm.changes[2] = {'id': 2, 'name':'Emergency'};

            if (vm.itsystems.length == 0) {
                vm.$store.dispatch("fetchItsystems");
            }
            if (vm.requestors.length == 0) {
                vm.$store.dispatch("fetchRequestors");
            }
            if (vm.standardchanges.length == 0){
                vm.$store.dispatch("fetchStandardchanges");
            }
            vm.addEventListeners();
        },
        retrieveUser: function(){
            // Gets the current user, then calls checkUser method with that ID no (pk).
            let vm = this;
            
            $.ajax({
                url: "/api/profile/",
                method: 'GET',
                success: function(data, stat, xhr){
                    vm.userpk = data.objects[0].pk;
                    vm.checkUser();
                    vm.loadDropDowns();
                },
                error: function(data, stat, xhr){
                    console.log("Not logged in.");
                }
            });
        },
        retrieveApproval: function(){
            let vm = this;
            $.ajax({
                url: "/api/v2/changerequest/" + vm.id + "/approval_list/",
                method: 'GET',
                success:function(data){
                    vm.approved = moment(data[0].date_approved).format("DD/MM/YYYY HH:mm");
                    if(data[0].type_of_approval == 0){
                        vm.approvedby = "Email";
                    } else if (data[0].type_of_approval == 1){
                        vm.approvedby = "Navigation";
                    } else {
                        vm.approvedby = "Other";
                    }
                    document.getElementById('approved').style.display = 'block';
                    document.getElementById('approvedby').style.display = 'block';
                }
            });
        },
        retrieveChange: function(){
            // Gets the change request object.
            // Some items are looked up (i.e. change type, urgency etc.) to provide a
            // user friendly display of the info. IF editable these are assigned by PK
            // that is stored in the change originally.
            let vm = this;
            $.ajax({
                url: "/api/v2/changerequest/" + vm.id + '/',
                method: 'GET',
                type: 'GET',
                contentType: false,
                success: function(data, stat, xhr){
                    // Common fields.
                    vm.title = data.title;
                    vm.description = data.description;
                    vm.submissionDate = moment(data.submission_date).format("DD/MM/YYYY HH:mm");
                    vm.altSystem = data.alternate_system;
                    vm.outage = data.outage;
                    vm.implementation = data.implementation;
                    vm.implementationDocs = data.implementation_docs;
                    vm.broadcast = data.broadcast;
                    vm.notes = data.notes;
                    vm.unexpectedIssues = data.unexpected_issues;
                    vm.causedIssues = data.caused_issues;
                    // PKs needed for comparison to current user.
                    vm.reqpk = data.requestor.id;
                    vm.apppk = data.approver.id;
                    vm.imppk = data.implementor.id;
                    vm.requestor = data.requestor.name;
                    vm.approver = data.approver.name;
                    vm.implementor = data.implementor.name;

                    // Provide works for read only cases.
                    // Keep the PK (changetypeno) for the drop down.
                    vm.changetypeno = data.change_type;
                    if(data.change_type == 0){
                        vm.changeType = "Normal";
                    } else if (data.change_type == 1){
                        vm.changeType = "Standard";
                    } else if (data.change_type == 2){
                        vm.changeType = "Emergency";
                    }
                    vm.urgencyno = data.urgency;
                    if(data.urgency == 0){
                        vm.urgency = "Low";
                    } else if (data.urgency == 1){
                        vm.urgency = "Medium";
                    } else if (data.urgency == 2){
                        vm.urgency = "High";
                    }

                    if(data.status == 0){
                        vm.status = "Open";
                    } else if (data.status == 1){
                        vm.status = "Approved";
                        vm.retrieveApproval();
                    } else if (data.status == 2){
                        vm.status = "Complete";
                        vm.retrieveApproval();
                        vm.dateCompleted = moment(data.completed_date).format("DD/MM/YYYY HH:mm");
                        document.getElementById('completed').style.display = 'block';
                    } else if (data.status == 3){
                        vm.status = "Rejected";
                    }

                    if(data.change_start){
                        vm.changeStart = moment(data.change_start).format("DD/MM/YYYY HH:mm");
                    }
                    if(data.change_end){
                        vm.changeEnd = moment(data.change_end).format("DD/MM/YYYY HH:mm");
                    }
                    vm.itsystemno = data.it_system.pk;
                    if(data.it_system){
                        vm.itSystem = data.it_system.name;
                        $(vm.$refs.itsystem).val(data.it_system.system_id);
                        $(vm.$refs.itsystem).trigger('change');
                        vm.itsystem = data.it_system.system_id;
                    } else {
                        if(data.alternate_system){
                            vm.itSystem = "System not listed";
                        } else {
                            vm.itSystem = null;
                        }
                    }
                },
                error: function(data, stat, xhr){
                    vm.id = null;
                }
            });            
        },
        setDatePickers: function(){
            let vm = this;
            var datepickerOptions = {
                format: 'DD/MM/YYYY HH:mm',
                showClear:true,
                useCurrent:false,
                keepInvalid:true,
                allowInputToggle:true,
                stepping:5
            };
            var datepickerOptions2 = {
                format: 'DD/MM/YYYY HH:mm',
                showClear:true,
                useCurrent:false,
                keepInvalid:true,
                allowInputToggle:true,
                stepping:5
            };
            vm.changeStartPicker = $('#changeStart').datetimepicker(datepickerOptions);
            vm.changeEndPicker = $('#changeEnd').datetimepicker(datepickerOptions2);
            vm.changeStartPicker.on("dp.change", function(e){
                vm.changeEndPicker.data("DateTimePicker").minDate(e.date);
                vm.changeStart = moment(e.date).format('DD/MM/YYYY HH:mm');
            });
            vm.changeEndPicker.on("dp.change", function(e){
                vm.changeEnd = moment(e.date).format('DD/MM/YYYY HH:mm');
            });
            if(vm.changeStart){
                vm.changeEndPicker.data("DateTimePicker").minDate(vm.changeStart);
            }
        },
        addEventListeners: function(){
            let vm = this;
            // Set the changes selector
            $(vm.$refs.changetype).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.changeType = selected.select2('data')[0].text;
                console.log(vm.changeType);
                vm.changetypeno = selected.val();
                if(vm.changetypeno == 1 && (vm.reqUser || vm.appUser)){
                    document.getElementById('standardchangerow').style.display = 'block';
                } else {
                    document.getElementById('standardchangerow').style.display = 'none';
                }
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.changeType = "";
                vm.changetypeno = "";
            });
            // Set the urgency selector
            $(vm.$refs.urgency).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.urgency = selected.select2('data')[0].text;
                vm.urgencyno = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.urgency = "";
                vm.urgencyno = "";
            });
            // Set the it systems selector
            $(vm.$refs.itsystem).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.itSystem = selected.select2('data')[0].text;
                vm.itsystem = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.itSystem = "";
                vm.itsystem = "";
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
            // Set the requestor selector
            $(vm.$refs.requestor).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.requestor = selected.select2('data')[0].text;
                vm.reqpk = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.requestor = "";
                vm.reqpk = "";
            }); 
            // Set the approver selector
            $(vm.$refs.approver).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.approver = selected.select2('data')[0].text;
                vm.apppk = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.approver = "";
                vm.apppk = "";
            }); 
            // Set the implementor selector
            $(vm.$refs.implementor).select2({
                "theme": "bootstrap",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.implementor = selected.select2('data')[0].text;
                vm.imppk = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.implementor = "";
                vm.imppk = "";
            });
            //On initial load, if the change type is standard display it.
            if(vm.changetypeno == 1 && (vm.reqUser || vm.appUser)){
                document.getElementById('standardchangerow').style.display = 'block';
            }
            setTimeout(function(){
                vm.setDatePickers();
                vm.isLoading = false;
            }, 1000);
        },
    },
    mounted: function(){
        let vm = this;
        vm.id = this.$route.params.id;
        vm.camefrom = this.$route.params.camefrom;
        vm.retrieveChange();
        setTimeout(function(){
            // Retrieve our current user profile whilst setting data for comparison.
            vm.retrieveUser();
        }, 50);
        vm.$watch(vm => [vm.title, vm.description, vm.requestor, vm.approver, vm.implementor, vm.changeType, vm.urgency, vm.changeStart,
            vm.changeEnd, vm.itSystem, vm.altSystem, vm.outage, vm.implementation, vm.broadcast, vm.notes, vm.unexpectedIssues, 
            vm.causedIssues, vm.standardchange], val => {
            if(vm.isLoading == false){
                vm.changesmade = true; 
            }
        }, {immediate: false});
        
    }
};
</script>

<style lang='css'>
textarea{
    resize: none;
}
.v--modal-box {
    background: #ffffff;
}
.well{
    background: #ffffff;
}
h1{
    color: #42b983;
}
</style>