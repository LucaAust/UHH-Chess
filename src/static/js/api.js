
function ApiError(message) {
    'use strict';
    this.message = message;
    this.name = "ApiError";
}

class Api{
    constructor() {
    }

    sendRequest(url, data, request_type, return_only_success_stat) {

        if (!data){
            data = {};
        }

        let xmlHttp = new XMLHttpRequest();

        request_type = request_type ? request_type : "GET";
        console.log(request_type, url);

        xmlHttp.open( request_type, url, false );

        if (request_type.toUpperCase().indexOf(['POST', 'PUT'])){
            xmlHttp.setRequestHeader('Content-Type', 'application/json');
            xmlHttp.send(JSON.stringify({data}));
        }else{
            xmlHttp.send( null );
        }

        if (return_only_success_stat){
            return xmlHttp.status < 400;
        }

        // try to parse response json
        try{
            return JSON.parse(xmlHttp.responseText);
        }catch (err){
            if (xmlHttp.status < 400){
                return xmlHttp.responseText;
            } else {
                throw new ApiError("Server responds with error: " + xmlHttp.status);
            }
        }
    }

    //delete(url_path, return_only_success_stat){
    //    return this.sendRequest(url_path, null, "DELETE", return_only_success_stat);
    //}

    //post(url_path, id, data, return_only_success_stat){
    //    return this.sendRequest(url_path, data , "POST", return_only_success_stat);
    //}

    put(url_path, data, return_only_success_stat){
        return this.sendRequest(url_path, data , "PUT", return_only_success_stat);
    }

    get(url_path, return_only_success_stat){
        return this.sendRequest(url_path, return_only_success_stat);
    }

    getCookie(cname) {
        var name = cname + "=";
        var decodedCookie = decodeURIComponent(document.cookie);
        var ca = decodedCookie.split(';');
        for(var i = 0; i <ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0) == ' ') {
                c = c.substring(1);
            }
            if (c.indexOf(name) == 0) {
                return c.substring(name.length, c.length);
            }
        }
        return "";
    }
}


let api = new Api();
