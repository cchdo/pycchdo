$(document).ready(function(upperBound, lowerBound) {
  function fmtDateYY(x) {
    return Number($.datepicker.formatDate("yy", x));
  }

  function pad(n, l, p) {
    if (l === undefined) {
      l = 2;
    }
    if (p === undefined) {
      p = 0;
    }
    var s = String(n);
    var a = new Array(l - s.length + 1);
    var i = 0;
    for (; i < a.length - 1; i++) {
      a[i] = p;
    }
    a[i] = s;
    return a.join('');
  }

  var currentMinDate = "";
  var currentMaxDate = "";
  var upperBound = new Date();
  var lowerBound = new Date(1980, 0, 1);
  upperBound.setDate(upperBound.getDate() + 365 * 3);

  var yearsApart = fmtDateYY(upperBound) - fmtDateYY(lowerBound);

  function updateValues(event, ui){
    displayValues(ui.label, ui.values)
  }
  function formatDate(date_obj){
    var month = date_obj.getUTCMonth() + 1;
    var day = date_obj.getUTCDate();
    return [date_obj.getFullYear(), pad(month), pad(day)].join("-");
  }
  function displayValues(slider, values){
    if (values.min instanceof Date) {
      var min = $("input[name=search_date_min]");
      var max = $("input[name=search_date_max]");
      min.val(formatDate(values.min));
      max.val(formatDate(values.max));
      currentMinDate = min.val();
      currentMaxDate = max.val();
    }
  }

  $("#defaultDateSlider").dateRangeSlider({
    defaultValues: {min: lowerBound, max: upperBound},
    bounds: {min: lowerBound, max: upperBound},
    valueLabels: "hide",
    arrows: false,
    formatter: function(value){
        var month = value.getMonth() + 1;
        return [value.getFullYear(), pad(month)].join("-");
      },
  })
  .bind("valuesChanging", function(event, ui) {updateValues(event, ui)});

  $("input[name=search_date_min]")
    .focus(function(even, ui) {
      currentMinDate = $(this).val();
    })
    .change(function() {
      var date = $(this).val() + ' 00:00:00';
      var newDate = new Date(date);
      if (newDate < upperBound && newDate > lowerBound){
        $("#defaultDateSlider").dateRangeSlider("min", newDate);
      } else{
        $(this).val(currentMinDate);
      }
    });
  $("input[name=search_date_max]")
    .focus(function() {
      currentMaxDate = $(this).val();
    })
    .change(function() {
      var date = $(this).val() + ' 00:00:00';
      newDate = new Date(date);
      if (newDate < upperBound && newDate > lowerBound){
        $("#defaultDateSlider").dateRangeSlider("max", newDate);
      } else{
        $(this).val(currentMaxDate);
      }
    });

  $("#timeline1").html(fmtDateYY(lowerBound));
  $("#timeline2").html(fmtDateYY(lowerBound) + Math.ceil(yearsApart * 0.2));
  $("#timeline3").html(fmtDateYY(lowerBound) + Math.ceil(yearsApart * 0.45));
  $("#timeline4").html(fmtDateYY(lowerBound) + Math.ceil(yearsApart * 0.70));
  $("#timeline5").html(fmtDateYY(upperBound));
});
