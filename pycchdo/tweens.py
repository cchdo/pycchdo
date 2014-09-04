import logging
from contextlib import contextmanager

from sqlalchemy_imageattach.context import push_store_context, pop_store_context


log = logging.getLogger(__name__)


@contextmanager
def fsstore_context(fsstore):
    push_store_context(fsstore)
    try:
        yield
    finally:
        pop_store_context()


def fsstore_tween_factory(handler, registry):
    def fsstore_tween(request):
        with fsstore_context(registry.settings['fsstore']):
            return handler(request)
    return fsstore_tween
