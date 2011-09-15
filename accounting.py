import cherrypy
import os
import MySQLdb
import subprocess
import tempfile

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
        self.db.query("""SELECT MIN(QDate) FROM completed_jobs""")
        r = self.db.store_result()
        return r.fetch_row()[0][0]
        

    def get_total_number_of_jobs_per_user_plot(self):
        self.db.query("""SELECT Owner, SUM(JobDuration)/60/60/24, SUM(JobDuration)/(SELECT SUM(JobDuration) FROM completed_jobs)*100 FROM completed_jobs GROUP BY Owner ORDER BY Owner""")
        r = self.db.store_result()
        data = []
        for row in r.fetch_row(maxrows=0):
            data.append('"%s",%d,%d' % (row[0], row[1], row[2]))
        commands = ["set title 'Total cloud usage by user'", "set xlabel 'User'", "set ylabel 'days'", "set nokey", "set datafile separator ','", "set terminal png enhanced size 400,300 font arial 11", "set output", "set style data histogram", "set style histogram cluster gap 1", "set style fill solid border -1", "set auto x", "set xtics rotate by -60", "plot [] [0:] '-' using 2:xtic(1) with histogram"]
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
            data.append('"%s",%d' % (row[0], row[1]))
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
        self.db.query("""SELECT Owner, COUNT(*), SUM(JobDuration), SUM(JobDuration)/(SELECT SUM(JobDuration) FROM completed_jobs)*100 FROM completed_jobs GROUP BY Owner ORDER BY Owner""")
        r = self.db.store_result()
        data = []
        return r.fetch_row(maxrows=0)

    # This method will return a dictionary that contains the cloud names as keys, and the sum of
    # JobDuration (minutes) as values.
    def get_cloud_usage(self):
        data = {}
        filters = {}
        filters['NRC'] = '%.nrc.ca'
        filters['FGHotel'] = '%.futuregrid.org'
        filters['Hermes'] = 'hermes-xen%'
        filters['Elephant'] = 'elephant%'
        for cloud in filters:
            self.db.query("""SELECT SUM(JobDuration) FROM completed_jobs WHERE RemoteHost LIKE '%s'""" % (filters[cloud]))
            r = self.db.store_result()
            data[cloud] = r.fetch_row()[0][0]
        return data

    def get_cloud_usage_plot(self):
        data = []
        cloud_usage_data = self.get_cloud_usage()
        for cloud in cloud_usage_data:
            if cloud_usage_data[cloud] != None:
                data.append('"%s",%d' % (cloud, cloud_usage_data[cloud]/60))
            else:
                data.append('"%s",%d' % (cloud, 0))
        commands = ["unset ytics", "set nokey", "set datafile separator ','", "set terminal png enhanced size 200,150 font arial 11", "set output", "set style data histogram", "set style histogram cluster gap 1", "set style fill solid border -1", "set xtics rotate by -90", "plot [] [0:] '-' using 2:xtic(1) with histogram"]
        args = ["gnuplot", "-e", (";".join([str(c) for c in commands]))]
        program = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in data:
            program.stdin.write(str(line)+os.linesep)
        program.stdin.close()
        return program.stdout.read()

    def get_job_history_plot(self):
        try:
            (gpfile, gpfile_path) = tempfile.mkstemp(suffix='.gp')
            (gpdatafile_NRC, gpdatafile_path_NRC) = tempfile.mkstemp(suffix='.gp')
            (gpdatafile_FG, gpdatafile_path_FG) = tempfile.mkstemp(suffix='.gp')
            (gpdatafile_Hermes, gpdatafile_path_Hermes) = tempfile.mkstemp(suffix='.gp')
            (gpdatafile_UVIC, gpdatafile_path_UVIC) = tempfile.mkstemp(suffix='.gp')

            commands = []
            commands.append("set terminal png  enhanced  size 3000,1500")
            commands.append("set output")
            commands.append('set ytics font "arial,10"')
            commands.append("set datafile separator ','")
            commands.append('set timefmt "%s"')
            commands.append('set format x "%d/%m/%Y"')
            commands.append('set xdata time')
            commands.append('set title "Jobs per VM"')
            commands.append('set xlabel "job start and end time"')
            commands.append('set ylabel "VM"')
            commands.append('set yrange [0:]')
            commands.append('set style arrow 1 nohead lw 2')
            commands.append('set arrow arrowstyle 1')


            host_index = 0
            hosts_indexes = {}
            self.db.query("""SELECT DISTINCT RemoteHost FROM completed_jobs ORDER BY RemoteHost""")
            host_index = 1
            r = self.db.store_result()
            for row in r.fetch_row(maxrows=0):
                hosts_indexes[row[0]] = host_index
                host_index += 1

            ytics = "set ytics ("
            tmp = 0
            for host in hosts_indexes:
                if tmp > 0:
                    ytics += ", "
                ytics += '"%s" %d' % (host, hosts_indexes[host])
                tmp += 1
            ytics += ")"
            commands.append(ytics)

            commands.append('plot "%s" u 1:2:3:4 t "NRC" w vec, "%s" u 1:2:3:4 t "UVIC" w vec, "%s" u 1:2:3:4 t "Hermes" w vec, "%s" u 1:2:3:4 t "Futuregrid" w vec' % (gpdatafile_path_NRC, gpdatafile_path_UVIC, gpdatafile_path_Hermes, gpdatafile_path_FG))

            self.db.query("""SELECT RemoteHost, UNIX_TIMESTAMP(JobStartDate), UNIX_TIMESTAMP(CompletionDate) FROM completed_jobs  WHERE RemoteHost LIKE '%.cloud.nrc.ca' ORDER BY RemoteHost""")
            r = self.db.store_result()
            data = []
            rownum = 1
            for row in r.fetch_row(maxrows=0):
                os.write(gpdatafile_NRC, "%d,%d,%d,0\n" % (row[1], hosts_indexes[row[0]], row[2]-row[1]))
            os.close(gpdatafile_NRC)
            self.db.query("""SELECT RemoteHost, UNIX_TIMESTAMP(JobStartDate), UNIX_TIMESTAMP(CompletionDate) FROM completed_jobs  WHERE RemoteHost LIKE '%.heprc.uvic.ca' ORDER BY RemoteHost""")
            r = self.db.store_result()
            data = []
            rownum = 1
            for row in r.fetch_row(maxrows=0):
                os.write(gpdatafile_UVIC, "%d,%d,%d,0\n" % (row[1], hosts_indexes[row[0]], row[2]-row[1]))
            os.close(gpdatafile_UVIC)
            self.db.query("""SELECT RemoteHost, UNIX_TIMESTAMP(JobStartDate), UNIX_TIMESTAMP(CompletionDate) FROM completed_jobs  WHERE RemoteHost LIKE 'hermes%' ORDER BY RemoteHost""")
            r = self.db.store_result()
            data = []
            rownum = 1
            for row in r.fetch_row(maxrows=0):
                os.write(gpdatafile_Hermes, "%d,%d,%d,0\n" % (row[1], hosts_indexes[row[0]], row[2]-row[1]))
            os.close(gpdatafile_Hermes)
            self.db.query("""SELECT RemoteHost, UNIX_TIMESTAMP(JobStartDate), UNIX_TIMESTAMP(CompletionDate) FROM completed_jobs  WHERE RemoteHost LIKE '%.futuregrid.org' ORDER BY RemoteHost""")
            r = self.db.store_result()
            data = []
            rownum = 1
            for row in r.fetch_row(maxrows=0):
                os.write(gpdatafile_FG, "%d,%d,%d,0\n" % (row[1], hosts_indexes[row[0]], row[2]-row[1]))
            os.close(gpdatafile_FG)

            for command in commands:
                os.write(gpfile, command + '\n')
            os.close(gpfile)

            args = ["gnuplot", gpfile_path]
            cherrypy.log("A")
            program = subprocess.Popen(args, stdout=subprocess.PIPE)
            cherrypy.log("B")
            #os.remove(gpfile_path)
            return program.stdout.read()
        except Exception, e:
            cherrypy.log("Error\n%s" % (e))
    

        
        


            
        
        
