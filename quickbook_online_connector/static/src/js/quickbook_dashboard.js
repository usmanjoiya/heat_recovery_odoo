/** @odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL: <https://store.webkul.com/license.html/> */
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Many2OneField, many2OneField } from "@web/views/fields/many2one/many2one_field";
import { rpc } from "@web/core/network/rpc";
import { Component, onWillStart, onMounted } from  "@odoo/owl";
export class QuickbookDashboard extends Component{
    setup(){
        this.rpc = rpc;
        this.action = useService("action")
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            var self = this;
            this.instance_id = false;
            self.payment = true;
            self.invoice = true;
            await this.fetch_instance_id();
            await this.fetch_instance_details();
            await this.fetch_instance_extra_details();
            await this.get_dashboard_line_data();
            await this.fetch_purchase_doughnut_data();
            await this.fetch_sales_doughnut_data();
		  
	   });

       onMounted(() => {
		this.on_attach_callback();
	  });
    }

    open_instance_setting(ev){
        var self = this;
        self.call_quickbook_online_action('Quickbook Connection Settings', 'quickbookonline.instance',
         [], [[false,'form'],[false,'list']],self.instance_id);
    }
    open_mapping_view(ev){
        var self = this;
        var model = ev.currentTarget.id;
        if(model)
            return self.call_quickbook_online_action(
            'Mapping',
             model,
            [['instance_id','=',self.instance_id]],
            [[false,'list'],[false,'form']]);
        
    }
    change_current_instance(){
        var self = this
        var selected_instance = $('#change_instance option:selected').val()
        return this.rpc('/quickbook_online_connector/change_instance_id',{'instance_id':selected_instance}
        ).then(function (result) {
            self.instance_id = result.instance_id
            location.reload(true)
        })
    }
    on_attach_callback () {
        this.render_line_graph()
        this.render_sale_graph()
        this.render_purchase_graph()
    }
    fetch_purchase_doughnut_data () {
        let self = this
        return this.rpc('/quickbook_online_connector/fetch_purchase_doughnut_data',{'instance_id':self.instance_id}
        ).then(function (result) {
            self.purchase_data = result.purchase_data
            self.purchase_statuses = result.purchase_statuses
            self.purchase_colors = result.color
        })
    }
    fetch_sales_doughnut_data () {
        let self = this
        return this.rpc('/quickbook_online_connector/fetch_sales_doughnut_data',{'instance_id':self.instance_id
        }).then(function (result) {
            self.sale_data = result.sale_data
            self.sale_statuses = result.sale_statuses
            self.sale_colors = result.color
        })
    }
    render_sale_graph () {
        let self = this;
        var newCanvas = document.createElement('canvas');
        newCanvas.id = 'quickbook_sale_order';
        document.querySelector('#quickbook_sale_order').replaceWith(newCanvas)
        var chart = new Chart('quickbook_sale_order',{
            type: 'doughnut',
            data: {
                labels: self.sale_statuses,
                datasets: [{
                    data: Object.values(self.sale_data),
                    backgroundColor:self.sale_colors,
                }],
            },
            options: {
                responsive:true,
                aspectRatio: 1.6,
                cutoutPercentage:60,
                // maintainAspectRatio: false,
                title: {
                    display: false,
                    text: 'Sale Order',
                    fontSize: 15,
                },
                plugins: {
                    legend: {
                        display:true,
                        position: 'right',
                        labels:{
                            usePointStyle:true
                        },
                    }
            },
                onClick (e,i){
                    if (i.length) {
                        var state = chart.data.labels[i[0].index]
                        // var state = i[0]['_view']['label']
                        state =  state.toLowerCase();
                        self.call_quickbook_online_action(
                            'Order Mapping',
                            'quickbookonline.order',
                            [['name.state','=',state],
                            ['instance_id','=',self.instance_id]],
                            [[false,'list'],[false,'form']]

                        )
                    }
                },
            },
        });
    }
    render_purchase_graph () {
        let self = this;
        var newCanvas = document.createElement('canvas');
        newCanvas.id = 'quickbook_purchase_order';
        document.querySelector('#quickbook_purchase_order').replaceWith(newCanvas)
        var chart = new Chart('quickbook_purchase_order',{
            type: 'doughnut',
            data: {
                labels: self.purchase_statuses,
                datasets: [{
                    data: Object.values(self.purchase_data),
                    backgroundColor:self.purchase_colors,
                }],
            },
            options: {
                responsive:true,
                aspectRatio: 1.6,
                cutoutPercentage:60,
                // maintainAspectRatio: false,
                title: {
                    display: false,
                    text: 'Purchase Order',
                    fontSize: 15,
                },
                plugins: {
                    legend: {
                        display:true,
                        position: 'right',
                        labels:{
                            usePointStyle:true
                        },
                    }
            },
                onClick (e,i){
                    if (i.length) {
                        var state = chart.data.labels[i[0].index]

                        // var state = i[0]['_view']['label']
                        state =  state.toLowerCase();
                        self.call_quickbook_online_action(
                            'Purchase Order Mapping',
                            'quickbookonline.purchase.order',
                            [['name.state','=',state],
                            ['instance_id','=',self.instance_id]],
                            [[false,'list'],[false,'form']]

                        )
                    }
                },
            },
        });
    }
    change_line_graph(ev){
        var self = this;
        var id = ev.currentTarget.id;
        if(id=='invoice'){
            if(self.invoice==false){
                self.invoice=true;
                $(ev.currentTarget).css('textDecoration','none');
            }else{
                self.invoice=false;
                $(ev.currentTarget).css('textDecoration','line-through');
            }
        }else{
            if(self.payment==false){
                self.payment=true;
                $(ev.currentTarget).css('textDecoration','none');
            }else{
                self.payment=false;
                $(ev.currentTarget).css('textDecoration','line-through');
            }
        }
        return $.when().then(function(){
            return self.reload_line_graph()
        })
    }
    reload_line_graph () {
        var self = this
        var selected_option = $('#line_obj_change option:selected').val()
        if(selected_option=='zero')
            selected_option = false;
        return $.when().then(function(){
            return self.get_dashboard_line_data(selected_option)
        }).then(function(){
            return self.render_line_graph()
        })
    }
    render_line_graph () {
        var newCanvas = document.createElement('canvas');
        newCanvas.id = 'line_chart';
        document.getElementById('line_chart').replaceWith(newCanvas)
        var self = this
        var data = self.line_data;
        var options= {
            maintainAspectfirefoxRatio: false,
            plugins: {
                legend: {
                    display: false,
                }
            },
            scales: {
                x: {
                   display: true,
                },
                y: {
                    display: true,
                    
                    ticks: {
                        precision: 0,
                    },
                },
            },
    };
    var myBarChart = new Chart('line_chart', {
    type: 'line',
    data: data,
    options: options
    }); 
    }
    get_dashboard_line_data(month=false){
        let self = this;
        return this.rpc('/quickbook_online_connector/get_dashboard_line_data',{'instance_id':self.instance_id,
        'month':month,
        'invoice':self.invoice,
        'payment':self.payment}
        ).then(function(result){
            self.line_data = result.data
        });
    }
    open_wizard_import(ev){
        let self = this;
        return this.rpc('/quickbook_online_connector/get_synchronisation_id',{
        action:'import',
        'instance':self.instance_id}
        ).then(function(result){
            var id = result.id;
            return self.call_quickbook_online_action('Bulk Synchronisation', 'quickbookonline.bulk.synchronisation', 
            [], [[false,'form']], id,true,'new');
        });

    }
    open_wizard_export(ev){
        let self = this;
        return this.rpc('/quickbook_online_connector/get_synchronisation_id',{action:'export',
        'instance':self.instance_id}
        ).then(function(result){
            var id = result.id;
            return self.call_quickbook_online_action('Bulk Synchronisation', 'quickbookonline.bulk.synchronisation', 
            [], [[false,'form']], id,true,'new');
        });
    }
    open_instance_form(ev){
        var action_id = parseInt(ev.currentTarget.dataset['id']);
        let self = this;
        var domain = [];
        var view_type = [[false,'form'],[false,'list']];
        var model = 'quickbookonline.instance';
        return self.call_quickbook_online_action('Quickbook Instance', model, domain, view_type,action_id);

    }


    fetch_instance_extra_details(){
        let self = this;
        return this.rpc('/quickbook_online_connector/fetch_instance_extra_details',{instance_id:self.instance_id}
        ).then(function (result) {
            self.extra_data = result
        })

    }
    fetch_instance_id () {
        let self = this;
        return this.rpc('/quickbook_online_connector/fetch_instace_id').then(function (result) {
            self.instance_id = result.instance_id
            self.current_date = result.current_date
        })
    }
    call_quickbook_online_action(name, res_model, domain, view_type, res_id=false,nodestroy=false,target='self'){
        let self = this;
        return self.action.doAction({
            name: name,
            type: 'ir.actions.act_window',
            res_model: res_model,
            views: view_type,
            domain:domain,
            res_id:res_id,
            nodestroy: nodestroy,
            target: target,	
        });
    }
    fetch_instance_details(){
        let self = this;
        return this.rpc('/quickbook_online_connector/fetch_instace_details').then(function (result) {
            self.selection_instance = result
        })
    }
    
}
QuickbookDashboard.template = "quickbook_online_dashboard"
registry.category('actions').add('quickbookonline_dashboard', QuickbookDashboard)
