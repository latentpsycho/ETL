from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

def create_countries_table(**context):
    """Create or replace Hive table ``countries`` in the configured S3 bucket."""

    bucket_name = context["ti"].xcom_pull(key="pyspark_output_bucket", task_ids="set_bucket_name")
    if not bucket_name:
        # Fallback to Airflow Variable (preferred for production)
        from airflow.models import Variable

        bucket_name = Variable.get("PYSPARK_OUTPUT_BUCKET")

    output_path = f"s3a://{bucket_name}/countries"

    spark = (
        SparkSession.builder.appName("create-table")
        .enableHiveSupport()
        .getOrCreate()
    )

    schema = StructType(
        [
            StructField("Name", StringType(), True),
            StructField("Capital", StringType(), True),
            StructField("Area", IntegerType(), True),
            StructField("Population", IntegerType(), True),
        ]
    )

    data = [
        ("Австралия", "Канберра", 7_686_850, 19_731_984),
        ("Австрия", "Вена", 83_855, 7_700_000),
    ]

    df = spark.createDataFrame(data, schema)

    (
        df.write.mode("overwrite")
        .option("path", output_path)
        .saveAsTable("countries")
    )

    spark.stop()


# -----------------------------------------------------------------------------
# DAG definition
# -----------------------------------------------------------------------------

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="create_countries_table",
    description="Create Hive table 'countries' in an S3-backed warehouse using PySpark.",
    schedule_interval=None,  # Manual trigger or set cron schedule here
    start_date=datetime(2025, 5, 12),
    catchup=False,
    default_args=default_args,
    tags=["spark", "pyspark", "example"],
) as dag:

    set_bucket_name = PythonOperator(
        task_id="set_bucket_name",
        python_callable=lambda **ctx: ctx["templates_dict"].get("bucket"),
        templates_dict={"bucket": "{{ var.value.PYSPARK_OUTPUT_BUCKET }}"},
    )

    run_spark_job = PythonOperator(
        task_id="create_countries_table_task",
        python_callable=create_countries_table,
        provide_context=True,
    )

    set_bucket_name >> run_spark_job
