install:
	ssh root@babar.cloud.nrc.ca "rm /srv/www/htdocs/vhosts/babar.cloud.nrc.ca/webui/*" ; scp ./*.py root@babar.cloud.nrc.ca:/srv/www/htdocs/vhosts/babar.cloud.nrc.ca/webui/ ; ssh root@babar.cloud.nrc.ca "/etc/init.d/apache2 reload"

