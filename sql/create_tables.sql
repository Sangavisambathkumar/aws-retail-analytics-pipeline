
CREATE EXTERNAL TABLE IF NOT EXISTS
retail_analytics.retail_sales (
    invoice_no STRING,
    stock_code STRING,
    description STRING,
    quantity BIGINT,
    invoice_date TIMESTAMP,
    unit_price DOUBLE,
    customer_id STRING,
    country STRING,
    is_return BOOLEAN,
    transaction_type STRING,
    revenue DOUBLE,
    year INT,
    month INT,
    year_month STRING
)
STORED AS PARQUET
LOCATION 's3://retail-analytics-sang-001/processed/';
