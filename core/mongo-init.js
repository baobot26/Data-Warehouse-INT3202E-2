db = db.getSiblingDB("landing");

db.createCollection("orders_raw");

db.orders_raw.createIndex({ order_id: 1 }, { unique: true });
db.orders_raw.createIndex({ "source.dataset": 1 });

// Source data is loaded explicitly from the Olist importer.
