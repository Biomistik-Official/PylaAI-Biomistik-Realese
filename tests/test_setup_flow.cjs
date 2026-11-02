const assert = require('node:assert/strict');
const flow = require('../webui/static/setup-flow.js');
assert.equal(flow.stepFor(''), 0);
assert.equal(flow.stepFor('#setup-account'), 1);
assert.equal(flow.stepFor('#setup-brawlers'), 2);
assert.equal(flow.stepFor('#setup-review'), 3);
assert.equal(flow.stepFor('#logs'), -1);
assert.throws(() => flow.next(0, {device:false, queue:1}), /эмулятор/);
assert.equal(flow.next(0, {device:true, queue:0}), '#setup-account');
assert.equal(flow.next(1, {device:true, queue:0}), '#setup-brawlers'); // Account optional.
assert.throws(() => flow.next(2, {device:true, queue:0}), /бойца/);
assert.equal(flow.next(2, {device:true, queue:1}), '#setup-review');
assert.equal(flow.next(3, {device:true, queue:1}), null); // Next never starts a game.
assert.equal(flow.canStart({device:false, queue:1}), false);
assert.equal(flow.canStart({device:true, queue:0}), false);
assert.equal(flow.canStart({device:true, queue:1}), true);
console.log('Setup flow: 13 assertions passed.');
