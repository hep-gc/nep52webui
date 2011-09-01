import cherrypy
import os
import MySQLdb
import subprocess

from config import app_config


class Accountant():
    def __init__(self):
        self.db = None
        self.connect_to_db()

    def __del__(self):
        self.db.close()
        cherrypy.log('Closed accounting db connection')

    def connect_to_db(self):
        try:
            dbhost = app_config.get_accounting_db_host()
            dbuser = app_config.get_accounting_db_username()
            dbpassword = app_config.get_accounting_db_password()
            dbname = app_config.get_accounting_db_name()
            self.db = MySQLdb.connect(host=dbhost, user=dbuser, passwd=dbpassword, db=dbname)
            cherrypy.log('Connected to accounting database at %s' % (dbhost))
        except Exception, e:
            cherrypy.log('Error connecting to accounting database.\n%s' % (e))

    def get_total_number_of_jobs(self):
        self.db.query("""SELECT COUNT(*) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]
       
    def get_total_job_duration(self):
        self.db.query("""SELECT ROUND(SUM(JobDuration)) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]

    def get_avg_job_duration(self):
        self.db.query("""SELECT AVG(JobDuration) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]

    def get_total_remote_sys_cpu(self):
        self.db.query("""SELECT SUM(RemoteSysCpu) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]

    def get_total_remote_user_cpu(self):
        self.db.query("""SELECT SUM(RemoteUserCpu) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]

    def get_total_remote_wallclock_time(self):
        self.db.query("""SELECT SUM(RemoteWallClockTime - CumulativeSuspensionTime) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]

    def get_avg_job_queued_time(self):
        self.db.query("""SELECT AVG(TIME_TO_SEC(TIMEDIFF(JobStartDate,QDate))) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]
       
    def get_earliest_timestamp(self):
        self.db.query("""SELECT MIN(ts) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]
        

    def get_total_number_of_jobs_per_user_plot(self):
        self.db.query("""SELECT Owner, SUM(JobDuration)/60, SUM(JobDuration)/(SELECT SUM(JobDuration) FROM completed_jobs)*100 FROM completed_jobs GROUP BY Owner ORDER BY Owner""")
        r = self.db.store_result()
        data = []
        for row in r.fetch_row(maxrows=0):
            data.append('%s,%d,%d' % (row[0], row[1], row[2]))
        commands = ["set title 'Total cloud usage by user'", "set xlabel 'User'", "set ylabel 'minutes'", "set nokey", "set datafile separator ','", "set terminal png enhanced size 400,300 font arial 11", "set output", "set style data histogram", "set style histogram cluster gap 1", "set style fill solid border -1", "set auto x", "set xtics rotate by -60", "plot [] [0:] '-' using 2:xtic(1) with histogram"]
        args = ["gnuplot", "-e", (";".join([str(c) for c in commands]))]
        #cherrypy.log('Running gnuplot command:\n%s' % (args))
        program = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in data:
            program.stdin.write(str(line)+os.linesep)
        program.stdin.close()
        return program.stdout.read()

    def get_total_number_of_jobs_per_remote_host_plot(self):
        self.db.query("""SELECT RemoteHost, COUNT(*) FROM completed_jobs GROUP BY RemoteHost ORDER BY RemoteHost""")
        r = self.db.store_result()
        data = []
        for row in r.fetch_row(maxrows=0):
            data.append('%s,%d' % (row[0], row[1]))
        commands = ["set title 'Jobs per host'", "set xlabel 'Host'", "set ylabel '# of jobs'", "set nokey", "set datafile separator ','", "set terminal png enhanced size 800,400 font arial 11", "set output", "set style data histogram", "set style histogram cluster gap 1", "set style fill solid border -1", "set auto x", "set xtics rotate by -90", "plot [] [0:] '-' using 2:xtic(1) with histogram"]
        args = ["gnuplot", "-e", (";".join([str(c) for c in commands]))]
        #cherrypy.log('Running gnuplot command:\n%s' % (args))
        program = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in data:
            program.stdin.write(str(line)+os.linesep)
        program.stdin.close()
        return program.stdout.read()

    # This method will return rows that contains the following:
    # (Owner, # of completed jobs, total job duration (seconds), % of total job duration for all users)
    def get_total_number_of_jobs_per_user(self):
        self.db.query("""SELECT Owner, COUNT(*), SEC_TO_TIME(SUM(JobDuration)), SUM(JobDuration)/(SELECT SUM(JobDuration) FROM completed_jobs)*100 FROM completed_jobs GROUP BY Owner ORDER BY Owner""")
        r = self.db.store_result()
        data = []
        return r.fetch_row(maxrows=0)


