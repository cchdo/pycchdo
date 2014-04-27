"""pycchdo file types.

TODO this may be a task better suited for libcchdo.

"""
class DataFileTypes(object):
    human_names = {}
    descriptions = {}

    @classmethod
    def add(cls, key, human_name, description):
        cls.human_names[key] = human_name
        cls.descriptions[key] = description

DataFileTypes.add('bottle_exchange', 'Bottle Exchange',
    'ASCII .csv bottle data with station information')
DataFileTypes.add('bottle_woce', 'Bottle WOCE',
    'ASCII bottle data')
DataFileTypes.add('bottle_zip_exchange', 'Bottle ZIP Exchange',
    'ZIP archive of ASCII bottle data with station information')
DataFileTypes.add('ctd_zip_exchange', 'CTD ZIP Exchange',
    'ZIP archive of ASCII .csv CTD data with station information')
DataFileTypes.add('bottle_zip_netcdf', 'Bottle ZIP NetCDF',
    'ZIP archive of binary bottle data with station information')
DataFileTypes.add('ctd_zip_netcdf', 'CTD ZIP NetCDF',
    'ZIP archive of binary CTD data with station information')
DataFileTypes.add('ctd_zip_woce', 'CTD ZIP WOCE',
    'ZIP archive of ASCII CTD data')
DataFileTypes.add('ctd_exchange', 'CTD Exchange',
    'ASCII .csv CTD data with station information')
DataFileTypes.add('ctd_woce', 'CTD WOCE',
    'ASCII CTD data')
DataFileTypes.add('ctd_wct', 'CTD WCT File',
    'ASCII CTD data')
DataFileTypes.add('sum_woce', 'Summary WOCE',
    'ASCII station/cast information')
DataFileTypes.add('large_volume_samples_exchange', 'Large Volume Samples WOCE',
    'ASCII .csv large volume samples')
DataFileTypes.add('large_volume_samples_woce', 'Large Volume Samples Exchange',
    'ASCII large volume samples')
DataFileTypes.add('trace_metals_exchange', 'Trace Metals WOCE',
    'ASCII .csv trace metal samples')
DataFileTypes.add('trace_metals_woce', 'Trace Metals Exchange',
    'ASCII trace metal samples')
DataFileTypes.add('map_thumb', 'Map Thumbnail',
    'Map thumbnail')
DataFileTypes.add('map_full', 'Map Fullsize',
    'Map full size')
DataFileTypes.add('doc_txt', 'Documentation Text',
    'ASCII cruise and data documentation')
DataFileTypes.add('doc_pdf', 'Documentation PDF',
    'Portable Document Format cruise and data documentation')
DataFileTypes.add('encrypted', 'Encrypted file',
    'Encrypted file')
DataFileTypes.add('jgofs', 'JGOFS File',
    'JGOFS File')
DataFileTypes.add('matlab', 'Matlab file',
    'Matlab file')
DataFileTypes.add('sea', 'SEA file',
    'ASCII SEA file')


data_file_human_names = DataFileTypes.human_names


data_file_descriptions = DataFileTypes.descriptions
