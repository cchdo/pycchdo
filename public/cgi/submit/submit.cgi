#!/usr/bin/perl
#   submit.cgi
#
# This form handles the uploading of hydrographic data. 
#

use CGI qw(:standard :cgi-lib);
use CGI qw(*table);
use CGI::Pretty;
use CGI::Carp;
use DBI;
require "./check_file.pl";
require "./tag.pl";

#File size limits (in bytes)
$min_size = 100;
$max_size = 50000000;#50M
$file_dir = "/var/www/hydro/cchdo/public/cgi/submit/incoming";
$base_url = "http://cchdo.ucsd.edu";
$error_file = "/var/www/hydro/cchdo/public/cgi/submit/error_file.txt";

$q = new CGI;

#First we print a preliminary form
print header,
 start_html(-title=>"Submit Hydrography Data",-style=>{-src=>"$base_url/style.css"});
	print <<HTML;
	<html xmlns="http://www.w3.org/1999/xhtml">
	<head>
	<title>CCHDO | CLIVAR & Carbon Hydrographic Data Office</title>
	<script language="JavaScript1.2" type="text/javascript" src="http://cchdo.ucsd.edu/javascripts/application.js"></script>
	<style type="text/css" media="screen">
		\@import url("http://cchdo.ucsd.edu/stylesheets/main.css");
	</style>
	</head>
	<body bgcolor="#ffffff" topmargin="0" leftmargin="0" onload="load()" onunload="GUnload()">
	<div id="Body_Container">
	<table border="0" cellpadding="0" cellspacing="0" width="750" align="center">
	  <tr>
	   <td colspan="6"><a href="http://cchdo.ucsd.edu/index.html">
		<img alt="CCHDO Home" src="http://cchdo.ucsd.edu/images/row1_col1.jpg" width="750" height="137" border="0"></td>
	  </tr>


	<!-- JavaScript Menu goes here -->
	  <tr>
	   <td><a href="http://cchdo.ucsd.edu/index.html" onmouseover="ShowMenu('Home_div', 'Home',11,31,'r2_c1');"><img name="r2_c1" src="http://cchdo.ucsd.edu/images/row2_col1.jpg" width="154" height="31" border="0" id="r2_c1" alt="" /></a></td>
	   <td><a  onmouseover="ShowMenu('Data_By_Ocean_div', 'Data_By_Ocean',-39,31,'r2_c3');"><img name="r2_c3" src="http://cchdo.ucsd.edu/images/row2_col3.jpg" width="128" height="31" border="0" id="r2_c3" alt="" /></a></td>
	   <td><a href="javascript:;"  onmouseover="ShowMenu('Search_Data_div', 'Search_Data',-64,31,'r2_c4');"><img name="r2_c4" src="http://cchdo.ucsd.edu/images/row2_col4.jpg" width="115" height="31" border="0" id="r2_c4" alt="" /></a></td>
	   <td><a href="http://cchdo.ucsd.edu/submit" onmouseover="ShowMenu('Submit_div', 'Submit',-64,31,'r2_c6');"><img name="r2_c6" src="http://cchdo.ucsd.edu/images/row2_col6.jpg" width="107" height="31" border="0" id="r2_c6" alt="" /></a></td>
	   <td><a href="http://cchdo.ucsd.edu/contact.html" onmouseover="ShowMenu('Contact_div', 'Contact',-64,31,'r2_c8');"><img name="r2_c8" src="http://cchdo.ucsd.edu/images/row2_col8.jpg" width="89" height="31" border="0" id="r2_c8" alt="" /></a></td>
	   <td><a href="javascript:;"  onmouseover="ShowMenu('Info_div', 'Info',-72,31,'r2_c9');"><img name="r2_c9" src="http://cchdo.ucsd.edu/images/row2_col9.jpg" width="157" height="31" border="0" id="r2_c9" alt="" /></a></td>
	  </tr>
	  <tr>
	   <td colspan="6"><img name="r3_c1" src="http://cchdo.ucsd.edu/images/row3_col1.jpg" width="750" height="22" border="0" id="r3_c1" alt="" /></td>
	  </tr>
	</table>
	<!-- End of JavaScript menu -->

	<!-- Table row for search 'n' date -->
	<table border="0" cellspacing="0" cellpadding="0" width="750"><form method="post" action="http://cchdo.ucsd.edu/search" enctype="multipart/form-data">
	<tr>
	   <td background="http://cchdo.ucsd.edu/images/row4_col1.jpg" width="32">&nbsp;</td>
	   <td bgcolor="#ffffff" class="thedate" align="left">
			<script>document.write(theDays[theDate.getDay()]+", "+theMonths[theDate.getMonth()]+" "+theDate.getDate()+", "+theDate.getFullYear());</script></td>
	   <td align="right" bgcolor="#ffffff"><table cellpadding="0" cellspacing="0" height="27">
	   <tr><td align="right" valign="center" bgcolor="#ffffff">&nbsp;</td>
	   <td valign="top" align="right" background="images/searchbar.jpg"><img alt="Main_r4_c4" border="0" id="main_r4_c4" src="http://cchdo.ucsd.edu/images/row4_col4.jpg" /></td>
				    <td><input type="text" name="query" size="20" value=""/></td>
				    <td align="left"><input type="image" src="http://cchdo.ucsd.edu/images/row4_col10.jpg" name="query" alt="SEARCH"/></td>
				</tr>
	                 </table>
	        </td>
	   <td background="http://cchdo.ucsd.edu/images/row4_col11.jpg" width="32">&nbsp;</td>
	   </tr>
	</form>
	</table>
	<!-- End of table row for search 'n' date -->

	<table border="0" width="750" cellpadding="0" cellspacing="0">
	  <tr>
	   <td background="http://cchdo.ucsd.edu/images/row5_col1.jpg" width="32">&nbsp;</td>
	   <td bgcolor="#ffffff" width="686">
	<!-- Page content goes here -->
HTML
if(!(param()))
{
   print_form();
}
elsif(param('datafile') or param('file'))
{
   #Place the cgi arguments in a hash
   %p = Vars();
   #If given a file, upload it
   if(param('datafile')) { $result = upload_file(); }
   undef $redirect;
   if($result !~/bad/)
   {
      #If any field is empty we write a message
      #and redirect
      if( not ($p{'Name'}  and $p{'institute'} 
        and $p{'email'} and $p{'Country'}))
      {
          incomplete_form();
      }
      else{ print_confirmation_table(\%p);}
   }

} 
# If not all fields have been filled out for submitted file
else
{
   incomplete_form();

}

print <<END;
   </td>
   <td background="http://cchdo.ucsd.edu/images/row5_col11.jpg" width="32">&nbsp;</td>
  </tr>
  <tr>
   <td colspan="3"><img name="r6_c1" src="http://cchdo.ucsd.edu/images/row6_col1.jpg" width="750" height="39" border="0" id="r6_c1" alt="" /></td>
  </tr>
</table>
<div id="Home_div">
	<div id="Home"  onmouseover="ResetTimeout();">
		&nbsp;
	</div>
</div>
<div id="Data_By_Ocean_div">
	<div id="Data_By_Ocean"  onmouseover="ResetTimeout();">
		<a href="javascript:;" id="Data_By_Ocean_Item_0" class="Data_By_Ocean_Menu_Style" onmouseover="OverMenuItem('Data_By_Ocean');">
			DATA&nbsp;BY&nbsp;OCEAN:
		</a>
		<a href="http://cchdo.ucsd.edu/arctic.html" id="Data_By_Ocean_Item_1" class="Data_By_Ocean_Menu_Style2" onmouseover="OverMenuItem('Data_By_Ocean');">
			Arctic&nbsp;Ocean
		</a>
		<a href="http://cchdo.ucsd.edu/atlantic.html" id="Data_By_Ocean_Item_2" class="Data_By_Ocean_Menu_Style2" onmouseover="OverMenuItem('Data_By_Ocean');">
			Atlantic&nbsp;Ocean
		</a>
		<a href="http://cchdo.ucsd.edu/pacific.html" id="Data_By_Ocean_Item_3" class="Data_By_Ocean_Menu_Style2" onmouseover="OverMenuItem('Data_By_Ocean');">
			Pacific&nbsp;Ocean
		</a>
		<a href="http://cchdo.ucsd.edu/indian.html" id="Data_By_Ocean_Item_4" class="Data_By_Ocean_Menu_Style2" onmouseover="OverMenuItem('Data_By_Ocean');">
			Indian&nbsp;Ocean
		</a>
		<a href="http://cchdo.ucsd.edu/southern.html" id="Data_By_Ocean_Item_5" class="Data_By_Ocean_Menu_Style2" onmouseover="OverMenuItem('Data_By_Ocean');">
			Southern&nbsp;Ocean
		</a>
	</div>
</div>
<div id="Search_Data_div">
	<div id="Search_Data"  onmouseover="ResetTimeout();">
		<a href="javascript:;" id="Search_Data_Item_0" class="Search_Data_Menu_Style" onmouseover="OverMenuItem('Search_Data');">
			SEARCH&nbsp;DATA:
		</a>
		<a href="http://cchdo.ucsd.edu/search_cart" id="Search_Data_Item_1" class="Search_Data_Menu_Style2" onmouseover="OverMenuItem('Search_Data');">
			Bulk Download
		</a>
		</a>
		<a href="http://cchdo.ucsd.edu/data_access/" id="Search_Data_Item_2" class="Search_Data_Menu_Style2" onmouseover="OverMenuItem('Search_Data');">
			Advanced&nbsp;Search
		</a>
		<a href="http://cchdo.ucsd.edu/map_search" id="Search_Data_Item_4" class="Search_Data_Menu_Style2" onmouseover="OverMenuItem('Search_Data');">
			Cruise&nbsp;Maps
		</a>
	</div>
</div>
<div id="Submit_div">
	<div id="Submit"  onmouseover="ResetTimeout();">
		&nbsp;
	</div>
</div>
<div id="Contact_div">
	<div id="Contact"  onmouseover="ResetTimeout();">
		&nbsp;
	</div>
</div>
<div id="Info_div">
	<div id="Info"  onmouseover="ResetTimeout();">
		<a href="javascript:;" id="Info_Item_0" class="Info_Menu_Style" onmouseover="OverMenuItem('Info');">
			INFO:
		</a>
		<a href="http://cchdo.ucsd.edu/manuals.html" id="Info_Item_1" class="Info_Menu_Style2" onmouseover="OverMenuItem('Info');">
			Manuals
		</a>
		<a href="http://cchdo.ucsd.edu/policies.html" id="Info_Item_2" class="Info_Menu_Style2" onmouseover="OverMenuItem('Info');">
			Policies
		</a>
		<a href="http://cchdo.ucsd.edu/format.html" id="Info_Item_3" class="Info_Menu_Style2" onmouseover="OverMenuItem('Info');">
			Format
		</a>
	</div>
</div>
</div>
</body>
</html>

END


#Subroutines #
##############

sub print_form
{

   print br,br;
   print start_form(-method=>'post',-action=>'submit.cgi',-enctype=>'multipart/form-data');
   print start_table({-class=>"master_table"});
   print Tr,td({-valign=>"top"});
   print_contact_table(\%param_hash);
   print td({-valign=>"top"});
   print_cruise_info_table(\%param_hash,\@parameters);
   print Tr({-valign=>"top"}),td();
   print_action_table(\%param_hash);
   print td();
   print_file_submit(\%param_hash);
   print end_table();
   print endform();
}

sub incomplete_form
{
  print br,br;
   my %param_hash=Vars();
   $datafile = $param_hash{'file'};
   if(!$param_hash{'file'} and $param_hash{'datafile'})
   {$param_hash{'file'} = $param_hash{'datafile'};}
   $param_hash{'Incomplete'} = 'true';
   foreach $k (keys %param_hash)
   {
      if($k =~ /^\d+/)
      {
         push @parameters,$param_hash{$k};
      }
   }
   print start_table({-class=>"master_table",-cellspacing=>"0", -cellpadding=>"0", -border=>"0"});
   print start_form(-method=>'post',-action=>'submit.cgi',-enctype=>'multipart/form-data');
   print Tr,td;
   print_contact_table(\%param_hash);
   print td({-valign=>"top"});
   print_cruise_info_table(\%param_hash,\@parameters);
   print Tr,td({-valign=>"top"});
   print_action_table(\%param_hash);
   print td();
#   if(param('file'))
#   {print_file_info_table($datafile,\%param_hash);}
#   else
#   {print_file_submit(\%param_hash);}
   print_file_submit(\%param_hash);
   print endform();
   print end_table;

}
sub upload_file
{
      $datafile = param("datafile");
      # Format the name to be a proper unix file
      $datafile =~ s/.*[\/\\] (.*)/$1/;
      $uploaded_file = upload("datafile")
        or die "couldn't upload file $datafile!!?!";
      $result = open (DFILE, ">$file_dir/$datafile")
          or die "couldn't open localfile";

      #check that we've recieved a proper hydrography file
      $result = check_upload();
        #Write file locally
   if($result !~ /bad/)
   {
         binmode DFILE;
         while (<$uploaded_file>)
         {
            print DFILE;
         }
         close DFILE;
         $code =~ s/[\ ]*(.*)/$1/; # drop leading whitespace
         my $incorrect_file=0;
         my $local_file = "$file_dir/$datafile";
         my $submitted=0;
         #Place files into their own directory within incoming
         $p{'file'} = $datafile;
         write_file(\%p);
   }
   return $result;
}
sub write_file
{
   my $ref = shift;
   my %hash = %$ref;
      if( $hash{'Line'} =~ /^\w+$/)
      {
         $t_stamp = &tag();
         $dir = $file_dir."/".$t_stamp."_".$hash{'Line'}."_".$hash{'Name'};
         $dir_message = $t_stamp."_".$hash{'Line'}."_".$hash{'Name'};
         $dir_message =~ s/\s+/_/g;
      }
      else
      { 
         $t_stamp = &tag();
         $dir = $file_dir."/".$t_stamp."_".$hash{'Name'};
         $dir_message = $t_stamp."_".$hash{'Name'};
         $dir_message =~ s/\s+/_/g;
      }
      
      $dir =~ s/\s+/_/g;
      if( not(-e $dir))
      {
         mkdir($dir,0777) or die "couldn't create directory $dir";
         $result = chmod 0777, $dir;
      }
      #Drop leading path for IE uploads
      $old_name = $hash{'file'};
      $hash{'file'} =~ s/\w:.*\\(.*)$/$1/;
      $out_file =$dir."/".$hash{'file'};
      $in_file = $file_dir."/".$old_name;
      $comment_file = $dir."/".$hash{'file'}.".Readme";
      open($out_fh,">$out_file") or die "couldn't open file($hash{'file'}) to write:$out_file";
      open($in_fh,$in_file) or die "couldn't open file to read";
      open($comment_fh,">$comment_file") or die "couldn't open file to read";
      undef $BytesRead;
      undef $Buffer;
      while ($Bytes = read($in_fh,$Buffer,1024)) 
      {
         $BytesRead += $Bytes;
         print $out_fh $Buffer;
      }
      print_description(\%hash,$comment_fh,$comment_file,$dir_message);
      close $out_fh;
      close $in_fh;
      close $comment_fh;
      
      unlink($in_file);
}

sub print_description
{
   my $ref = shift;
   my %hash = %$ref;
   my $fh = shift;
   my $file = shift;
   my $incoming_dir = shift;

   @actions = param('action');
   print $fh "File: $hash{'file'}  Type: $hash{'filetype'} Status: $hash{'status'}\n";
   print $fh "Name: $hash{'Name'} \nInstitute: $hash{'institute'} \nCountry: $hash{'Country'}\n";
   if($hash{'Expocode'}){ print $fh "Expo:$hash{'Expocode'}";}
   else { print $fh "No ExpoCode given";}
   if($hash{'Line'}){ print $fh " Line: $hash{'Line'}";}
   print $fh "\nDate: $hash{'BegMonth'}/$hash{'BegYear'}";
   print $fh "\nAction:"; 
   foreach (0..$#actions)
   {
      print $fh "$actions[$_]";
      unless ($_ eq $#actions){ print $fh ","};
   }
   print $fh "\nNotes:\n$hash{'OtherAction'}";
   print $fh "\nUpload directory: /incoming_data/$incoming_dir\n";
   $file =~ s/,/\,/g;
   $file =~ s/\s/\\ /g;
   open ($temp_out,">$file_dir/cat_arg.txt");
   print $temp_out $file,"\n";
   open($confirmation,">$file_dir/confirmation.txt"); 
   print $confirmation "CCHDO has accepted the file: $hash{'file'}\n";
   close $confirmation;
   #$result = `cat $file_dir/confirmation.txt | mail -s \"File Recieved\" $hash{'email'}`;
   #$result = `cat $file_dir/failed_confirmation.txt | mail -s \"Email confirmation failed\" fieldsjustin\@gmail.com`;
   $result = `cat $file | mail -s \"CCHDO File Submission $hash{'file'}\" $hash{'email'},sdiggs\@ucsd.edu,fieldsjustin\@gmail.com,cchdo\@googlegroups.com`;
   #$result = `cat $file | mail -s \"CCHDO File Submission\" $hash{'email'},fieldsjustin\@gmail.com`;

    if($result=~/\w/){`cat $error_file | mail -s \"Submit error\" sdiggs\@ucsd.edu,fieldsjustin\@gmail.com`;}
    print $temp_out "\n\nresult::$result\n";
    close $temp_out;
}
sub print_contact_table
{
   my $ref = shift;
   my %hash = %$ref;
   ($lname,$institute) = split /\//,$hash{'Chief_Scientist'};
   ## This table contains the contact form 
   print start_table({-class=>"sub_table"});
   print caption({-class=>"table_header"}),b({-class=>"submit_bold"},"Contact Information (Required)");
   print Tr,td,td;
   print Tr,td();
   if($hash{'Incomplete'} and not($hash{'Name'}))
   {
     print b({-class=>"Incomplete"}),"*";
   }
   print "Name(Last,First)",td(),textfield({-name=>"Name",-default=>$hash{'Name'}});
   print Tr,td();
   if($hash{'Incomplete'} and not($hash{'institute'}))
   {print b({-class=>"Incomplete"}),"*";}
   print "Institution",td(),textfield({-name=>"institute",-default=>$institute});

   print Tr,td();
   if($hash{'Incomplete'} and not($hash{'Country'}))
   {print b({-class=>"Incomplete"}),"*";}
   print "Country",td(),textfield({-name=>"Country",-default=>$hash{'Country'}});

   print Tr,td();
   if($hash{'Incomplete'} and not($hash{'email'}))
   {print b({-class=>"Incomplete"}),"*";}
   print "Email",td(),textfield({-name=>"email",-default=>$hash{'email'}});

   print Tr,td({-colspan=>"2"}),radio_group({-name=>"status", -values=>['Public','Non-Public']});
   print end_table;
}

sub print_cruise_info_table
{
   my $ref = shift;
   my %hash = %$ref;
   my $ref = shift;
   my @params = @$ref;

   my ($beg_year,$beg_month,$beg_day) = split /-/,$hash{'Begin_Date'};
   my ($end_year,$end_month,$end_day) = split /-/,$hash{'EndDate'};
   ## This table contains the data form 
   print start_table({-class=>"sub_table"});
   print caption({-class=>"table_header"}),b({-class=>"submit_bold"},"Cruise Information (Requested)");
   print Tr,td;
   print hidden('file',$datafile);
   print Tr,td({-align=>"left"});
   print "ExpoCode Or Cruise Name",td(),textfield({-name=>"Expocode",-default=>$hash{'Expocode'},-size=>"12"});
   print Tr,td({-align=>"left"});
   print "WOCE Line If Known",td(),textfield({-name=>"Line",-default=>$hash{'Line'},-size=>"6"});
   print Tr,td({-align=>"left"});
   print "Cruise Date (YYYY/MM)",td(),
	textfield({-name=>"BegYear",-default=>$beg_year,-size=>"4" ,-maxlength=>"4"}),"/",
	textfield({-name=>"BegMonth",-default=>$beg_month,-size=>"2",-maxlength=>"2"});
   if($hash{'FileType'} =~ /BOT/i)
   {
      print Tr,td({-align=>"right"});
      print "Parameters",Tr;
      $tctr=0;
      foreach $type (@params)
      {
         $tctr++;
         print td,textfield({-name=>"$tctr",-default=>$type});
         if($tctr %2 eq 0){print Tr;}
      } 
   }
   print end_table;
}

sub print_action_table
{
   @actions = param('action'); 
   if(@actions)
   {
      @defaults = @actions;
   }
   else
   {
      @defaults = ['Place Data Online'];
   }
   ## This table contains the data form 
   print start_table({-class=>"sub_table"});
   print caption({-class=>"table_header"}),b({-class=>"submit_bold"},"Type of Submission (Requested)");
   print Tr,td,td(),td();
   print Tr,td(),;
   print checkbox_group(-name=>"action",
	 -values=>['Merge Data','Place Data Online','Updated Parameters'],
         -defaults=>@defaults,
         -linebreak=>"true");
   print Tr,td();
   print "Notes",td,td,Tr,td,textarea({-rows=>"4",-cols=>"30",-name=>"OtherAction",-default=>""});
   print td(),td(),Tr,td,td,td;
   print end_table;
}

sub print_file_submit
{
   my $ref = shift;
   my %hash = %$ref;
   ## This table contains the form 
   print start_table({-class=>"sub_table"});
   print caption({-class=>"table_header"},b({-class=>"submit_bold"},"Upload Hydrography File"));
   if($hash{'file'})
   {
      print Tr,td,b(em($hash{'file'}));
      #param(-name=>'file',-value=>"$hash{'file'}");
      unless (param('file')){print hidden(-name=>'file',-value=>$hash{'file'});}
   }
   else
   {
   print Tr,td,'File',td(),Tr,td,filefield({-size=>'16', -name=>'datafile',-value=>"Submit File"});
   }
   print Tr,td,'File Type (ASCII,Exchange,Zipped CTD,etc.)',td,Tr,td,textfield({-size=>'10',-name=>'filetype',-default=>$hash{'filetype'}});
   print Tr,td,submit(-name=>"Submit File");
   print end_table;
}

sub check_upload
{
# Check file size of uploaded file,
#if the size doesn't make sense send a 
#message and restart form
   ($dev,$ino,$mode,$nlink,$uid,$gid,$rdev,$size,
       $atime,$mtime,$ctime,$blksize,$blocks)
           = stat($uploaded_file);
   if($size <$min_size or $size >$max_size) 
   {
      #print redirect(-URL=>'submit.cgi'); 
      print h1("Invalid file size, please try again");
      print q{<META HTTP-EQUIV="Refresh"
      CONTENT="3; URL="submit.cgi"></a><br><br>};
      return "bad file";
   }
   else{return 'continue';}
}

sub print_confirmation_table 
{
   my $ref = shift;
   my %hash =%$ref;
   
   ($lname,$fname) = split /,/,$hash{'Name'};
   @actions = param('action');
   ## This table contains the contact form 
   print br,br;

   print start_table({-class=>"conf_table"});
   print Tr({-class=>"table_header"}),td({-align=>"center"}),b({-class=>"submit_bold"},"File Submitted"),td;
   print Tr,td,td;
   print Tr,td();
   print "File:",td({-align=>"left"}),$hash{'file'};
   if($hash{'filetype'})
   {print Tr,td(); print "Type:",td({-align=>"left"}),$hash{'filetype'};}
   print Tr,td();
   print "Status:",td({-align=>"left"}),$hash{'status'};
   print Tr,td();
   print "Action:",td({-align=>"left"});
   for (0..$#actions){print "$actions[$_]";unless($_ eq $#actions) {print ",";}}
   print Tr,td();
   if($hash{'Expocode'})
   {print "ExpoCode:",td({-align=>"left"}),$hash{'Expocode'}; print Tr,td();}
   if($hash{'Line'})
   {print "Line:",td({-align=>"left"}),$hash{'Line'}; print Tr,td();}
   if($hash{'BegMonth'} and $hash{'BegYear'})
   {print "Cruise Date:",td({-align=>"left"})," $hash{'BegYear'}/$hash{'BegMonth'}";print Tr,td;}
   print "Name:",td({-align=>"left"}),$hash{'Name'};
   print Tr,td();
   print "Institution:",td({-align=>"left"}),$hash{'institute'};
   print Tr,td();
   print "Country:",td({-align=>"left"}),$hash{'Country'};
   print Tr,td({-colspan=>"2"},"Response sent to:",br," $hash{'email'}");
   print end_table;

}

