class Cart
  attr_reader :files

  def initialize
    @files = []
  end

  def add_file(cart_file)
    unless self.include? cart_file
      @files << cart_file
      return true
    end
    return false
  end

  def remove_file(cart_file)
    @backup = Array.new(@files)
    if self.include? cart_file
      @files.delete(cart_file)
      return true
    end
    return false
  end

  def include?(file)
    @files.each do |oldfile|
      if oldfile == file
        return true
      end
    end
    return false
  end

  def empty
    @backup = @files
    @files = []
  end

  def empty?
    return @files.empty?
  end

  def size
    return @files.length
  end

  def undo
    if @backup
      temp = @files
      @files = @backup
      @backup = temp
    end
  end

end
