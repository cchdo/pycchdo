#!/usr/local/bin/perl -w
#
#
#
#require "ctime.pl";
sub tag	{

	my($tagtime,$tmptime, @newtime, $day, $d, 
		$mon, $m, $min, $sec);

	$tmptime = localtime();
	@newtime = split(/\s+/,$tmptime);
	$tagtime = join(':',@newtime);
	@newtime = split(/:/,$tagtime);
	$day  = sprintf("%02d", $newtime[2]);
	$hour = sprintf("%02d", $newtime[3]);
	$min  = sprintf("%02d", $newtime[4]);
	$sec  = sprintf("%02d", $newtime[5]);
	$year = substr($newtime[6],0,4);
	$m = $newtime[1];
	#print join('|',($year,$m,$day,$hour,$min,$sec))."\n";
	SELECT_MON:	{

		$month = '01', last SELECT_MON if ($m =~ /Jan/i);
		$month = '02', last SELECT_MON if ($m =~ /Feb/i);
		$month = '03', last SELECT_MON if ($m =~ /Mar/i);
		$month = '04', last SELECT_MON if ($m =~ /Apr/i);
		$month = '05', last SELECT_MON if ($m =~ /May/i);
		$month = '06', last SELECT_MON if ($m =~ /Jun/i);
		$month = '07', last SELECT_MON if ($m =~ /Jul/i);
		$month = '08', last SELECT_MON if ($m =~ /Aug/i);
		$month = '09', last SELECT_MON if ($m =~ /Sep/i);
		$month = '10', last SELECT_MON if ($m =~ /Oct/i);
		$month = '11', last SELECT_MON if ($m =~ /Nov/i);
		$month = '12', last SELECT_MON if ($m =~ /Dec/i);
	  $month = '00';
	}
	$retval = $year.$month.$day.'.'.$hour.$min.$sec;
}
sub tag2	{

	my($tagtime,$tmptime, @newtime, $day, $d, 
		$mon, $m, $min, $sec);

	$tmptime = localtime();
	@newtime = split(/\s+/,$tmptime);
	$tagtime = join(':',@newtime);
	@newtime = split(/:/,$tagtime);
	$day  = sprintf("%02d", $newtime[2]);
	$hour = sprintf("%02d", $newtime[3]);
	$min  = sprintf("%02d", $newtime[4]);
	$sec  = sprintf("%02d", $newtime[5]);
	$year = $newtime[6];
	$m = $newtime[1];
	#print join('|',($year,$m,$day,$hour,$min,$sec))."\n";
	SELECT_MON:	{

		$month = '01', last SELECT_MON if ($m =~ /Jan/i);
		$month = '02', last SELECT_MON if ($m =~ /Feb/i);
		$month = '03', last SELECT_MON if ($m =~ /Mar/i);
		$month = '04', last SELECT_MON if ($m =~ /Apr/i);
		$month = '05', last SELECT_MON if ($m =~ /May/i);
		$month = '06', last SELECT_MON if ($m =~ /Jun/i);
		$month = '07', last SELECT_MON if ($m =~ /Jul/i);
		$month = '08', last SELECT_MON if ($m =~ /Aug/i);
		$month = '09', last SELECT_MON if ($m =~ /Sep/i);
		$month = '10', last SELECT_MON if ($m =~ /Oct/i);
		$month = '11', last SELECT_MON if ($m =~ /Nov/i);
		$month = '12', last SELECT_MON if ($m =~ /Dec/i);
	  $month = '00';
	}
	$retval = $year.$month.$day;
}
1;
	
