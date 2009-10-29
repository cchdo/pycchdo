class BtlcmpController < ApplicationController
  layout 'standard'

  def index
    filel_upload = params[:filel_prompt]
    filer_upload = params[:filer_prompt]
    if filel_upload.blank? or filer_upload.blank?
      @filel = nil
      @filer = nil
      flash[:notice] = "Please specify two files to compare; you gave me: #{filel_upload} and #{filer_upload}."
    else
      # Rails uploads can give either StringIOs or UploadedTempFiles
      # Turn StringIOs into tempfile and give the path to the tempfile
      def get_tempfile_path(uploaded_file)
        if uploaded_file.kind_of? ActionController::UploadedStringIO
          temp = Tempfile.new 'btlcmp_upload'
          uploaded_file.each_line {|line| temp.write line }
          temp.flush
          return temp.path
        else
          return uploaded_file.path
        end
      end
  
      begin
        @filel_name = filel_upload.original_filename
        @filel = ExchangeBotFile.new(get_tempfile_path(filel_upload))
      rescue
        flash[:notice] = "Error parsing LEFT file: #{$!}"
      end
  
      if params[:merge_file]
        begin
          @filer_name = filer_upload.original_filename
          @filer = MergeFile.new(get_tempfile_path(filer_upload))
        rescue
          flash[:notice] = "Error parsing RIGHT merge file: #{$!}"
        end
      else
        begin
          @filer_name = filer_upload.original_filename
          @filer = ExchangeBotFile.new(get_tempfile_path(filer_upload))
        rescue
          flash[:notice] = "Did you forget to check the merge file box? Error parsing RIGHT file: #{$!}"
        end
      end
    end
    def sanitize_datafile!(file)
      file.data.each_key do |param|
        values = file.data[param]
        values.map! do |x|
          x.chomp! if x.kind_of? String
          if x =~ /[A-Za-z]/
            "\"#{x}\""
          else
            tmp = x.to_f
            if out_of_band(tmp)
              '-Infinity'
            else
              tmp
            end
          end
        end
      end
      (%w[STNNBR CASTNO SAMPNO BTLNBR] - file.parameters).each do |param|
        file.data[param] = ['null'] * file.data[file.parameters.first].length
      end
    end
    def to_json(datafile)
      sanitize_datafile!(datafile)
      '{'+datafile.data.to_a.collect {|param, values| "'#{param}': [#{values.join(',')}]"}.join(',')+'}'
    end
    if @filel and @filer
      @filel_json = to_json(@filel)
      @filer_json = to_json(@filer)
    end
  end

  def plot
    lparam = params[:lparam] || 'left'
    rparam = params[:rparam] || 'right'
    xs = (params[:l] || "1,2,3").split(',').map {|x| x.to_f}
    ys = (params[:r] || "1,2,3").split(',').map {|x| x.to_f}

    # If the data point count doesn't match only plot pairs
    if xs.length > ys.length
      xs = xs[0..ys.length-1]
    elsif ys.length > xs.length
      ys = ys[0..xs.length-1]
    end

    xs.reject! {|x| out_of_band(x)}
    ys.reject! {|y| out_of_band(y)}

    temp_path = "#{RAILS_ROOT}/public/images/btlcmp.png"
    Gnuplot.open do |gp|
      Gnuplot::Plot.new(gp) do |plot|
        plot.title "#{lparam} vs #{rparam}"
        plot.xlabel lparam
        plot.ylabel rparam
        plot.terminal 'png'
        plot.output temp_path
        plot.data << Gnuplot::DataSet.new([xs,ys]) do |ds|
          ds.notitle
        end
      end
    end
    send_file temp_path, :type => 'image/png', :disposition => 'inline'
  end
end
