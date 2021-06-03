var nodes = []; //this is an array that holds all nodes

var layout; //this is the layout of the whole map, all distances etc. included

var cars = []; //array with all car objects on map

var numNodes = 0;
var _numNodes = 0;

var nodeIndexIterator = 0; //this counts up to create a new index for every node every time

var selectedNode; //this is the currently selected node


function setup() {
  canvas = createCanvas(windowWidth, windowHeight);
  // canvas.position(0, 0);


  // nodes.push(new Node(100, 50))
  nodes.push(new Node(width * 0.1, height * 0.1))
  nodes.push(new Node(width * 0.8, height * 0.8))



  // nodes.push(new Node(300, 220))

  selectNode(1);
}

function windowResized() {
  //console.log('resized');
  resizeCanvas(windowWidth, windowHeight);
}


function draw() {
  numNodes = nodes.length;
  if (numNodes != _numNodes) {
    console.log("SOMETHING CHANGED");
    layout = getLayout();
    console.log(layout);

  }

  textSize(16);

  // background(255);
  clear();

  drawNodes();

  drawCars();

  _numNodes = numNodes;
}

function keyPressed() {
  if (keyCode == 32) {

    //get the layout in a global variable
    layout = getLayout();

    //get all the nodes in the layaout
    var possibleTargets = Object.keys(layout);

    //the point where we are going to spawn a new car
    var carTarget;

    //find a random point to spawn car
    while(carTarget == undefined) {
      carTarget = possibleTargets[Math.floor(Math.random()*possibleTargets.length)];
    }

    console.log("Creating new car at " + carTarget);

    //create the car in the cars array
    cars.push(new Car(carTarget));


  } else if (keyCode == 68) {
    createDefaultMap();
  }

}


function mousePressed() {

  var clickedOnNode = false;

  //for every node
  for (let i = 0; i < nodes.length; i ++) {
    //check if the mouse is closer than 50 pixels to the node
    if (dist(mouseX, mouseY, nodes[i].x, nodes[i].y) < 20) {


      console.log("clicked on node " + nodes[i].id);
      clickedOnNode = true;

      //if we hold control while clicking on a node, select that node
      if (keyIsDown(CONTROL)) {
        selectNode(nodes[i].id);
      } else if (selectedNode != undefined) {
        //else if there is no node selected yet, select that node regardless
        connectNodes(nodes[i].id, selectedNode.id)
      }

    }
  }

  //if we did not click on a node, and if the mouse is in the screen
  if (clickedOnNode == false && mouseX > 0 && mouseX < width && mouseY > 0 && mouseY < height) {

    //if we have a selected node
    if (selectedNode != null) {
      //deselect the last selected node so we can select the next new one
      selectedNode.selected = false;

      var lastNodeId = selectedNode.id;
    }



    console.log("mouse is pressed, creating new node");
    //create a new node that is selected by default
    let newNode = new Node(mouseX, mouseY, true);
    //add node to the array of nodes
    nodes.push(newNode);

    console.log(nodes);

    if (lastNodeId != undefined) {
      connectNodes(lastNodeId, newNode.id)
    }
  }
}

function connectNodes(nodeOne, nodeTwo) {
  //this function connects two ndoes by adding their numbers to eachothers connection array
  console.log("Connecting nodes: " + nodeOne + " to " + nodeTwo);

  var nodeOneObj = nodes.find(x => x.id === nodeOne);
  var nodeTwoObj = nodes.find(x => x.id === nodeTwo);

  if (nodeOneObj == undefined || nodeTwoObj == undefined) {
    return false;
  }
  nodeOneObj.connections.push(nodeTwo);
  nodeTwoObj.connections.push(nodeOne);
}

function selectNode(id) {
  //this function selects a node with a certain id and deselects all eachothers
  for (var i = 0; i < nodes.length; i ++ ) {
    if (nodes[i].id == id) {
      nodes[i].selected = true;
      selectedNode = nodes[i];
      console.log("Selected node " + id);
    } else {
      nodes[i].selected = false;
    }
  }
}

function drawNodes() {
  //for every node in the network
  for (let i = 0; i < nodes.length; i ++) {
    //draw it
    nodes[i].draw();
  }
}

function drawCars() {
  //for every car in the network
  var carHovered = false; //whether any car is hovered right now
  var hoveredCar = 0; //what car got hovered?

  for (let i = 0; i < cars.length; i ++) {
    //draw it
    var drawResult = cars[i].draw();

    if (dist(mouseX, mouseY, cars[i].x, cars[i].y) < 20) {
      cars[i].highlightRoute();
      cars[i].hovered = true;
    } else {
      //set this car to not hovered
      cars[i].hovered = false;
    }

    if (!drawResult) {
      //do something because this car could not be drawn
    }
  }

  for (let i = 0; i < nodes.length; i ++) {
    nodes[i].highlighted = false;
  }

}

function createDefaultMap() {

  //convert default map into readable object
  layout = JSON.parse(defaultMap);

  console.log("Created default map")
  console.log(layout);

  recreateLayout();

}

function recreateLayout() {
  var newNodes = Object.keys(layout);


  //remove all existing nodes
  nodes = [];
  nodeIndexIterator = 0;

  //go through all nodes in the default map and create their objects
  for (let i = 0; i < newNodes.length; i ++ ) {
    //get the object for a single node from json
    newNode = layout[newNodes[i]];
    // console.log(newNode);

    //get the coordinatses
    let newNodeX = newNode.x;
    let newNodeY = newNode.y;

    //spawn the node at the coordinates
    nodes.push(new Node(newNodeX, newNodeY, false));

    nodes[i].id = Number(newNodes[i]);

    console.log("Created node");
    console.log(nodes[i]);
  }


  //now go through all nodes again (not optimal I know) and recreate their connections
  //you cant do this in the first loop because not all nodes exist at that point
  console.log("Connecting all nodes together...");
  for (let i = 0; i < newNodes.length; i ++ ) {
    //retreive this node from array
    let currentNode = layout[newNodes[i]];
    console.log("Connecting node " + newNodes[i]);
    console.log(currentNode);
    //get all keys this node is supposed to have
    let currentNodeKeys = Object.keys(currentNode);
    for (let c = 0; c < currentNodeKeys.length; c ++) {
      let key = currentNodeKeys[c];

      //if this key is a number, it is a node-connection
      if (!isNaN(key)) {
        console.log("Connecting " + newNodes[i] + " to : " + key);
        let connection = connectNodes(Number(newNodes[i]), Number(key));
        if (connection == false) {
          console.log("Failed to connect " + newNodes[i] + " to " + key) ;
        }
      }
    }
  }

}
