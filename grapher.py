import tempfile
import cherrypy
import os
import subprocess
import uuid
import datetime
import threading
import condor_utils
import json
import time
from config import app_config

class Grapher():
    graph_file_path = '/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/tmp/overview_graph.jpg'
    imap_file_path = '/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/tmp/overview_graph.imap'

    def get_overall_graph(self):
        imap_file = open(self.imap_file_path, 'r')
        imap_data = imap_file.read()
        imap_file.close()

        return '<img src="/tmp/%s" USEMAP="#G"/>\n%s' % (self.graph_file_path.split('/')[-1], imap_data)



    def create_overall_graph(self, cloud_info, job_classads):
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/tmp')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('digraph G {\n')
        #input_file.write('size = "4,8";\n')
        #input_file.write('ratio=2.0;\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        for resource in cloud_info['resources']:
            input_file.write('"%s" [label="%s\\n(%s)"];\n' % (resource['network_address'], resource['name'], resource['cloud_type']))
            for vm in resource['vms']:
                node_color = 'black'
                if vm['status'] == "Error":
                    node_color = 'red'
                elif vm['status'] == "Running":
                    node_color = 'green'

                label_hostname = '???'
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                input_file.write('"%s" [color=%s, shape=box, label="%s\\n%s\\n[%s]"];\n' % (vm['hostname'], node_color, label_hostname, vm['vmtype'], vm['status']))
                input_file.write('"%s" -> "%s";\n' % (resource['network_address'], vm['hostname']))

        for job_classad in job_classads:
            if job_classad['JobStatus'] == '2':
                input_file.write('"%s" [style=rounded, shape=box, label="%s\\n(%s)", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['x509userproxysubject'].split('/CN=')[-1], job_classad['GlobalJobId'].split('#')[1]))
                input_file.write('"%s" -> "%s";\n' % (job_classad['RemoteHost'], job_classad['GlobalJobId']))

        input_file.write('subgraph cluster_idle_jobs {\nnode [style=filled];\nlabel = "Idle jobs";\n')
        for job_classad in job_classads:
            if job_classad['JobStatus'] == '1':
                input_file.write('"%s" [style=rounded, shape=box, label="%s\\n(%s)", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['x509userproxysubject'].split('/CN=')[-1], job_classad['GlobalJobId'].split('#')[1]))
        input_file.write(' }\n')

        input_file.write('}\n')
        input_file.close()

        
        cmd = ['/usr/bin/dot', '-Tjpg', '-o', self.graph_file_path, '-Tcmapx', '-o', self.imap_file_path, input_file_path]
        cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)

        # Cleanup Graphviz input file.
        os.remove(input_file_path)

        return (self.graph_file_path, self.imap_file_path)



class OverviewGraphUpdaterThread(threading.Thread):
    cloud_scheduler = None
    should_stop = False

    def __init__(self, cloud_scheduler):
        threading.Thread.__init__(self, name=self.__class__.__name__)
        self.cloud_scheduler = cloud_scheduler

    def stop(self):
        self.should_stop = True

    def run(self):
        try:
            cherrypy.log('Overview graph update thread started.  Refresh every %ss' % app_config.get_overview_graph_update_period())

            while not self.should_stop:
                cmd = ['cloud_status', '-s', self.cloud_scheduler, '-a', '-j']
                cloud_info = json.loads(subprocess.check_output(cmd))

                try:
                    condor_q = ['/usr/bin/condor_q', '-l']
                    env={'X509_USER_CERT':'/etc/grid-security/nep52webuicert.pem', 'X509_USER_KEY':'/etc/grid-security/nep52webuikey.pem'}
                    condor_out = subprocess.check_output(condor_q, env=env)
                except Exception, e:
                    cherrypy.log('%s' % e)
                    return

                job_classads = condor_utils.CondorQOutputParser().condor_q_to_classad_list(condor_out)

                Grapher().create_overall_graph(cloud_info, job_classads)

                time.sleep(app_config.get_overview_graph_update_period())
                

        except Exception, e:
            cherrypy.log('%s' % e)
        
