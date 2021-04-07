#!/usr/bin/env bash

cat << EOF > valheim.env
SERVER_NAME="My server"
WORLD_NAME="Dedicated"
SERVER_PASS="secret"
SERVER_PUBLIC=false
DISCORD=""
SERVER_IP=$(dig +short myip.opendns.com @resolver1.opendns.com)
EOF

export $(cat valheim.env | xargs)
docker-compose up | python3.8 /home/ec2-user/valheim-server/parser.py > /dev/null 2>&1 &
