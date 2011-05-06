 /*
 * TipTipTip
 * Modified 2011 by Matt Shen
 * Copyright 2010 Drew Wilson
 * www.drewwilson.com
 * code.drewwilson.com/entry/tiptip-jquery-plugin
 *
 * Version 1.3   -   Updated: Mar. 23, 2010
 *
 * This Plug-In will create a custom tooltip to replace the default
 * browser tooltip. It is extremely lightweight and very smart in
 * that it detects the edges of the browser window and will make sure
 * the tooltip stays within the current window size. As a result the
 * tooltip will adjust itself to be displayed above, below, to the left 
 * or to the right depending on what is necessary to stay within the
 * browser window. It is completely customizable as well via CSS.
 *
 * This TipTip jQuery plug-in is dual licensed under the MIT and GPL licenses:
 *   http://www.opensource.org/licenses/mit-license.php
 *   http://www.gnu.org/licenses/gpl.html
 */

(function($){
  var elem_tip_map = {};

  var showing = null;

  function noop() {}

  var defaults = { 
    activation: "hover",
    keepAlive: false,
    maxWidth: "200px",
    edgeOffset: 3,
    defaultPosition: "bottom",
    delay: 400,
    fadeIn: 200,
    fadeOut: 200,
    attribute: "title",
    content: false, // HTML or String to fill TipTIp with
    controlled: false,
    enter: function(){},
    exit: function(){}
  };

  function Tip(opts, org_elem) {
    var self = this;

    opts = $.extend({}, defaults, opts);

    this.opts = opts;
    this.org_elem = org_elem;

    if(opts.content){
      this.org_title = opts.content;
    } else {
      this.org_title = org_elem.attr(opts.attribute);
    }
    if(this.org_title != ""){
      if(!opts.content){
        org_elem.removeAttr(opts.attribute); //remove original Attribute
      }
      this.timeout = false;

      if (!this.opts.controlled) {
        this.setActivation(opts.activation);
      }
      this.holder = $('<div class="tiptip_holder" style="max-width:'+ this.opts.maxWidth +';"></div>');
      this.content = $('<div class="tiptip_content"></div>');
      this.arrow = $('<div class="tiptip_arrow"></div>').html('<div class="tiptip_arrow_inner"></div>');
      $("body").append(this.holder.html(this.content).prepend(this.arrow));
    }
  }

  Tip.prototype.setActivation = function (type) {
    var self = this;
    function activate() {
      self.active();
      return false;
    }
    function deactivate() {
      self.deactive();
    }
    function deactivateIfNotKeepAlive() {
      if(!self.opts.keepAlive){
        self.deactive();
      }
    }

    this.activated_type = type;

    if(type == "hover"){
      this.org_elem.hover(activate, deactivateIfNotKeepAlive);
      if(this.opts.keepAlive){
        this.holder.hover(noop, deactivate);
      }
    } else if(type == "focus"){
      this.org_elem.focus(activate).blur(deactivate);
    } else if(type == "click"){
      this.org_elem.click(activate).hover(noop,deactivateIfNotKeepAlive);
      if(this.opts.keepAlive){
        this.holder.hover(noop, deactivate);
      }
    } else {
    }
  };

  Tip.prototype.active = function () {
    if (showing && !this.opts.controlled) {
      return;
    }
    if (!this.opts.controlled) {
      showing = this;
    }
    this.opts.enter.call(this.org_elem);
    this.content.html(this.org_title);
    var match = /\s+tip_\w+/.exec(this.holder.attr('class'));
    this.holder.hide().removeClass(match).css("margin","0");
    this.arrow.removeAttr("style");

    var top = parseInt(this.org_elem.offset()['top']);
    var left = parseInt(this.org_elem.offset()['left']);
    var org_width = parseInt(this.org_elem.outerWidth());
    var org_height = parseInt(this.org_elem.outerHeight());
    var tip_w = this.holder.outerWidth();
    var tip_h = this.holder.outerHeight();
    var w_compare = Math.round((org_width - tip_w) / 2);
    var h_compare = Math.round((org_height - tip_h) / 2);
    var marg_left = Math.round(left + w_compare);
    var marg_top = Math.round(top + org_height + this.opts.edgeOffset);
    var t_class = "";
    var arrow_top = "";
    var arrow_left = Math.round(tip_w - 12) / 2;

    if(this.opts.defaultPosition == "bottom"){
      t_class = "_bottom";
    } else if(this.opts.defaultPosition == "top"){ 
      t_class = "_top";
    } else if(this.opts.defaultPosition == "left"){
      t_class = "_left";
    } else if(this.opts.defaultPosition == "right"){
      t_class = "_right";
    }

    var right_compare = (w_compare + left) < parseInt($(window).scrollLeft());
    var left_compare = (tip_w + left) > parseInt($(window).width());

    if((right_compare && w_compare < 0) || (t_class == "_right" && !left_compare) || (t_class == "_left" && left < (tip_w + this.opts.edgeOffset + 5))){
      t_class = "_right";
      arrow_top = Math.round(tip_h - 13) / 2;
      arrow_left = -12;
      marg_left = Math.round(left + org_width + this.opts.edgeOffset);
      marg_top = Math.round(top + h_compare);
    } else if((left_compare && w_compare < 0) || (t_class == "_left" && !right_compare)){
      t_class = "_left";
      arrow_top = Math.round(tip_h - 13) / 2;
      arrow_left =  Math.round(tip_w);
      marg_left = Math.round(left - (tip_w + this.opts.edgeOffset + 5));
      marg_top = Math.round(top + h_compare);
    }

    var top_compare = (top + org_height + this.opts.edgeOffset + tip_h + 8) > parseInt($(window).height() + $(window).scrollTop());
    var bottom_compare = ((top + org_height) - (this.opts.edgeOffset + tip_h + 8)) < 0;

    if(top_compare || (t_class == "_bottom" && top_compare) || (t_class == "_top" && !bottom_compare)){
      if(t_class == "_top" || t_class == "_bottom"){
        t_class = "_top";
      } else {
        t_class = t_class+"_top";
      }
      arrow_top = tip_h;
      marg_top = Math.round(top - (tip_h + 5 + this.opts.edgeOffset));
    } else if(bottom_compare | (t_class == "_top" && bottom_compare) || (t_class == "_bottom" && !top_compare)){
      if(t_class == "_top" || t_class == "_bottom"){
        t_class = "_bottom";
      } else {
        t_class = t_class+"_bottom";
      }
      arrow_top = -12;
      marg_top = Math.round(top + org_height + this.opts.edgeOffset);
    }

    if(t_class == "_right_top" || t_class == "_left_top"){
      marg_top = marg_top + 5;
    } else if(t_class == "_right_bottom" || t_class == "_left_bottom"){
      marg_top = marg_top - 5;
    }
    if(t_class == "_left_top" || t_class == "_left_bottom"){
      marg_left = marg_left + 5;
    }
    this.arrow.css({"margin-left": arrow_left+"px", "margin-top": arrow_top+"px"});
    this.holder.css({"margin-left": marg_left+"px", "margin-top": marg_top+"px"}).addClass("tip"+t_class);

    if (this.timeout){ clearTimeout(this.timeout); }
    var self = this;
    this.timeout = setTimeout(function(){ self.holder.stop(true,true).fadeIn(self.opts.fadeIn); }, this.opts.delay);
  };

  Tip.prototype.deactive = function () {
    this.opts.exit.call(this.org_elem);
    if (this.timeout){ clearTimeout(this.timeout); }
    this.holder.fadeOut(this.opts.fadeOut);
    if (!this.opts.controlled && showing === this) {
      showing = null;
    }
  };

  $.fn.tipTipTip = function(options) {
    return this.each(function(){
      var tip = $(this).data('tip');

      if (typeof options == 'string') {
        if (!tip) {
          return;
        }
        if (options == 'on') {
          tip.active();
        } else if (options == 'off') {
          tip.deactive();
        }
      } else {
        if (!tip) {
          $(this).data('tip', new Tip(options, $(this)));
        }
      }
    });
  }
})(jQuery);
