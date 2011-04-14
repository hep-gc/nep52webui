import sys
sys.stdout = sys.stderr

import atexit
import threading
import cherrypy
import urllib
import subprocess
import re
import json
from repoman_client.client import RepomanClient
from repoman_client.client import RepomanError

from html_renderers import VmImageRenderer
from html_renderers import JobRenderer
from html_renderers import RunningVmRenderer
from html_renderers import CloudInfoRenderer

from forms import VmImageEditForm
from forms import VmBootForm
from forms import VmImageCreationForm

import html_utils
import condor_utils

import pycurl 

cherrypy.config.update({'environment': 'embedded', 'log.error_file':'/tmp/nep52webui.error.log', 'log.access_file':'/tmp/nep52webui.access.log'})

if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)


class Root():

    def get_repoman_client(self, server_string=None):
        server = 'vmrepo.cloud.nrc.ca'
        port = 443
        fields = []
        if server_string != None:
            fields = server_string.split(':')
        if len(fields) > 1 and fields[1].isdigit():
            port = int(fields[1])
        elif len(fields) == 1:
            server = fields[0]
        user_proxy = cherrypy.request.wsgi_environ['X509_USER_PROXY']
        cmd = ['grid-proxy-info', '-f', user_proxy]
        proxy_info = subprocess.check_output(cmd)
        cherrypy.log(proxy_info)
        return RepomanClient(host=server, port=port, proxy=user_proxy)


    def get_username(self):
        return self.get_repoman_client().whoami()['user_name']


    @cherrypy.expose
    def get_clouds_info(self, cloud_scheduler='condor.heprc.uvic.ca'):
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
    def list_current_user_images(self):
        user_proxy = cherrypy.request.wsgi_environ['X509_USER_PROXY']
        try:
            images = self.get_repoman_client().list_current_user_images()
        except RepomanError, e:
            return html_utils.exception_page(e)
        if(len(images) == 0):
            return html_utils.wrap("You do not own any images on this server.")
        else:
            return html_utils.wrap(VmImageRenderer().images_to_html_table(images, show_actions=True))




    @cherrypy.expose
    def list_all_images(self):
        try:
            images = self.get_repoman_client().list_all_images()
        except RepomanError, e:
            return html_utils.exception_page(e)
        if(len(images) == 0):
            return html_utils.wrap("No images on server.")
        else:
            return html_utils.wrap(VmImageRenderer().images_to_html_table(images))



    @cherrypy.expose
    def describe_image(self, owner, name):
        try:
            image = self.get_repoman_client().describe_image(owner + '/' + name)
        except RepomanError, e:
            return html_utils.exception_page(e)
        except Exception, e:
            return html_utils.exception_page(e)
        return html_utils.wrap((VmImageRenderer().image_to_html_table(image)))


    @cherrypy.expose
    def delete_image_confirmation(self, owner, name):
        return html_utils.yes_no_page('Are you sure you want to delete %s/%s?' % (owner, name), '/webui/delete_image?owner=%s&name=%s' % (urllib.quote_plus(owner), urllib.quote_plus(name)), '/webui/list_current_user_images')

    @cherrypy.expose
    def show_image_creation_form(self):
        images = self.get_repoman_client().list_current_user_images()
        return html_utils.wrap(VmImageCreationForm(images).get_form_html())

    @cherrypy.expose
    def create_image(self, image_name=None, image_description=None, image_file=None, image_source=None, source_image=None, unauthenticated_access=False):
        args = {}
        args['name'] = image_name
        args['description'] = image_description
        args['unauthenticated_access'] = unauthenticated_access

        try:
            # Check if image already exist.
            try:
                previous_image = self.get_repoman_client().describe_image('%s/%s' % (self.get_username(), image_name))
                return html_utils.message('An image with name <i>%s</i> already exist.<br>Please select another name.' % (image_name))
            except:
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

            if image_source == 'from_uploaded_file' and image_file != None and image_file.file != None:
                url = 'https://vmrepo.cloud.nrc.ca/api/images/raw/%s/%s' % (self.get_username(), image_name)

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
        return self.list_current_user_images()

    @cherrypy.expose
    def delete_image(self, owner, name):
        try:
            image = self.get_repoman_client().remove_image(owner + '/' + name)
        except RepomanError, e:
            return html_utils.exception_page(e)
        return self.list_current_user_images()


    @cherrypy.expose
    def show_edit_image_form(self, owner, name):
        try:
            image = self.get_repoman_client().describe_image(owner + '/' + name)
            users = self.get_repoman_client().list_users()
            groups = self.get_repoman_client().list_groups(list_all=True)
            form_html = VmImageEditForm().get_form_html(image, users, groups)
            return html_utils.wrap(form_html)
        except RepomanError, e:
            return html_utils.exception_page(e)

    @cherrypy.expose
    def edit_image(self, orig_name = None, orig_owner = None, name = None, description = None, hypervisor = None, os_arch = None, os_type = None, os_variant = None, read_only = None, shared_with_users = None, shared_with_groups = None, unauthenticated_access = None, image_file = None):
        try:
            # Before we make changes to the image's metadata, let's get it's current
            # metadata.
            metadata = self.get_repoman_client().describe_image(orig_owner + '/' + orig_name)

            new_metadata = {}
            new_metadata['description'] = description
            new_metadata['name'] = name
            new_metadata['hypervisor'] = hypervisor
            new_metadata['os_arch'] = os_arch
            new_metadata['os_type'] = os_type
            new_metadata['os_variant'] = os_variant
            new_metadata['read_only'] = read_only
            new_metadata['unauthenticated_access'] = unauthenticated_access

            self.get_repoman_client().modify_image(orig_owner + '/' + orig_name, **new_metadata)

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
                    self.get_repoman_client().unshare_with_user(orig_owner + '/' + name, user.split('/')[-1])

            for user in shared_with_users:
                if user not in current_shared_with_users:
                    cherrypy.log("Adding %s" % (user))
                    self.get_repoman_client().share_with_user(orig_owner + '/' + name, user.split('/')[-1])

            for group in current_shared_with_groups:
                if group not in shared_with_groups:
                    cherrypy.log("Removing %s" % (group))
                    self.get_repoman_client().unshare_with_group(orig_owner + '/' + name, group.split('/')[-1])

            for group in shared_with_groups:
                if group not in current_shared_with_groups:
                    cherrypy.log("Adding %s" % (group))
                    self.get_repoman_client().share_with_group(orig_owner + '/' + name, group.split('/')[-1])

            if image_file != None and image_file.file != None:
                url = 'https://vmrepo.cloud.nrc.ca/api/images/raw/%s/%s' % (self.get_username(), name)

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
        except RepomanError, e:
            return html_utils.exception_page(e)


    @cherrypy.expose
    def show_image_boot_form(self, owner, name):
        try:
            image = self.get_repoman_client().describe_image(owner + '/' + name)
            image_url = image['http_file_url']
        except RepomanError, e:
            return html_utils.exception_page(e)
        return html_utils.wrap(VmBootForm(image).get_html())

    @cherrypy.expose
    def boot_vm(self, image_name=None, image_location=None, arch=None, cloud=None, ram=None, network=None, cpus=None):
        try:
            # Make vm_run call to boot the image.
            cmd = ['/usr/local/nimbus-cloud-client-018-plus-extras/bin/vm-run', '-i', image_location, '-u', cherrypy.request.wsgi_environ['X509_USER_PROXY'], '-n', network, '-r', ram, '-c', cloud, '-p', cpus, '-a', arch]
            cherrypy.log(" ".join(cmd))
            env = {'X509_USER_PROXY': cherrypy.request.wsgi_environ['X509_USER_PROXY']}
            p = subprocess.Popen(cmd, shell=False, env=env)
            # Save booting output to temporary file.
            # TODO

            return html_utils.wrap('Image boot process started.')
        except Exception, e:
            return html_utils.exception_page(e)

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
            for resource in clouds_info['resources']:
                cmd = ['/usr/local/nimbus-cloud-client-018-plus-extras/bin/vm-list', resource['network_address']]
                env = {'X509_USER_PROXY': cherrypy.request.wsgi_environ['X509_USER_PROXY']}
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, env=env)
                html_for_resources += RunningVmRenderer().running_vms_to_html_table(cloud_scheduler, output, resource)

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


# Class which holds a file reference and the read callback
class FileReader:
    def __init__(self, fp):
        self.fp = fp
    def read_callback(self, size):
 	return self.fp.read(size) 


application = cherrypy.Application(Root(), script_name=None, config=None)

