var util = require('util');
var bleno = require('bleno');
// Includes
var sdp = require('./index.js');
var assert = require('chai').assert;
var fs = require('fs');

// Properties
var blenoCharacteristic = bleno.Characteristic;
var datagramCount = 0;
var message = fs.readFileSync('./juice.txt');
var messageLength = message.byteLength;
var packetSize = 100;
var totalPackets = getPacketCount(messageLength, packetSize);
var datagramView = new sdp.DatagramView(message, 0, packetSize);

// Private Functions
var generateBuffer = function(length) {
	var buffer = Buffer.alloc(length);
	for (var i = 0; i < length; i++) {
		buffer[i] = i % 255;
	}
	return buffer;
}
function delayedNotification(callback) {
    setTimeout(function() {
        if (isSubscribed) {
            var data = new Buffer(3);
            var now = new Date();
            data.writeUInt8(now.getHours(), 0);
            data.writeUInt8(now.getMinutes(), 1);
            data.writeUInt8(now.getSeconds(), 2);
            callback(data);
            delayedNotification(callback);
        }
    }, notifyInterval * 1000);
}
// get total datagrams
function getPacketCount(messageSize, packetSize) {
	var payload = packetSize - 9;
	var totalPacket = messageSize / payload;
	if (messageSize % payload === 0) {
		return totalPacket;
	}
	return totalPacket;
}

// Define Kadd Characteristic
var kaddCharacteristic = function() {
	kaddCharacteristic.super_.call(this, {
        uuid: 'fd758b93-0bfa-4c52-8af0-85845a74a606',
		properties: ['read', 'write', 'notify'],
	});
	this._value = new Buffer(0);
	this.UpdateValueCallback = null;
};
util.inherits(kaddCharacteristic, blenoCharacteristic);
module.exports = kaddCharacteristic;

// Kadd Read
kaddCharacteristic.prototype.onReadRequest = function (offset, callback) {
	console.log('Kadd Characteristic onReadRequest');
	console.log('Message Length: ' + messageLength);
	console.log('Total Packets: ' + totalPackets);
	console.log('Message Length: ' + messageLength);
	console.log('Offset: ' + datagramCount);
	
	// check datagramcount
	if (datagramCount < totalPackets) {
		console.log('Not the last packet');
		callback(this.RESULT_SUCCESS, datagramView.getDatagram(datagramCount++));
	} else {
		// send FYN packet
		console.log('Sending FYN...');
		var fyn = Buffer.from('yup');

		// create new datagram
		fynDatagramView = new sdp.DatagramView(fyn, 6, 20);
		fynDatagram = fynDatagramView.getDatagram(0);
		// send fyn datagram
		callback(this.RESULT_SUCCESS, fynDatagram);

	}
};

// Kadd Write
kaddCharacteristic.prototype.onWriteRequest = function(data, offset, withoutResponse, callback) {
	// reset datagramCount to 0
	datagramCount = 0;
	this._value = data;
	console.log('Kadd Characteristic - onWriteRequest: value = ' + this._value.toString('hex'));
	console.log('Reset offset: ' + datagramCount);
	callback(this.RESULT_SUCCESS);
};

var isSubscribed = false; 
var notifyInterval = 5;


// Kadd Subscribe
kaddCharacteristic.prototype.onSubscribe = function(maxValueSize, updateValueCallback) {
	console.log('Kadd Characteristic - onSubscribe');
	isSubscribed = true;
	delayedNotification(updateValueCallback);
	this._updateValueCallback = updateValueCallback;
};

// Kadd Unsubscribe
kaddCharacteristic.prototype.onUnsubscribe = function() {
	console.log('Kadd Characteristic - onUnsubscribe');
	isSubscribed = false;
	this._updateCallbackValue = null;
};
