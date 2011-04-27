import tempfile
import cherrypy
import os
import subprocess
import uuid
import datetime

class Grapher():
    def get_overall_graph(self, cloud_info, job_classads):
        (input_fd, input_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/tmp')
        (output_fd, output_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/tmp')
        (imap_fd, imap_file_path) = tempfile.mkstemp(dir='/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/tmp')
        cherrypy.log('Graph input file: %s' % (input_file_path))

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('digraph G {\n')
        #input_file.write('size = "4,8";\n')
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

        input_file.write('}\n')
        input_file.close()

        input_file_data = open(input_file_path, 'r').read()
        cherrypy.log('Graphviz input file:\n%s' % (input_file_data))

        cmd = ['/usr/bin/dot', '-Tjpg', '-o', output_file_path, '-Tcmapx', '-o', imap_file_path, input_file_path]
        cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        cherrypy.log('Graphviz output:\n%s\n\n%s' % (cmd, cmd_output))

        # Read file in memory
        #graph_data = open(output_file_path, 'rb').read()
        imap_data = open(imap_file_path, 'rb').read()

        # Cleanup
        #os.remove(input_file_path)

        #return graph_data
        return '<img src="/tmp/%s" USEMAP="#G"/>\n%s' % (output_file_path.split('/')[-1], imap_data)
        
