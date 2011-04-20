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
        cherrypy.log('Graph input file: %s' % (input_file_path))

        input_file = os.fdopen(input_fd, 'w+b')
        input_file.write('digraph G {\n')
        #input_file.write('size = "4,8";\n')
        input_file.write('label = "%s";\n' % (datetime.datetime.today()))
        for resource in cloud_info['resources']:
            input_file.write('"%s" [label="%s\\n(%s)"];\n' % (resource['network_address'], resource['name'], resource['cloud_type']))
            for vm in resource['vms']:
                input_file.write('"%s" [shape=box, label="%s\\n[%s]"];\n' % (vm['hostname'], vm['hostname'].split('.')[0], vm['status']))
                input_file.write('"%s" -> "%s";\n' % (resource['network_address'], vm['hostname']))

        for job_classad in job_classads:
            if job_classad['JobStatus'] == 2:
                input_file.write('"%s" [shape=house, label="%s"];\n' % (job_classad['GlobalJobId'], job_classad['GlobalJobId'].split('#')[1]))
                input_file.write('"%s" -> "%s";\n' % (job_classad['LastRemoteHost'], job_classad['GlobalJobId']))

        input_file.write('}\n')
        input_file.close()

        input_file_data = open(input_file_path, 'r').read()
        cherrypy.log('Graphviz input file:\n%s' % (input_file_data))

        cmd = ['/usr/bin/dot', '-Tjpg', input_file_path, '-o', output_file_path]
        cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        cherrypy.log('Graphviz output:\n%s' % (cmd_output))

        # Read file in memory
        graph_data = open(output_file_path, 'rb').read()
        
        # Cleanup
        os.remove(input_file_path)

        return graph_data
        
