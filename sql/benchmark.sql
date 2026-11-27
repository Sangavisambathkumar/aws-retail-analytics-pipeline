-- Benchmark 1: Raw CSV
SELECT
    country,
    COUNT(*) AS transaction_rows,
    SUM(TRY_CAST(quantity AS BIGINT)) AS units
FROM retail_analytics.retail_raw
GROUP BY country;

--Benchmark 2: Processed Parquet
SELECT
    country,
    COUNT(*) AS transaction_rows,
    SUM(quantity) AS units
FROM retail_analytics.retail_sales
GROUP BY country;