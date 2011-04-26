import threading
import cherrypy
import subprocess
import tempfile
import os
import uuid

from config import app_config

class ImageBooter(threading.Thread):
    
    image_name = None
    image_location = None
    arch = None
    cloud = None
    ram = None
    network = None
    cpus = None
    output_fd = None
    boot_process_id = None
    blank_space_MB = None

    def __init__(self, image_name=None, image_location=None, arch=None, cloud=None, ram=None, network=None, cpus=None, user_proxy=None, blank_space_MB=None):
        threading.Thread.__init__(self, name=self.__class__.__name__)
        self.image_name = image_name
        self.image_location = image_location
        self.arch = arch
        self.cloud = cloud
        self.ram = ram
        self.network = network
        self.cpus = cpus
        self.user_proxy = user_proxy
        self.blank_space_MB = blank_space_MB
        (self.output_fd, self.output_file_path) = tempfile.mkstemp()
        self.boot_process_id = str(uuid.uuid1())
        image_boot_output_map.add_entry(self.boot_process_id, self.output_file_path)


    def get_boot_process_id(self):
        return self.boot_process_id

    def run(self):
        # Make vm_run call to boot the image.
        cmd = [app_config.get_vm_run_command(), '-i', self.image_location, '-u', self.user_proxy, '-n', self.network, '-r', self.ram, '-c', self.cloud, '-p', self.cpus, '-a', self.arch]
        if self.blank_space_MB != None:
            cmd += ['-b', self.blank_space_MB]
        cherrypy.log(" ".join(cmd))

        env = {'X509_USER_PROXY': self.user_proxy}
        p = subprocess.Popen(cmd, shell=False, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        cherrypy.log(self.output_file_path)
        f = os.fdopen(self.output_fd, 'w+b')
        for line in iter(p.stdout.readline, ""):
            f.write(line)
            f.flush()
        f.close()
        p.wait()

class ImageBootOutputMap():
    boot_output_map = {}
    
    def add_entry(self, boot_id, output_file_path):
        self.boot_output_map[boot_id] = output_file_path
        cherrypy.log('boot process output mapping added [%s -> %s]' % (boot_id, output_file_path))

    def get_output_file_path(self, boot_id):
        if boot_id in self.boot_output_map:
            return self.boot_output_map[boot_id]
        else:
            cherrypy.log('Could not find boot output map for %s\n%s' % (boot_id, self.boot_output_map))
            return None

image_boot_output_map = ImageBootOutputMap()
