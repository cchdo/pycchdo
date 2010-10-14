# Everything here is available for all controllers.
require 'csv'
require 'parsedate'

class ApplicationController < ActionController::Base
  layout 'standard'

  COUNTRIES = {
    'germany' => 'ger', 'japan'     => 'jpn', 'france'  => 'fra', 'england'		=> 'uk',
    'canada'  => 'can', 'us'        => 'usa', 'india'   => 'ind', 'russia'		=> 'rus',
    'spain'   => 'spn', 'argentina'	=> 'arg', 'ukrain'  => 'ukr', 'netherlands'	=> 'net',
    'norway'  => 'nor', 'finland'   => 'fin', 'iceland' => 'ice', 'australia'	=> 'aus',
    'chile'   => 'chi', 'china'     => 'prc', 'taiwan'  => 'tai'
  }

  private

  def check_authentication
    unless session[:user]
      session[:intended_action] = action_name
      session[:intended_controller] = controller_name
      redirect_to :controller => '/staff', :action => 'signin'
    end
  end

  def thumbnail_uri(expocode)
    if map = Document.first(:conditions => { :ExpoCode => expocode, :FileType => 'Small Plot'})
      return map.FileName[0..-5]
    end
    return nil
  end

  def best_query_type(query)
    best_queries = Hash.new
    param_queries = Array.new

    ignored_queries = ['commit', 'action', 'controller', 'post', 'FileType', 'limit', 'skip']
    queries = parse_query_string(query) - ignored_queries

    keywords = {'group' => '`Group`', 'chief_scientist' => 'Chief_Scientist', 
                'expocode' => 'ExpoCode', 'alias' => 'Alias', 
                'ship_name' => 'Ship_Name', 'ship' => 'Ship_Name',
                'year_start' => 'year_start', 'year_end' => 'year_end',
                'month_start' => 'month_start', 'month_end' => 'month_end',
                'date' => 'Date', 'line' => 'Line'}
    parameters = Parameter.column_names

    # See if we recognize the query type
    queries.each do |query|
      # Query term is in format 'keyword:value'
      if query =~ /(\w+\:\w+)/
        keyword, value = query.split(':', 2)
        if keywords.include?(keyword.downcase.strip)
          best_queries[keywords[keyword.downcase]] = value
        end
      elsif query =~ /^([a-zA-Z]{1,3})(\d{1,2})$/i # Line number
        query = "#{$1}#{$2}"
        # Change queries formatted like I9, or A6 to be I09 or A06
        if $2.length == 1
           query = "#{$1}0#{$2}"
        end
        best_queries['Line'] = query
      elsif query =~ /\b\d{4}\b/
        best_queries['Date'] = query
      elsif country = COUNTRIES[query.downcase]
        best_queries['Country'] = country
      elsif parameters.include? query.upcase
        param_queries << query
      elsif query.downcase =~ /\ball\b/i
        best_queries['All'] = ' All results are on this page.'
      else # Resort to highest number of matches
        best_queries[find_best_query(query)] = query
      end
    end

    best_queries.delete_if {|key, value| key.empty?}
    return best_queries, param_queries
  end

  def find_cruises(query, skip=0, limit=10, count=false)
    best_queries, param_queries = best_query_type(query)
 
    # Build SQL query
    where_clauses = Array.new
    limit_clause = "LIMIT #{skip}, #{limit}"

    if best_queries
      best_queries.each_pair do |type, query|
        if type == 'All'
          skip = 0
          limit = 0
          limit_clause = ''
        elsif type == 'Date'
          where_clauses << "(Begin_Date REGEXP '#{query}' OR EndDate REGEXP '#{query}')"
        # Also search for aliases that look like lines
        elsif type == 'Line'
          where_clauses << "#{type} REGEXP '#{query}' OR Alias REGEXP '#{query}'"
        elsif type =~ /\byear.?start/ # \b to keep from grabbing file_year_start too
          required_others = ['year_end', 'month_start', 'month_end']
          other_types = best_queries.keys
          if required_others == required_others & other_types
            begin_date = "#{sprintf("%04u", best_queries['year_start'])}-#{sprintf("%02u", best_queries['month_start'])}-00"
            end_date   = "#{sprintf("%04u", best_queries['year_end'])}-#{sprintf("%02u", best_queries['month_end'])}-00"
            where_clauses << "(\"#{begin_date}\" < Begin_Date AND Begin_Date < \"#{end_date}\")"
          end
        elsif type =~ /(year_end)|(month_start)|(month_end)|(file_month_start)|(file_year_start)|(FileType)/i
          # ignore these (already handled or not handling)
        else
          if type == 'ExpoCode'
            type = 'cruises.ExpoCode'
          end
          where_clauses << "#{type} REGEXP '#{query}'"
        end
      end
    end

    param_queries.each do |parameter|
      where_clauses << "parameters.`#{parameter}` > 0"
    end

    # join them all together
    where_clause = ''
    if wheres = where_clauses.join(' AND ') and not wheres.empty?
      where_clause = "WHERE #{wheres}"
    end

    join_on = ''
    unless param_queries.empty?
      join_on = 'LEFT JOIN (parameters) ON (cruises.ExpoCode=parameters.ExpoCode)'
    end

    cruises = Cruise.find_by_sql("SELECT DISTINCT * FROM cruises #{join_on} #{where_clause} #{limit_clause}")
    cruises.each do |cruise|
    end
    if count
      # Hopefully we can make expocodes indexed in the future
      return cruises, best_queries, Cruise.count_by_sql("SELECT count(cruises.id) FROM cruises #{join_on} #{where_clause}")
    else
      return cruises, best_queries
    end
  end

  def parse_query_string(query_str)
    # There must be words in a query
    if query_str !~ /\w/
      return nil
    end

    # Erase illegal characters
    query_str = query_str.strip.tr(";'$%&*()<>/@~`+=#?|{}[]", '.')

    # Get the literals and replace them with place holders
    literals = query_str.scan(/".*?"/)
    literals.each {|literal| query_str.gsub!(literal, '?')}
    literals.map! {|query| query[1..-2]}

    # Make all keyworded queries one chunk
    query_str.gsub!(/\:\s*/, ':')

    # All spaces are now delimiters
    query_str.gsub!(/\s+/, ';')

    # Delete all keywords without values
    query_str.gsub!(/\w+\:;/, '')

    # Get all the terms
    terms = query_str.split(';')

    # Fill in all place holders; they are in order of appearance
    count = 0
    terms.each do |term|
      if term.include? '?'
        term.gsub!('?', literals[count])
        count += 1
      end
    end
    return terms
  end

  def find_best_query(query)
    best = ''
    cur_max = 0
    Cruise.column_names.each do |column|
      if column !~ /(14C)|(id)/
        if column == 'Group'
          column = "`#{column}`"
        end
        num_matches = Cruise.count(:all, :conditions => ["#{column} REGEXP '#{query}'"])
        if num_matches > cur_max
          best = column
          cur_max = num_matches
        end
      end
    end
    return best
  end

  def track_coords_in(expocode)
    # Returns an array of track coordinates for given expocode.
    track_coords = Array.new
    if track = Track.find(:first, :conditions => { :ExpoCode => expocode})
      coords = track.Track.split(/\n/)
      coords.each_index do |coord_i|
        if coord_i % 10 == 0
          track_coords << coords[coord_i]
        end
      end
    end
    return track_coords
  end
  
  def chief_scientists_to_links!(pi)
  # Turn the chief scientists into links if we have a contact entries.
    if pi
      # Take Chief Scientist string and extract multiple names
      pi_names = pi.split(/\/|\\|\:/)
      # Substitute name matches for links to the contact's page
      pi_names.each do |name|
        pi.sub!(name, "<a href=\"/search?query=#{name}\">#{name}</a>") if Contact.exists?(:LastName => name)
      end
    end
  end

  def switch_x_y_polygon(polygon)
    rings = polygon.rings
    @points = []
    for ring in rings 
        for coord in ring
          @points << Point.from_x_y(coord.y,coord.x)
        end
    end
    poly = Polygon.from_points([@points])
    return poly
  end

  # Auto selects the correct Google API key when called with the hostname.
  def getGAPIkey(host)
    return case host
      when 'cchdo.ucsd.edu':        'ABQIAAAAZICfw-7ifUWoyrSbSFaNixTec8MiBufSHvQnWG6NDHYU8J6t-xTRqsJkl7OBlM2_ox3MeNhe_0-jXA'
      when 'whpo.ucsd.edu':         'ABQIAAAATXJifusyeTqIXK5-oRfMqRRrtQtAbE2ICKyeJmE150l9FUtvWRQ_qb0gC6W0P4gBV_W3RstdZXEcOw'
      when 'watershed.ucsd.edu':    'ABQIAAAATXJifusyeTqIXK5-oRfMqRRkZzjLi0nUJ4TwOC8xt4Ov2IJhKBQTGSNz9nt4_eT3w1Wv_O1VSaMyBA'
      when 'goship.ucsd.edu:3000':  'ABQIAAAATXJifusyeTqIXK5-oRfMqRSVxuI6xAiiU0y37vRLQcURlSg9FhSh-0iK98GAcbE_yabEYgs-ehj6Xg'
      when 'ghdc.ucsd.edu:3000':    'ABQIAAAATXJifusyeTqIXK5-oRfMqRQbm_T9Aut8KIkQepcdoibG6hz3ZBSwpsEu6JXesbZc0gcOonL9xKdIBA'
    else
        'ABQIAAAAnfs7bKE82qgb3Zc2YyS-oBT2yXp_ZAY8_ufC3CFXhHIE1NvwkxSySz_REpPq-4WZA27OwgbtyR3VcA'
    end
  end
end

def out_of_band(x)
  oob_value = -999
  oob_tolerance = 1
  return (oob_value-oob_tolerance <= x and x <= oob_value+oob_tolerance)
end
