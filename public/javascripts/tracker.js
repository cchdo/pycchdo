/* rail_stat */
c=0;s=0;n=navigator;d=document;mime="application/x-shockwave-flash]";
plugin=(n.mimetypes && n.mimetypes[mime])?n.mimetypes[mime].enabledplugin:0;
if(plugin){
 w=n.plugins["Shockwave Flash"].description.split("");
 for(i=0;i<w.length;++i){if(!isNaN(parseInt(w[i]))){f=w[i];break;}}
} else if(n.userAgent&&n.userAgent.indexOf("MSIE")>=0&&(n.appVersion.indexOf("Win")!=-1)) {
 d.write('<script language="VBScript">On Error Resume Next\\nFor f=10 To 1 Step-1\\nv=IsObject(CreateObject("ShockwaveFlash.ShockwaveFlash."&f))\\nIf v Then Exit For\\nNext\\n</script>');
}
if(typeof(top.document)=="object"){
 t=top.document;rf=escape(t.referrer);pd=escape(t.URL);
} else {
 x=window;
 for(i=0;i<20&&typeof(x.document)=="object";i++){rf=escape(x.document.referrer);x=x.parent;}
 pd=0;
}
c=screen.colorDepth;s=screen.width;
if(typeof(f)=='undefined') f=0;
d.write('<img src="/staff/rail_stat/track?size='+s+'&colors='+c+'&referer='+rf+'&java=1&je='+(n.javaEnabled()?1:0)+'&flash='+f+'">');
/* GAnalytics */
var gaJsHost = (("https:" == document.location.protocol) ? "https://ssl." : "http://www.");
document.write(unescape("%3Cscript src='" + gaJsHost + "google-analytics.com/ga.js' type='text/javascript'%3E%3C/script%3E"));
try{ _gat._getTracker("UA-2167386-1")._trackPageview(); } catch(err) {}
try{ _gat._getTracker("UA-2201797-1")._trackPageview(); } catch(err) {}
