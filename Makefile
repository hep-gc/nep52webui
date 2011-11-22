install:
	ssh root@science.cloud.nrc.ca "rm /srv/www/htdocs/vhosts/science.cloud.nrc.ca/webui/*" ; scp ./*.py root@science.cloud.nrc.ca:/srv/www/htdocs/vhosts/science.cloud.nrc.ca/webui/ ; ssh root@science.cloud.nrc.ca "/etc/init.d/apache2 reload"

