import logging

from sqlalchemy_imageattach.context import push_store_context, pop_store_context


log = logging.getLogger(__name__)


def fsstore_tween_factory(handler, registry):
    def fsstore_tween(request):
        push_store_context(registry.settings['fsstore'])
        try:
            response = handler(request)
        finally:
            pop_store_context()
        return response
    return fsstore_tween
