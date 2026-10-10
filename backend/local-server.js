// Persistent, isolated local MongoDB; no connection to the ZIP's cloud database.
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const { MongoMemoryServer } = require('mongodb-memory-server');
async function main() {
  const root=path.resolve(__dirname,'..'); const directory=path.join(root,'.local-data');
  fs.mkdirSync(path.join(directory,'mongo'),{recursive:true});
  const secretPath=path.join(directory,'jwt-secret.txt');
  if (!fs.existsSync(secretPath)) fs.writeFileSync(secretPath,crypto.randomBytes(48).toString('hex'));
  process.env.JWT_SECRET=fs.readFileSync(secretPath,'utf8');
  process.env.MONGODB_URI='';process.env.MONGODB_DB_NAME='SmartVehicleInventoryLocal';
  process.env.MONGODB_LOCAL_URI='mongodb://127.0.0.1:27028/SmartVehicleInventoryLocal';
  process.env.PORT='5008';process.env.HOST='127.0.0.1';process.env.SEED_INVENTORY_DEMO='1';
  process.env.INVENTORY_ML_URL='http://127.0.0.1:8770';
  const mongo=await MongoMemoryServer.create({binary:{version:'7.0.14'},instance:{ip:'127.0.0.1',port:27028,dbPath:path.join(directory,'mongo'),storageEngine:'wiredTiger'},auth:{enable:false}});
  const stop=async()=>{await mongo.stop({doCleanup:false});process.exit(0);};
  process.on('SIGINT',stop);process.on('SIGTERM',stop);
  require('./src/app');
}
main().catch(error=>{console.error('Local startup failed:',error.message);process.exit(1);});
