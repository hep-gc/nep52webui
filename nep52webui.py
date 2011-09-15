import sys
sys.stdout = sys.stderr

import atexit
import threading
import cherrypy
import urllib
import subprocess
import re
import json
import os
import ConfigParser
import datetime

from repoman_client.client import RepomanClient
from repoman_client.client import RepomanError

from html_renderers import VmImageRenderer
from html_renderers import JobRenderer
from html_renderers import RunningVmRenderer
from html_renderers import CloudInfoRenderer
from html_renderers import AccountingInfoRenderer

from forms import VmImageEditForm
from forms import VmBootForm
from forms import VmImageCreationForm
from image_booter import ImageBooter
from image_booter import image_boot_output_map
import grapher
from accounting import Accountant

from threading_utils import BackgroundCommand
import html_utils
import condor_utils

from config import app_config

import pycurl 


cherrypy.config.update({'environment': 'embedded', 'log.error_file':app_config.get_error_logfile(), 'log.access_file':app_config.get_access_logfile()})

if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)

class InvalidUserProxy(Exception):
    pass

class Root():

    def get_repoman_client(self, server_string=None):
        user_proxy = cherrypy.request.wsgi_environ['X509_USER_PROXY']
        # Check to make sure proxy is RFC 3820 compliant.
        cmd = [app_config.get_grid_proxy_info_command(), '-f', user_proxy]
        cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        if cmd_output.find('RFC 3820 compliant') == -1:
            # Non RFC 3820 compilant proxy detected... throw an exception
            raise InvalidUserProxy('You are using a non RFC 3820 proxy.  The repoman server currently only accepts RFC 3820 compliant impersonation proxies.<p>To correct this problem, first replace your user proxy in the MyProxy server with a RFC 3820 compliant proxy and then click <a href="/webui/delete_cached_user_proxy">here</a> to clear the cached user proxy.</p>')

        server = app_config.get_repoman_server()
        port = 443
        fields = []
        if server_string != None:
            fields = server_string.split(':')
        if len(fields) > 1 and fields[1].isdigit():
            port = int(fields[1])
        elif len(fields) == 1:
            server = fields[0]
        return RepomanClient(host=server, port=port, proxy=user_proxy)

    @cherrypy.expose
    def delete_cached_user_proxy(self):
        user_proxy = cherrypy.request.wsgi_environ['X509_USER_PROXY']
        user_info_file = user_proxy.replace('-delegation','-user')
        os.remove(user_proxy)
        os.remove(user_info_file)
        return html_utils.message('Cached user proxy deleted.')

    def get_repoman_username(self, repoman_server = None):
        return self.get_repoman_client(repoman_server).whoami()['user_name']


    @cherrypy.expose
    def get_clouds_info(self, cloud_scheduler=None):
        if cloud_scheduler == None:
            cloud_scheduler = app_config.get_default_cloud_scheduler()
        cmd = ['cloud_status', '-s', cloud_scheduler, '-a', '-j']
        clouds_info = json.loads(subprocess.check_output(cmd))
        
        return html_utils.wrap(CloudInfoRenderer().clouds_to_html_table(clouds_info, cloud_scheduler))


    @cherrypy.expose
    def get_vms_on_cloud(self, cloud_name=None, cloud_scheduler=None):
        cmd = ['cloud_status', '-s', cloud_scheduler, '-c', cloud_name, '-j']
        cloud_info = json.loads(subprocess.check_output(cmd))
        vms = cloud_info['vms']
        html = ''
        html += '<a href="/webui/get_vms_on_cloud?cloud_name=%s&cloud_scheduler=%s">Refresh</a>' % (cloud_name, cloud_scheduler)
        html += CloudInfoRenderer().vms_to_html_table(vms)
        return html_utils.wrap(html)
        
    @cherrypy.expose
    def list_current_user_images(self, repoman_server):
        user_proxy = cherrypy.request.wsgi_environ['X509_USER_PROXY']
        try:
            images = self.get_repoman_client(repoman_server).list_current_user_images()
            images_shared_with_user =  self.get_repoman_client(repoman_server).list_images_shared_with_user()
        except Exception, e:
            return html_utils.exception_page(e)
        if(len(images) == 0 and len(images_shared_with_user) == 0):
            return html_utils.wrap("You do not have access to any images on %s." % (repoman_server))
        else:
            return html_utils.wrap(VmImageRenderer().images_to_html_table(images + images_shared_with_user, repoman_server, show_actions=True))




    @cherrypy.expose
    def list_all_images(self, repoman_server):
        try:
            images = self.get_repoman_client(repoman_server).list_all_images()
        except Exception, e:
            return html_utils.exception_page(e)
        if(len(images) == 0):
            return html_utils.wrap("No images on server.")
        else:
            return html_utils.wrap(VmImageRenderer().images_to_html_table(images, repoman_server))



    @cherrypy.expose
    def describe_image(self, repoman_server, owner, name):
        try:
            image = self.get_repoman_client(repoman_server).describe_image(owner + '/' + name)
        except Exception, e:
            return html_utils.exception_page(e)
        return html_utils.wrap((VmImageRenderer().image_to_html_table(image)))


    @cherrypy.expose
    def delete_image_confirmation(self, repoman_server, owner, name):
        return html_utils.yes_no_page('Are you sure you want to delete %s/%s on %s?' % (owner, name, repoman_server), '/webui/delete_image?repoman_server=%s&owner=%s&name=%s' % (urllib.quote_plus(repoman_server), urllib.quote_plus(owner), urllib.quote_plus(name)), '/webui/list_current_user_images')

    @cherrypy.expose
    def show_image_creation_form(self):
        try:
            images = self.get_repoman_client().list_current_user_images()
            return html_utils.wrap(VmImageCreationForm(images).get_form_html())
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def create_image(self, image_name=None, image_description=None, image_file=None, image_source=None, source_image=None, unauthenticated_access=False):
        args = {}
        args['name'] = image_name
        args['description'] = image_description
        args['unauthenticated_access'] = unauthenticated_access

        try:
            # Check if image already exist.
            try:
                previous_image = self.get_repoman_client().describe_image('%s/%s' % (self.get_repoman_username(), image_name))
                return html_utils.message('An image with name <i>%s</i> already exist.<br>Please select another name.' % (image_name))
            except InvalidUserProxy, e:
                return html_utils.exception_page(e)
            except Exception, e:
                pass

            if image_name == None or len(image_name) == 0:
                return html_utils.message('You need to enter a image name for the new image.<br>Please try again.')

            if image_source == 'from_existing_image':
                # Feature not implemented yet.
                return html_utils.message('Creating an image by cloning an existing image as not been been implemented.<br>Please select another image source.')

            if image_source == 'from_uploaded_file' and (image_file == None or image_file.file == None):
                return html_utils.message('Please select an image file to upload.')

            # Proceed and create the new image metadata.
            self.get_repoman_client().create_image_metadata(**args)
            cherrypy.log('New image metadata created.')

            if image_source == 'from_uploaded_file' and image_file != None and image_file.file != None:
                url = 'https://vmrepo.cloud.nrc.ca/api/images/raw/%s/%s' % (self.get_repoman_username(), image_name)

                # Compute total file size.
                size = 0
                while True:
                    data = image_file.file.read(8192)
                    if not data:
                        break
                    size += len(data)
                image_file.file.seek(0) # rewind

                c = pycurl.Curl()
                c.setopt(pycurl.URL, str(url))
                c.setopt(pycurl.UPLOAD, 1)             
                c.setopt(pycurl.READFUNCTION, FileReader(image_file.file).read_callback)
                c.setopt(pycurl.INFILESIZE, size)
                c.setopt(pycurl.SSLCERT, cherrypy.request.wsgi_environ['X509_USER_PROXY'])
                c.setopt(pycurl.SSL_VERIFYHOST, 1)
                c.perform()
                c.close()

        except Exception, e:
            return html_utils.exception_page(e)
        return html_utils.wrap('New image created.')

    @cherrypy.expose
    def delete_image(self, repoman_server, owner, name):
        try:
            image = self.get_repoman_client(repoman_server).remove_image(owner + '/' + name)
        except Exception, e:
            return html_utils.exception_page(e)
        return self.list_current_user_images(repoman_server)


    @cherrypy.expose
    def show_edit_image_form(self, repoman_server, owner, name):
        try:
            image = self.get_repoman_client(repoman_server).describe_image(owner + '/' + name)
            users = self.get_repoman_client(repoman_server).list_users()
            groups = self.get_repoman_client(repoman_server).list_groups(list_all=True)
            form_html = VmImageEditForm().get_form_html(repoman_server, image, users, groups)
            return html_utils.wrap(form_html)
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def edit_image(self, repoman_server = None, orig_name = None, orig_owner = None, name = None, description = None, hypervisor = None, os_arch = None, os_type = None, os_variant = None, read_only = None, shared_with_users = None, shared_with_groups = None, unauthenticated_access = None, image_file = None):
        try:
            # Before we make changes to the image's metadata, let's get it's current
            # metadata.
            metadata = self.get_repoman_client(repoman_server).describe_image(orig_owner + '/' + orig_name)

            new_metadata = {}
            new_metadata['description'] = description
            new_metadata['name'] = name
            new_metadata['hypervisor'] = hypervisor
            new_metadata['os_arch'] = os_arch
            new_metadata['os_type'] = os_type
            new_metadata['os_variant'] = os_variant
            new_metadata['read_only'] = read_only
            new_metadata['unauthenticated_access'] = unauthenticated_access

            self.get_repoman_client(repoman_server).modify_image(orig_owner + '/' + orig_name, **new_metadata)

            # Shared-with users and groups need to be modified seperately.
            if shared_with_users == None:
                shared_with_users = []
            elif type(shared_with_users) == unicode:
                shared_with_users = [shared_with_users]
            if shared_with_groups == None:
                shared_with_groups = []
            elif type(shared_with_groups) == unicode:
                shared_with_groups = [shared_with_groups]

            current_shared_with_users = metadata['shared_with']['users']
            if current_shared_with_users == None:
                current_shared_with_users = []

            current_shared_with_groups = metadata['shared_with']['groups']
            if current_shared_with_groups == None:
                current_shared_with_groups = []

            for user in current_shared_with_users:
                if user not in shared_with_users:
                    cherrypy.log("Removing %s" % (user))
                    self.get_repoman_client(repoman_server).unshare_with_user(orig_owner + '/' + name, user.split('/')[-1])

            for user in shared_with_users:
                if user not in current_shared_with_users:
                    cherrypy.log("Adding %s" % (user))
                    self.get_repoman_client(repoman_server).share_with_user(orig_owner + '/' + name, user.split('/')[-1])

            for group in current_shared_with_groups:
                if group not in shared_with_groups:
                    cherrypy.log("Removing %s" % (group))
                    self.get_repoman_client(repoman_server).unshare_with_group(orig_owner + '/' + name, group.split('/')[-1])

            for group in shared_with_groups:
                if group not in current_shared_with_groups:
                    cherrypy.log("Adding %s" % (group))
                    self.get_repoman_client(repoman_server).share_with_group(orig_owner + '/' + name, group.split('/')[-1])

            if image_file != None and image_file.file != None:
                url = 'https://vmrepo.cloud.nrc.ca/api/images/raw/%s/%s' % (self.get_repoman_username(repoman_server), name)

                # Compute total file size.
                size = 0
                while True:
                    data = image_file.file.read(8192)
                    if not data:
                        break
                    size += len(data)
                image_file.file.seek(0) # rewind

                c = pycurl.Curl()
                c.setopt(pycurl.URL, str(url))
                c.setopt(pycurl.UPLOAD, 1)             
                c.setopt(pycurl.READFUNCTION, FileReader(image_file.file).read_callback)
                c.setopt(pycurl.INFILESIZE, size)
                c.setopt(pycurl.SSLCERT, cherrypy.request.wsgi_environ['X509_USER_PROXY'])
                c.setopt(pycurl.SSL_VERIFYHOST, 1)
                c.perform()
                c.close()
                
            return html_utils.wrap('Image updated.')
        except Exception, e:
            return html_utils.exception_page(e)


    @cherrypy.expose
    def show_image_boot_form(self, repoman_server, owner, name):
        try:
            image = self.get_repoman_client().describe_image(owner + '/' + name)
            image_url = image['http_file_url']
        except Exception, e:
            return html_utils.exception_page(e)
        return html_utils.wrap(VmBootForm(image).get_html())

    @cherrypy.expose
    def boot_vm(self, image_name=None, image_location=None, arch=None, cloud=None, ram=None, network=None, cpus=None, blank_space_MB=None):
        try:
            t = ImageBooter(image_name, image_location, arch, cloud, ram, network, cpus, cherrypy.request.wsgi_environ['X509_USER_PROXY'], blank_space_MB)
            boot_process_id = t.get_boot_process_id()
            
            t.start()
            cherrypy.log('Image booter thread started.')
            #return html_utils.message('Boot process started.')
            return html_utils.message('Image boot process initiated.<br><a href="/webui/show_vm_boot_process?output_id=%s">Watch boot progress</a>' % (boot_process_id))
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def show_vm_boot_process(self, output_id):
        output_file = image_boot_output_map.get_output_file_path(output_id)
        if output_file != None:
            return html_utils.file_watch_page(output_file)
        else:
            return html_utils.message('Could not get output of image boot process.')

    @cherrypy.expose
    def shutdown_vm_confirmation(self, cloud_scheduler, cloud, image_id):
        return html_utils.yes_no_page('Are you sure you want to shutdown image %s on %s?' % (image_id, cloud), '/webui/shutdown_vm?cloud=%s&image_id=%s' % (urllib.quote_plus(cloud), urllib.quote_plus(image_id)), '/webui/list_running_interactive_images?cloud_scheduler=%s' % cloud_scheduler)

    @cherrypy.expose
    def shutdown_vm(self, cloud, image_id):
        try:
            # Make vm_run call to boot the image.
            cmd = ['/usr/local/nimbus-cloud-client-018-plus-extras/bin/vm-kill', cloud, image_id]
            cherrypy.log(" ".join(cmd))
            env = {'X509_USER_PROXY': cherrypy.request.wsgi_environ['X509_USER_PROXY']}
            p = subprocess.Popen(cmd, shell=False, env=env)
            return html_utils.wrap('Image shutdown request issued.')
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def list_running_interactive_images(self, cloud_scheduler):
        try:
            cmd = ['cloud_status', '-s', cloud_scheduler, '-a', '-j']
            clouds_info = json.loads(subprocess.check_output(cmd))
            html_for_resources = ''
            background_commands = {}
            resources = {}
            for resource in clouds_info['resources']:
                resource_address = resource['network_address']
                # skip over synnefo.westgrid.ca for now (Andre)
                if resource_address == 'synnefo.westgrid.ca':
                    continue

                resources[resource_address] = resource

                cmd = ['/usr/local/nimbus-cloud-client-018-plus-extras/bin/vm-list', resource_address]
                env = {'X509_USER_PROXY': cherrypy.request.wsgi_environ['X509_USER_PROXY']}
                background_command = BackgroundCommand(cmd, env)
                background_commands[resource_address] = background_command
                background_command.start()
                background_command.join()

            for resource_address in background_commands.keys():
                #background_commands[resource_address].join()
                output = background_commands[resource_address].get_output()
                if output != None:
                    html_for_resources += RunningVmRenderer().running_vms_to_html_table(cloud_scheduler, output, resources[resource_address])


            return html_utils.wrap(html_for_resources)
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def list_batch_jobs(self):
        try:
            condor_q = ['/usr/bin/condor_q', '-l']
            env = {'X509_USER_PROXY': cherrypy.request.wsgi_environ['X509_USER_PROXY']}
            sp = subprocess.Popen(condor_q, shell=False,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            (condor_out, condor_err) = sp.communicate(input=None)
            returncode = sp.returncode
        except Exception, e:
            return html_utils.exception_page(e)

        if returncode != 0:
            return html_utils.wrap("Got non-zero return code '%s' from '%s'. stderr was: %s" %
                              (returncode, condor_q, condor_err))
        job_classads = condor_utils.CondorQOutputParser().condor_q_to_classad_list(condor_out)
        if(len(job_classads) == 0):
            return html_utils.wrap("No batch jobs running.")
        else:
            return html_utils.wrap('There are %d batch job(s) in the cloud:<br>%s' % (len(job_classads), JobRenderer().jobs_to_html_table(job_classads)))


    @cherrypy.expose
    def list_batch_job(self, job_id):
        try:
            condor_q = ['/usr/bin/condor_q', '-l', job_id]
            env = {'X509_USER_PROXY': cherrypy.request.wsgi_environ['X509_USER_PROXY']}
            sp = subprocess.Popen(condor_q, shell=False,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            (condor_out, condor_err) = sp.communicate(input=None)
            returncode = sp.returncode
        except Exception, e:
            return html_utils.exception_page(e)

        if returncode != 0:
            return html_utils.wrap("Got non-zero return code '%s' from '%s'. stderr was: %s" %
                              (returncode, condor_q, condor_err))
        job_classads = condor_utils.CondorQOutputParser().condor_q_to_classad_list(condor_out)
        if(len(job_classads) == 0):
            return html_utils.wrap("Could not get job info.")
        else:
            return html_utils.wrap(JobRenderer().job_to_html_table(job_classads[0]))


    @cherrypy.expose
    def remove_job(self, job_id):
        try:
            condor_rm = ['/usr/bin/condor_rm', job_id]
            env = {'X509_USER_PROXY': cherrypy.request.wsgi_environ['X509_USER_PROXY']}
            sp = subprocess.Popen(condor_rm, shell=False,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            (condor_out, condor_err) = sp.communicate(input=None)
            returncode = sp.returncode
        except Exception, e:
            return html_utils.exception_page(e)

        if returncode != 0:
            return html_utils.wrap("Got non-zero return code '%s' from '%s'. stderr was: %s" % (returncode, condor_rm, condor_err))
        return self.list_batch_jobs()

    @cherrypy.expose
    def get_overall_graph(self, cloud_scheduler):
        try:
            graph_data = grapher.graphers_container.get_graphers()[0].get_overall_graph()
            return html_utils.wrap(graph_data, refresh_time=30)
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def get_overall_accounting_stats(self):
        try:
            return html_utils.wrap(AccountingInfoRenderer().get_overall_accoutning_info_page())
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def get_total_number_of_jobs_per_user_plot(self):
        try:
            cherrypy.response.headers['Content-Type'] = 'image/png'
            return Accountant().get_total_number_of_jobs_per_user_plot()
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def get_total_number_of_jobs_per_remote_host_plot(self):
        try:
            cherrypy.response.headers['Content-Type'] = 'image/png'
            return Accountant().get_total_number_of_jobs_per_remote_host_plot()
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def get_cloud_usage_plot(self):
        try:
            cherrypy.response.headers['Content-Type'] = 'image/png'
            return Accountant().get_cloud_usage_plot()
        except Exception, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def get_job_history_plot(self):
        try:
            cherrypy.response.headers['Content-Type'] = 'image/png'
            return Accountant().get_job_history_plot()
        except Exception, e:
            return html_utils.exception_page(e)
        

# Class which holds a file reference and the read callback
class FileReader:
    def __init__(self, fp):
        self.fp = fp
    def read_callback(self, size):
 	return self.fp.read(size) 


application = cherrypy.Application(Root(), script_name=None, config=None)
cherrypy.log('nep52webui app started')

# Start the backround threads

overview_graph_updater = grapher.GraphUpdaterThread('condor.heprc.uvic.ca')
overview_graph_updater.start()
