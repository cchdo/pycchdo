class ConvertController < ApplicationController

    $ALLOWED_OCEANSITES_TIMESERIES = ['BATS', 'HOT']

    def index
    end

    def ctd_netcdf_to_ctd_oceansites_netcdf
        timeseries = params[:timeseries]
        timeseries = "" unless $ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)
        __convert('ctd_netcdf_to_ctd_oceansites_netcdf.py',
                  timeseries, 'OS_.nc')
    end

    def ctdzip_netcdf_to_ctdzip_oceansites_netcdf
        timeseries = params[:timeseries]
        timeseries = "" unless $ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)
        __convert('ctdzip_netcdf_to_ctdzip_oceansites_netcdf.py',
                  timeseries, 'OS_.zip')
    end

    def ctd_exchange_to_ctdzip_oceansites_netcdf
        timeseries = params[:timeseries]
        timeseries = "" unless $ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)
        __convert('ctd_exchange_to_ctd_oceansites_netcdf.py',
                  timeseries, 'OS_.nc')
    end

    def bottle_exchange_to_kml
        __convert('bottle_exchange_to_kml.py', '', 'converted.kml')
    end

    private

    def __convert(executable, args, filename)
        if params[:file].blank?
            flash[:notice] = 'Please give me a file to convert.'
            render :action => :index
        else
            begin
                tmpfilepath = get_tempfile_path(params[:file])

                cmd = "#{LIBCCHDOBIN}/#{executable} #{tmpfilepath} #{args}"
                cmdio = IO.popen(cmd, 'rb')
                file = Tempfile.new('convert')
                file.write(cmdio.read)
                file.flush()

                send_file(file.path, :filename => filename)
            rescue
                logger.debug($!)
                flash[:notice] = "Error converting file: #{$!.inspect}"
                render :action => :index
            end
        end
    end
  
end
