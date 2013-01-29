"""pycchdo file types.

TODO this may be a task better suited for libcchdo.

"""
data_file_human_names = {
    'bottle_exchange': 'Bottle Exchange',
    'bottlezip_exchange': 'Bottle ZIP Exchange',
    'ctdzip_exchange': 'CTD ZIP Exchange',
    'bottlezip_netcdf': 'Bottle ZIP NetCDF',
    'ctdzip_netcdf': 'CTD ZIP NetCDF',
    'bottle_woce': 'Bottle WOCE',
    'ctdzip_woce': 'CTD ZIP WOCE',
    'sum_woce': 'Summary WOCE',
    'map_thumb': 'Map Thumbnail',
    'map_full': 'Map Fullsize',
    'doc_txt': 'Documentation Text',
    'doc_pdf': 'Documentation PDF',
    'woce_ctd': 'CTD WOCE',
    'encrypted': 'Encrypted file',
    'ctd_exchange': 'CTD Exchange',
    'jgofs': 'JGOFS File',
    'large_volume_samples_exchange': 'Large Volume Samples WOCE',
    'large_volume_samples_woce': 'Large Volume Samples Exchange',
    'matlab': 'Matlab file',
    'sea': 'SEA file',
    'ctd_wct': 'CTD WCT File',
    }


data_file_descriptions = {
    'bottle_woce': 'ASCII bottle data',
    'ctdzip_woce': 'ZIP archive of ASCII CTD data',
    'bottle_exchange': 'ASCII .csv bottle data with station information',
    'ctdzip_exchange': 'ZIP archive of ASCII .csv CTD data with station '
                       'information',
    'ctdzip_netcdf': 'ZIP archive of binary CTD data with station information',
    'bottlezip_netcdf': 'ZIP archive of binary bottle data with station '
                        'information',
    'sum_woce': 'ASCII station/cast information',
    'large_volume_samples_woce': 'ASCII large volume samples',
    'large_volume_samples_exchange': 'ASCII .csv large volume samples',
    'trace_metals_woce': 'ASCII trace metal samples',
    'trace_metals_exchange': 'ASCII .csv trace metal samples',
    'map_thumb': 'Map thumbnail',
    'map_full': 'Map full size',
    'doc_txt': 'ASCII cruise and data documentation',
    'doc_pdf': 'Portable Document Format cruise and data documentation',
    'woce_ctd': 'ASCII CTD data',
    'encrypted': 'Encrypted file',
    'ctd_exchange': 'ASCII .csv CTD data with station information',
    'jgofs': 'JGOFS File',
    'matlab': 'Matlab file',
    'sea': 'ASCII SEA file',
    'ctd_wct': 'ASCII CTD data',
    }
