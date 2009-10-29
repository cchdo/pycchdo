#!/usr/bin/perl -w
#
#


use DBI;
use CGI qw(:standard *table :cgi-lib);
use CGI::Pretty;
require "hydro_file_tools.pl";

# Local structure variables
$base_dir = "";
$file_base = "/Users/Shared/cchdo2/public/data/$base_dir";
#$file_base = "/var/www/hydro/cchdo/public/data/$base_dir";
$base_url ="http://cchdo.ucsd.edu"; 
$datahist_url = $base_url."/data_history?ExpoCode=";
$lineentry_url = $base_url."/data_access?ExpoCode=";
$dataparam_url = $base_url."/cgi/public/basin_tables/new_param.cgi?Expo=";

# Variables for database interaction   
$database = 'DBI:mysql:cchdo';
$user = 'jfields';
$passwd = 'hydr0d@t@';
@basin_order = ('North Atlantic','Central Atlantic','South Atlantic','East Pacific','South West Pacific', 'West Pacific','Indian','Southern');

#Begin HTML
print header;
#start_html(-title=>"Data Histories",
#                       -style=>{-src=>"$base_url/style.css"},
#                        -script=>{-src=>"gmap.js",-type=>"text/javascript"},
#                        -script=>{-src=>'http://maps.google.com/maps?file=api&amp;v=2&amp;key=ABQIAAAAZICfw-7ifUWoyrSbSFaNixSFdTZeOB4GIl_XiWXVYYElhJSuoxTjIA2MnqBrs6duw1DN6Gr0tKlAhQ',-type=>"text/javascript"},
#                        -onload=>"load()",
#                        -onunload=>"GUnload()");
#cchdo => ABQIAAAAZICfw-7ifUWoyrSbSFaNixTec8MiBufSHvQnWG6NDHYU8J6t-xTRqsJkl7OBlM2_ox3MeNhe_0-jXA
# cchdo => ABQIAAAAZICfw-7ifUWoyrSbSFaNixRkZzjLi0nUJ4TwOC8xt4Ov2IJhKBTtZSVhnjKeLlrh2pPmjzyAFgBIdA
# cchdo.ucsd.edu => ABQIAAAAZICfw-7ifUWoyrSbSFaNixRz6rsNmenKPKujDhOQdQ7stlkpShSXsD_WCcTY2gZCHEPjXNnq5iLMSA
print <<HTML;
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml">
<head>
<title>CCHDO | CLIVAR & Carbon Hydrographic Data Office</title>
<script language="JavaScript1.2" type="text/javascript" src="http://cchdo.ucsd.edu/javascripts/application.js"></script>
<script src="http://maps.google.com/maps?file=api&amp;v=2&amp;key=ABQIAAAAZICfw-7ifUWoyrSbSFaNixRz6rsNmenKPKujDhOQdQ7stlkpShSXsD_WCcTY2gZCHEPjXNnq5iLMSA" type="text/javascript"></script>
<script  type="text/javascript" src="./gmap.js"></script>

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
   <td colspan="6"><img name="main2_r3_c1" src="http://cchdo.ucsd.edu/images/row3_col1.jpg" width="750" height="22" border="0" id="main2_r3_c1" alt="" /></td>
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
HTML
print start_table();
print Tr,
        td;
print " | "; 
$basin_ctr = 0;
foreach (@basin_order)
{
   $basin_ctr++;
   print      a({-href=>"$base_url/maps?basin=$_"},"$_")," | ";
   if($basin_ctr == 4){print br;}
}
#print   td,td,Tr,td,
#           start_form,"Filter for:",textfield({-name=>"filter",-size=>"10"}),end_form;
print hr({-align=>"left"});
print end_table;
print start_table,Tr,td,div({-id=>"message"}),end_table;
$ctr=1;
%arguments = Vars();
if($arguments{'Basin'})
{
print start_table({-class=>"Basin_table"});
   my $basin = $arguments{'Basin'};
   $img_name = $basin;
   $img_name =~ s/\s/_/g;
   $image = "$base_url/images/$img_name.gif";
   print Tr,td,h1({-id=>"Basin"},"$basin"),
         Tr,td(div({-id=>"map",-style=>"width:670px; height: 420px"}));
   $lines_ref = print_list($basin);
   %lines = %$lines_ref;
   $line_ctr=1;
   print start_table;
   print Tr;
   foreach (reverse sort {sort_func($a,$b)} keys %lines)
   {
      print td,a({-id=>"$_",-href=>"$lineentry_url$lines{$_}"},"$_");
      if($line_ctr % 6 eq 0){print Tr;}
      $line_ctr++;
   }
   #print end_table;
  # print end_table;
}
else
{
   foreach (keys %basins)
   {
      print start_table({-class=>"Basin_table"});
   	my $img_name =$_;
   	$img_name =~ s/\s/_/g;	
   	if($ctr %2 == 0)
   	{
      	$image = "$base_url/images/$img_name.gif";
      	print Tr,td,h1($_),Tr,td,img({-height=>"200px",-src=>$image}),td;
      	$lines_ref = print_list($_);
      	%lines = %$lines_ref;
      	$line_ctr=1;
      	print start_table;
      	foreach (keys %lines)
      	{
         	print td,a({-href=>"$lineentry_url$lines{$_}"},"$_");
         	if($line_ctr % 6 eq 0){print Tr;}
         	$line_ctr++;
      	}
      	print end_table;
      	print Tr,td;
      	print end_table;
   	}
   	else
   	{
      	$image = "$base_url/images/$img_name.gif";
      	print Tr,td,h1($_),
            Tr,td;
      		$lines_ref = print_list($_);
      		%lines = %$lines_ref;
      	$line_ctr=1;
      	print start_table;
      	foreach (keys %lines)
      	{
         	print td,a({-href=>"$lineentry_url$lines{$_}"},"$_");
         	if($line_ctr % 6 eq 0){print Tr;}
         	$line_ctr++;
      	}
      	print end_table;
      	print td, img({-height=>"200px",-src=>$image}),td;
      	print end_table;

   	}
   	$ctr++;
	}
}
print end_table;
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
print end_html;


sub print_list
{
   my $search = shift;
   my %lines;
   my $db = DBI->connect('DBI:mysql:cchdo',$user,$passwd)
      or die "couldn't connect to documents";
   my $statement = qq{SELECT distinct(cruises.Line), cruises.ExpoCode
                      FROM internal,cruises
		      WHERE internal.Basin = '$search' AND internal.ExpoCode = cruises.ExpoCode};

   my $sh = $db->prepare($statement);
   $sh->execute() or die "couldn't retrieve data from documents";
   my $ctr = 0;
   while($ref = $sh->fetchrow_hashref)
   {
      $lines{$ref->{'Line'}}=$ref->{'ExpoCode'};
      $ctr++;
   }
   return \%lines;
}

sub sort_func
{
   my $a = shift;
   my $b = shift;
   my $complete_a = $complete_b = 1;
   if($a =~ /^([a-z]+)([0-9]+)/i)
   {
      $a_basin = $1;
      $a_number = $2;
   }else{$complete_a = 0;}
   if($b =~ /^([a-z]+)([0-9]+)/i)
   {
      $b_basin = $1;
      $b_number = $2;
   }else{$complete_b = 0;}
   if( $complete_a and $complete_b)
   {
      @a = split //, $a_basin;
      @b = split //,$b_basin;
      if($#a eq $#b)
      {
         if($a_number > $b_number)
         {$ret_val = -1;}
         elsif($b_number > $a_number)
         {$ret_val = 1;}
         else
         {
            $ret_val = 0;
         }
#print h1($a,"a: ",$a_basin," ",$a_number,"    ",$b,"b: ",$b_basin,"  ",$b_number);
      }
      else
      {
         if($#a > $#b)
         { $ret_val = -1;}
         elsif($#b >$#a)
         { $ret_val = 1;}
         else{$ret_val = 0;}
      }
   }
   else
   { $ret_val = 0;}
   return $ret_val;
}
      
