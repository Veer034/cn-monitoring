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

    pip install flask psutil requests

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
    git clone https://github.com/Veer034/cn-monitorting.git

### Install Python

    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install python3.10 python3.10-venv python3.10-distutils

### Install library in production VM

    pip install flask psutil requests python-dateutil prometheus-client

    # Ensure pip build tools are up to date
    pip install --upgrade pip setuptools wheel
    pip install --upgrade build

### Create Systemd file for as a service execution

    sudo tee /etc/systemd/system/service-monitor.service > /dev/null << 'EOF'
    [Unit]
    Description=Service Monitor
    After=network.target

    [Service]
    Type=simple
    User=azureuser
    WorkingDirectory=/home/azureuser
    ExecStart=/usr/bin/python3 /home/azureuser/service_monitor.py
    Restart=always
    RestartSec=10
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=multi-user.target
    EOF

    sudo systemctl daemon-reload
    sudo systemctl enable service-monitor
    sudo systemctl start service-monitor
    sudo systemctl status service-monitor

### HuggingFace model storage location

    ~/.cache/huggingface/

### List all services

    systemctl list-units --type=service
    systemctl list-units --type=service | grep cn-

### Reload systemd

    sudo systemctl daemon-reload

### Enable all services to start on boot

    sudo systemctl enable cn-monitorting

### Start Service

    sudo systemctl start cn-monitorting

### Check Status

    sudo systemctl status cn-monitorting

### Stop service

    sudo systemctl stop cn-monitorting

### Restart service

    sudo systemctl restart cn-monitorting

### Check logs for specific service

    sudo journalctl -u cn-monitorting -f

### Check service generated logs

    tail -n 50 ~/cn-monitorting/logs/server.log

### Check logs for that service

    journalctl -u cn-monitorting.service

### Rotate the journal for that service (so old logs can be vacuumed)

    sudo journalctl --unit=cn-monitorting.service --rotate

### Delete old logs for that service

    sudo journalctl --unit=cn-monitorting.service --vacuum-time=1s


    # Or to keep only the last 7 days:
    sudo journalctl --unit=cn-monitorting.service --vacuum-time=7d
