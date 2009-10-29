#!/usr/bin/perl -w
# ajax_gmt.cgi
#  
#  This file interacts returns maps requested for the
# ajax map viewer
#

use DBI;
use CGI qw(:standard *table :cgi-lib);


# Html server 
`rm ./*.ps`;
`rm ./*.gif`;
print header(-type=>"text/xml"),start_html;
%input = Vars();
$new_map = draw_map(\%input);
open($lns,">lines");
print $lns $input{'Lines'};
#foreach $key (keys %input)
#{ print $key,"    ",$input{$key},"   ";}
print "<map_name>$new_map.gif</map_name>";
print end_html;


sub draw_map()
{
   $name = time;
   $hash_ref = shift;
   my %coords = %$hash_ref;
   my @lines = split /,/, $coords{'Lines'};
   
   my $lat = $coords{'Lat'};
   my $lon = $coords{'Lon'};
   ($lat1,$lat2) = split /,/, $lat; 
   ($lon1,$lon2) = split /,/, $lon; 
   $lat1 = -1*int($lat1/2);
   $lat2 = -1*int($lat2/2);
   $lon1 = int($lon1/2);
   $lon2 = int($lon2/2);
   print "Lats $lat1 $lat2 and Lons $lon1 $lon2";
   if(@lines){$state = "open";}
   else      {$state = "closed";}
   if($lat1 < $lat2)
   {$bottom_lat = $lat1; $top_lat = $lat2;}
   else{$bottom_lat = $lat2; $top_lat = $lat1;}
   if($lon1 < $lon2)
   {$bottom_lon = $lon1; $top_lon = $lon2;}
   else{$bottom_lon = $lon2; $top_lon = $lon1;}
   base_map($bottom_lat,$top_lat,$bottom_lon,$top_lon,$coords{'Lines'},$name,$coords{'Map'});
#   if($state eq "open") { draw_lines(\@lines);}
   return($name);
}
   
sub base_map
{

   my $bottom_lat = shift;
   my $top_lat = shift;
   my $bottom_lon = shift;
   my $top_lon = shift;
   $lines = shift;
  # my @lines = @$array_ref;
   $f_name = shift;
   $map_type = shift;
# GMT pscoast
#	-R     west, east, south, and north specify the Region of interest.
#	-B	Sets map boundary annotation and tickmark intervals
#	-W Draw coastlines.
#	-M 
#	-S Select painting or clipping of "wet" areas. Append the shade (0?255), color (r/g/b), 
#		pattern (see ?G), or c for clipping.
#       -D Selects the resolution of the data set to use ((f)ull, (h)igh, (i)ntermediate, (l)ow, and (c)rude).
##	-J     select map projection
#	  mercator	-Jmlon0/lat0/scale lon0 is meridian, lat0 standard parallel
#	  transverse mercator	-Jt
#	  Eckert 4      -JK 


# Eckert 4
#  $gmt_command2 = "pscoast -R-180/180/-90/90 -JKf-160/9i -B60g30/30g15 -K -G180/120/60 -S150/230/255 -W0.25p >| $f_name.ps"; 

if($map_type eq 'Southern')
{
# Lambert
$gmt_command2 = "pscoast -R0/360/-90/90 -JA200/-80/4.5i -B30g30/15g15 -Dc -K -G0/0/0 -S100/180/255 -P >| $f_name.ps";

}
else
{
# Transverse Mercator
#$gmt_command2 = "pscoast -R0/360/-80/80 -JT330/-45/3.5i -B30g15/15g15WSne -Dc -K -G4:black -P > $f_name.ps";

# Mercator
   $gmt_command2 = "pscoast -R$bottom_lon/$top_lon/$bottom_lat/$top_lat -JM10i -B -K -G  >| $f_name.ps";
}
#   $gmt_command2 = "pscoast -R-180/180/-80/80 -JM3i -B -K -G  >| $f_name.ps";
# Cartesian Linear
# $gmt_command2 = "pscoast -R-20/340/-85/85 -Jx0.014id -B60g30f15/30g30f15WSen -K -G180/120/60 -S150/230/255  -W0.25p >| $f_name.ps";

# Orthographic Projection
 #$gmt_command2 = "pscoast -R0/360/-90/90 -JG-75/41/5i -B15g15 -K -G180/120/60 -S150/230/255 -W0.25p -P >| $f_name.ps";

# Azimuthal Equidistant 
 #$gmt_command2 = "pscoast -R-50/310/-90/90 -JE-100/40/4.5i -B15g15 -K -G180/120/60 -S150/230/255 -W0.25p -P >| $f_name.ps";

# Gnomonic 
  #$gmt_command2 = "pscoast -R-100/260/-90/90 -JF120/35/60/4.5i -Bg15  -K -G180/120/60 -S150/230/255 -W0.25p -P >| $f_name.ps";

# Hammer
   #$gmt_command2 = "pscoast -R-200/160/-90/90 -JH-180/4.5i -Bg30/g15   -K -G180/120/60 -S150/230/255 -W0.25p -P >| $f_name.ps";

# Mollweide
  # $gmt_command2 = "pscoast -R0/360/-90/90 -JW0/5i -Bg30/g15   -K -G180/120/60 -S150/230/255 -W0.25p -P >| $f_name.ps";

# Winkel Tripel
#    $gmt_command2 = "pscoast -R0/360/-90/90 -JR10/5i -Bg30/g10 -K -G180/120/60 -S150/230/255 -W0.25p -P >| $f_name.ps";
print $gmt_command2;
`$gmt_command2`;
draw_lines($lines,$f_name,$map_type);
`convert -rotate 90 $f_name.ps -trim +repage  $f_name.gif`;
}

sub draw_lines
{
#First get and open the sum file with location info
$search = shift;
$name = shift;
$map_type = shift;
@searches = split /,/,$search;
foreach my $s (@searches)
{
   $db = DBI->connect('DBI:mysql:metadata','root')
	or die "Couldn't open database";
   $statement = qq{SELECT ExpoCode 
		   FROM cruiseDB
                   WHERE Line regexp '$s'};
   $sh = $db->prepare($statement);
   $sh->execute() or die "couldn't gather ExpoCodes";
   while(@data = $sh->fetchrow_array())
   {
      push @expos,$data[0];
   }
}

foreach $expo (@expos)
{
   $statement = qq{SELECT dir_files,directories
        	FROM fileDB
		WHERE ExpoCode='$expo'};
   $sh = $db->prepare($statement);
   $sh->execute() or die "couldn't gather files";
   while(@data = $sh->fetchrow_array())
   {
      undef @sums;undef @directories;
      @sums =  split /,/,$data[0];
      @directories = split /,/,$data[1];
      undef $found;
      foreach (@sums)
      { if(/\.jpg/){$found = 1;}}
      if($found)
      {  
     # if($#directories eq 0)
     # {
         foreach (@sums)
         { 
            #if($_ !~ /(pr20|p31|ar13)/)
            #{
            if(/na\.txt$/)
            {push @files,$directories[0]."/".$_;}
            #}
         }
         #}
      }
   }
}
$ctr=0;
foreach $file (@files){$ctr++;}


$file_ctr=0;
#Plot the data from the collected files
FILE: foreach $file (@files)
{
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
   #Print coordinate data to a temp file
      if( defined @lat and defined @lon)
      {
         open(OUT,">data");
         for $ctr (0..$#lat)
         {
            print OUT "$lon[$ctr]	$lat[$ctr]\n";
      #print  "$lon[$ctr]	$lat[$ctr]\n";
         }
   #Create map: 
   #   -R = 
         undef $color;
         if($file =~ /\/(ar|pr|sr|ir)\w*\.txt$/){$color = "220/0/0";}
         else{$color = "0/0/220";}
         if($file_ctr == $ctr){$close_map = ""}
         else{$close_map = "-K";}
# 
#  psxy
#	-W Set pen attributes for lines or the outline of symbols.
#       -R xmin, xmax, ymin, and ymax specify the Region of interest.
#	-O Selects Overlay plot mode 
#	-K More PostScript code will be appended later
#	-G 

if($map_type eq 'Southern')
{
# Lambert
   $gmt_command = "psxy ./data -R  -JA -O $close_map -W2p/$color -P  >> $name.ps";
}
else
{
# Transverse Mercator
   #$gmt_command = "psxy ./data -R  -JT330/-45/3.5i -O $close_map -Sc.01 -G$color  >> $search.ps";

# Ekert 4   
         #$gmt_command = "psxy ./data -R -JK  -O $close_map  -Sc.05 -G$color >> $search.ps";
# Mercator
 #        $gmt_command = "psxy ./data -R  -JM10i -O $close_map -W1p/200/100/255  >> new_map.ps";
	$gmt_command = "psxy ./data -R -JM10i -O $close_map -Sc.015 -G$color >> $name.ps";
}
# Cartesian Linear
	#$gmt_command = "psxy ./data -R -Jx -O $close_map -Sc.015 -G$color >> $search.ps";

# Orthographic
	#$gmt_command = "psxy ./data -R -JG -O $close_map -Sc.05 -G$color -P >> $search.ps";

# Azimuthal Equidistant
#	$gmt_command = "psxy ./data -R -JE -O $close_map -Sc.02 -G$color -P >> $search.ps";

# Gnomonic
       #$gmt_command = "psxy ./data -R -JF -O $close_map -Sc.04 -G$color -P >> $search.ps";

# Hammer
	#$gmt_command = "psxy ./data -R -JH -O $close_map -Sc.04 -G$color -P >> $search.ps";

# Mollweide
	#$gmt_command = "psxy ./data -R -JW -O $close_map -Sc.03 -G$color -P >> $search.ps";

# Winkel Tripel
#	$gmt_command = "psxy ./data -R -JR -O $close_map -Sc.02 -G$color -P >> $search.ps";

      `$gmt_command`;
      close OUT;
      }
   close $fh;
   `rm ./data`;
   }
}
}   



