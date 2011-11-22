import urllib
import re
import datetime
import cherrypy
from accounting import Accountant

class CloudInfoRenderer():
    def clouds_to_html_table(self, clouds_info, cloud_scheduler):
        html = ''
        html += '<table>'
        html += '<thead>'
        html += '<tr><th>Cloud Name</th><th>Type</th><th>CPU Archs</th><th>VM Slots</th><th># of VMs</th></tr>'
        html += '</thead>'
        html += '<tbody>'
        for resource in clouds_info['resources']:
            html += '<tr>'
            html += '<td>%s</td>' % (resource['name'])
            html += '<td>%s</td>' % (resource['cloud_type'])
            html += '<td>%s</td>' % (resource['cpu_archs'])
            html += '<td>%s</td>' % (resource['vm_slots'])
            if len(resource['vms']) == 0:
                html += '<td>%s</td>' % (len(resource['vms']))
            else:
                html += '<td><a href="/webui/get_vms_on_cloud?cloud_name=%s&cloud_scheduler=%s">%s</a></td>' % (resource['name'], cloud_scheduler, len(resource['vms']))
            html += '</tr>'
        html += '</tbody>'
        html += '</table>'
        return html

    def vms_to_html_table(self, vms):
        html = ''
        html += '<table class="sortable">'
        html += '<thead>'
        html += '<tr><th>VM ID</th><th>Hostname</th><th>VM Type</th><th>Memory</th><th>CPU Arch</th><th>CPU Cores</th><th>Status</th></tr>'
        html += '</thead>'
        html += '<tbody>'
        for vm in vms:
            html += '<tr>'
            html += '<td>%s</td>' % (vm['id'])
            html += '<td>%s</td>' % (vm['hostname'])
            html += '<td>%s</td>' % (vm['vmtype'])
            html += '<td>%s</td>' % (vm['memory'])
            html += '<td>%s</td>' % (vm['cpuarch'])
            html += '<td>%s</td>' % (vm['cpucores'])
            html += '<td>%s</td>' % (vm['status'])
            html += '</tr>'
        html += '</tbody>'
        html += '</table>'
        return html


class VmImageRenderer():
    def image_to_html_table(self, image):
        html = ''
        html += '<h2>Image: %s</h2>' % image['name']

        html += '<h3>Raw Metadata:</h3>'
        html += '<table class="sortable">'
        html += '<thead>'
        html += '<tr>'
        html += '<th>Attribute</th><th>Value</th>'
        html += '</tr>'
        html += '</thead>'
        html += '<tbody>'
        for key in image:
            html += '<tr>'
            html += ('<th align="right">%s:</th>' % (key))
            html += ('<td>%s</td>' % (image[key]))
            html += '</tr>'
        html += '</tbody>'
        html += '</table>'
        return html

    def images_to_html_table(self, images, repoman_server, show_actions=False):
        html = ''
        html += '<table class="sortable">'
        html += '<thead><tr><th>Owner:</th><th>Image:</th></tr></thead>'
        html += '<tbody>'
        for image in images:
            owner = image.rsplit('/', 2)[1]
            name = image.rsplit('/', 2)[2]
            html += '<tr>'
            html += '<td>%s</td>' % (urllib.quote_plus(owner))
            html += '<td><a href="/webui/describe_image?repoman_server=%s&owner=%s&name=%s">%s</a></td>' % (urllib.quote_plus(repoman_server), urllib.quote_plus(owner), urllib.quote_plus(name), urllib.quote_plus(name)) 
            if show_actions:
                html += '<td><a href="/webui/show_image_boot_form?repoman_server=%s&owner=%s&name=%s">boot interactive</a></td>' % (urllib.quote_plus(repoman_server), urllib.quote_plus(owner), urllib.quote_plus(name))
                html += '<td><a href="/webui/show_edit_image_form?repoman_server=%s&owner=%s&name=%s">edit</a></td>' % (urllib.quote_plus(repoman_server), urllib.quote_plus(owner), urllib.quote_plus(name))
                html += '<td><a href="/webui/delete_image_confirmation?repoman_server=%s&owner=%s&name=%s">delete</a></td>' % (urllib.quote_plus(repoman_server), urllib.quote_plus(owner), urllib.quote_plus(name))
            html += '</tr>'
        html += '</tbody>'
        html += '</table>'
        return html


class JobRenderer():
    def job_to_html_table(self, job_classad):
        html = ''
        html += '<table class="sortable">'
        html += '<thead><tr><th>Variable</th><th>Value</th></tr></thead>'
        html += '<tbody>'
        for key in job_classad:
            html += '<tr>'
            html += ('<td align="right">%s:</td>' % (key))
            html += ('<td>%s</td>' % (job_classad[key]))
            html += '</tr>'
        html += '</tbody>'
        html += '</table>'
        return html

    def jobs_to_html_table(self, job_classads):

        def get_hr_status(classad):
            status = int(classad['JobStatus'])
            current_status_datetime = datetime.datetime.fromtimestamp(int(classad['EnteredCurrentStatus']))
            hr_status = ''
            if status == 0:
                hr_status = 'Unexpanded'
            elif status == 1:
                hr_status = 'Idle'
            elif status == 2:
                hr_status = 'Running'
            elif status == 3:
                hr_status = 'Removed'
            elif status == 4:
                hr_status = 'Completed'
            elif status == 5:
                hr_status = 'Held'
            elif status == 6:
                hr_status = 'Submission error'
            else:
                hr_status = '?'
            return "%s (%s)" % (hr_status, current_status_datetime)

        html = ''
        html += '<table class="sortable">'
        html += '<thead><tr><th>Job ID</th><th>VM Type</th><th>Command</th><th>Status</th></tr></thead>'
        html += '<tbody>'
        for classad in job_classads:
            jobid = '%s.%s' % (classad['ClusterId'], classad['ProcId'])
            html += '<tr>'
            html += ('<td><a href="/webui/list_batch_job?job_id=%s">%s</a></td>' % (jobid, jobid))
            html += ('<td>%s</td>' % (classad['VMType']))
            html += ('<td>%s</td>' % (classad['Cmd']))
            html += ('<td>%s</td>' % (get_hr_status(classad)))
            html += ('<td><a href="/webui/remove_job?job_id=%s">remove</a></td>' % (jobid))
            html += '</tr>'
        html += '</tbody>'
        html += '</table>'
        return html

class RunningVmRenderer():
    def running_vms_to_html_table(self, cloud_scheduler, vm_list_output, resource):
        cloud = resource['network_address']
        cherrypy.log('%s' % (vm_list_output))
        matches = re.findall('Workspace \#(\d+)\. (\d+\.\d+\.\d+\.\d+) \[ (\S+) \]\s+State: (\S+)', vm_list_output)
        html = ''
        html += '<h2>%s</h2>' % (cloud)
        if len(matches) == 0:
            html += "You do not have any running VMs on %s" % (cloud)
        else:
            interactive_vms = []
            non_interactive_vms = []

            for match in matches:
                vm_id = match[0]
                vm_ip = match[1]
                vm_hostname = match[2]
                vm_status = match[3]
                
                # Determine if the VM is interactive or not.
                # To do this, we look at the VMs that the cloud
                # scheduler knows about.  If it is not in there,
                # then we assume it was booted interactively.
                is_interactive = True
                for vm in resource['vms']:
                    if vm['id'] == vm_id:
                        is_interactive = False
                        break
                if is_interactive:
                    interactive_vms.append([vm_id, vm_ip, vm_hostname, vm_status])
                else:
                    non_interactive_vms.append([vm_id, vm_ip, vm_hostname, vm_status])

            if len(interactive_vms) > 0:
                html += '<h3>Interactive:</h3>'
                html += '<table class="sortable"><thead><tr><th>Id</th><th>IP</th><th>Hostame</th><th>Status</th></tr></thead><tbody>'
                for vm in interactive_vms:
                    html += '<tr>'
                    html += '<td>%s</td><td>%s</td><td>%s</td><td>%s</td>' % (vm[0], vm[1], vm[2], vm[3])
                    html += '<td><a href="/webui/shutdown_vm_confirmation?cloud_scheduler=%s&cloud=%s&image_id=%s">shutdown</a></td>' % (cloud_scheduler, cloud, vm[0])
                    html += '</tr>'
                html += '</tbody></table>'

            if len(non_interactive_vms) > 0:
                html += '<h3>Batch:</h3>'
                html += '<table class="sortable"><thead><tr><th>Id</th><th>IP</th><th>Hostame</th><th>Status</th></tr></thead><tbody>'
                for vm in non_interactive_vms:
                    html += '<tr>'
                    html += '<td>%s</td><td>%s</td><td>%s</td><td>%s</td>' % (vm[0], vm[1], vm[2], vm[3])
                    html += '<td><a href="/webui/shutdown_vm_confirmation?cloud_scheduler=%s&cloud=%s&image_id=%s">shutdown</a></td>' % (cloud_scheduler, cloud, vm[0])
                    html += '</tr>'
                html += '</tbody></table>'
        return html
 

class AccountingInfoRenderer():
    def get_overall_accoutning_info_page(self):
        accountant = Accountant()
        html = ''
        html += '<p>From %s to %s</p>' % (accountant.get_earliest_timestamp(), datetime.datetime.now())
        html += '<br>Click <a href="https://science.cloud.nrc.ca/webui/get_job_history_plot">here</a> for a plot of all jobs per VM.'
        html += '<table><thead></thead><tbody>'
        html += '<tr><td>Total # of jobs:</td><td>%s</td>' % (accountant.get_total_number_of_jobs())
        html += '<tr><td>Total job runtime:</td><td>%s</td>' % (datetime.timedelta(seconds=accountant.get_total_job_duration()))
        html += '<tr><td>Average job runtime:</td><td>%s</td>' % (datetime.timedelta(seconds=accountant.get_avg_job_duration()))
        html += '<tr><td>Average job queued time:</td><td>%s</td>' % (datetime.timedelta(seconds=float(accountant.get_avg_job_queued_time())))
        html += '<tr><td>Total remote system CPU:</td><td>%s</td>' % (datetime.timedelta(seconds=accountant.get_total_remote_sys_cpu()))
        html += '<tr><td>Total remote user CPU:</td><td>%s</td>' % (datetime.timedelta(seconds=accountant.get_total_remote_user_cpu()))
        html += '<tr><td>Total remote wallclock time:<br><small>(RemoteWallClockTime - CumulativeSuspensionTime)</small></td><td>%s</td>' % (datetime.timedelta(seconds=accountant.get_total_remote_wallclock_time()))
        html += '</tbody></table>'

        html += '<h2>Cloud Usage</h2>'
        html += '<table><thead><tr><th>Cloud</th><th>Total job duration</th></tr></thead><tbody>'
        cloud_usage_data =  accountant.get_cloud_usage()
        total_duration = accountant.get_total_job_duration()
        tr = 0
        if cloud_usage_data != None:
            for cloud in cloud_usage_data:
                html += '<tr>'
                if cloud_usage_data[cloud] == None:
                    html += '<td>%s</td><td>(no data)</td>' % (cloud)
                else:
                    html += '<td>%s</td><td>%s (%d %%)</td>' % (cloud, datetime.timedelta(seconds=cloud_usage_data[cloud]), (cloud_usage_data[cloud]/total_duration)*100)
                if tr == 0:
                    html += '<td rowspan=%d><img src="get_cloud_usage_plot"/></td>' % (len(cloud_usage_data))
                else:
                    html += '<td></td>'
                html += '</tr>'
                tr += 1
            html += '</tbody></table>&nbsp;'


        html += '<table class="sortable"><thead><tr><th>Owner</th><th>Completed jobs</th><th>Total job duration</th></tr></thead><tbody>'
        for row in accountant.get_total_number_of_jobs_per_user():
            html += '<tr><td>%s</td><td>%d</td><td>%s (%d %%)</td></tr>' % (row[0], row[1],  datetime.timedelta(seconds=row[2]), row[3])
        html += '</tbody></table>'
        html += '<img src="get_total_number_of_jobs_per_user_plot"/>'
        html += '</body></html>'
        return html
