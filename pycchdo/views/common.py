import transaction

from pycchdo.views import log
from pycchdo.models import Cruise
from pycchdo.models.models import disjoint_load_cruise_attrs


def get_cruise(cruise_id, load_attrs=True):
    """Retrieve a cruise given an id. The id may be a number or uid."""
    cruise_obj = None
    if not cruise_id:
        return None

    try:
        cid = int(cruise_id)
        cruise_obj = Cruise.get_by_id(cid)
    except ValueError:
        pass

    # If the id does not refer to a Cruise, try searching based on ExpoCode
    if not cruise_obj:
        cruise_obj = Cruise.get_one_by_attrs({'expocode': cruise_id})
    if not cruise_obj:
        # If not, try based on aliases.
        cruise_obj = Cruise.get_one_by_attrs({'aliases': cruise_id})
        # cruise_show will redirect to the main cruise page when ValueError is
        # raised with an expocode
        raise ValueError(cruise_obj.expocode)
    if not cruise_obj:
        raise ValueError('Not found')

    if load_attrs:
        disjoint_load_cruise_attrs([cruise_obj])
    return cruise_obj


