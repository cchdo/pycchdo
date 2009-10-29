class CartController < ApplicationController

  def index
    redirect_to :action => 'view'
  end

  def add_files
    session[:cart] ||= Cart.new
    count = 0
    params.keys.each do |param|
      if param.start_with? 'checkbox_'
        trash, tag = param.split 'checkbox_'
        if session[:cart].add_file(CartFile.tag_to_cart_file(tag, params[param]))
          count += 1
        end
      end
    end
    plurality = ''
    unless count <= 1 and count >= -1
      plurality = 's'
    end
    flash[:notice] ||= ''
    unless count <= 0
      flash[:notice] << "Added #{count} file#{plurality} to your cart."
    else
      flash[:notice] << "You can't add #{count} file#{plurality} to your cart."
    end
    redirect_to :action => 'view'
  end

  def remove
    if tag = params[:id]
      flash[:notice] ||= ''
      if session[:cart].remove_file(CartFile.tag_to_cart_file(tag))
        flash[:notice] << "Removed a file (#{tag}) from your cart. <a href='/cart/undo?id=#{tag}'>Undo</a>"
      else
        flash[:notice] << "Failed to remove a file (#{tag}). Your cart is UNCHANGED."
        logger.warn("Failed to remove file with tag (#{tag}) from cart: #{CartFile.tag_to_cart_file(tag)}")
      end
    end
    redirect_to :action => 'view'
  end
 
  def empty
    session[:cart].empty
    flash[:notice] ||= ''
    flash[:notice] << 'Emptied your cart. <a href="/cart/undo_empty">Undo</a>'
    redirect_to :action => 'view'
  end

  def view

  end

  def undo
    if tag = params[:id]
      session[:cart].undo
      flash[:notice] ||= ''
      flash[:notice] << "Re-added a file (#{tag}) to your cart."
    end
    redirect_to :action => 'view'
  end

  def undo_empty
    session[:cart].undo
    flash[:notice] ||= ''
    flash[:notice] << 'Restored your cart.'
    redirect_to :action => 'view'
  end

  def checkout
    begin
      `mkdir -p #{RAILS_ROOT}/public/cart`
      zip_filename = "#{RAILS_ROOT}/public/cart/cchdo_data_for_#{session.session_id[0..7]}.zip"
      zip_file = Zip::ZipFile.open(zip_filename, Zip::ZipFile::CREATE) do |zip|
        session[:cart].files.each do |file|
          zip.add("#{file.ExpoCode}/#{File.basename(file.url)}", file.url)
        end
      end
      File.chmod(0644, zip_filename)
      send_file(zip_filename, :disposition => 'attachment')
    rescue => e
      flash[:notice] ||= ''
      flash[:notice] << '<span class="warning">There was an error packaging your files. We are working to fix this.</span>'
      logger.warn "\n!!!\ncart/checkout error:\n\t#{e}\n!!!\n"
      redirect_to :action => 'view'
    end
  end
end
