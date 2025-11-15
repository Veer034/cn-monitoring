#!/usr/bin/env python3
"""
Simple Service Monitor for Prometheus
Keeps all existing endpoints and metric names
"""

from flask import Flask, jsonify
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge
import subprocess
import requests
import psutil
import time
from threading import Thread
from datetime import datetime

app = Flask(__name__)

# Config
SERVICES = ['cn-lexi-gen-ai', 'cn-data-forge-ai', 'cn-lexi-mail-ai']
OLLAMA_URL = 'http://localhost:11434'

# Prometheus metrics
service_active = Gauge('systemd_service_active', 'Service active status', ['service'])
service_uptime_seconds = Gauge('systemd_service_uptime_seconds', 'Service uptime', ['service'])
ollama_up = Gauge('ollama_up', 'Ollama status')
ollama_response_time_ms = Gauge('ollama_response_time_ms', 'Ollama response time')
ollama_models_loaded = Gauge('ollama_models_loaded', 'Ollama models loaded')
system_cpu_percent = Gauge('system_cpu_percent', 'CPU usage')
system_memory_percent = Gauge('system_memory_percent', 'Memory usage')
system_memory_used_gb = Gauge('system_memory_used_gb', 'Memory used GB')
system_memory_total_gb = Gauge('system_memory_total_gb', 'Memory total GB')
system_disk_percent = Gauge('system_disk_percent', 'Disk usage')
system_disk_used_gb = Gauge('system_disk_used_gb', 'Disk used GB')
system_disk_total_gb = Gauge('system_disk_total_gb', 'Disk total GB')
system_uptime_seconds = Gauge('system_uptime_seconds', 'System uptime')

# Store for JSON endpoints
metrics = {}


def check_service(service_name):
    """Check systemd service"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True, text=True, timeout=5
        )
        is_active = result.stdout.strip() == 'active'
        
        service_active.labels(service=service_name).set(1 if is_active else 0)
        
        uptime = 0
        if is_active:
            uptime_result = subprocess.run(
                ['systemctl', 'show', service_name, '--property=ActiveEnterTimestampMonotonic'],
                capture_output=True, text=True, timeout=5
            )
            line = uptime_result.stdout.strip()
            if 'ActiveEnterTimestampMonotonic=' in line:
                microseconds = line.split('=')[1]
                if microseconds and microseconds != '0':
                    with open('/proc/uptime', 'r') as f:
                        system_uptime = float(f.readline().split()[0])
                    uptime = max(0, int(system_uptime - int(microseconds) / 1000000))
        
        service_uptime_seconds.labels(service=service_name).set(uptime)
        
        metrics['systemd_services'][service_name] = {
            'status': 'active' if is_active else 'inactive',
            'uptime_seconds': uptime
        }
    except Exception as e:
        service_active.labels(service=service_name).set(0)
        service_uptime_seconds.labels(service=service_name).set(0)
        metrics['systemd_services'][service_name] = {'status': 'error', 'uptime_seconds': 0}


def check_ollama():
    """Check Ollama"""
    try:
        start = time.time()
        response = requests.get(f'{OLLAMA_URL}/api/tags', timeout=5)
        response_time = (time.time() - start) * 1000
        
        if response.status_code == 200:
            models = len(response.json().get('models', []))
            ollama_up.set(1)
            ollama_response_time_ms.set(response_time)
            ollama_models_loaded.set(models)
            metrics['ollama'] = {
                'status': 'up',
                'response_time_ms': round(response_time, 2),
                'models_loaded': models
            }
        else:
            raise Exception("Non-200 response")
    except:
        ollama_up.set(0)
        ollama_response_time_ms.set(0)
        ollama_models_loaded.set(0)
        metrics['ollama'] = {'status': 'down', 'response_time_ms': 0, 'models_loaded': 0}


def check_system():
    """Check system resources"""
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        with open('/proc/uptime', 'r') as f:
            uptime = int(float(f.readline().split()[0]))
        
        system_cpu_percent.set(cpu)
        system_memory_percent.set(mem.percent)
        system_memory_used_gb.set(round(mem.used / (1024**3), 2))
        system_memory_total_gb.set(round(mem.total / (1024**3), 2))
        system_disk_percent.set(disk.percent)
        system_disk_used_gb.set(round(disk.used / (1024**3), 2))
        system_disk_total_gb.set(round(disk.total / (1024**3), 2))
        system_uptime_seconds.set(uptime)
        
        metrics['system'] = {
            'cpu_percent': round(cpu, 1),
            'memory_percent': round(mem.percent, 1),
            'memory_used_gb': round(mem.used / (1024**3), 2),
            'memory_total_gb': round(mem.total / (1024**3), 2),
            'disk_percent': round(disk.percent, 1),
            'disk_used_gb': round(disk.used / (1024**3), 2),
            'disk_total_gb': round(disk.total / (1024**3), 2),
            'uptime_seconds': uptime
        }
    except Exception as e:
        print(f"System check error: {e}")


def format_uptime(seconds):
    """Format uptime"""
    if seconds == 0:
        return "N/A"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else f"{seconds}s"


def monitoring_loop():
    """Background monitoring"""
    global metrics
    metrics = {'systemd_services': {}, 'ollama': {}, 'system': {}}
    
    while True:
        for service in SERVICES:
            check_service(service)
        check_ollama()
        check_system()
        time.sleep(10)


# Endpoints
@app.route('/')
def index():
    """HTML dashboard"""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Service Monitor</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .service {{ padding: 10px; margin: 5px 0; border-left: 4px solid #ccc; }}
        .service.active {{ border-left-color: #4CAF50; background: #f1f8f4; }}
        .service.inactive {{ border-left-color: #f44336; background: #fef1f1; }}
        .metric {{ display: inline-block; margin-right: 20px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ Service Monitor</h1>
        <div class="section">
            <h2>Systemd Services</h2>"""
    
    for service_name in SERVICES:
        data = metrics.get('systemd_services', {}).get(service_name, {})
        status = data.get('status', 'unknown')
        uptime = format_uptime(data.get('uptime_seconds', 0))
        html += f"""
            <div class="service {status}">
                <strong>{service_name}</strong>: {status.upper()} 
                {f"(uptime: {uptime})" if status == 'active' else ""}
            </div>"""
    
    ollama_data = metrics.get('ollama', {})
    ollama_status = ollama_data.get('status', 'unknown')
    html += f"""
        </div>
        <div class="section">
            <h2>Ollama Service</h2>
            <div class="service {'active' if ollama_status == 'up' else 'inactive'}">
                <strong>Ollama</strong>: {ollama_status.upper()}
                ({ollama_data.get('response_time_ms', 0)}ms, {ollama_data.get('models_loaded', 0)} models)
            </div>
        </div>
        <div class="section">
            <h2>System Resources</h2>"""
    
    sys_data = metrics.get('system', {})
    html += f"""
            <div class="metric">
                <div class="metric-value">{sys_data.get('cpu_percent', 0)}%</div>
                <div class="metric-label">CPU Usage</div>
            </div>
            <div class="metric">
                <div class="metric-value">{sys_data.get('memory_percent', 0)}%</div>
                <div class="metric-label">Memory ({sys_data.get('memory_used_gb', 0)}/{sys_data.get('memory_total_gb', 0)} GB)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{sys_data.get('disk_percent', 0)}%</div>
                <div class="metric-label">Disk ({sys_data.get('disk_used_gb', 0)}/{sys_data.get('disk_total_gb', 0)} GB)</div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html


@app.route('/status')
def get_status():
    """JSON status"""
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'systemd_services': {
            service: {
                'status': data['status'],
                'uptime_seconds': data['uptime_seconds'],
                'uptime_human': format_uptime(data['uptime_seconds'])
            }
            for service, data in metrics.get('systemd_services', {}).items()
        },
        'ollama': metrics.get('ollama', {}),
        'system': {**metrics.get('system', {}), 'uptime_human': format_uptime(metrics.get('system', {}).get('uptime_seconds', 0))}
    })


@app.route('/health')
def health():
    """Health check"""
    all_up = all(d.get('status') == 'active' for d in metrics.get('systemd_services', {}).values())
    ollama_status = metrics.get('ollama', {}).get('status') == 'up'
    status_code = 200 if (all_up and ollama_status) else 503
    return jsonify({'status': 'healthy' if status_code == 200 else 'unhealthy'}), status_code


@app.route('/prometheus')
def prometheus_metrics():
    """Prometheus metrics - KEEPS YOUR EXISTING FORMAT"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


if __name__ == '__main__':
    print("Starting monitor on :8888")
    Thread(target=monitoring_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=8888)