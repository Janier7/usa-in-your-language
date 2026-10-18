const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const context=vm.createContext({URL,location:{origin:'https://example.test'},console,Date,Number,Error});
vm.runInContext(fs.readFileSync(require('path').join(__dirname,'..','admin-modules.js'),'utf8'),context);
const rows=[
{id:1,entry_date:'2026-09-01',kind:'adjustment',amount_cents:10000},
{id:2,entry_date:'2026-10-01',kind:'income',category:'membership',amount_cents:2500,activation_at:'2026-10-01T00:00:00Z'},
{id:3,entry_date:'2026-10-02',kind:'income',category:'membership',amount_cents:2500,activation_at:'2026-09-01T00:00:00Z'},
{id:4,entry_date:'2026-10-03',kind:'income',category:'promotion',amount_cents:1000},
{id:5,entry_date:'2026-10-04',kind:'expense',category:'hosting',amount_cents:4000}];
let inserted;const cloud={from:()=>({select(){return this},lt(){return this},order(){return this},range(){return Promise.resolve({data:rows,error:null})},insert(row){inserted=row;return Promise.resolve({data:null,error:null})}})};
const unwrap=async p=>{const r=await p;if(r.error)throw r.error;return r.data};
(async()=>{const api=context.moduleApi;const r=await api(cloud,['finance'],unwrap,'/api/admin/statement?month=2026-10','GET');assert.equal(r.opening_cents,10000);assert.equal(r.new_accounts_cents,2500);assert.equal(r.existing_accounts_cents,2500);assert.equal(r.income_cents,6000);assert.equal(r.expenses_cents,4000);assert.equal(r.closing_cents,12000);assert.equal(r.entries.length,4);await assert.rejects(api(cloud,[],unwrap,'/api/admin/statement?month=2026-10','GET'));await assert.rejects(api(cloud,['finance'],unwrap,'/api/admin/ledger','POST',{amount:'1e6'}));await api(cloud,['finance'],unwrap,'/api/admin/ledger','POST',{amount:'12.34',date:'2026-10-01',kind:'income',category:'other',description:'QA',request_key:'test'});assert.equal(inserted.amount_cents,1234);console.log('PASS: monthly statement, balance carryover, cohorts, permissions and exact cent input.')})().catch(e=>{console.error(e);process.exit(1)});
