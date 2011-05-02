import threading
import subprocess
import cherrypy

class BackgroundCommand(threading.Thread):
    cmd = None
    env = None
    output = None

    def __init__(self, cmd, env):
        threading.Thread.__init__(self, name=self.__class__.__name__)
        self.cmd = cmd
        self.env = env

    def run(self):
        try:
            cherrypy.log('Running: %s' % (self.cmd))
            self.output = subprocess.check_output(self.cmd, stderr=subprocess.STDOUT, env=self.env)
            cherrypy.log('%s returned' % (self.cmd))
        except Exception, e:
            cherrypy.log('%s\nOutput:\n%s' % (e, self.output))
            self.output = None

    def get_output(self):
        return self.output
