<template lang="html">
   <div id="DataTable">
      <table class="hover table table-striped table-bordered dt-responsive nowrap" cellspacing="0" width="100%" :id="id">
            <thead>
                <tr>
                    <th :data-class="(i == 0 )? 'expand':null" v-for="(header,i) in dtHeaders"> {{ header}}</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        </table>
   </div>

</template>

<script>
    import {$, DataTable, DataTableBs,DataTableRes} from '../hooks.js'
    import ResponsiveDatatablesHelper from "./responsive_datatable_helper.js"
module.exports = {
   name : 'DataTable',
   props:{
      dtHeaders:{
         type:Array,
         required:true
      },
      dtOptions: {
         type:Object,
         required:true
     },
     id:{
         required:true
     }
   },
   data : function () {
      return {
         table:null,
         vmDataTable: null,
      }
   },
   computed:{

   },
   methods:{
       initEvents: function () {
           let vm =this;
           var responsiveHelper;
           var breakpointDefinition = {
               //bootstrap grid values
               tablet: 992,
               phone : 768
           };
           var responsiveOptions = {
               autoWidth        : false,
               preDrawCallback: function () {
                 // Initialize the responsive datatables helper once.
                 if (!responsiveHelper) {
                     responsiveHelper = new ResponsiveDatatablesHelper(vm.table, breakpointDefinition);
                 }
             },
             rowCallback    : function (nRow) {
                 responsiveHelper.createExpandIcon(nRow);
             },
             drawCallback   : function (oSettings) {
                 responsiveHelper.respond();
             },
           }
           var options = Object.assign(vm.dtOptions,responsiveOptions)
           vm.vmDataTable = $(vm.table).DataTable(options);
           $(vm.table).resize(function (e) {
               vm.vmDataTable.draw(true);
           });
       }
   },
   mounted:function () {
      let vm = this;
      vm.table =$('#'+vm.id);
      $.fn.dataTable.ext.errMode = 'throw';
      vm.initEvents();
   }
};
</script>

<style lang="css">
    td > a{
        border: none;
        border-radius: 2px;
        position: relative;
        padding: 8px 10px;
        margin: 10px 1px;
        font-weight: 500;
        text-transform: capitalize;
        letter-spacing: 0;
        will-change: box-shadow, transform;
        -webkit-transition: -webkit-box-shadow 0.2s cubic-bezier(0.4, 0, 1, 1), background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        -o-transition: box-shadow 0.2s cubic-bezier(0.4, 0, 1, 1), background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        transition: box-shadow 0.2s cubic-bezier(0.4, 0, 1, 1), background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        outline: 0;
        cursor: pointer;
        text-decoration: none;
        background: transparent;
        color: #03a9f4;
    }
    td{
        word-wrap: break-word;
    }
    table.table-bordered.dataTable tbody th, table.table-bordered.dataTable tbody td {
        border-bottom-width: 0;
        vertical-align: middle;
        text-align: left;
    }
    .schedule-button {
        width: 80px;
    }
    table.dataTable thead .sorting {
        background:none;
    }
    table.dataTable thead .sorting_desc{
        background:none;
    }
    table.dataTable thead .sorting_asc{
        background:none;
    }
    .table.rowlink td:not(.rowlink-skip), .table .rowlink td:not(.rowlink-skip) {
        cursor: pointer;
    }
    table.collapsed > tbody > tr > td > span.responsiveExpander,table.has-columns-hidden > tbody > tr > td > span.responsiveExpander {
        background: url("https://raw.githubusercontent.com/Comanche/datatables-responsive/master/files/1.10/img/plus.png") no-repeat 5px center;
        padding-left: 32px;
        cursor: pointer;
    }
    table.collapsed > tbody > tr.parent > td span.responsiveExpander,table.has-columns-hidden > tbody > tr.detail-show > td span.responsiveExpander {
        background: url("https://raw.githubusercontent.com/Comanche/datatables-responsive/master/files/1.10/img/minus.png") no-repeat 5px center;
    }
    table.collapsed > tbody > tr > td.child,table.has-columns-hidden > tbody > tr > td.child {
        background: #eee;
    }
    table.collapsed > tbody > tr > td > ul, table.has-columns-hidden > tbody > tr > td > ul {
        list-style: none;
        margin: 0;
        padding: 0;
    }
    table.collapsed > tbody > tr > td > ul > li > span.dtr-title, table.has-columns-hidden > tbody > tr > td > ul > li > span.columnTitle {
        font-weight: bold;
    }
    .table>tbody>tr>td, .table>tbody>tr>th, .table>tfoot>tr>td, .table>tfoot>tr>th, .table>thead>tr>td, .table>thead>tr>th{
        vertical-align: middle;
    }
    div.dataTables_filter input {
        margin-left: 10px;
    }
    div.dataTables_filter, div.dataTables_paginate {
        float:right;
    }
    div.dataTables_length select {
        margin-left: 10px;
        margin-right: 10px;
        display: inline-block;
    }
    .input-sm {
        width: auto;
    }
    @media screen and (max-width: 767px)
    {
        div.dataTables_length,div.dataTables_info {
             float:left;
             width: auto;
        }
        div.dataTables_filter, div.dataTables_paginate {
             float:right;
        }
    }
</style>
