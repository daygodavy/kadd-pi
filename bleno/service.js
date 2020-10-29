var bleno = require('bleno');
var BlenoPrimaryService = bleno.PrimaryService;


bleno.on('stateChange', function(state) {
	console.log('on -> stateChange: ' + state);
	if (state === 'poweredOn') {
		console.log("request Kadd - startAdvertising");
		bleno.startAdvertising('KaddService', ['27cf08c1-076a-41af-becd-02ed6f6109b9']);
	} else {
		console.log("request Kadd stopAdvertising");
		bleno.stopAdvertising();
	}
});

var kaddDataCharacteristic = require('./characteristic');
var kaddInitCharacteristic = require('./setup-characteristic');
bleno.on('advertisingStart', function(error) {
	console.log('on -> Kadd advertisingStart: ' + (error ? 'error' + error : 'success'));
	if (!error) {
		bleno.setServices([
			new BlenoPrimaryService({
				uuid: '27cf08c1-076a-41af-becd-02ed6f6109b9',
				characteristics: [
					new kaddDataCharacteristic(),
                    new kaddInitCharacteristic()
				]
			})
		]);
	}
});


