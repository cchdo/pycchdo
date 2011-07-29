import datetime

import pycchdo.models as models

from . import *


def cruises_index(request):
    return {'cruises': models.Cruise.map_mongo(models.Cruise.find())}


def cruise_show(request):
    cruise_id = request.matchdict['cruise_id']
    cruise_obj = models.Cruise.get_id(cruise_id)

    # If the id is not an ObjectId, try searching based on ExpoCode
    if not cruise_obj:
        # TODO
        pass

    cruise = {}
    history = []
    if cruise_obj:
        cruise['date_start'] = cruise_obj.date_start()
        cruise['date_end'] = cruise_obj.date_end()
        if cruise['date_start'] and cruise['date_end']:
            cruise['cruise_dates'] = '/'.join(map(str, (cruise['date_start'], cruise['date_end'])))

        def getAttr(cruise_obj, type):
            id = None
            for c in cruise_obj.attrs.accepted_changes:
                if c['key'] == type:
                    id = c['_id']
            return models.Attr.get_id(id)

        data_files = {}
        data_files['map'] = {
            'full': getAttr(cruise_obj, 'map_full'),
            'thumb': getAttr(cruise_obj, 'map_thumb'),
        }
        data_files['exchange'] = {
            'ctdzip_exchange': getAttr(cruise_obj, 'ctdzip_exchange'),
            'bottle_exchange': getAttr(cruise_obj, 'bottle_exchange'),
        }
        data_files['netcdf'] = {
            'ctdzip_netcdf': getAttr(cruise_obj, 'ctdzip_netcdf'),
            'bottlezip_netcdf': getAttr(cruise_obj, 'bottlezip_netcdf'),
        }
        data_files['woce'] = {
            'sum_woce': getAttr(cruise_obj, 'sum_woce'),
            'bottle_woce': getAttr(cruise_obj, 'bottle_woce'),
            'ctdzip_woce': getAttr(cruise_obj, 'ctdzip_woce'),
        }
        data_files['doc'] = {
            'doc_txt': getAttr(cruise_obj, 'doc_txt'),
            'doc_pdf': getAttr(cruise_obj, 'doc_pdf'),
        }

        history = models.Attr.map_mongo(cruise_obj.attrs.history(accepted=True))

    return {
        'cruise': cruise_obj,
        'cruise_dict': cruise,
        'data_files': _collapsed_dict(data_files) or {},
        'history': history,
        }

