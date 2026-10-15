"""One public Next.js listener; FastAPI stays on container loopback."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    env=dict(os.environ)
    origin=env.get('APP_URL') or env.get('RENDER_EXTERNAL_URL','')
    if not origin.startswith('https://'):
        raise SystemExit('Set APP_URL to the HTTPS deployment URL, or run on Render with RENDER_EXTERNAL_URL.')
    env['APP_URL']=origin.rstrip('/')
    env['API_URL']=origin.rstrip('/')
    env['PRIVATE_DEMO']='true'
    env['DEMO_MODE']='true'
    env['ENABLE_EMAIL_SEND']='false'
    # Hosted demo is intentionally a separate mode from the live production system.
    env['APP_ENV']='hosted-demo'
    data=Path('/var/data')
    data.mkdir(parents=True,exist_ok=True)
    local=Path('/app/backend/.local')
    if not local.exists():
        local.symlink_to(data,target_is_directory=True)
    env.setdefault('DATABASE_URL','sqlite:////var/data/construction.db')
    children=[]
    def stop(*args):
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
    signal.signal(signal.SIGTERM,lambda *args:sys.exit(0))
    signal.signal(signal.SIGINT,lambda *args:sys.exit(0))
    try:
        api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--proxy-headers','--forwarded-allow-ips','127.0.0.1'],cwd='/app/backend',env=env)
        children.append(api)
        for _ in range(60):
            if api.poll() is not None:
                raise RuntimeError('API startup failed. Review server logs.')
            try:
                with urlopen('http://127.0.0.1:8000/api/health',timeout=1) as response:
                    if response.status==200:
                        break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError('API did not become healthy.')
        env['HOSTNAME']='0.0.0.0'
        env['PORT']=env.get('PORT','10000')
        children.append(subprocess.Popen(['node','server.js'],cwd='/app/frontend',env=env))
        while all(p.poll() is None for p in children):
            time.sleep(1)
        raise RuntimeError('A server exited; restarting the container is required.')
    finally:
        stop()


if __name__=='__main__':
    main()
