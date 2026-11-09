import { test } from 'node:test';
import assert from 'node:assert/strict';
import {difference,extrema,formatNumber} from '../src/studentMath.ts';
test('null is excluded, zero and negative numbers remain',()=>{
  const values=[{label:'?',value:null},{label:'A',value:0},{label:'B',value:-5},{label:'C',value:0}];
  assert.deepEqual(extrema(values),{min:-5,max:0,minLabels:['B'],maxLabels:['A','C'],excluded:1});
  assert.equal(difference(values,0,1),null);
  assert.equal(difference(values,1,2),5);
  assert.equal(difference(values,1,1),null);
  assert.equal(difference(values,10,1),null);
});
test('all unknown values never become zero',()=>{
  assert.equal(extrema([{label:'A',value:null},{label:'B',value:null}]),null);
  assert.equal(difference([{label:'A',value:null},{label:'B',value:null}],0,1),null);
});
test('decimals display a deterministic finite difference',()=>{
  assert.equal(formatNumber(difference([{label:'A',value:0.3},{label:'B',value:0.2}],0,1)!), '0.1');
  assert.equal(difference([{label:'A',value:Infinity},{label:'B',value:1}],0,1),null);
  assert.equal(formatNumber(1e-13),'0.0000000000001');
  assert.equal(difference([{label:'A',value:0.3},{label:'B',value:0.2}],0,1),0.1);
});
test('unrepresentable differences are rejected instead of silently rounded',()=>{
  assert.equal(difference([{label:'A',value:1e16},{label:'B',value:1}],0,1),null);
  assert.equal(difference([{label:'A',value:1e308},{label:'B',value:-1e308}],0,1),null);
  assert.equal(difference([{label:'A',value:-2.75},{label:'B',value:1.5}],0,1),-4.25);
});
