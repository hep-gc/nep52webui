import ConfigParser


class AppConfig():

    config = None

    def __init__(self, config_file_path='/etc/nep52webui/nep52webui.conf'):
        self.config = ConfigParser.ConfigParser()
        try:
            self.config.readfp(open(config_file_path))
        except Exception, e:
            pass


    def get_error_logfile(self):
        return self.config.get('logging', 'error_log_file')

    def get_access_logfile(self):
        return self.config.get('logging', 'access_log_file')


    def get_repoman_server(self):
        return self.config.get('repoman', 'server')

    def get_default_cloud_scheduler(self):
        return self.config.get('cloud_scheduler', 'default_cloud_scheduler')

