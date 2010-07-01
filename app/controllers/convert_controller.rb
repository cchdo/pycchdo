class ConvertController < ApplicationController

    $ALLOWED_OCEANSITES_TIMESERIES = ['BATS', 'HOT']

    def index
    end

    def ctd_netcdf_to_ctd_oceansites_netcdf
        if params[:file].blank?
            flash[:notice] = 'Please give me a file to convert.'
            render :action => :index
        else
            begin
                tmpfilepath = get_tempfile_path(params[:file])
                timeseries = params[:timeseries]
                timeseries = "" unless $ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)

                cmd = "#{LIBCCHDOBIN}/ctd_netcdf_to_ctd_oceansites_netcdf.py " + 
                      "#{tmpfilepath} #{timeseries}"
                cmdio = IO.popen(cmd, 'rb')
                file = Tempfile.new('convert')
                file.write(cmdio.read)
                file.flush

                send_file(file.path, :filename => 'OS_.nc', :type => 'applications/x-netcdf')
            rescue
                raise
                flash[:notice] = "Error converting file: #{$!}"
                render :action => :index
            end
        end
    end

    def ctdzip_netcdf_to_ctdzip_oceansites_netcdf
        if params[:file].blank?
            flash[:notice] = 'Please give me a file to convert.'
            render :action => :index
        else
            begin
                tmpfilepath = get_tempfile_path(params[:file])
                timeseries = params[:timeseries]
                timeseries = "" unless $ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)

                cmd = "#{LIBCCHDOBIN}/ctdzip_netcdf_to_ctdzip_oceansites_netcdf.py " + 
                      "#{tmpfilepath} #{timeseries}"
                cmdio = IO.popen(cmd, 'rb')
                file = Tempfile.new('convert')
                file.write(cmdio.read)
                file.flush

                send_file(file.path, :filename => 'OS_.zip')
            rescue
                raise
                flash[:notice] = "Error converting file: #{$!}"
                render :action => :index
            end
        end
    end

    def bottle_exchange_to_kml
        if params[:file].blank?
            flash[:notice] = 'Please give me a file to convert.'
            render :action => :index
        else
            begin
                tmpfilepath = get_tempfile_path(params[:file])

                cmd = "#{LIBCCHDOBIN}/bottle_exchange_to_kml.py " + 
                      "#{tmpfilepath}"
                cmdio = IO.popen(cmd, 'rb')
                file = Tempfile.new('convert')
                file.write(cmdio.read)
                file.flush

                send_file(file.path, :filename => 'converted.kml')
            rescue
                raise
                flash[:notice] = "Error converting file: #{$!}"
                render :action => :index
            end
        end
    end
  
end
