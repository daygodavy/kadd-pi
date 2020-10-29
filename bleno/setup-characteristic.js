var util = require('util');
var bleno = require('bleno');
var sdp = require('./index.js');
var fs = require('fs');
var xml2js = require('xml2js');
var parser = require('fast-xml-parser');
var builder = require('xmlbuilder');
// Properties
var blenoCharacteristic = bleno.Characteristic;
//var parser = new xml2js.Parser();

var file = fs.readFileSync('./about.xml', 'utf8');
var xmlData = parser.parse(file);
var tokens = null;


// Init Characteristic
var kaddInitCharacteristic = function() {
    kaddInitCharacteristic.super_.call(this, {
                           uuid: 'c37ce97e-40cb-4875-9886-df66323f6e4c',
                           properties: ['read', 'write', 'notify'],
                        });
    this._value = new Buffer(0);
    this.UpdateValueCallback = null;
};
util.inherits(kaddInitCharacteristic, blenoCharacteristic);
module.exports = kaddInitCharacteristic;

function writeXML(tokens) {

	fs.readFile("about.xml", "utf-8", (err, data) => {
		if (err) {
			throw err;
		}

		xml2js.parseString(data, (err, result) => {
			if (err) {
				throw err;
			}
			result.kaddpi.devId = tokens[1];
			result.kaddpi.uid = tokens[0];
			result.kaddpi.geofenceRadius = tokens[2];
			result.kaddpi.geofenceLat = tokens[3];
			result.kaddpi.geofenceLong = tokens[4];
			result.kaddpi.phone = tokens[5];
			
			console.log(result);

			// new xml
			const builder = new xml2js.Builder();
			const xml = builder.buildObject(result);

			// overwrite file
			fs.writeFileSync("./about.xml", xml);
		})

	})

}

// kadd init read
kaddInitCharacteristic.prototype.onReadRequest = function (offset, callback) {
    console.log('Kadd Characteristic onReadRequest');

	var data = Buffer.from(xmlData.kaddpi.model + ',' + xmlData.kaddpi.serial + ',' + xmlData.kaddpi.manufacturer); 
	console.log('DATA READ: ' + data);
	callback(this.RESULT_SUCCESS, data);
};

// kadd init write
kaddInitCharacteristic.prototype.onWriteRequest = function(data, offset, withoutResponse, callback) {
    	this._value = data;
    	console.log('Kadd Characteristic - onWriteRequest: value = ' + this._value.toString('utf8'));
    	var string = this._value.toString('utf8');
	// tokens: userid, device name, gf radius, latitude, longitude
	tokens = string.split(",");
	console.log(tokens);
	writeXML(tokens);
	callback(this.RESULT_SUCCESS);
};
