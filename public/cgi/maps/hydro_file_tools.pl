#!/usr/bin/perl -w
#
#
#

%known_file_types = ( 
        'hy.txt' => 'Woce Bottle',
        'su.txt' => 'Woce Sum',
	'ct.zip' => 'Woce CTD (Zipped)',
        'sum'    => 'Sum File',
        'ctd'    => 'CTD File',
	'ct1.zip' =>'Exchange CTD (Zipped)',
	'ct1.csv' =>'Exchange CTD',
	'hy1.zip' =>'Exchange Bottle (Zipped)',
	'hy1.csv' =>'Exchange Bottle',
	'ctd.zip'  =>'NetCDF CTD',
	'hyd.zip'  =>'NetCDF Bottle',
	'do.txt'  =>'Documentation',
	'do.pdf' =>'PDF Documentation',
	'xml'     =>'Directory Description',
	'na.txt'  =>'Coord info',
	'sea'	  =>'SEA file',
	'detail.html' => 'Data History HTML',
	'person.html' => 'Person HTML',
	'type.html' => 'Type HTML',
	'datahist.html' => 'Data History HTML',
	'trk.jpg' => 'Small Plot',
	'trk.gif' => 'Large Plot',
	'.gof'	  => 'JGOFS File',
	'.wct'    => 'WCT CTD File',
	'index.html' => 'Index HTML File',
	'index_OLD.html' => 'Old Index HTML File',
	'.gmt'	    => 'GMT info File',
	'hyd.txt'   => 'Exchange Bottle',
	'.ecp'   => 'French data file',
	'.nav'   => 'Coordinates?',
	'.asc'   => 'Encrypted file',
	'.ps'   => 'Postscript file',
	'.mat'   => 'Matlab file',

);

%hemi_val = ( 'N' => '','S'=>'-','E'=>'','W'=>'-',
              'n' => '','s'=>'-','e'=>'','w'=>'-');
#Define Basin areas
%pacific = ( 'north' => 64, 'south'=>-60, 'west'=>120, 'east'=>-85);
%east_pacific = ( 'north' => 70, 'south'=>-70, 'west'=>165, 'east'=>-85);
%west_pacific = ( 'north' => 70, 'south'=>-10, 'west'=>115, 'east'=>175);
%south_west_pacific = ( 'north' => 0, 'south'=>-70, 'west'=>115, 'east'=>175);
%atlantic = ( 'north' => 75, 'south'=>-60, 'west'=>-80, 'east'=>15);
%north_atlantic = ( 'north' => 75, 'south'=>35, 'west'=>-80, 'east'=>15);
%central_atlantic = ( 'north' => 45, 'south'=>0, 'west'=>-80, 'east'=>15);
%south_atlantic = ( 'north' => 5, 'south'=>-60, 'west'=>-80, 'east'=>15);
%indian = ( 'north' => 20, 'south'=>-65, 'west'=>35, 'east'=>130);
%southern_west = ( 'north' => -40, 'south'=>-90, 'west'=>-180, 'east'=>0);
%southern_east = ( 'north' => -40, 'south'=>-90, 'west'=>0, 'east'=>180);

#Define Basin areas
%view_pacific = ( 'north' => 74, 'south'=>-70, 'west'=>110, 'east'=>-75);
%view_east_pacific = ( 'north' => 80, 'south'=>-80, 'west'=>120, 'east'=>-55);
%view_west_pacific = ( 'north' => 80, 'south'=>-20, 'west'=>105, 'east'=>165);
%view_south_west_pacific = ( 'north' => 10, 'south'=>-80, 'west'=>105, 'east'=>180);
%view_atlantic = ( 'north' => 85, 'south'=>-70, 'west'=>-90, 'east'=>25);
%view_north_atlantic = ( 'north' => 85, 'south'=>25, 'west'=>-90, 'east'=>25);
%view_central_atlantic = ( 'north' => 55, 'south'=>-10, 'west'=>-90, 'east'=>25);
%view_south_atlantic = ( 'north' => 15, 'south'=>-70, 'west'=>-90, 'east'=>25);
%view_indian = ( 'north' => 30, 'south'=>-75, 'west'=>25, 'east'=>135);
%view_southern_west = ( 'north' => -50, 'south'=>-90, 'west'=>-180, 'east'=>0);
%view_southern_east = ( 'north' => -50, 'south'=>-90, 'west'=>0, 'east'=>180);

%basins = (
      'East Pacific' => \%east_pacific,
      'West Pacific' => \%west_pacific,
      'South West Pacific' => \%south_west_pacific,
      'North Atlantic' => \%north_atlantic,
      'Central Atlantic' => \%central_atlantic,
      'South Atlantic' => \%south_atlantic,
      'Indian' => \%indian,
      'Southern' => \%southern_west,
      'Southern' => \%southern_east);

%view_basins =(
      'East Pacific' => \%view_east_pacific,
      'West Pacific' => \%view_west_pacific,
      'South West Pacific' => \%view_south_west_pacific,
      'North Atlantic' => \%view_north_atlantic,
      'Central Atlantic' => \%view_central_atlantic,
      'South Atlantic' => \%view_south_atlantic,
      'Indian' => \%view_indian,
      'Southern' => \%view_southern_west,
      'Southern' => \%view_southern_east);
sub parse_woce_sum
{
   my $file = shift;
   my @lat;
   my @lon;
   undef @expocodes;
   undef @tokens;
   undef @token;
   undef @lines;
   undef %return_hash;
   undef @lat;
   undef @lon;
   my @token;
   my @lines;
   open(BTL_FILE,$file)
      or die "couldn't open sum file";
   for (1..3)
   {@token = split /\s/,<BTL_FILE>;}
   my $code = "";
  # $distinct = 1;
   while(<BTL_FILE>) #Read each line
   {
      @token = split /\s+/;#Split by whitespace
      #Collect distinct expocodes into an array
      if($token[0])
      {
	 $token[0] =~ s/\//_/;;
         if($token[0] =~ /\w/ and $token[0] ne $code)
         {$code = $token[0]; push @expocodes,$code;}
      } 
      for $x (1..3)
      {
         if($token[$x] and $token[$x] =~  /^[apsi(ar)(pr)(ir)(sr)]{1,3}\d{1,2}[a-z]{0,1}$/i)
         {
            $match =1;
            foreach $l (@lines)
            {
               if($token[$x] eq $l)
               { undef $match;}
            }
            if($#lines==-1){push @lines,$token[$x];undef $match;}
            if($match and $#lines != -1){push @lines,$token[$x];}
         }
      }
#if($file =~ /pr33/){print $file,"\n\n";}
      #Get coordinates
      #if(/([0-9A-Za-z]{1,10}_?[A-Z0-9a-z]{0,3}).*(?:(?:[A-Z][A-Z]\s(\d+)\s+(\d+)\.(\d+)\s+([NS]))\s+(?:(\d+)\s+(\d+)\.(\d+)\s+([EW])))/xims)
      if(/([0-9A-Za-z_]+).*(?:(?:[A-Z][A-Z]\s+(\d+)\s+(\d+)\.(\d+)\s+([NS]))\s+(?:(\d+)\s+(\d+)\.(\d+)\s+([EW])))/xims)
      {
#print "1:$1 2:$2 3:$3 4:$4 5:$5 6:$6 7:$7 8:$8 9:$9 \n";
         #($degree,$minute,$second,$hemi) = split /[\s]/xims,$1;
         $expo = $1;
         $formatted_lat = $hemi_val{$5}.$2.".".$3.$4;
         push @lat, $formatted_lat;
         #print h2( split /[\.\s+]/,$2);
         #($degree,$minute,$second,$hemi) = split /[\W]/xims,$2;
         $formatted_lon = $hemi_val{$9}.$6.".".$7.$8;
         push @lon, $formatted_lon;
      }
   }
   if($#lines == 0){$return_hash{'Line'} = $lines[0];}
   elsif($#lines == -1){$return_hash{'Line'} = "NULL";}
   else { foreach (@lines){$return_hash{'Line'}.="$_,";}chop $return_hash{'Line'};}
   if($#expocodes eq 0) {$return_hash{'ExpoCode'} = $expocodes[0];}
   elsif($#expocodes == -1){$return_hash{'ExpoCode'} = "NULL";}
   else {foreach (@expocodes){$return_hash{'ExpoCode'}.="$_,";}chop $return_hash{'ExpoCode'};}
   if(($#lat > 0) and ($#lat eq $#lon))
   {
      $return_hash{'Lat_array'} = \@lat;
      $return_hash{'Lon_array'} = \@lon;
      $return_hash{'expo'} = $expo;
   }
   close BTL_FILE;
   return(\%return_hash);
}

sub parse_woce_bottle
{
   #Retrieve the Line, ExpoCode, and file ID from the 
   #bottle file, return a hash
   
   my $file = shift;
   undef @expocodes;
   undef $ec_return;
   undef $l_return;
   my %return_hash;
   #my @line;
   #Open the passed file
   open(BTL_FILE,$file)
     or die "couldn't open file";
   #Read the first line, which contains most of the info
   $header = <BTL_FILE>;
   @line = split(/[\s+]+/,$header);
   
   $collect_expocodes = 0; 
   $collect_lines = 0;
   undef @lines;
   undef @expocodes;
   if($header =~ 
     /^\s*(expocode\s+
	(\d\w+_?\/?\w{0,3}(,?\s{0,3}_?\/?\d*\w*,?\s{0,3}_?\/?\d*\w*,?\s{0,3}_?\/?\d*\w*)))
	\s*\(?\w*\)?\s*   .*
	(whp-id\s*(WOCE)?\s*
	(\w*\/?_?(-PREWOCE)?([,\/]\s{0,3}\w*)?([,\/]\s{0,3}\w*)?([,\/]\s{0,3}\w*)?))\s+

     /ix)
   {
      @expo_tokens = split /[,\s]+/,$2;
      foreach (@expo_tokens){push @expocodes,$_;}
      if($6 !~ /CRUISE/i)
      { 
         @line_tokens = split /[,\s]+/,$6;
	 foreach (@line_tokens){push @lines,$_;}
      }
      else{push @lines,'NULL';}
   }
   else{print "Couldn't get info from $header   $file\n";}
      $expocodes[0] =~ s/\//_/;
   if($#expocodes >0)
   {
      for $count (1..$#expocodes)
      {
         if(length($expocodes[$count]) < 4)
         {
            ($base,$trash) = split /[_\/]/,$expocodes[0];
	    print "Base $base\n";
	    $expocodes[$count] =~ s/_//g;
            $expocodes[$count] = $base."_".$expocodes[$count];
         }
      }
   } 
   #Seperate lines
   foreach (@lines)
   { 
      if( /[,\/][a-z]/i)
      { 
         @extra_lines = split /[,\/]/,$_;
         $lines[0] = $extra_lines[0];
         for $count(1..$#extra_lines)
         {
            push @lines,$extra_lines[$count];
         }
      }
   }  
   foreach (@lines) { s/,//;if(/^([a-z]{1,2})([0-9][a-z]?)$/i){$_ = $1."0".$2;}}

   close BTL_FILE;
   
   undef $ln_return;
   if( $#expocodes == 0){$ec_return = $expocodes[0];}
   else{ foreach $ec (@expocodes){$ec_return.="$ec,";} if($ec_return){chop $ec_return;}else{$ec_return="NULL";}}
   $return_hash{'ExpoCode'} = $ec_return;
   if( $#lines == 0){$ln_return = $lines[0];}
   else{ foreach $ln (@lines){$ln_return.="$ln,";} if($ln_return){chop $ln_return;}else{$ln_return="NULL";}}
   $return_hash{'Line'} = $ln_return;
   #print "returning $return_hash{'ExpoCode'} and $return_hash{'Line'}\n";
   return (\%return_hash);
}


sub parse_exchange_bot
{
   my $file = shift;
   open($exchange_bot_fh,$file);
   while(<$exchange_bot_fh>)
   {
      @line = split /,/;
      if($line[0] =~ /^\s*[0-9]+\w+[0-9]+/)
      {
         $expo = $line[0];
         if($#expos == -1){ push @expos,$expo;}
         elsif($expo ne $expos[$#expos])
         {push @expos,$expo;}
      }
   }
   return(\@expos);
}

sub parse_exchange_ctd
{


}
sub parse_xml
{
   open($xml_fh,$_);
   $_ = do { local $/; <$xml_fh> };
#print $_,"\n";
#   while(<$xml_fh>)
#   {
      if(/\s* #Whitespace
         (<expocode>) \s* 
         (\d+\w+\d) \s*  # Our expocode
         (<\/expocode>) \s*
        /ix)
      {
         $xml_hash{'ExpoCode'}= $2;
      }
      if(/\s* #Whitespace
         (<woce_line_num>) \s* 
         (.*) \s*  # Our line
         (<\/woce_line_num>) \s*
        /ix)
      {
         my $line = $2;
         if($line =~ /\w/i){ $xml_hash{'Line'} = $line;}
         else{$xml_hash{'Line'} = 'NULL';}
      }
      if(/\s* #Whitespace
         (<ship>) \s* 
         (\w+) \s*  # vessel 
         (<\/ship>) \s*
        /ix)
      {
         $xml_hash{'ship'} = $2;
      }
      if(/\s* #Whitespace
         (<country>) \s* 
         (\w+) \s*  # 
         (<\/country>)
        /ix)
      {
         $xml_hash{'country'} = $2;
      }
      if(/\s* #Whitespace
         (<date>) \s* 
         (\d+-\d+) \s*  # Our line
         (<\/date>) \s*
        /ix)
      {
  #       $xml_hash{'Date'} = $2;
      }
      if(/(<woce>).*(<sum\s*href)[=\s]*"([\w_\.]*)".*(<\/sum>)/mixs)
      {
         $xml_hash{'woce_sum'} = $3;
      }
      if(/(<woce>).*(<bot\s*href)[=\s]*"([\w_\.]*)".*(<\/bot>)/mixs)
      {
         $xml_hash{'woce_bot'} = $3;
      }
      if(/(<woce>).*(<ctd\s*href)[=\s]*"([\w_\.]*)".*(<\/ctd>)/mixs)
      {
         $xml_hash{'woce_ctd'} = $3;
      }
      if(/(<exchange>).*(<bot\s*href)[=\s]*"([\w_\.]*)".*(<\/bot>)/mixs)
      {
         $xml_hash{'exchange_bot'} = $3;
      }
      if(/(<exchange>).*(<ctd\s*href)[=\s]*"([\w_\.]*)".*(<\/ctd>)/mixs)
      {
         $xml_hash{'exchange_ctd'} = $3;
      }
      if(/(<netcdf>).*(<bot\s*href)[=\s]*"([\w_\.]*)".*(<\/bot>)/mixs)
      {
         $xml_hash{'netcdf_bot'} = $3;
      }
      if(/(<netcdf>).*(<ctd\s*href)[=\s]*"([\w_\.]*)".*(<\/ctd>)/mixs)
      {
         $xml_hash{'netcdf_ctd'} = $3;
      }
      if(/(<documentation>).*(<text\s*href)[=\s]*"([\w_\.]*)".*(<\/text>)/mixs)
      {
         $xml_hash{'txt_doc'} = $3;
      }
      if(/(<documentation>).*(<pdf\s*href)[=\s]*"([\w_\.]*)".*(<\/pdf>)/mixs)
      {
         $xml_hash{'pdf_doc'} = $3;
      }
#   }
   close $xml_fh;
   return \%xml_hash;
}

sub parse_na
{
   my $file = shift;
   if($file !~ /test_ana.txt/)
   {
      open($fh,$file) or next FILE;
      $file_ctr++;
      undef @lat;
      undef @lon;
   #Collect coordinates into @lat and @lon
      while (<$fh>)
      {
         @ln_data = split /\s+/;
         if(defined @ln_data)
         {
            $count = 0;
            $lat = $ln_data[2];
            $lon = $ln_data[1];
            push @lat,$lat;
            push @lon,$lon;
         }
      }
      if(($#lat > 0) and ($#lat eq $#lon))
      {
         $return_hash{'Lat_array'} = \@lat;
         $return_hash{'Lon_array'} = \@lon;
      }
   }
   close $fh;
   return(\%return_hash);
}

sub get_bounds
{
   my $file = shift;
   my $hash_ref = $file =~ /su.txt$/? parse_woce_sum($file):
               $file =~ /na.txt$/? parse_na($file): 0;
   my %hash = %$hash_ref;
   my $lat_ref = $hash{'Lat_array'};
   my $lon_ref = $hash{'Lon_array'};
   my @lat = @$lat_ref;
   my @lon = @$lon_ref;
   if($#lat == $#lon and $lat[$#lat] =~/\d+/)
   {
   my $min_lat = 10000;
   my $min_lon = 10000;
   my $max_lat = -10000;
   my $max_lon = -10000;
   my $current_basin;
#print "$file\n";
   my %basin_ctr;
#   undef %basin_ctr;
   foreach (keys %basins){$basin_ctr{$_} = 0;}
#   foreach (keys %basins){print "RESET:::$_ : $basin_ctr{$_}\n";}
   for (1..$#lat)
   {
#print "Lat $lat[$_]  Lon $lon[$_]\n";
      $index = $_;
      if($lat[$_] > $max_lat){$max_lat = $lat[$_];} 
      if($lat[$_] < $min_lat){$min_lat = $lat[$_];} 
      if($lon[$_] > $max_lon){$max_lon = $lon[$_];} 
      if($lon[$_] < $min_lon){$min_lon = $lon[$_];} 
      foreach (keys %basins)
      { 
         $ref = $basins{$_};
         %current_basin = %$ref;
#if(/North Atlantic/)
#{print "$current_basin{'north'}--$current_basin{'south'} $current_basin{'west'}--$current_basin{'east'}\n
#	Lat:$lat[$index]  Lon:$lon[$index]  $basin_ctr{$_} \n$file\n\n";}
         if( ($lat[$index] < $current_basin{'north'}) and ($lat[$index] > $current_basin{'south'}))
         { 
            if( ($current_basin{'west'} >= 0) and ($current_basin{'east'} <= 0))
            {
               if(($lon[$index] >= $current_basin{'west'} and $lon[$index] <= 180)
                 or ($lon[$index] >= -180 and $lon[$index] <= $current_basin{'east'}))
               { $basin_ctr{$_}++;}
            }
            elsif( ($current_basin{'west'} <= 0) and ($current_basin{'east'} >= 0))
            {
               if(($lon[$index] >= $current_basin{'west'} and $lon[$index] <= 0)
                or($lon[$index] <= $current_basin{'east'} and $lon[$index] >= 0))
               { $basin_ctr{$_}++;}
            }
            else
            {
               if($lon[$index] >= $current_basin{'west'} and $lon[$index] <= $current_basin{'east'})
               {$basin_ctr{$_}++;}
            }
         }
      }
   }
#print $out_file "$file \t";
#foreach (keys %basins){print $out_file "$_ : $basin_ctr{$_}\t";}
#print $out_file "\n";
   if(($max_lon > 175) and ($min_lon <-175))
   {
      $temp = $min_lon; 
      $min_lon = $max_lon;
      $max_lon = $temp;
      for (1..$#lat)
      {
         if(($lon[$_] < $min_lon) and ($lon[$_] >0)){$min_lon =$lon[$_];}
         if(($lon[$_] > $max_lon) and ($lon[$_] < 0)){$max_lon =$lon[$_];}
      }
   }
   $basin_max = 0;
$temp_ctr = 0;
   foreach (keys %basin_ctr)
   {
      if($basin_ctr{$_} > $basin_max)
      { 
         $basin_max = $basin_ctr{$_};
         $bounds{'basin'} = $_;
         $bounds{'containment'} = $basin_ctr{$_};
      }
      $temp_ctr++;
   } 
    $bounds{'north'} = $max_lat;
    $bounds{'south'} = $min_lat;
    $bounds{'west'} = $min_lon;
    $bounds{'east'} = $max_lon;
    $bounds{'expo'} = $hash{'expo'};
   return (\%bounds);
   }
}

sub get_basin
{
   my $file = shift;
   my $bounds;
   $bounds = get_bounds($file);
   if($bounds)
   {
   my %bounds = %$bounds;
   my $basin = $bounds{'basin'};
   $current_basin_ref = $basins{$basin};
   my %current_basin = %$current_basin_ref;
   $bounds{'basin_north'} = $current_basin{'north'};
   $bounds{'basin_south'} = $current_basin{'south'};
   $bounds{'basin_east'} = $current_basin{'east'};
   $bounds{'basin_west'} = $current_basin{'west'};
   return(\%bounds);
   }
}
1;
