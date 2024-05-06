
var mapClicked = false;

var randomIndex = Math.floor(Math.random() * cities_list.length);
var random_city = cities_list[randomIndex];
cities_list.splice(randomIndex,1)
var polyline
var score = 0
var question = 1

function next_question(){

    if (!mapClicked) return
    
    console.log(total_cites)
    if (cities_list.length <= 18){
        //post score
        fetch('/scores', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
                body: 'score=' + encodeURIComponent(score)
        }).then(window.location.href = '/view_leaderboard')
    }


    randomIndex = Math.floor(Math.random() * cities_list.length);
    random_city = cities_list[randomIndex];
    cities_list.splice(randomIndex,1)

    

    mapClicked = false
    mymap.removeLayer(polyline)
    mymap.on('click', onMapClick);
    //remove existing line

    

    question += 1
    render_variables()
}

function render_variables(){
    document.getElementById("find_text").innerHTML = "Find: " + random_city.name
    document.getElementById("score_text").innerHTML = "Total Score: " + score
    document.getElementById("question_text").innerHTML = "Question: " + question + "/" + total_cites  
}

document.onload = render_variables()




var mymap = L.map('map', {
    center: [0, 0],
    zoom: 2,
    minZoom: 2.3,
    maxZoom: 10,
    maxBounds: [
        [-90, -180], 
        [90, 180]    
    ],
    maxBoundsViscosity: 1.0
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap contributors',
    noWrap: true
}).addTo(mymap);


function onMapClick(e) {
    if (!mapClicked) {
        var clickedLatLng = e.latlng;
        var cityLatLng = L.latLng(random_city.latitude, random_city.longitude);
        var distance = clickedLatLng.distanceTo(cityLatLng);
        var threshold = 500000; // 500 km 

        // score based on distance
        var distanceScore = Math.max(0, 1000 - Math.floor(distance / 1000));
        score += distanceScore;

        polyline = L.polyline([clickedLatLng, cityLatLng], {color: distance <= threshold ? 'green' : 'red'}).addTo(mymap);
        var popup = L.popup()
            .setLatLng(clickedLatLng)
            .setContent("Distance: " + (distance / 1000).toFixed(2) + " km<br>Score: " + distanceScore)
            .openOn(mymap);

        mapClicked = true;
        mymap.off('click', onMapClick);
        render_variables();
    }
}

mymap.on('click', onMapClick);