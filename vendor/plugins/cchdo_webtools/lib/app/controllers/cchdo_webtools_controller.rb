class CchdoWebtoolsController < ApplicationController
  require 'open3'
  layout :only => [:visual, :datacmp, :convert]

  def visual
  end

  def datacmp
  end

  def convert
    @oceansites_timeseries = ALLOWED_OCEANSITES_TIMESERIES || []
  end

  def any_to_google_wire
    begin
      raise unless tmpfile = _get_tempfile_of_file_to_convert()
      tmpfilepath = tmpfile.path
    rescue ArgumentError => e
      render_json_error("No file.", :bad_request) and return
    rescue Exception => e
      render_json_error("Unable to get tempfile path: #{e.to_s}")
      return
    end

    input_type = params[:input_type]
    if not ALLOWED_FILE_FORMATS.include?(input_type) or input_type == 'detect'
      input_type = ''
    else
      input_type = "--input-type #{input_type} "
    end

    command = ["#{LIBCCHDOBIN}/any_to_type", input_type, '--type google_wire',
               '--json', tmpfilepath].join(' ')

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

    Rails.logger.error(command)

    if wire.empty?
      render_json_error("Failed to parse: #{errors.gsub('"', '\"').gsub(/\n/, '\n')}")
    else
      error_list = errors.split(/$/).map {|x| "\"#{x.strip().gsub(/[^\w\s[:punct:]]/, '?')}\""}
      error_list = error_list.select {|x| x =~ /(ERROR|WARNING|INFO):/}
      error_list = error_list.map {|x|
        if x =~ /.*\w+:(\s\?\[0m|)(.*)$/
          "\"#{$2}"
        else
          x
        end
      }
      render_json("{\"data\": #{wire}, \"errors\": [#{error_list.join(', ')}]}")
    end
  end

  def ctd_netcdf_to_ctd_oceansites_netcdf
    timeseries = params[:timeseries]
    timeseries = "" unless ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)
    __convert('ctd_netcdf_to_ctd_oceansites_netcdf',
              timeseries, 'OS_.nc')
  end

  def ctdzip_netcdf_to_ctdzip_oceansites_netcdf
    timeseries = params[:timeseries]
    timeseries = "" unless ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)
    __convert('ctdzip_netcdf_to_ctdzip_oceansites_netcdf',
              timeseries, 'OS_.zip')
  end

  def ctd_exchange_to_ctdzip_oceansites_netcdf
    timeseries = params[:timeseries]
    timeseries = "" unless ALLOWED_OCEANSITES_TIMESERIES.include?(timeseries)
    __convert('ctd_exchange_to_ctd_oceansites_netcdf',
              timeseries, 'OS_.nc')
  end

  def bottle_exchange_to_kml
    __convert('bottle_exchange_to_kml', '', 'converted.kml')
  end

 private

  ALLOWED_FILE_FORMATS = ['botex', 'ctdzipex']
 
  ALLOWED_OCEANSITES_TIMESERIES = ['BATS', 'HOT']

  LIBCCHDOBIN = File.join(File.dirname(__FILE__), '..', '..', 'libcchdoenv', 'bin')

  def render_json(json, status=:ok)
    if request.xhr?
      render :text => json, :status => status
    else
      render :text => "<textarea>#{json}</textarea>", :status => status
    end
  end

  def render_json_error(error, errorCode=:internal_server_error)
    render_json("{\"error\": \"#{error}\"}", errorCode)
  end

  # Modify make_tmpname to maintain file extensions.
  class UploadedTempfile < Tempfile
    attr_accessor :original_filename

    def make_tmpname(basename, n)
      sprintf('%d-%d%s', $$, n, basename)
    end
  end

  def _get_tempfile_of_file_to_convert
    if autoopen = params[:autoopen]
      logger.debug(autoopen)
      response = StringIO.new(Net::HTTP.get('cchdo.ucsd.edu', autoopen))
      logger.debug(response.string)
      get_tempfile(response, autoopen)
    else
      file = params[:file]
      # Hack for Rails 3 (Rails 3 encapsulates files)
      begin
        file.tempfile
      rescue
        raise ArgumentError unless file and
                                   (file.kind_of?(StringIO) or
                                    file.kind_of?(File) or
                                    file.kind_of?(Tempfile))
        get_tempfile(file)
      end
    end
  end

  # Rails uploads can give either StringIOs or UploadedTempFiles
  # Turn StringIOs into tempfile and give the path to the tempfile
  def get_tempfile(uploaded_file, filename='tempfile')
    unless uploaded_file
      return nil
    end
    unless filename
      begin
        filename = uploaded_file.original_filename
      rescue
        filename = 'data'
      end
    end
    Rails.logger.error('asdfasdfasd')
    Rails.logger.error(uploaded_file)
    Rails.logger.error(filename)
    Rails.logger.error('jkljkjlkjl')
    Rails.logger.error(File.basename(filename))
    begin
      temp = UploadedTempfile.new(File.basename(filename))
      temp.write(uploaded_file.read())
      temp.flush()
    rescue => e
      Rails.logger.error(e)
    end
    Rails.logger.error('qwerqwereqwr')
    uploaded_file.close()
    Rails.logger.error(temp.inspect)
    temp
  end

  def __convert(executable, args, filename)
    if params[:file].blank?
      render :text => "Please give a file to convert.",
             :status => :bad_request
      return
    end
    begin
      tmpfilepath = get_tempfile(params[:file]).path

      cmd = "#{LIBCCHDOBIN}/#{executable} #{tmpfilepath} #{args}"
      cmdio = IO.popen(cmd, 'rb')
      file = Tempfile.new('convert')
      file.write(cmdio.read)
      file.flush()

      send_file(file.path, :filename => filename)
    rescue
      logger.debug($!)
      render :text => "Error converting file: #{$!.inspect}",
             :status => :internal_server_error
    end
  end
end
