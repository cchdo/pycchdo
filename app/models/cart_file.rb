class CartFile
  attr_reader :ExpoCode, :type, :format, :url

  def initialize(expocode, type, format, url)
    @ExpoCode = expocode
    @type = type
    @format = format
    @url = url
  end

  def == (cart_file)
    return (self <=> cart_file) == 0
  end
  
  def <=> (cart_file)
    return self.to_s <=> cart_file.to_s
  end
  
  def to_s
    return "#{@ExpoCode}-#{type}_#{format}"
  end

  def CartFile.tag_to_cart_file(tag, url='')
    expocode, type_format = tag.split '-'
    type, format = type_format.split '_'
    return CartFile.new(expocode, type, format, url)
  end

end
