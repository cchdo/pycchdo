var Slider = function(container, min, max, length) {
  var me = this;
	me.slider = container;
	me.minVal = min;
	me.maxVal = max;
	me.length = length;
  me.gen_slider(me.slider);
	me.slideRatio = 1.0*me.length/(me.maxVal-me.minVal);
  me.dispL = me.$('min_time_display');
  me.dispR = me.$('max_time_display');

	me.sliding = false;
	me.x; // current event's x position
	me.activept;

  me.ptrL.onmousedown = function(e){me.start(e)};
  me.ptrR.onmousedown = function(e){me.start(e)};
  me.move_ear = function(e){me.slide(e);};
  me.stop_ear = function(e){me.stop(e);};
  me.dispL.onblur = function(){me.sync();};
  me.dispR.onblur = function(){me.sync();};
  me.dispL.onkeyup = function(){me.sanitize();}
  me.dispR.onkeyup = function(){me.sanitize();}

  me.sanitize();
  me.sync();
}
Slider.prototype.$ = function(id){return document.getElementById(id);};
Slider.prototype.sliderValue = function(point) { return Math.round(this.minVal + this.pointValue(point) / this.slideRatio); }
Slider.prototype.pointValue = function(point) { return parseInt(point.style.left.substring(-2)); }
Slider.prototype.pointToSlide = function(pointValue) { return Math.round(pointValue / this.slideRatio + this.minVal); }
Slider.prototype.slideToPoint = function(slideValue) { return (slideValue - this.minVal) * this.slideRatio; }
Slider.prototype.setPoint = function(point, slideValue) { point.style.left = (slideValue - this.minVal) * this.slideRatio + "px"; }
Slider.prototype.gen_slider = function() {
  var cover = this.cover = document.createElement('div');
  cover.id = 'cover';
  cover.className = 'slideCover';
  cover.style.left = '0px';
  cover.style.width = parseInt(this.length)+'px';
  var track = this.track = document.createElement('div');
  track.className = 'slider_track';
  var ptrL = this.ptrL = document.createElement('div');
  ptrL.id = "min_time";
  ptrL.className = "point_left";
  ptrL.style.left = '0px';
  var ptrR = this.ptrR = document.createElement('div');
  ptrR.id = "max_time";
  ptrR.className = "point_right";
  ptrR.style.left = this.length+'px';
  var s = this.slider;
  s.appendChild(cover);
  s.appendChild(track);
  s.appendChild(ptrL);
  s.appendChild(ptrR);
}
Slider.prototype.drawCover = function() {
  var pointL = this.pointValue(this.ptrL);
  this.cover.style.left = pointL+'px';
  this.cover.style.width = parseInt(this.pointValue(this.ptrR)-pointL) + 'px';
}
Slider.prototype.sanitize = function() {
  if(this.dispL.value > this.dispR.value) {
    var tmp = this.dispL.value;
    this.dispL.value = this.dispR.value;
    this.dispR.value = tmp;
  }
  if(this.dispL.value == this.dispR.value){
    if(this.dispL.value > this.minVal) {
      this.dispL.value--;
    } else {
      this.dispR.value++;
    }
  }
}
Slider.prototype.sync = function() {
  if(this.dispL.value < this.minVal) this.dispL.value = this.minVal;
  if(this.dispR.value > this.maxVal) this.dispR.value = this.maxVal;
  this.setPoint(this.ptrL, this.dispL.value);
  this.setPoint(this.ptrR, this.dispR.value);
  this.drawCover();
}
Slider.prototype.start = function(e) {
	this.sliding = true;
	this.x = e.screenX;
	this.activept = e.target;
	window.addEventListener('mousemove', this.move_ear, false);
	window.addEventListener('mouseup', this.stop_ear, false);
}
Slider.prototype.stop = function(e) {
	this.sliding = false;
	this.activept = null;
	window.removeEventListener('mousemove', this.move_ear, false);
	window.removeEventListener('mouseup', this.stop_ear, false);
}
Slider.prototype.slide = function(e) {
	if(this.sliding) {
		var newPt = this.pointValue(this.activept)+e.screenX-this.x;
		//verify
		if (newPt < 0) { newPt = 0; }
		if (newPt > this.length) { newPt = this.length; }
		if (this.activept == this.ptrL && this.pointToSlide(newPt) >= this.sliderValue(this.ptrR)) {
			newPt = this.slideToPoint(this.pointToSlide(newPt) - 1);
		}
		if (this.activept == this.ptrR && this.pointToSlide(newPt) <= this.sliderValue(this.ptrL)) {
			newPt = this.slideToPoint(this.pointToSlide(newPt) + 1);
		}

		//do cover
		this.activept.style.left = newPt+"px";
    this.drawCover();
		this.$(this.activept.id + "_display").value = this.sliderValue(this.activept);
		this.x = e.screenX; //update current position
	}
}
