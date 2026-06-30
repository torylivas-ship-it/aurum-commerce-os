#!/bin/bash
# Wait for postgres and redis to accept connections
until python3 - <<'EOF' 2>/dev/null
import socket
socket.create_connection(("localhost", 5432), 2)
EOF
do
    sleep 2
done

until python3 - <<'EOF' 2>/dev/null
import socket
socket.create_connection(("localhost", 6379), 2)
EOF
do
    sleep 2
done
