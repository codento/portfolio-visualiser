//  COOOOOOOKIES
function getCookie(name)
{
  var cookieValue = null;
  if (document.cookie && document.cookie !== "") {
      var cookies = document.cookie.split(";");
      for(i = 0; i < cookies.length; i++) {
          var cookie = jQuery.trim(cookies[i]);
          // Does this cookie string begin with the name we want?
          if (cookie.substring(0, name.length + 1) === (name + "=")) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
          }
      }
  }
  return cookieValue;
}
// Cookies and csrf
var csrftoken = getCookie("csrftoken");
function csrfSafeMethod(method)
{
  // these HTTP methods do not require CSRF protection
  return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}
$.ajaxSetup({
  beforeSend: function(xhr, settings) {
    if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
      xhr.setRequestHeader("X-CSRFToken", csrftoken);
    }
  }
});

function addColClick(pid) {
  var lastTds = $('#'+pid+'-tablebody').children('tr').children('td:last-child'),
      lastTh = $('#'+pid+'-tablehead').children('tr:last-child').children('th:last-child'),
      numberInput = $('<input>').attr('class', 'text-center new-mile-field-'+pid)
                                .attr('type', 'number')
                                .attr('step', 0.01);

  $.each(lastTds, function(idx, td) {
    $('<td>').insertAfter(td);
  });
  $('#'+pid+'-tablebody').children('tr')
                         .children('td:last-child')
                         .last()
                         .append(numberInput);
  var ths = $('#'+pid+'-tablehead').children('tr').children();
  var existingMileFields = [];
  $.each(ths, function(idx, th) {
    var id = th.dataset.dimid;
    if(id != undefined) {
      existingMileFields.push(parseInt(id));
    }
  });

  $.ajax({
    method: "GET",
    url: "/get/"+pid+"/fields/",
    data: {'existing': JSON.stringify(existingMileFields)},
    success: function(fields){
      var select = $('<select>').attr('class', 'text-center');
      $.each(fields.fields, function(id, name) {
        select.append($('<option>').attr('value', id).append(name));
      });
      numberInput.attr('name', Object.keys(fields.fields)[0]);
      $('<th>').append(select).insertAfter(lastTh);
      select.change(function() {
        numberInput.attr('name', $(this).val());
      });
    }
  });
}

function checkRows(pid) {
  var inputs = $('.new-mile-field-' + pid),
    errorFree = true;

  inputs.each(function() {
    errorFree = errorFree && ($(this).val() != '');
  });

  return errorFree;
}

function submitRow(pid) {
  var inputs = $('.new-mile-field-' + pid),
      ajaxdata = {'pid': pid};

  inputs.each(function() {
    ajaxdata[$(this)[0].name] = $(this).val();
  });

  $.ajax({
    method: "POST",
    url: "/manage/milestone",
    data: ajaxdata,
    error: function() {
      alert("Milestone wasn't saved! Refresh page to see all saved milestones!");
    }
  });
}

function inputsToCells(pid) {
  var inputs = $(".new-mile-field-" + pid);
  inputs.each(function() {
    if ($(this)[0].type == 'date') {  // Date needs to be formatted
      var dateparts = $(this).val().split("-"),
          datestr = dateparts.reverse().join('/');
      $(this).parent().html(datestr);
    }
    else {
      $(this).parent().html($(this).val());
    }
  });
}

function addClick(btn){
  var pid = $(btn).data('pid'),
    tablebody = $('#' + pid + "-tablebody"),
    inputClass = 'text-center new-mile-field-' + pid,
    due_date_cell = $('<input>').attr('name', 'due_date')
                                .attr('class', inputClass)
                                .attr('type', 'date'),
    row = $('<tr>').append($('<td>').append(due_date_cell)),
    ths = $('#' + pid + '-tablehead').children('tr').children(),
    plus = $('<span>').attr('class', 'glyphicon glyphicon-plus'),
    button = $('<button>').attr('type', 'button')
                          .attr('class', 'btn btn-success add-col-btn text-center')
                          .append(plus);

  $.each(ths, function(idx, th) {
    if( th.innerText != '') {
      row.append($('<td>').append($('<input>')
                           .attr('name', th.dataset.dimid)
                           .attr('class', inputClass)
                           .attr('type', 'number')
                           .attr('step', 0.01)));
    }
  });
  tablebody.append(row);

  row.children()
     .wrapInner('<div style="display:none;"></div>')
     .parent()
     .find('td > div')
     .slideDown(100);

  tablebody.append(button);
  button.click(function() {
    addColClick(pid);
  });

  $(btn).toggleClass('submit');
  $(btn).children('.icons').toggleClass('icons-active');
}

function submitClick(btn) {
  var pid = $(btn).data('pid');
  if(checkRows(pid)) {
    submitRow(pid);
    inputsToCells(pid);

    $(btn).toggleClass('submit');
    $(btn).children('.icons').toggleClass('icons-active');
  }
  else {
    // DO SMARTER ERROR MESSAGE
    alert("Please fill in all the fields!");
  }
}

$(function(){
  $(".add-row-btn").click(function(e){
    if (!$(e.target).hasClass('submit')) {
      addClick(e.target);
    }
    else {
      submitClick(e.target);
    }
  });
});
