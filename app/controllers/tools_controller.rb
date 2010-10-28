class Tempfile
  attr_accessor :original_filename
end

class ToolsController < ApplicationController
  require 'open3'
  layout 'standard', :except => :any_to_google_wire

  def visual
    # if autoload = params[:autoload]
    #     file = Tempfile.new('visual_autoopen')
    #     file.write(Net::HTTP.get('cchdo.ucsd.edu', autoopen))
    #     file.original_filename = autoopen
    #     file.flush
    # end
  end

  def btlcmp
  end

  def convert
  end

  def any_to_google_wire
    file = params[:file]
    unless file and (file.kind_of?(String) or file.kind_of?(Tempfile))
      render_json_error("No file.")
      return
    end
    #filename = file.original_filename || 'data'
    begin
      tmpfilepath = get_tempfile_path(file)
    rescue Exception => e
      render_json_error("Unable to get tempfile path: #{e.to_s}")
      return
    end

    command = "#{LIBCCHDOBIN}/any_to_google_wire.py --json --type botex #{tmpfilepath}"

    errors = ''
    wire = ''
    Open3.popen3(command) do |stdin, stdout, stderr|
      read_wire = Thread.new do 
        begin
          while true
            wire << stdout.readpartial(stdout.stat.blksize)
          end
        rescue EOFError
        end
      end
      read_errors = Thread.new do
        begin
          while true
            errors << stderr.readpartial(stderr.stat.blksize)
          end
        rescue EOFError
        end
      end
      read_wire.join
      read_errors.join
    end

    #errors = 'Unknown'
    #wire = `#{LIBCCHDOBIN}/any_to_google_wire.py --json --type botex #{tmpfilepath}`
    if wire.empty?
      render_json_error("Failed to parse: #{errors}")
    else
      render_json(wire)
    end
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

  LIBCCHDOBIN = '/Users/myshen/Documents/libcchdo/bin'
  $ALLOWED_OCEANSITES_TIMESERIES = ['BATS', 'HOT']

  def render_json(json, status=:ok)
    render :text => "<textarea>#{json}</textarea>", :status => status
  end

  def render_json_error(error)
    render_json("{\"error\": \"#{error}\"}", :internal_server_error)
  end

  # Modify make_tmpname to maintain file extensions.
  class UploadedTempfile < Tempfile
    def make_tmpname(basename, n)
      sprintf('%d-%d%s', $$, n, basename)
    end
  end

  # Rails uploads can give either StringIOs or UploadedTempFiles
  # Turn StringIOs into tempfile and give the path to the tempfile
  def get_tempfile(uploaded_file)
    unless uploaded_file
      return nil
    end
    filename = uploaded_file.original_filename || 'data'
    basename = File.basename(filename)
    temp = UploadedTempfile.new(basename)
    temp.write(uploaded_file.read())
    temp.flush()
    uploaded_file.close()
    temp
  end

  def get_tempfile_path(uploaded_file)
    get_tempfile(uploaded_file).path
  end

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
