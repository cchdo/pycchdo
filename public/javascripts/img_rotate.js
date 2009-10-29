//Rotate banner
var ImgRotate = {
  id: 'banner',
  rotate_speed: 20000,
  rotate_timer: null,
  to_rotate: null,
  index: 1,
  index_max: 14
};
ImgRotate.next_image_in_rotation = function() {
	var next_img = '/images/banners/banner_' + this.index + '.jpg';
	this.index++;
	if (this.index > this.index_max) this.index = 1;
	return next_img;
}
ImgRotate.setTimeout = function(time) { this.rotate_timer = setTimeout('ImgRotate.rotate_banner()', time); }
ImgRotate.rotate_banner = function() {
	if (this.rotate_timer) {
		clearTimeout(this.rotate_timer);
		this.rotate_timer = null;
	}
	if (this.to_rotate) {
		this.to_rotate.src = this.next_image_in_rotation();
	  this.setTimeout(this.rotate_speed);
	} else {
		this.to_rotate = document.getElementById(this.id);
		this.setTimeout(200);
	}
}
ImgRotate.rotate_banner();
