#!/usr/bin/env python3
"""
Simple System Monitor
- Monitors systemd services
- Monitors Ollama availability
- Monitors system performance (CPU, Memory, Disk)
"""

import time
import subprocess
import psutil
import requests
from datetime import datetime
from threading import Thread, Lock
from flask import Flask, jsonify
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
SYSTEMD_SERVICES = [
    'cn-lexi-gen-ai',
    'cn-data-forge-ai',
    'cn-lexi-mail-ai'
]

OLLAMA_URL = 'http://localhost:11434'
CHECK_INTERVAL = 10  # seconds

# Metrics storage
metrics = {
    'systemd_services': {},
    'ollama': {
        'status': 'unknown',
        'response_time_ms': 0,
        'models_loaded': 0,
        'last_check': None
    },
    'system': {
        'cpu_percent': 0,
        'memory_percent': 0,
        'memory_used_gb': 0,
        'memory_total_gb': 0,
        'disk_percent': 0,
        'disk_used_gb': 0,
        'disk_total_gb': 0,
        'uptime_seconds': 0,
        'last_check': None
    }
}

# Initialize systemd services in metrics
for service in SYSTEMD_SERVICES:
    metrics['systemd_services'][service] = {
        'status': 'unknown',
        'uptime_seconds': 0,
        'last_check': None
    }

lock = Lock()


def check_systemd_service(service_name):
    """Check if a systemd service is running and get its uptime"""
    try:
        # Check if service is active
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        is_active = result.stdout.strip() == 'active'
        status = 'active' if is_active else 'inactive'
        
        # Get service uptime if active
        uptime_seconds = 0
        if is_active:
            try:
                # Get ActiveEnterTimestamp
                uptime_result = subprocess.run(
                    ['systemctl', 'show', service_name, '--property=ActiveEnterTimestampMonotonic'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # Parse microseconds since boot
                line = uptime_result.stdout.strip()
                if 'ActiveEnterTimestampMonotonic=' in line:
                    microseconds = line.split('=')[1]
                    if microseconds and microseconds != '0':
                        # Get system uptime
                        with open('/proc/uptime', 'r') as f:
                            system_uptime = float(f.readline().split()[0])
                        
                        service_start_time = int(microseconds) / 1000000  # Convert to seconds
                        uptime_seconds = int(system_uptime - service_start_time)
                        
                        if uptime_seconds < 0:
                            uptime_seconds = 0
                            
            except Exception as e:
                logger.debug(f"Could not get uptime for {service_name}: {e}")
        
        with lock:
            metrics['systemd_services'][service_name]['status'] = status
            metrics['systemd_services'][service_name]['uptime_seconds'] = uptime_seconds
            metrics['systemd_services'][service_name]['last_check'] = datetime.now().isoformat()
        
        logger.debug(f"✓ {service_name}: {status} (uptime: {format_uptime(uptime_seconds)})")
        return is_active
        
    except subprocess.TimeoutExpired:
        with lock:
            metrics['systemd_services'][service_name]['status'] = 'timeout'
            metrics['systemd_services'][service_name]['last_check'] = datetime.now().isoformat()
        logger.error(f"✗ Timeout checking {service_name}")
        return False
        
    except Exception as e:
        with lock:
            metrics['systemd_services'][service_name]['status'] = 'error'
            metrics['systemd_services'][service_name]['last_check'] = datetime.now().isoformat()
        logger.error(f"✗ Error checking {service_name}: {e}")
        return False


def check_ollama():
    """Check if Ollama is responding and get loaded models"""
    try:
        start = time.time()
        response = requests.get(f'{OLLAMA_URL}/api/tags', timeout=5)
        response_time = (time.time() - start) * 1000  # Convert to ms
        
        models_loaded = 0
        if response.status_code == 200:
            data = response.json()
            models_loaded = len(data.get('models', []))
        
        with lock:
            metrics['ollama']['status'] = 'up' if response.status_code == 200 else 'down'
            metrics['ollama']['response_time_ms'] = round(response_time, 2)
            metrics['ollama']['models_loaded'] = models_loaded
            metrics['ollama']['last_check'] = datetime.now().isoformat()
        
        logger.debug(f"✓ Ollama: up ({response_time:.0f}ms, {models_loaded} models)")
        return True
        
    except requests.exceptions.ConnectionError:
        with lock:
            metrics['ollama']['status'] = 'down'
            metrics['ollama']['last_check'] = datetime.now().isoformat()
        logger.debug("✗ Ollama: down (connection refused)")
        return False
        
    except Exception as e:
        with lock:
            metrics['ollama']['status'] = 'error'
            metrics['ollama']['last_check'] = datetime.now().isoformat()
        logger.error(f"✗ Ollama error: {e}")
        return False


def check_system():
    """Check system resources"""
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = round(memory.used / (1024**3), 2)
        memory_total_gb = round(memory.total / (1024**3), 2)
        
        # Disk (root partition)
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = round(disk.used / (1024**3), 2)
        disk_total_gb = round(disk.total / (1024**3), 2)
        
        # System uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = int(float(f.readline().split()[0]))
        
        with lock:
            metrics['system']['cpu_percent'] = round(cpu_percent, 1)
            metrics['system']['memory_percent'] = round(memory_percent, 1)
            metrics['system']['memory_used_gb'] = memory_used_gb
            metrics['system']['memory_total_gb'] = memory_total_gb
            metrics['system']['disk_percent'] = round(disk_percent, 1)
            metrics['system']['disk_used_gb'] = disk_used_gb
            metrics['system']['disk_total_gb'] = disk_total_gb
            metrics['system']['uptime_seconds'] = uptime_seconds
            metrics['system']['last_check'] = datetime.now().isoformat()
        
        logger.debug(
            f"✓ System: CPU={cpu_percent:.1f}%, "
            f"Memory={memory_percent:.1f}%, "
            f"Disk={disk_percent:.1f}%"
        )
        
    except Exception as e:
        logger.error(f"✗ System check error: {e}")


def format_uptime(seconds):
    """Format uptime in human readable format"""
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
    """Background thread to continuously monitor all services"""
    logger.info("🔄 Starting monitoring loop...")
    
    while True:
        try:
            # Check all services
            for service in SYSTEMD_SERVICES:
                check_systemd_service(service)
            
            check_ollama()
            check_system()
            
            # Log summary
            with lock:
                systemd_status = ', '.join([
                    f"{svc}={metrics['systemd_services'][svc]['status']}" 
                    for svc in SYSTEMD_SERVICES
                ])
                
                logger.info(
                    f"📊 Services=[{systemd_status}], "
                    f"Ollama={metrics['ollama']['status']}, "
                    f"CPU={metrics['system']['cpu_percent']}%, "
                    f"Memory={metrics['system']['memory_percent']}%, "
                    f"Disk={metrics['system']['disk_percent']}%"
                )
            
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")
        
        time.sleep(CHECK_INTERVAL)


# ============== Flask Endpoints ==============

@app.route('/')
def index():
    """Home page with simple HTML status"""
    with lock:
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Service Monitor</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; }
        .section { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .service { padding: 10px; margin: 5px 0; border-left: 4px solid #ccc; }
        .service.active { border-left-color: #4CAF50; background: #f1f8f4; }
        .service.inactive { border-left-color: #f44336; background: #fef1f1; }
        .service.error { border-left-color: #ff9800; background: #fff8f1; }
        .metric { display: inline-block; margin-right: 20px; }
        .metric-value { font-size: 24px; font-weight: bold; }
        .metric-label { color: #666; font-size: 12px; }
        .timestamp { color: #999; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ Service Monitor</h1>
        <div class="timestamp">Last updated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</div>
        
        <div class="section">
            <h2>Systemd Services</h2>
"""
        
        for service_name in SYSTEMD_SERVICES:
            service_data = metrics['systemd_services'][service_name]
            status = service_data['status']
            uptime = format_uptime(service_data['uptime_seconds'])
            
            html += f"""
            <div class="service {status}">
                <strong>{service_name}</strong>: {status.upper()} 
                {f"(uptime: {uptime})" if status == 'active' else ""}
            </div>
"""
        
        ollama_status = metrics['ollama']['status']
        ollama_class = 'active' if ollama_status == 'up' else 'inactive'
        
        html += f"""
        </div>
        
        <div class="section">
            <h2>Ollama Service</h2>
            <div class="service {ollama_class}">
                <strong>Ollama</strong>: {ollama_status.upper()}
                ({metrics['ollama']['response_time_ms']}ms, 
                {metrics['ollama']['models_loaded']} models loaded)
            </div>
        </div>
        
        <div class="section">
            <h2>System Resources</h2>
            <div class="metric">
                <div class="metric-value">{metrics['system']['cpu_percent']}%</div>
                <div class="metric-label">CPU Usage</div>
            </div>
            <div class="metric">
                <div class="metric-value">{metrics['system']['memory_percent']}%</div>
                <div class="metric-label">Memory ({metrics['system']['memory_used_gb']}/{metrics['system']['memory_total_gb']} GB)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{metrics['system']['disk_percent']}%</div>
                <div class="metric-label">Disk ({metrics['system']['disk_used_gb']}/{metrics['system']['disk_total_gb']} GB)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{format_uptime(metrics['system']['uptime_seconds'])}</div>
                <div class="metric-label">System Uptime</div>
            </div>
        </div>
        
        <div class="section">
            <h3>API Endpoints</h3>
            <ul>
                <li><a href="/status">/status</a> - JSON status</li>
                <li><a href="/prometheus">/prometheus</a> - Prometheus metrics</li>
                <li><a href="/health">/health</a> - Health check</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
        return html


@app.route('/status')
def get_status():
    """Get complete status as JSON"""
    with lock:
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'systemd_services': {
                service: {
                    'status': data['status'],
                    'uptime_seconds': data['uptime_seconds'],
                    'uptime_human': format_uptime(data['uptime_seconds'])
                }
                for service, data in metrics['systemd_services'].items()
            },
            'ollama': {
                'status': metrics['ollama']['status'],
                'response_time_ms': metrics['ollama']['response_time_ms'],
                'models_loaded': metrics['ollama']['models_loaded']
            },
            'system': {
                'cpu_percent': metrics['system']['cpu_percent'],
                'memory_percent': metrics['system']['memory_percent'],
                'memory_used_gb': metrics['system']['memory_used_gb'],
                'memory_total_gb': metrics['system']['memory_total_gb'],
                'disk_percent': metrics['system']['disk_percent'],
                'disk_used_gb': metrics['system']['disk_used_gb'],
                'disk_total_gb': metrics['system']['disk_total_gb'],
                'uptime_seconds': metrics['system']['uptime_seconds'],
                'uptime_human': format_uptime(metrics['system']['uptime_seconds'])
            }
        })


@app.route('/health')
def health():
    """Simple health check"""
    with lock:
        all_services_up = all(
            data['status'] == 'active' 
            for data in metrics['systemd_services'].values()
        )
        ollama_up = metrics['ollama']['status'] == 'up'
    
    status_code = 200 if (all_services_up and ollama_up) else 503
    
    return jsonify({
        'status': 'healthy' if status_code == 200 else 'unhealthy',
        'timestamp': datetime.now().isoformat()
    }), status_code


@app.route('/prometheus')
def prometheus_metrics():
    """Expose metrics in Prometheus format"""
    with lock:
        output = []
        
        # Systemd services (1 = active, 0 = inactive/error)
        for service_name, data in metrics['systemd_services'].items():
            status_value = 1 if data['status'] == 'active' else 0
            output.append(f'systemd_service_active{{service="{service_name}"}} {status_value}')
            output.append(f'systemd_service_uptime_seconds{{service="{service_name}"}} {data["uptime_seconds"]}')
        
        # Ollama
        ollama_up = 1 if metrics['ollama']['status'] == 'up' else 0
        output.append(f'ollama_up {ollama_up}')
        output.append(f'ollama_response_time_ms {metrics["ollama"]["response_time_ms"]}')
        output.append(f'ollama_models_loaded {metrics["ollama"]["models_loaded"]}')
        
        # System metrics
        output.append(f'system_cpu_percent {metrics["system"]["cpu_percent"]}')
        output.append(f'system_memory_percent {metrics["system"]["memory_percent"]}')
        output.append(f'system_memory_used_gb {metrics["system"]["memory_used_gb"]}')
        output.append(f'system_memory_total_gb {metrics["system"]["memory_total_gb"]}')
        output.append(f'system_disk_percent {metrics["system"]["disk_percent"]}')
        output.append(f'system_disk_used_gb {metrics["system"]["disk_used_gb"]}')
        output.append(f'system_disk_total_gb {metrics["system"]["disk_total_gb"]}')
        output.append(f'system_uptime_seconds {metrics["system"]["uptime_seconds"]}')
        
        return '\n'.join(output) + '\n', 200, {'Content-Type': 'text/plain; charset=utf-8'}


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 STARTING SERVICE MONITOR")
    logger.info("=" * 60)
    logger.info(f"📋 Monitoring services: {', '.join(SYSTEMD_SERVICES)}")
    logger.info(f"🧠 Monitoring Ollama: {OLLAMA_URL}")
    logger.info(f"⏱️  Check interval: {CHECK_INTERVAL} seconds")
    logger.info("=" * 60)
    
    # Start monitoring thread
    monitor_thread = Thread(target=monitoring_loop, daemon=True, name="MonitorThread")
    monitor_thread.start()
    
    logger.info("🌐 Web interface: http://localhost:8888")
    logger.info("📊 Metrics: http://localhost:8888/prometheus")
    logger.info("📋 Status: http://localhost:8888/status")
    logger.info("=" * 60)
    
    # Start Flask server
    app.run(host='0.0.0.0', port=8888, debug=False, threaded=True)