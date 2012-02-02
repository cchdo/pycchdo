(function menuMods() {
  var menu = document.getElementById('cchdo_menu');
  function add_class(e, c) {
    e.className = e.className + ' ' + c;
  }
  function remove_class(e, c) {
    e.className = e.className.replace(' ' + c, '');
  }
  function has_class(e, c) {
    return e.className.indexOf(c) >= 0;
  }
  (function tabableMenu() {
    function addfocusblur(e, limit) {
      var lis = [];
      var f = e;
      while (f !== limit) {
        if (f.tagName == 'LI') {
          lis.push(f);
        }
        f = f.parentNode;
      }
      e.onfocus = function () {
        for (var i = 0; i < lis.length; i++) {
          add_class(lis[i], 'focus');
        }
      };
      e.onblur = function () {
        for (var i = 0; i < lis.length; i++) {
          remove_class(lis[i], 'focus');
        }
      };
    }
    function walkFor(root, tagname, callback) {
      for (var i = 0; i < root.children.length; i++) {
        walkFor(root.children[i], tagname, callback);
      }
      if (root.tagName == tagname) {
        callback(root);
      }
    }
    walkFor(menu, 'A', function (a) {
      addfocusblur(a, menu);
    });
  })();
  (function toggleableMenu() {
    var down = '&#x25BC; open menu';
    var up = '&#x25B2; close menu';
    var down = 'open menu';
    var up = 'close menu';
    var ul = menu.children[0];
    var expander = document.createElement('LI');
    var h1 = document.createElement('H1');
    var link = document.createElement('A');
    link.className = 'expander';
    link.href = 'javascript:void(0);';
    link.title = 'Pin open';
    link.innerHTML = down;
    h1.appendChild(link);
    expander.appendChild(h1);
    ul.appendChild(expander);
    expander.onclick = function () {
      if (has_class(ul, 'open')) {
        remove_class(ul, 'open');
        link.innerHTML = down;
        link.title = 'Pin open';
      } else {
        add_class(ul, 'open');
        link.innerHTML = up;
        link.title = 'Unpin';
      }
    };
  })();
})();
