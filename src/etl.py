
import argparse
import boto3
import pandas as pd
import io
import json
import time


def run_etl(bucket):
    start_time = time.perf_counter()

    s3 = boto3.client("s3")

    raw_key = "raw/online_retail.csv"

    print("Extracting data from S3...")

    response = s3.get_object(
        Bucket=bucket,
        Key=raw_key
    )

    raw_data = response["Body"].read()

    df = pd.read_csv(
        io.BytesIO(raw_data),
        encoding="utf-8-sig",
        dtype={
            "InvoiceNo": "string",
            "StockCode": "string",
            "CustomerID": "string"
        }
    )

    initial_rows = len(df)

    print(f"Original records: {initial_rows}")

    # Standardize column names
    df.columns = [
        col.strip().lower()
        for col in df.columns
    ]

    df = df.rename(columns={
        "invoiceno": "invoice_no",
        "stockcode": "stock_code",
        "invoicedate": "invoice_date",
        "unitprice": "unit_price",
        "customerid": "customer_id"
    })

    # Remove exact duplicate records
    df = df.drop_duplicates()
    duplicate_rows = initial_rows - len(df)

    # Convert data types
    df["invoice_date"] = pd.to_datetime(
        df["invoice_date"],
        format="mixed",
        errors="coerce"
    )

    df["quantity"] = pd.to_numeric(
        df["quantity"],
        errors="coerce"
    )

    df["unit_price"] = pd.to_numeric(
        df["unit_price"],
        errors="coerce"
    )

    # Remove invalid essential fields
    df = df.dropna(subset=[
        "invoice_no",
        "stock_code",
        "invoice_date",
        "quantity",
        "unit_price",
        "country"
    ])

    df = df[
        (df["unit_price"] > 0) &
        (df["quantity"] != 0) &
        (df["quantity"] % 1 == 0)
    ].copy()

    df["description"] = (
        df["description"]
        .fillna("Unknown product")
    )

    df["customer_id"] = (
        df["customer_id"]
        .str.replace(r"\.0$", "", regex=True)
    )

    df["quantity"] = df["quantity"].astype("int64")

    # Identify cancelled and returned transactions
    df["is_return"] = (
        (df["quantity"] < 0) |
        df["invoice_no"].str.upper().str.startswith("C")
    )

    df["transaction_type"] = "Sale"

    df.loc[
        df["is_return"],
        "transaction_type"
    ] = "Return"

    # Calculate sales metrics
    df["revenue"] = (
        df["quantity"] * df["unit_price"]
    ).round(2)

    df.loc[df["is_return"], "revenue"] = (
        -df.loc[df["is_return"], "revenue"].abs()
    )

    df["year"] = df["invoice_date"].dt.year
    df["month"] = df["invoice_date"].dt.month

    df["year_month"] = (
        df["invoice_date"]
        .dt.strftime("%Y-%m")
    )

    columns = [
        "invoice_no", "stock_code", "description",
        "quantity", "invoice_date", "unit_price",
        "customer_id", "country", "is_return",
        "transaction_type", "revenue",
        "year", "month", "year_month"
    ]

    df = df[columns]

    # Validate processed records
    assert len(df) > 0, "No valid records remain"
    assert df["invoice_date"].notna().all()
    assert df["unit_price"].gt(0).all()

    # Write Parquet to memory
    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        engine="pyarrow",
        compression="snappy",
        index=False,
        coerce_timestamps="ms",
        allow_truncated_timestamps=True
    )

    parquet_data = buffer.getvalue()

    # Upload processed dataset to S3
    s3.put_object(
        Bucket=bucket,
        Key="processed/retail_sales.parquet",
        Body=parquet_data
    )

    duration = time.perf_counter() - start_time

    metrics = {
        "input_rows": initial_rows,
        "duplicate_rows_removed": duplicate_rows,
        "output_rows": len(df),
        "total_rows_removed": initial_rows - len(df),
        "raw_size_bytes": len(raw_data),
        "parquet_size_bytes": len(parquet_data),
        "storage_reduction_pct": round(
            (1 - len(parquet_data) / len(raw_data)) * 100,
            2
        ),
        "gross_sales_gbp": round(
            float(df.loc[~df["is_return"], "revenue"].sum()),
            2
        ),
        "net_revenue_gbp": round(
            float(df["revenue"].sum()), 2
        ),
        "etl_duration_seconds": round(duration, 2)
    }

    print(json.dumps(metrics, indent=4))

    with open("etl_metrics.json", "w") as file:
        json.dump(metrics, file, indent=4)

    print("ETL pipeline completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    args = parser.parse_args()

    run_etl(args.bucket)
