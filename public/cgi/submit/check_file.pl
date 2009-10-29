#!/usr/bin/perl
#
#   check_file.pl
#
# This script checks the file extension and
#data structure of a given file.  Recognized
#file types are:
#            WOCE- BTL,CTD,SUM
#            Exchange- CTD,BTL
#            NetCDF- CTD,BTL


%sub_check = (
	'expocode'   => \&check_woce,
	'ctd'	     => \&check_exchange,
        'bottle'     => \&check_exchange,
        'cdf'        => \&check_cdf,
        'r/v'        => \&check_woce);
	
sub check_file
{
   $file = shift;
   ($dev,$ino,$mode,$nlink,$uid,$gid,$rdev,$size,
       $atime,$mtime,$ctime,$blksize,$blocks)
           = stat($file);
   my $file_guess = $file =~ /gz/	?'Zipped file'
		   :$file =~ /su.txt/   ?'Woce Sum file'
                   :$file =~ /hy1.csv/  ?'Exchange Bottle'
                   :$file =~ /hy.txt/   ?'Woce Bottle'
                   :$file =~ /ct1.csv/  ?'Exchange CTD'
                   :$file =~ /.ctd/     ?'Woce CTD'
                   :                     'Undetermined';
   #First we open the file and check the first
   #line.  Exchange files always begin with either
   #BOTTLE or CTD.
   open $fh,'<',$file or die "Couldn't open file";
   $line = <$fh>;
   @line = split /[\s+,]/, $line; 
   foreach $l (@line)
   {
      @t = split //,$l;
      if($#t ne -1)
      { push @header,$l;}
   }
  ## Check the first word, and
  # call the appropriate subroutine
   if($sub_check{lc($header[0])})
   { $sub_check{lc($header[0])}->(lc($header[0]),\@header);}
   else
   { check_woce();}
   #%data_hash = get_data($file_type,$fh);
   close $fh;
   #print h1(@parameters);
   return ($file_type,$code,\@parameters);
}
1;

sub get_data
{
}
sub check_unidentified
{
}
sub check_exchange
{
   $file_t = shift;
   #this line sets the input record seperator
   #variable($/) to be undefined, allowing the entire
   #file to be input as one line.
   $code = do { local $/; <$fh> };
   seek($fh,0,0);
   if($code =~ /END_DATA/)
   {
      $file_type = "Exchange ".$file_t;
      $line = <$fh>;
      $line = <$fh>;
      while($line =~ /#/)
      {$line = <$fh>;}
      if($file_t =~ "bottle") 
      {
#print h1($line),br;
         if(lc($line) =~ "expocode")
         {
            @temp_parameters = split /,/,$line; 
         }
         $line=();
         for(1..8)
         {
            $line = <$fh>;
         }
         @line = split /,\s+/, $line;
         $code = $line[0];
#print h1(@line),br,h2($line[0]);
      }
      if($file_t eq "ctd")
      {
         while(lc($line) !~ /expocode/)
         {$line = <$fh>;}
         @line = split /=/,$line;
         $code = $line[1];
         while(lc($line) !~ /ctdprd/ and lc($line) !~/,/)
         {$line = <$fh>;}
         @temp_parameters = split /,/,$line;
      }
   } 
   foreach $param (@temp_parameters)
   {
      if( $param =~ /[A-Z]/)
      {  push @parameters, $param;}
   } 
}
sub check_cdf
{
}
sub check_woce
{
  $clue = shift;
  $cur_line = shift;
#print b("check woce",$clue,$cur_line);
  @cur_line = @$cur_line;
   if($clue eq "expocode")
   {
      $code = $cur_line[1];
      CHECK:
      for my $count (1..3)
      {
         $line = <$fh>;
         if(  $line !~ /STNNBR/
          and $line =~ /CTD/
          and $line !~ /,/)
         {
            $file_type = "Woce CTD";
            last CHECK;
         }
         if($line =~ /(STNNBR)/
          and $line =~/(CASTNO)/
          and $line =~/(SAMPNO)/
          and $line =~/(BTLNBR)/
          and $line !~/,/)
         {  
            $file_type = "Woce bottle";
            @temp_parameters = split /\s+/, $line;
            last CHECK;
         }
      }
   }
   else
   {
      CHECK:
      for my $count (1..3)
      {
         $line = <$fh>;
#print h1($line);
         if($line =~ /(STNNBR)/
          and $line =~/(EXPOCODE)/
          and $line =~/(CASTNO)/
          and $line =~/(LAT)/
          and $line =~/(LON)/
          and $line !~/,/)
         {  
            $file_type = "Woce SUM";
            @temp_parameters = split /\s+/, $line;
            $line = <$fh>;
            $line = <$fh>;
            $line = <$fh>;
            @vals = split /\s+/, $line;
            $code = $vals[0];
            last CHECK;
         }
      }
   }
   foreach $param (@temp_parameters)
   {
      if( $param =~ /[A-Z]/)
      {  push @parameters, $param;}
   } 
    #$file_type = "Woce";
}
