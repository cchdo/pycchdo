#!/usr/bin/perl -w
#
#  This file extracts content from old html files,
#  and creates a page with the old content and the
#  new style.

use CGI qw(:standard :cgi-lib *table);
use CGI::Pretty;

#my $file = shift;
@table_files = `ls ./old_files/`;
for $ctr ( 1..$#table_files){unless ($table_files[$ctr] =~ /.html/){splice @table_files,$ctr,1;}}
foreach $file (@table_files)
{
   undef @content;
   @chunks = split /\//,$file;
   $name =$chunks[$#chunks];
   chomp($file);
   $file =~ s/\s+//g;
   open($fh,"./old_files/$file") or die "Couldn't open $file\n";
   open($html,">./$name") or die "Couldn't open output file\n";

   @file = <$fh>;
   $collect =0;
   foreach $ctr (1..$#file)
   {
      if($file[$ctr] =~ /begin content/i) { $collect =1; }

      if($file[$ctr] =~ /end content/i){$collect = 0;}

      if($collect eq 1)
      {
         $file[$ctr] =~ s/align=\"center\"//i;
         $file[$ctr] =~ s/Table/Table class=\"status_table\"/i;
         $file[$ctr] =~ s/align=center//i;
         $file[$ctr] =~ s/<center>//i;
         $file[$ctr] =~ s/<\/center>//i;
         $file[$ctr] =~ s/width=\"*\"//i;
         $file[$ctr] =~ s/colspan=\"*\"//i;
         if( $file[$ctr] =~ /<a.*<\/a>/)
         {  
            $link = $file[$ctr];
            ($line) = $link =~ /<a.*>(.*)<\/a>/;
            if($link =~ /(name=.*)href/)
            { $name = $1;}
            else
            {$name = "";}
            if($file[$ctr+1] =~ /<i>.*<\/i>/)
            {
               ($expo) = $file[$ctr+1]=~ /<i>(.*)<\/i>/;
               print "Found match $link $expo\n";
               $file[$ctr] = "<a $name href=\"http://cchdo.ucsd.edu/data_access?ExpoCode=$expo\">$line</a><br>";
            }
            elsif($file[$ctr+2] =~ /<i>.*<\/i>/)
            {
               ($expo) = $file[$ctr+2]=~ /<i>(.*)<\/i>/;
               print "Found match $link $expo $ctr\n";
               $file[$ctr] = "<a $name href=\"http://cchdo.ucsd.edu/data_access?ExpoCode=$expo\">$line</a><br>";
            }
         } 
         push @content,$file[$ctr];
      }
   }

   print $html <<STOP;
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>CCHDO | CLIVAR & Carbon Hydrographic Data Office</title>
<script language="JavaScript1.2" type="text/javascript" src="http://cchdo.ucsd.edu/javascripts/application.js"></script>
<style type="text/css" media="screen">
	\@import url("http://cchdo.ucsd.edu/stylesheets/main.css");
</style>
</head>
<body bgcolor="#ffffff" topmargin="0" leftmargin="0">
<div id="Body_Container">
<table border="0" cellpadding="0" cellspacing="0" width="750" align="center">
  <tr>
   <td colspan="6"><a href="index.html">
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
   <td valign="top" align="right" background="http://cchdo.ucsd.edu/images/searchbar.jpg"><img alt="Main_r4_c4" border="0" id="main_r4_c4" src="http://cchdo.ucsd.edu/images/row4_col4.jpg" /></td>
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
STOP
   
   foreach (@content)
   {
      print $html $_,"\n";
   }
   
   print $html <<END;
<!-- End of page content -->
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

   close $html;
   close $fh;
}
