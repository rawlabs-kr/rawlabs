# celeryd 변경시
sudo cp server/celeryd.conf /etc/supervisor/conf.d/

# celeryd 시작/종료/재시작
sudo supervisorctl
restart imagefilter_celery

# google cloud flatform
## production key rawlabs-image-filter-2d9bb63692c5.json
## dev key rawlabs-image-filter-a3dfa7db52e2.json