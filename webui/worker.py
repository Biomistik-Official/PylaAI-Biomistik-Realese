"""Headless entry point: reuse the fork's game loop with a saved browser queue."""
import os
from pathlib import Path

from webui.storage import ProjectStore


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    store = ProjectStore(root)
    instance = store.instance_id(os.environ.get('PYLAAI_INSTANCE', '1'))
    queue = store.queue(instance)
    if not queue:
        raise ValueError('The browser queue is empty.')
    from main import pyla_main
    pyla_main(queue)


if __name__ == '__main__':
    main()
