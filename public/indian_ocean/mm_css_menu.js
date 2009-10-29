var mmOpenContainer = null;
var mmOpenMenus = null;
var mmHideMenuTimer = null;

function MM_menuStartTimeout(hideTimeout) {
	mmHideMenuTimer = setTimeout("MM_menuHideMenus()", hideTimeout);	
}

function MM_menuHideMenus() {
	MM_menuResetTimeout();
	if(mmOpenContainer) {
		var c = document.getElementById(mmOpenContainer);
		c.style.visibility = "inherit";
		mmOpenContainer = null;
	}
	if( mmOpenMenus ) {
		for(var i in mmOpenMenus) {
			var m = document.getElementById(mmOpenMenus[i]);
			m.style.visibility = "hidden";			
		}
		mmOpenMenus = null;
	}
}

function MM_menuHideSubmenus(menuName) {
	if( mmOpenMenus ) {
		var h = false;
		var c = 0;
		for(var i in mmOpenMenus) {
			if( h ) {
				var m = document.getElementById(mmOpenMenus[i]);
				m.style.visibility = "hidden";
			} else if( mmOpenMenus[i] == menuName ) {
				h = true;
			} else {
				c++;
			}
		}
		mmOpenMenus.length = c+1;
	}
}

function MM_menuOverMenuItem(menuName, subMenuSuffix) {
	MM_menuResetTimeout();
	MM_menuHideSubmenus(menuName);
	if( subMenuSuffix ) {
		var subMenuName = "" + menuName + "_" + subMenuSuffix;
		MM_menuShowSubMenu(subMenuName);
	}
}

function MM_menuShowSubMenu(subMenuName) {
	MM_menuResetTimeout();
	var e = document.getElementById(subMenuName);
	e.style.visibility = "inherit";
	if( !mmOpenMenus ) {
		mmOpenMenus = new Array;
	}
	mmOpenMenus[mmOpenMenus.length] = "" + subMenuName;
}

function MM_menuResetTimeout() {
	if (mmHideMenuTimer) clearTimeout(mmHideMenuTimer);
	mmHideMenuTimer = null;
}

function MM_menuShowMenu(containName, menuName, xOffset, yOffset, triggerName) {
	MM_menuHideMenus();
	MM_menuResetTimeout();
	MM_menuShowMenuContainer(containName, xOffset, yOffset, triggerName);
	MM_menuShowSubMenu(menuName);
}

function MM_menuShowMenuContainer(containName, x, y, triggerName) {	
	var c = document.getElementById(containName);
	var s = c.style;
	s.visibility = "inherit";
	
	mmOpenContainer = "" + containName;
}

function modDate() {
var defaultDate = "04/05/2007";
var lm = document.lastModified

if (Date.parse(lm) == 0) {
lm = defaultDate
}
document.write("Last updated: " + lm)
}

function takemethere(){
linefolder = document.lineurl.line.options[document.lineurl.line.selectedIndex].value;
menupage = document.lineurl.submenu.options[document.lineurl.submenu.selectedIndex].value;


if( menupage == "data_link") {
        if (linefolder == "p16_1984a") {newpage = "http://cchdo.ucsd.edu/table?id=p16";}
        else if (linefolder == "p01w") {newpage = "http://cchdo.ucsd.edu/table?id=p01";}
        else if (linefolder == "p02t") {newpage = "http://cchdo.ucsd.edu/table?id=p02";}
        else if (linefolder == "p13j") {newpage = "http://cchdo.ucsd.edu/table?id=p13";}
        else if (linefolder == "p15sa") {newpage = "http://cchdo.ucsd.edu/table?id=p15";}
        else if (linefolder == "p17e") {newpage = "http://cchdo.ucsd.edu/table?id=p17";}
        else if (linefolder == "p17ca") {newpage = "http://cchdo.ucsd.edu/table?id=p17";}
        else if (linefolder == "p17cca") {newpage = "http://cchdo.ucsd.edu/table?id=p17";}
        else if (linefolder == "p17ne") {newpage = "http://cchdo.ucsd.edu/table?id=p17";}
	else {newpage = "http://cchdo.ucsd.edu/table?id=" + linefolder;}
}
else
{newpage = "./" + linefolder + "/" + menupage + ".html";}



window.document.location = newpage;
return(false);
}
