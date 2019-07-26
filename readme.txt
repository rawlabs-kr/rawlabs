# celeryd 변경시
sudo cp server/celeryd.conf /etc/supervisor/conf.d/

# celeryd 시작/종료/재시작
sudo supervisorctl
restart imagefilter_celery