"""Run browser menus before importing the heavy game and desktop modules."""
import argparse
import os
from pathlib import Path
import threading
import webbrowser


def main(argv=None):
    parser = argparse.ArgumentParser(description='PylaAI Biomistik — local browser control panel. Use --legacy on the original entry point for desktop menus.')
    parser.add_argument('--port', type=int, default=5185, help='Preferred local port (default: 5185).')
    parser.add_argument('--no-browser', '--headless', action='store_true', help='Serve the panel without opening a browser tab.')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('Port must be between 1024 and 65535.')
    try:
        from werkzeug.serving import make_server
        from webui.app import create_app
    except ImportError as error:
        raise SystemExit('Browser dependencies are missing. Run: python -m pip install -r requirements-web.txt') from error
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    app = create_app(root)
    server = None
    # Bind the actual listening socket to avoid a separate port-check race.
    for port in range(args.port, min(args.port + 50, 65536)):
        try:
            server = make_server('127.0.0.1', port, app, threaded=True)
            break
        except (OSError, SystemExit):
            continue
    if server is None:
        raise SystemExit('Could not bind a local port. Try --port with another number.')
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'PylaAI Biomistik browser panel: {url}', flush=True)
    print('Close this process with Ctrl+C to stop the panel and its bot instances.', flush=True)
    if not args.no_browser:
        timer = threading.Timer(.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.config['runtime_manager'].close()


if __name__ == '__main__':
    main()
