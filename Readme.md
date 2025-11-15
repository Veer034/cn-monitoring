About

    For Monitoring

Remove docker images

    docker-compose down

Just for building

    docker-compose build

Build with new code

    docker-compose up --build

Remove old venv

    rm -rf venv

Install Python

    brew install python@3.10

Activiate Env

    #can change the env names
    python3.10 -m venv myvenv
    source myvenv/bin/activate

    #make sure version is 3.10.*
    python --version

Install library in local VM

    pip install flask psutil requests gunicorn

Start in local

    python3.10 monitoring.py

deactivate your virtual environment if it's active:

    deactivate

# Production Setup

### Login VM

    ssh azureuser@YOUR-VM-PUBLIC-IP

### Install Git

    sudo apt update
    sudo apt install git -y
    git clone https://github.com/Veer034/service-monitor.git

### Install Python

    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install python3.10 python3.10-venv python3.10-distutils

### Install library in production VM

    pip install flask psutil requests gunicorn

### Create Systemd file for as a service execution

    sudo tee /etc/systemd/system/service-monitor.service > /dev/null << 'EOF'
    [Unit]
    Description=Service Monitor
    After=network.target

    [Service]
    Type=notify
    User=azureuser
    WorkingDirectory=/home/azureuser
    Environment="PATH=/usr/local/bin:/usr/bin:/bin"
    ExecStart=/usr/local/bin/gunicorn \
        --bind 0.0.0.0:8888 \
        --workers 4 \
        --threads 2 \
        --worker-class gthread \
        --timeout 120 \
        --access-logfile /var/log/service-monitor/access.log \
        --error-logfile /var/log/service-monitor/error.log \
        --log-level info \
        --preload \
        service_monitor:app

    Restart=always
    RestartSec=10
    StandardOutput=journal
    StandardError=journal

    # Security
    NoNewPrivileges=true
    PrivateTmp=true

    # Resource limits
    MemoryMax=512M
    CPUQuota=100%

    [Install]
    WantedBy=multi-user.target
    EOF

### HuggingFace model storage location

    ~/.cache/huggingface/

### List all services

    systemctl list-units --type=service
    systemctl list-units --type=service | grep cn-

### Reload systemd

    sudo systemctl daemon-reload

### Enable all services to start on boot

    sudo systemctl enable service-monitor

### Start Service

    sudo systemctl start service-monitor

### Check Status

    sudo systemctl status service-monitor

### Stop service

    sudo systemctl stop service-monitor

### Restart service

    sudo systemctl restart service-monitor

### Check logs for specific service

    sudo journalctl -u service-monitor -f

### Check service generated logs

    tail -n 50 ~/service-monitor/logs/server.log

### Check logs for that service

    journalctl -u service-monitor.service

### Rotate the journal for that service (so old logs can be vacuumed)

    sudo journalctl --unit=service-monitor.service --rotate

### Delete old logs for that service

    sudo journalctl --unit=service-monitor.service --vacuum-time=1s


    # Or to keep only the last 7 days:
    sudo journalctl --unit=service-monitor.service --vacuum-time=7d
