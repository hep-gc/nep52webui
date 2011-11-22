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
import shutil
from config import app_config

class GraphFileContainer():
    file_max = 20

    def __init__(self):
        self.graph_files = []
        cherrypy.log('GraphFileContainer instance created.')

    def add(self, graph_file):
        # Make an internal copy first and then keep track of that copy.
        (copy_fd, copy_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs', suffix='.jpg')
        os.close(copy_fd)
        shutil.copy2(graph_file, copy_path)
        self.graph_files.append((datetime.datetime.today(), copy_path))

        if(len(self.graph_files) > self.file_max):
            (ts, file_path) = self.graph_files.pop(0)
            cherrypy.log('Deleting %s' % (file_path))
            os.remove(file_path)
        
        return

    def get_files(self):
        return self.graph_files
        
    
class Grapher():
    def __init__(self):
        self.graph_file_container = GraphFileContainer()


    def get_hourglass_graph_with_imap(self):
        imap_file = open(self.get_imap_file_path(), 'r')
        imap_data = imap_file.read()
        imap_file.close()

        return '<img src="/graphs/%s" USEMAP="#G"/>\n%s' % (self.get_graph_file_path().split('/')[-1], imap_data)

    def create_graph(self, cloud_info, job_classads):
        # Get graphviz input data.
        graph_input_file_path = self.create_graph_input(cloud_info, job_classads)
        # Get graphviz command to run
        (graph_output_fd, graph_output_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs', suffix='.jpg')
        os.close(graph_output_fd)
        (imap_output_fd, imap_output_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs', suffix='.imap')
        os.close(imap_output_fd)
        cmd = self.get_graph_command(graph_input_file_path,graph_output_path,imap_output_path)
        # Run graphviz command
        cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        # Cleanup graphiz input file
        os.remove(graph_input_file_path)
        # Rename temp output files to non-temp files (overwrites previous graph files)
        self.graph_file_container.add(graph_output_path)
        os.rename(graph_output_path, self.get_graph_file_path())
        os.rename(imap_output_path, self.get_imap_file_path())
        return

    def get_graph_file_path(self):
        return '/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs/overview_graph.' + self.get_name() + '.jpg'

    def get_imap_file_path(self):
        return '/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs/overview_graph.' + self.get_name() + '.imap'

    def get_movie_file_path(self):
        return '/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs/overview_graph.' + self.get_name() + '.gif'

    def get_name(self):
        raise NotImplementedError()

    def create_graph_input(self, cloud_info, job_classads):
        raise NotImplementedError()

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        raise NotImplementedError()

    def create_movie(self):
        graph_files = self.graph_file_container.get_files()
        if len(graph_files) > 1:
            movie_output_path = self.get_movie_file_path()
            (new_movie_output_fd, new_movie_output_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs', suffix='.gif')
            os.close(new_movie_output_fd)
            (resized_frame_fd, resized_frame_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs', suffix='.resized-frame.jpg')
            os.close(resized_frame_fd)

            (ts, new_frame) = graph_files[-1]
            cmd = []
            cmd.append('/usr/bin/convert')
            cmd.append(new_frame)
            cmd.append('-resize')
            cmd.append('800x800>')
            cmd.append('-background')
            cmd.append('white')
            cmd.append('-gravity')
            cmd.append('center')
            cmd.append('-extent')
            cmd.append('800x800')
            cmd.append(resized_frame_path)
            cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)

            cmd = []
            cmd.append('/usr/bin/convert')
            try:
                if os.stat(movie_output_path):
                    cmd.append(movie_output_path)
            except Exception, e:
                pass
            cmd.append('-delay')
            cmd.append('100')
            cmd.append(resized_frame_path)
            cmd.append(new_movie_output_path)
            
            cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            os.remove(resized_frame_path)

            os.rename(new_movie_output_path, movie_output_path)
            cherrypy.log('%s created/updated' % (movie_output_path))





class HourglassGrapher(Grapher):

    def __init__(self):
        Grapher.__init__(self)

    def get_name(self):
        return self.__class__.__name__

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        cmd = ['/usr/bin/dot', '-Tjpg', '-o', graph_output_file_path, '-Tcmapx', '-o', imap_output_file_path, graph_input_file_path]
        return cmd

    def create_graph_input(self, cloud_info, job_classads):
        input_file_path = None
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('graph G {\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        vms = []
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
                node_id = uuid.uuid1().int
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                    node_id = vm['hostname']
                    vms.append(vm['hostname'])
                input_file.write('"%s" [color=%s, shape=box, label="%s\\n%s"];\n' % (node_id, node_color, label_hostname, vm['vmtype']))
                input_file.write('"%s" -- "%s";\n' % (resource['network_address'], node_id))

        for job_classad in job_classads:
            if (job_classad['JobStatus'] == '2') and (job_classad['RemoteHost'] in vms):
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




class CompactRadialGrapher(Grapher):

    def __init__(self):
        Grapher.__init__(self)

    def get_name(self):
        return self.__class__.__name__

    def get_graph_command(self, graph_input_file_path, graph_output_file_path, imap_output_file_path):
        cmd = ['/usr/bin/twopi', '-Tjpg', '-o', graph_output_file_path, '-Tcmapx', '-o', imap_output_file_path, graph_input_file_path]
        return cmd

    def create_graph_input(self, cloud_info, job_classads):
        input_file_path = None
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('digraph G {\n')
        input_file.write('ranksep=2;\n')
        input_file.write('nodesep=0.1;\n')
        #input_file.write('ratio=auto;\n')
        #input_file.write('overlap=scale;\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        input_file.write('CS [shape=box, style=filled, color=linen];\n')
        vms = []
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
                node_id = uuid.uuid1().int
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                    node_id = vm['hostname']
                    vms.append(vm['hostname'])
                input_file.write('"%s" [style=filled, color=%s, shape=box, height=0.2, width=0.2, label=""];\n' % (node_id, node_color))
                input_file.write('"%s" -> "%s" [style=%s];\n' % (resource['network_address'], node_id, edge_style))

        for job_classad in job_classads:
            if (job_classad['JobStatus'] == '2') and (job_classad['RemoteHost'] in vms):
                input_file.write('"%s" [shape=none, label="%s", URL="/webui/list_batch_job?job_id=%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1], job_classad['GlobalJobId'].split('#')[1]))
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
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs')

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
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/science.cloud.nrc.ca/graphs')

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('graph G {\n')
        input_file.write('ranksep=2;\n')
        input_file.write('ratio=auto;\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        input_file.write('CS [shape=box, style=filled, color=linen];\n')
        vms = []
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
                node_id = uuid.uuid1().int
                if vm['hostname'] != None and len(vm['hostname']) > 0:
                    label_hostname = vm['hostname'].split('.')[0]
                    node_id = vm['hostname']
                    vms.append(vm['hostname'])
                input_file.write('"%s" [style=filled, color=%s, shape=box, height=0.2, width=0.2, label=""];\n' % (node_id, node_color))
                input_file.write('"%s" -- "%s" [style=%s];\n' % (resource['network_address'], node_id, edge_style))

        for job_classad in job_classads:
            if (job_classad['JobStatus'] == '2') and (job_classad['RemoteHost'] in vms):
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


class GraphersContainer():
    graphers = None
    def __init__(self):
        self.graphers = []
        self.graphers.append(HourglassGrapher())
        self.graphers.append(CompactRadialGrapher())
        self.graphers.append(NeatoGrapher())
    
    def get_graphers(self):
        return self.graphers


# The globally accessible GraphersContainer instance.
graphers_container = GraphersContainer()


class GraphUpdaterThread(threading.Thread):
    cloud_scheduler = None
    should_stop = False

    def __init__(self, cloud_scheduler):
        threading.Thread.__init__(self, name=self.__class__.__name__)
        self.cloud_scheduler = cloud_scheduler

    def stop(self):
        self.should_stop = True

    def run(self):
        try:
            cherrypy.log('Graph update thread started.  Wait between updates: %ss' % app_config.get_overview_graph_update_period())

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

                for g in graphers_container.get_graphers():
                    g.create_overall_graph(cloud_info, job_classads)
                    #g.create_movie()

                time.sleep(app_config.get_overview_graph_update_period())
                

        except Exception, e:
            cherrypy.log('%s' % e)


