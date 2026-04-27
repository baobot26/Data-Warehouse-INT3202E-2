db = db.getSiblingDB("landing");

db.createCollection("orders_raw");

db.orders_raw.createIndex({ order_id: 1 }, { unique: true });

db.orders_raw.insertMany([
  {
    order_id: "ORD-1001",
    sold_at: new Date("2026-03-20T09:15:00Z"),
    quantity: 2,
    price: 120.0,
    discount: 10.0,
    tax: 8.4,
    customer: {
      customer_id: "CUS-001",
      customer_name: "Nguyen Minh Anh",
      phone_number: "0900000001",
      email: "minh.anh@example.com",
      membership: "Gold"
    },
    product: {
      product_id: "PRO-001",
      product_name: "Wireless Earbuds",
      product_category: "Audio",
      product_brand: "SonicWave",
      quantity_in_stock: 140
    },
    retailer: {
      retailer_id: "RET-001",
      retailer_name: "Downtown Store",
      phone_number: "02873000001",
      email: "downtown@example.com",
      rating: 4.7
    },
    address: {
      street: "12 Le Loi",
      commune_ward: "Ben Nghe",
      province_city: "Ho Chi Minh City"
    },
    payment: {
      payment_type: "Card",
      method_provider: "Visa"
    }
  },
  {
    order_id: "ORD-1002",
    sold_at: new Date("2026-03-21T14:45:00Z"),
    quantity: 1,
    price: 899.0,
    discount: 50.0,
    tax: 67.4,
    customer: {
      customer_id: "CUS-002",
      customer_name: "Tran Gia Bao",
      phone_number: "0900000002",
      email: "gia.bao@example.com",
      membership: "Silver"
    },
    product: {
      product_id: "PRO-002",
      product_name: "Gaming Laptop",
      product_category: "Computers",
      product_brand: "NovaTech",
      quantity_in_stock: 24
    },
    retailer: {
      retailer_id: "RET-002",
      retailer_name: "Tech Mall",
      phone_number: "02873000002",
      email: "techmall@example.com",
      rating: 4.9
    },
    address: {
      street: "89 Tran Hung Dao",
      commune_ward: "Cau Ong Lanh",
      province_city: "Ho Chi Minh City"
    },
    payment: {
      payment_type: "E-Wallet",
      method_provider: "MoMo"
    }
  },
  {
    order_id: "ORD-1003",
    sold_at: new Date("2026-03-22T11:10:00Z"),
    quantity: 3,
    price: 35.5,
    discount: 0.0,
    tax: 7.1,
    customer: {
      customer_id: "CUS-001",
      customer_name: "Nguyen Minh Anh",
      phone_number: "0900000001",
      email: "minh.anh@example.com",
      membership: "Gold"
    },
    product: {
      product_id: "PRO-003",
      product_name: "USB-C Charger",
      product_category: "Accessories",
      product_brand: "Voltix",
      quantity_in_stock: 320
    },
    retailer: {
      retailer_id: "RET-001",
      retailer_name: "Downtown Store",
      phone_number: "02873000001",
      email: "downtown@example.com",
      rating: 4.7
    },
    address: {
      street: "12 Le Loi",
      commune_ward: "Ben Nghe",
      province_city: "Ho Chi Minh City"
    },
    payment: {
      payment_type: "Bank Transfer",
      method_provider: "Vietcombank"
    }
  }
]);
