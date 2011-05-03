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
    def __init__(self):
        pass

    def get_overall_graph(self):
        imap_file = open(self.get_imap_file_path(), 'r')
        imap_data = imap_file.read()
        imap_file.close()

        return '<img src="/graphs/%s" USEMAP="#G"/>\n%s' % (self.get_graph_file_path().split('/')[-1], imap_data)

    def create_overall_graph(self, cloud_info, job_classads):
        # Get graphviz input data.
        graph_input_file_path = self.create_graph_input(cloud_info, job_classads)
        # Get graphviz command to run
        (graph_output_fd, graph_output_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs')
        (imap_output_fd, imap_output_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs')
        cmd = self.get_graph_command(graph_input_file_path,graph_output_path,imap_output_path)
        # Run graphviz command
        cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        # Cleanup graphiz input file
        os.remove(graph_input_file_path)
        # Rename temp output files to non-temp files (overwrites previous graph files)
        os.rename(graph_output_path, self.get_graph_file_path())
        os.rename(imap_output_path, self.get_imap_file_path())
        return

    def get_graph_file_path(self):
        return '/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs/overview_graph.' + self.get_name() + '.jpg'

    def get_imap_file_path(self):
        return '/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs/overview_graph.' + self.get_name() + '.imap'

    def get_name(self):
        raise NotImplementedError()

    def create_graph_input(self, cloud_info, job_classads):
        raise NotImplementedError()

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        raise NotImplementedError()




class LinearGrapher(Grapher):

    def __init__(self):
        Grapher.__init__(self)

    def get_name(self):
        return self.__class__.__name__

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        cmd = ['/usr/bin/dot', '-Tjpg', '-o', graph_output_file_path, '-Tcmapx', '-o', imap_output_file_path, graph_input_file_path]
        return cmd


    def create_graph_input(self, cloud_info, job_classads):
        input_file_path = None
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('digraph G {\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        for resource in cloud_info['resources']:
            input_file.write('"%s" [label="%s"];\n' % (resource['network_address'], resource['name']))
            input_file.write('CS -> "%s";\n' % (resource['network_address']))
            for vm in resource['vms']:
                node_color = 'black'
                if vm['status'] == "Error":
                    node_color = 'red'
                elif vm['status'] == "Running":
                    node_color = 'green'

                label_hostname = '???'
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                input_file.write('"%s" [color=%s, shape=box, label="%s\\n%s"];\n' % (vm['hostname'], node_color, label_hostname, vm['vmtype']))
                input_file.write('"%s" -> "%s";\n' % (resource['network_address'], vm['hostname']))

        for job_classad in job_classads:
            if job_classad['JobStatus'] == '2':
                input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                input_file.write('"%s" -> "%s";\n' % (job_classad['RemoteHost'], job_classad['GlobalJobId']))

        if True:
            for job_classad in job_classads:
                if job_classad['JobStatus'] == '1':
                    input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                    input_file.write('"%s" -> "Q";\n' % (job_classad['GlobalJobId']))
            input_file.write('Q -> CS')

        input_file.write('}\n')
        input_file.close()
        return input_file_path





class NonDirGrapher(Grapher):

    def __init__(self):
        Grapher.__init__(self)

    def get_name(self):
        return self.__class__.__name__

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        cmd = ['/usr/bin/dot', '-Tjpg', '-o', graph_output_file_path, '-Tcmapx', '-o', imap_output_file_path, graph_input_file_path]
        return cmd

    def create_graph_input(self, cloud_info, job_classads):
        input_file_path = None
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('graph G {\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        for resource in cloud_info['resources']:
            input_file.write('"%s" [label="%s"];\n' % (resource['network_address'], resource['name']))
            input_file.write('CS -- "%s";\n' % (resource['network_address']))
            for vm in resource['vms']:
                node_color = 'black'
                if vm['status'] == "Error":
                    node_color = 'red'
                elif vm['status'] == "Running":
                    node_color = 'green'

                label_hostname = '???'
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                input_file.write('"%s" [color=%s, shape=box, label="%s\\n%s"];\n' % (vm['hostname'], node_color, label_hostname, vm['vmtype']))
                input_file.write('"%s" -- "%s";\n' % (resource['network_address'], vm['hostname']))

        for job_classad in job_classads:
            if job_classad['JobStatus'] == '2':
                input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                input_file.write('"%s" -- "%s";\n' % (job_classad['RemoteHost'], job_classad['GlobalJobId']))

        if True:
            input_file.write('"Q" [shape=hexagon];\n')
            for job_classad in job_classads:
                if job_classad['JobStatus'] == '1':
                    input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                    input_file.write('"%s" -- "Q";\n' % (job_classad['GlobalJobId']))
            input_file.write('Q -- CS')

        input_file.write('}\n')
        input_file.close()
        return input_file_path




class RadialGrapher2(Grapher):

    def __init__(self):
        Grapher.__init__(self)

    def get_name(self):
        return self.__class__.__name__

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        cmd = ['/usr/bin/twopi', '-Tjpg', '-o', graph_output_file_path, '-Tcmapx', '-o', imap_output_file_path, graph_input_file_path]
        return cmd

    def create_graph_input(self, cloud_info, job_classads):
        input_file_path = None
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('digraph G {\n')
        input_file.write('ranksep=2;\n')
        input_file.write('nodesep=0.1;\n')
        #input_file.write('ratio=auto;\n')
        #input_file.write('overlap=scale;\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        input_file.write('CS [shape=box, style=filled, color=linen];\n')
        for resource in cloud_info['resources']:
            input_file.write('"%s" [label="%s"];\n' % (resource['network_address'], resource['name']))
            input_file.write('CS -> "%s";\n' % (resource['network_address']))
            for vm in resource['vms']:
                node_color = 'black'
                edge_style = 'dotted'
                if vm['status'] == "Error":
                    node_color = 'red'
                    edge_style = 'filled'
                elif vm['status'] == "Running":
                    node_color = 'green'
                    edge_style = 'filled'

                label_hostname = '???'
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                input_file.write('"%s" [style=filled, color=%s, shape=box, height=0.2, width=0.2, label=""];\n' % (vm['hostname'], node_color))
                input_file.write('"%s" -> "%s" [style=%s];\n' % (resource['network_address'], vm['hostname'], edge_style))

        for job_classad in job_classads:
            if job_classad['JobStatus'] == '2':
                input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                input_file.write('"%s" -> "%s";\n' % (job_classad['RemoteHost'], job_classad['GlobalJobId']))

        if False:
            input_file.write('subgraph cluster_idle_jobs {rank = source;\n\nnode [style=filled];\nlabel = "Idle jobs";\n')
            for job_classad in job_classads:
                if job_classad['JobStatus'] == '1':
                    input_file.write('"%s" [shape=point, label="", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1]))
                    input_file.write('"Idle Jobs" -> "%s";\n' % (job_classad['GlobalJobId']))
            input_file.write(' }\n')

        input_file.write('}\n')
        input_file.close()
        return input_file_path
        



class RadialGrapher(Grapher):

    def __init__(self):
        Grapher.__init__(self)

    def get_name(self):
        return self.__class__.__name__

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        cmd = ['/usr/bin/twopi', '-Tjpg', '-o', graph_output_file_path, '-Tcmapx', '-o', imap_output_file_path, graph_input_file_path]
        return cmd

    def create_graph_input(self, cloud_info, job_classads):
        input_file_path = None
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('digraph G {\n')
        input_file.write('ranksep=2;\n')
        input_file.write('ratio=auto;\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        for resource in cloud_info['resources']:
            input_file.write('"%s" [label="%s"];\n' % (resource['network_address'], resource['name']))
            input_file.write('CS -> "%s";\n' % (resource['network_address']))
            for vm in resource['vms']:
                node_color = 'black'
                if vm['status'] == "Error":
                    node_color = 'red'
                elif vm['status'] == "Running":
                    node_color = 'green'

                label_hostname = '???'
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                input_file.write('"%s" [color=%s, shape=box, label="%s\\n%s"];\n' % (vm['hostname'], node_color, label_hostname, vm['vmtype']))
                input_file.write('"%s" -> "%s";\n' % (resource['network_address'], vm['hostname']))

        for job_classad in job_classads:
            if job_classad['JobStatus'] == '2':
                input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                input_file.write('"%s" -> "%s";\n' % (job_classad['RemoteHost'], job_classad['GlobalJobId']))

        if True:
            input_file.write('subgraph cluster_idle_jobs {rank = source;\n\nnode [style=filled];\nlabel = "Idle jobs";\n')
            for job_classad in job_classads:
                if job_classad['JobStatus'] == '1':
                    input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                    input_file.write('"Idle Jobs" -> "%s";\n' % (job_classad['GlobalJobId']))
            input_file.write(' }\n')

        input_file.write('}\n')
        input_file.close()
        return input_file_path
        




class NeatoGrapher(Grapher):

    def __init__(self):
        Grapher.__init__(self)

    def get_name(self):
        return self.__class__.__name__

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        cmd = ['/usr/bin/neato', '-Tjpg', '-o', graph_output_file_path, '-Tcmapx', '-o', imap_output_file_path, graph_input_file_path]
        return cmd

    def create_graph_input(self, cloud_info, job_classads):
        input_file_path = None
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('graph G {\n')
        input_file.write('ranksep=2;\n')
        input_file.write('ratio=auto;\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        input_file.write('CS [shape=box, style=filled, color=linen];\n')
        for resource in cloud_info['resources']:
            input_file.write('"%s" [label="%s"];\n' % (resource['network_address'], resource['name']))
            input_file.write('CS -- "%s";\n' % (resource['network_address']))
            for vm in resource['vms']:
                node_color = 'black'
                edge_style = 'dotted'
                if vm['status'] == "Error":
                    node_color = 'red'
                    edge_style = 'filled'
                elif vm['status'] == "Running":
                    node_color = 'green'
                    edge_style = 'filled'

                label_hostname = '???'
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                input_file.write('"%s" [style=filled, color=%s, shape=box, height=0.2, width=0.2, label=""];\n' % (vm['hostname'], node_color))
                input_file.write('"%s" -- "%s" [style=%s];\n' % (resource['network_address'], vm['hostname'], edge_style))

        for job_classad in job_classads:
            if job_classad['JobStatus'] == '2':
                input_file.write('"%s" [style=rounded, shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
                input_file.write('"%s" -- "%s";\n' % (job_classad['RemoteHost'], job_classad['GlobalJobId']))

        if False:
            input_file.write('subgraph cluster_idle_jobs {rank = source;\n\nnode [style=filled];\nlabel = "Idle jobs";\n')
            for job_classad in job_classads:
                if job_classad['JobStatus'] == '1':
                    input_file.write('"%s" [shape=point, label="", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1]))
                    input_file.write('"Idle Jobs" -- "%s";\n' % (job_classad['GlobalJobId']))
            input_file.write(' }\n')

        input_file.write('}\n')
        input_file.close()
        return input_file_path




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

                graphers = []
                graphers.append(NonDirGrapher())
                graphers.append(RadialGrapher2())
                graphers.append(NeatoGrapher())

                for g in graphers:
                    g.create_overall_graph(cloud_info, job_classads)

                time.sleep(app_config.get_overview_graph_update_period())
                

        except Exception, e:
            cherrypy.log('%s' % e)
        
