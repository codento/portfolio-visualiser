
var db_json;

function fourField(json, xToBe, yToBe, radToBe, startDate, endDate, sliderValues) {
	// console.log(json);

	var projects = [],
			colorToBe = 'AssociatedOrganizationDimension',
			// size of the display box and other scaling related variables
			sliderHeight = 50,
			fieldWidth = $(window).height()*0.85,
			svgHeight = fieldWidth + sliderHeight,
			margin = {right: fieldWidth * 0.05, left: fieldWidth * 0.05, top: fieldWidth * 0.05, bottom: sliderHeight},
			axisLengthX = fieldWidth * 0.9,
			axisLengthY = fieldWidth * 0.9,
			sliderY = fieldWidth,
			percentInPx = (axisLengthX / (2*sliderValues)) * 100,
			// variables for default dates
			startDefault = 0,
			endDefault = 0;

	// The scales for the x and y axis.
	// range means the length of the line and domain the numbers beneath it
	var scaleX = d3.scaleLinear()
				   			 .range([0,axisLengthX])
				   	 		 .domain([-1 * sliderValues, sliderValues]);

	var scaleY = d3.scaleLinear()
				   			 .range([0,axisLengthY])
				   	 		 .domain([sliderValues,-1 * sliderValues]);

	//list for the organizations
	var organizations = [];

	for (j = 0; j < json.length; j++) {
		var size = json[j].dimensions.length;
		//inProgress is object which will contain the data from 1 project.
		var inProgress = {
			"name": json[j].name,
			"organization": "",
			"xAxisActual": [],
			"xAxisPlanned": [],
			"xAxis": 0,
			"radius": [],
			"yAxisActual": [],
			"yAxisPlanned": [],
			"yAxis": 0
		};
		var xID = 0,
				yID = 0;

		for (i = 0; i < size; i++) {
			var dimension = json[j].dimensions[i];
	    if (dimension.dimension_type == 'DecimalDimension' ) {
				// collectVal is array which will contain a value and a corresponding
				// date. The type of the values is determined later (budget, manHours etc.).
				var collectVal = [];
				var historyList = dimension.dimension_object.history;
				var historyLen = historyList.length;
				for (h = 0; h < historyLen; h++) {
					var date = historyList[h].history_date;
					var planned = historyList[h].value;
					var parsedDate = new Date(date).getTime() / 1000 // parsing date to timestamp. It is divided by 1000 since JS timestamp is in milliseconds.
					setDateScale(parsedDate)
					collectVal.push([parsedDate, planned])
				};
				// here we determine the type of the array, set the inProgress arrays.
				var valueName = dimension.dimension_object.name;
				if ( valueName === xToBe) {
					xID = dimension.id // x-axis id is saved. This value is used in the milestone-loop.
					inProgress.xAxisActual = (collectVal).reverse();
				} else if (valueName === yToBe) {
					yID = dimension.id // y-axis id is saved. This value is used in the milestone-loop.
					inProgress.yAxisActual = (collectVal).reverse();
				} else if (valueName === radToBe) {
					inProgress.radius = (collectVal)
				}
			} else if (dimension.dimension_type === colorToBe ) {
				inProgress.organization = dimension.dimension_object.history[0].value.name
				organizations.push(dimension.dimension_object.history[0].value.name)
			};

		}
		var collectXPlan = [], // array for x-axis milestones
				collectYPlan = []; // array for y-axis milestones

		if(json[j].milestones != undefined) {
			for(e = 0; e < json[j].milestones.length ; e++ ) {
				var milestone = json[j].milestones[e];
	      if(milestone.dimensions != undefined) {
		      for(q = 0; q < milestone.dimensions.length ; q++ ) {
		        if(milestone.dimensions[q].project_dimension == xID) {	// ADD X
		          var date = milestone.due_date,
		          		parsedDate = new Date(date).getTime() / 1000,
		              milestoneValue = milestone.dimensions[q].dimension_milestone_object.value;
		          collectXPlan.push([parsedDate,milestoneValue])
		        } else if( milestone.dimensions[q].project_dimension == yID ) {	// ADD Y
		          var date = milestone.due_date,
		          		parsedDate = new Date(date).getTime() / 1000,
		          		milestoneValue = milestone.dimensions[q].dimension_milestone_object.value;
		          collectYPlan.push([parsedDate,milestoneValue])
		        }
						setDateScale(new Date(date).getTime() / 1000)
		    	}
      	}
    	}
		//pushing the milestone-arrays to inProgress, and push inProgress to projects-array.
		inProgress.xAxisPlanned = (collectXPlan)
		inProgress.yAxisPlanned = (collectYPlan)
		projects.push(inProgress);
		}
	}

	var uniqueOrganizations = organizations.filter( onlyUnique );

	var fourFieldColors = enoughColors(uniqueOrganizations.length, colors);

	//creating colorscale for the visualization
	var colorScale = d3.scaleOrdinal()
										.domain(uniqueOrganizations)
										.range(fourFieldColors);

	mmddyy = d3.timeFormat("%m/%d/%Y");

	if (isNaN(startDate)) {
		startDate = startDefault;
		$('#start-date-selector').val(mmddyy(startDate*1000));
	}
	if(isNaN(endDate)) {
		endDate = endDefault;
		$('#end-date-selector').val(mmddyy(endDate*1000));
	}

// console.log(projects);

/***********************/
/* functions live here */
/***********************/

	//function to determine the x-coordinate of a circle in the graph.
	function x(d) {
		return margin.left + (sliderValues/100 + d.xAxis) * percentInPx
	}
	//function to determine the y-coordinate of a circle in the graph.
	function y(d) {
		return margin.top + (sliderValues/100 + d.yAxis) * percentInPx
	}
	/*function to determine the radius of a circle in the graph.
	 *If given location is not valid, the radius is set to 0, and the circle is not displayed
	 */
	function radius(d) {
		if (validLocation(d)) {
			console.log("true")
			return d.radius;
		} else {
			// console.log("false");
			d.radius = 0
			return d.radius;
		}
	}
	//This function is for the filter to rule out not unique values from array
	function onlyUnique(value, index, self) {
    return self.indexOf(value) === index;
	}
	/*
	 * Helps to set timescale-slider by min&max values of
	 * given data points and milestones
	 */
	function setDateScale(date) {
		if (startDefault == 0 && endDefault == 0) {
			startDefault = date
			endDefault = date
			return;
		}
		if (date > endDefault) {
			endDefault = date
		} else if (date < startDefault) {
			startDefault = date
		}
	}

  /* If
	 * 1) y- or x-coordinates are infinite (the ball lacks milestones or dimension values)
	 * or
	 * 2) Ball location is outside of given axis
	 * the calculated location will not be valid
	 */
	function validLocation(d) {
		return (
		d.yAxis !== -Infinity &&
		d.yAxis !== Infinity &&
		d.xAxis !== Infinity &&
		d.xAxis !== -Infinity &&
		y(d) > margin.top  &&
		x(d) > margin.left &&
		y(d) < (margin.top + axisLengthY) &&
		x(d) < (margin.left + axisLengthX));
	}
	function validXCoordinates(d) {
		if(!isNaN(d)) {return Math.min(Math.max(d,0),fieldWidth) } else {return 0};
	}
	function validYCoordinates(d) {
		if(!isNaN(d)) {return Math.min(Math.max(d,0),fieldWidth) } else {return 0};
	}

	//function to determine color of the circle. Currently is set to color the circles by their "AssociatedOrganizationDimension"
	function color(d) { return colorScale(d.organization); }
	function key(d) { return d.name; }

	// Positions the dots based on data.
	function position(dot) {
		dot.attr("cx", function(d) { return validXCoordinates(x(d)) ; })
		   .attr("cy", function(d) { return validYCoordinates(y(d)); })
		   .attr("r", function(d) { return Math.min(Math.max( radius(d),0 ),100); });
	}

	// Set ball locations and date label value
	function setBalls(date) {
		dot.data(interpolateData(date), key).call(position).sort(order);
		  dateLabel.text(parseDate((new Date(date*1000))));
	}

	// interpolate data of the given day
	function interpolateData(date) {
		return projects.map(function(d) {
		  return {
				name: d.name,
				organization: d.organization,
				xAxis: processValues(interpolateValues(d.xAxisActual, date),interpolateValues(d.xAxisPlanned, date)),
				yAxis: processValues(interpolateValues(d.yAxisActual, date),interpolateValues(d.yAxisPlanned, date)),
				radius: interpolateValues(d.radius, date)
		  };
		});
	}
	// this function returns the required % in decimal form to position the circle correctly.
	function processValues(actual,planned) {
		return ( ((actual/planned) -1))
	}

	/*
    this function interpolates the values of the given array "values", and returns the value that is in the date "date".
    is used in interpolateData-function.
	*/
	function interpolateValues(values, date) {
		if(values == undefined || date == undefined) {
			//array containing the data is undefined, most likely the data never existed.
			//The value will be eventyally set to 0.
			return 0;
		}
		var i = bisect.left(values, date, 0, values.length - 1),
			a = values[i];
		if(a == undefined) {
			return 0;
		} else if(a.length == 0) {
			return 0;
		}
		if (i > 0) {
		  var b = values[i - 1],
			  t = (date - a[0]) / (b[0] - a[0]);
		  return a[1] * (1 - t) + b[1] * t;
		}
		return a[1];
	  }
		//Bisector for interpolation
		var bisect = d3.bisector(function(d) { return d[0]; });

		// The function compares the radius of circles a and b and
		//then with the sort command aligns the smaller circle in front of the bigger one
		function order(a, b) {
			return radius(b) - radius(a);
		}
/*********************************/
/* Graph elements live down here */
/*********************************/

		//container for everything
		var svg = d3.select("#visualization").append("svg")
					.attr("width", fieldWidth)
					.attr("height", svgHeight);

		//Parser for a human readable date format dd. mm. yyyy
		var parseDate = d3.timeFormat("%d. %m. %Y");

		// Add the date label; the value is set on transition.
		var dateLabel =  svg.append("text")
							.attr("class", "currentDate")
							.attr("text-anchor", "end")
							.attr("y", svgHeight - 100)
							.attr("x", fieldWidth )
							.text(parseDate((new Date(startDate*1000))));

		//slider start & stop values
		var labelStart = parseDate(startDate * 1000)
		var labelEnd = parseDate(endDate * 1000)
		//label for the start date next to the slider
		var sSLabel = svg.append("text")
						 .attr("class", "sliderLabel")
						 .attr("text-anchor", "start")
						 .attr("x", 0)
						 .attr("y", svgHeight)
						 .text("Start date: " + labelStart);

		//label for the end date next to the slider
		var sELabel = svg.append("text")
						.attr("class", "sliderLabel")
						.attr("text-anchor", "end")
						.attr("x", fieldWidth)
						.attr("y", svgHeight)
						.text("End date: " + labelEnd);
		//label for project-name. visible when cursor is hovered over the circle representing the project
		var namelabel =  svg.append("text")
							.attr("class", "info")
							.attr("text-anchor", "start")
							.attr("y", 80)
							.attr("x", 20)
							.text("");

		//label for the organizations
		var orglabel = svg.append("text")
						  .attr("class", "info")
						  .attr("text-anchor", "start")
						  .attr("y", 140)
						  .attr("x", 20)
						  .text("");
		//label for x-axis
		var xlabel = svg.append("text")
						  .attr("class", "axisLabel")
						  .attr("text-anchor", "start")
						  .attr("y", 240)
						  .attr("x", 20)
						  .text("x-axis: "+xToBe);
		//label for y-axis
		var ylabel = svg.append("text")
						  .attr("class", "axisLabel")
						  .attr("text-anchor", "start")
						  .attr("y", 340)
						  .attr("x", 20)
						  .text("y-axis: "+yToBe);

		// Place and colorise circles, and define mouseenter and mouseleave functions
		var dot = svg.append("g")
					  .attr("class", "dots")
					  .selectAll(".dot")
					  .data(interpolateData(startDate))
					  .enter().append("circle")
					  .attr("class", "dot")
						.attr("name", function(d) { return d.name;})
						.attr('fill-opacity', 0.8)
					  .style("fill", function(d) { return colorScale(color(d)); })
					  .call(position)
						.sort(order)
						.on("mouseenter", function(d) {
							namelabel.text(d.name);
							orglabel.text(d.organization);
							dot.style("opacity", .4)
							d3.select(this).style("opacity", 1)
							d3.selectAll(".selected").style("opacity", 1)
						})
						.on("mouseleave", function(d) {
							namelabel.text("");
							orglabel.text("");
							dot.style("opacity", 1);
						})

	//Timescale under the graph
	var scaleDate = d3.scaleTime()
						.domain([startDate*1000, endDate*1000])
						.range([0, axisLengthX])
						.clamp(true); //keeps the slider on the scale

	//building the timeScale-slider
	var timeAxis = svg.append("g")
					  .attr("class","slider")
					  .attr("transform", "translate("+margin.right+","+sliderY+")");

	timeAxis.append("line")
			.attr("class", "track")
			.attr("x1", scaleDate.range()[0])
			.attr("x2", scaleDate.range()[1])
			.select(function() { return this.parentNode.appendChild(this.cloneNode(true)); })
			.attr("class", "track-overlay")
			.call(d3.drag()
					.on("start drag", function() {
		  		setBalls((scaleDate.invert(d3.event.x)/1000)); /*relocates the balls by given date*/
					handle.attr("cx", scaleDate(scaleDate.invert(d3.event.x))); /*moves the slider handle*/
												 }));

	// Slider handle
	var handle = timeAxis.insert("circle", ".track-overlay")
						  .attr("class", "handle");

	  // The y and x axis are moved in to place
	  svg.append("g")
		 .attr("class", "xAxis")
		 .attr("transform", "translate("+margin.left+","+(fieldWidth / 2)+")")
		 .call(d3.axisBottom(scaleX));

	  svg.append("g")
		 .attr("class", "yAxis")
		 .attr("transform", "translate("+fieldWidth / 2+","+margin.top+")")
		 .call(d3.axisLeft(scaleY));
return svg;
}
