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

    def get_vm_run_command(self):
        # TODO: make the following configurable via the config file
        return '/usr/local/nimbus-cloud-client-018-plus-extras/bin/vm-run'

    def get_grid_proxy_info_command(self):
        # TODO: make the following configurable via the config file
        return '/usr/local/gt5.0.3/bin/grid-proxy-info'

    def get_overview_graph_update_period(self):
        # TODO: make the following configurable via the config file
        return 30

    def get_accounting_db_host(self):
        return self.config.get('accounting', 'dbhost')

    def get_accounting_db_name(self):
        return self.config.get('accounting', 'dbname')

    def get_accounting_db_username(self):
        return self.config.get('accounting', 'dbusername')

    def get_accounting_db_password(self):
        return self.config.get('accounting', 'dbpassword')

# The globally accessible AppConfig instance.
app_config = AppConfig()
