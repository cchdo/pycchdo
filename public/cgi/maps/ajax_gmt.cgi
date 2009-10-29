#!/usr/bin/perl -w
# ajax_gmt.cgi
#  
#  This file interacts returns maps requested for the
# ajax map viewer
#

use DBI;
use CGI qw(:standard *table :cgi-lib);
require "./hydro_file_tools.pl";

%east_pacific_area = (
    'lat' => -4, 'lon' => -155, 'zoom' => 2);
%west_pacific_area = (
    'lat' => 10, 'lon' => -120, 'zoom' => 2);
%south_west_pacific_area = (
    'lat' => -20, 'lon' => -120, 'zoom' => 3);
%north_atlantic_area = (
    'lat' => 45, 'lon' => 10, 'zoom' => 3);
%central_atlantic_area = (
    'lat' => 10, 'lon' => 10, 'zoom' => 3);
%south_atlantic_area = (
    'lat' => -25, 'lon' => 10, 'zoom' => 3);
%indian_area = (
    'lat' => -34, 'lon' => 80, 'zoom' => 2);
%southern_area = (
    'lat' => -80, 'lon' => 10, 'zoom' => 2);
%basins = (
      'East Pacific' => \%east_pacific_area,
      'West Pacific' => \%west_pacific_area,
      'South West Pacific' => \%south_west_pacific_area,
      'North Atlantic' => \%north_atlantic_area,
      'Central Atlantic' => \%central_atlantic_area,
      'South Atlantic' => \%south_atlantic_area,
      'Indian' => \%indian_area,
      #'Southern' => \%southern_west_area,
      'Southern' => \%southern_area);

$db_user = 'jfields';
$passwd = 'hydr0d@t@';
open(ERROR_FILE,">./errors");
# Html server 
print header,start_html;
#print <<HEADER;
#<html xmlns="http://www.w3.org/1999/xhtml">
#<HEAD>
#<title>Untitled Document</title>
#</HEAD>
#<BODY>
#HEADER
%input = Vars();
$coord_ref = print_list($input{'Basin'});
print "<Which>$input{'Basin'}</Which>";
$ref = $basins{$input{'Basin'}};
%hash = %$ref;
$lat = $hash{'lat'};
$lon = $hash{'lon'};
$zoom = $hash{'zoom'};
print "<basinlat>$lat</basinlat><basinlon>$lon</basinlon><zoom>$zoom</zoom>";
%coordinates = %$coord_ref;
#foreach $line (keys %coordinates)
print "<basin>\n";
foreach $line (keys %coordinates)
{  
   #my $info_ref = $coordinates{$line};
   my %info_hash = %{$coordinates{$line}};
   #my $lt_ref = $coordinates{$line}{'Lat'};
   #my $ln_ref = $info_hash{'Lon'};
   my @ln = @{$info_hash{'Lon'}};
   my @lt = @{$info_hash{'Lat'}};
  # my $expo = $info_hash{'ExpoCode'};
   my $expo = $info_hash{'ExpoCode'};
   if($expo and $line and @ln and @lt)
   {
 #     print "<$line><expo>$expo</expo>\n";
      print "<line>\n";
      if($#lt > 0)
      {
         print "\t<coordinates>";
         #print "<line_no>$line</line_no>\n";
         for (1..$#lt)
         {
	        # $line =~ s/_//g;
            print "<cpair><expo>$expo</expo><lineno>$line</lineno><lat>$lt[$_]</lat><lon>$ln[$_]</lon></cpair>";
         }
         print "</coordinates>";
      }
      print "\n</line>\n";
   }
}
print "</basin>";
print end_html;
close ERROR_FILE;

sub get_coords
{
#First get and open the sum file with location info
   $search = shift;
   $db = DBI->connect('DBI:mysql:cchdo',$db_user,$passwd)
	or die "Couldn't open database";
   $statement = qq{SELECT ExpoCode 
                   FROM cruises
                   WHERE Line='$search' LIMIT 1};
   $sh = $db->prepare($statement);
   $sh->execute() or die "couldn't gather ExpoCodes";
   while(@data = $sh->fetchrow_array())
   {
       $expo = $data[0];
   }


   $statement = qq{SELECT ExpoCode,Files,FileName
                      FROM documents
		      WHERE ExpoCode regexp '$expocode' and FileType = 'Directory'};

   my $sh = $db->prepare($statement);
   $sh->execute() or die "couldn't retrieve data from dirDB";
   $ctr = 0;
   while($ref = $sh->fetchrow_hashref())
   {
      $path = $ref->{'FileName'};
      $data_hash{$expocode}{'Files'} .= $ref->{'Files'}.",";
      $ctr++;
   }
   # Drop extra comma
   ($trash,$path) = split /data/,$path;
   $data_hash{$expocode}{'Files'} = substr($data_hash{$expocode}{'Files'},0,-1); 
   $data_hash{$expocode}{'Files'} =~ s/\*//g;
   @dir_files = split /\s+/,$data_hash{$expocode}{'Files'};
   foreach (@dir_files)
   {
      if(/na\.txt$/)
      {$file = $path."/".$_;}
   }
         
   #
   #          
   $file_ctr=0;
#Plot the data from the collected files

   if(open($fh,$file)) 
   {
      $file_ctr++;
      undef @lat_array;
      undef @lon_array; 
      #Collect coordinates into @lat and @lon
      my $lat_ctr = 0;
      @file = <$fh>;
      for($x = 0; $x<$#file; $x+=($#file/5))
      {
         $_ = $file[$x];
         @ln_data = split /\s+/;
         if(defined @ln_data)
         {
            $count = 0;
            $lat = $ln_data[2];
            $lon = $ln_data[1];
            #Push every tenth entry, Only need to represent lines,
            #Don't need every station.
            #if($lat_ctr % ($#file/5) eq 0)
            #{
               push @lat_array,$lat;
               push @lon_array,$lon;
            #}
         }
      }
   $return_hash{"file"} = $file;
   }
   else
   {$f = "no file $file"; @lat_array; @lon_array; $return_hash{"file"} = $f;}
   $return_hash{"Lat"} = \@lat_array;
   $return_hash{"Lon"} = \@lon_array;
   if($bound_ref)
   {$return_hash{"bounds"} = $bound_ref;}
   return \%return_hash;
}
   
sub print_list
{
   my $search = shift;
   my %lines;
   my $db = DBI->connect('DBI:mysql:cchdo',$db_user,$passwd)
      or die "couldn't connect to documents";
   $statement = "SELECT distinct  cruises.Line , internal.File,internal.ExpoCode
                 FROM internal,cruises
                 WHERE internal.Basin = '$search' and cruises.ExpoCode = internal.ExpoCode
                 ORDER BY cruises.Line";
print ERROR_FILE $statement,"\n";
   $sh = $db->prepare($statement);
   $sh->execute() or die "couldn't gather sum files";

   while(@data = $sh->fetchrow_array())
   {
      if($data[0]=~ /[A-Z]/ and $data[0] !~ /original/)
      {
print ERROR_FILE "$data[0] $data[1] $data[2]  \n";
         push @{$basin_files},$data[1];
         push @{$basin_Lines},$data[0];
         push @{$basin_expos},$data[2];
      }
   }
   @current = @{$basin_files};
   @cur_lines = @{$basin_Lines};
   @cur_expos = @{$basin_expos};

   $file_ctr=0;
   $color_ctr = 0;
   #Plot the data from the collected files
   FILE: for (1..$#current)
   {
      my $file = $current[$_];
      my $line = $cur_lines[$_];
      my $cur_expo = $cur_expos[$_];
      open($fh,$file) or next FILE;
      $file_ctr++;
      undef @lat;
      undef @lon;
      undef %line_info;
   #Collect coordinates into @lat and @lon
      @file = <$fh>;
      for($x = 0; $x <=$#file; $x+=($#file/10))
      {
         $_ = $file[$x];
    if(/([0-9A-Za-z_]+).*(?:(?:[A-Z][A-Z]\s+(\d+)\s+(\d+)\.(\d+)\s+([NS]))\s+(?:(\d+)\s+(\d+)\.(\d+)\s+([EW])))/xims)
      {
#         $expo = $1;
         $formatted_lat = $hemi_val{$5}.$2.".".$3.$4;
         push @lat, $formatted_lat;
         $formatted_lon = $hemi_val{$9}.$6.".".$7.$8;
         push @lon, $formatted_lon;
      }
      }
      $line_info{'ExpoCode'} = $cur_expo;
      @{$line_info{'Lat'}} = @lat;
      @{$line_info{'Lon'}} = @lon;
      %{$return_hash{$line}} = %line_info;

   }
   return \%return_hash;
} 
