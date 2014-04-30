import transaction

from pycchdo.views import log
from pycchdo.models.serial import Cruise


def get_cruise(cruise_id, load_attrs=True):
    """Retrieve a cruise given an id. The id may be a number or uid."""
    cruise_obj = None
    if not cruise_id:
        return None

    try:
        cid = int(cruise_id)
        cruise_obj = Cruise.query().get(cid)
    except ValueError:
        pass

    # If the id does not refer to a Cruise, try searching based on ExpoCode
    if not cruise_obj:
        cruise_obj = Cruise.get_by_expocode(cruise_id)
    if not cruise_obj:
        # If not, try based on aliases.
        cruise_obj = Cruise.query().filter(
            Cruise.aliases.any(cruise_id)).first()
    if not cruise_obj:
        raise ValueError('Not found')
    return cruise_obj


