function ImportKML() {
}

ImportKML.prototype.importURL = function (url, callback) {
  callback({
    mapsLayer: new google.maps.KmlLayer(CM.host + '/' + url),
    earth: {kml: null, tour: null}});
};

ImportKML.prototype._getTour = function (kmlroot, callback) {
  CM.earth._withEarth(function (ge) {
    var found = false;
    new GEarthExtensions(ge).dom.walk({
      rootObject: kmlroot,
      features: true,
      geometries: false,
      visitCallback: function (context) {
        if (this.getType() == 'KmlTour') {
          found = true;
          callback(this);
          // Stop walking
          return false;
        }
      }
    });
    if (!found) {
      callback(null);
    }
  });
};

//  importKMLFile: function (file, filename) {
//    CM.GE(function (ge) {
//      google.earth.fetchKml(ge, CM.host() + '/'+file, function (kmlobj) {
//        if (kmlobj) {
//          var importedFile = CM.importFile.newImportedFile(filename)
//                                          .data('kml', kmlobj);
//          var tour = CM.importFile.getKmlTour(kmlobj);
//          if (tour) {
//            importedFile.append($(' <a href="#">Play</a>').click(function () {
//              CM.GE(function (ge) {
//                ge.getTourPlayer().setTour(tour);
//                ge.getTourPlayer().play();
//              });
//           }));
//          }
//          CM.importFile.gotoImported(importedFile);
//        } else {
//          alert('Sorry, there was an error loading the file.');
//        }
//      });
//    });
//    CM.map.setMapType(G_SATELLITE_3D_MAP);
//  },
